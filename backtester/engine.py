"""Backtest engine: the monthly roll loop.

Pulls prices, computes trailing realized vol, walks month-end to month-end
entering/settling the overlay, and assembles NAV paths plus a tidy monthly
results frame. Returns a :class:`BacktestResult` consumed by ``report.py``.

The engine is deliberately thin: data, pricing, and strategy decisions all live
behind protocols/functions, so Phase-2 components slot in without editing the
loop itself.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import metrics
from .config import BacktestConfig
from .data import PriceProvider, make_provider
from .pricing import BlackScholesPricer, OptionPricer
from .strategy import enter_overlay, monthly_return

_PERIODS_PER_YEAR = 12


@dataclass
class BacktestResult:
    """Everything a report needs from one run."""

    config: BacktestConfig
    monthly: pd.DataFrame  # per-cycle detail (returns, NAVs, strikes, vol)
    strategy_stats: metrics.PerformanceStats
    buy_hold_stats: metrics.PerformanceStats
    benchmark_curve: pd.Series | None  # optional real-fund overlay (growth of $1)
    benchmark_label: str | None


def _realized_vol(prices: pd.Series, window: int, periods_per_year: int) -> pd.Series:
    """Trailing annualized realized vol from daily log returns."""
    log_ret = np.log(prices / prices.shift(1))
    return log_ret.rolling(window).std(ddof=1) * np.sqrt(periods_per_year)


def _month_end_dates(prices: pd.Series) -> pd.DatetimeIndex:
    """Last available trading day of each calendar month in the series."""
    # Group by year-month period, take the max (last) index per group.
    idx = prices.index
    periods = idx.to_period("M")
    last_per_month = (
        pd.Series(idx, index=periods).groupby(level=0).last().to_numpy()
    )
    return pd.DatetimeIndex(last_per_month)


def run_backtest(
    config: BacktestConfig,
    *,
    provider: PriceProvider | None = None,
    pricer: OptionPricer | None = None,
) -> BacktestResult:
    """Run the full Phase-1 backtest and return a results object.

    ``provider`` / ``pricer`` can be injected (tests, Phase-2 swaps); otherwise
    they are built from ``config``.
    """
    config.validate()
    provider = provider or make_provider(config)
    pricer = pricer or BlackScholesPricer(config.risk_free, config.dividend_yield)

    prices = provider.get_prices(config.ticker, config.start, config.end)
    if len(prices) < config.vol_window + 2:
        raise ValueError(
            f"not enough price history for {config.ticker}: got {len(prices)} rows"
        )

    rvol = _realized_vol(prices, config.vol_window, config.trading_days_per_year)
    month_ends = _month_end_dates(prices)

    rows: list[dict[str, object]] = []
    for d0, d1 in zip(month_ends[:-1], month_ends[1:]):
        s0 = float(prices.loc[d0])
        s1 = float(prices.loc[d1])
        vol0 = rvol.loc[d0]
        if not np.isfinite(vol0):
            continue  # not enough lookback yet (warm-up period)

        # Option time-to-expiry in YEARS on a calendar basis (decay is calendar).
        t = max((d1 - d0).days / 365.0, 1e-6)

        leg = enter_overlay(pricer, config, d0, s0, float(vol0), t)
        port_ret, income = monthly_return(
            leg, s1, config.coverage, config.dividend_yield, t
        )
        bh_ret = s1 / s0 - 1.0 + config.dividend_yield * t

        rows.append(
            {
                "date": d1,
                "entry_date": d0,
                "spot_entry": s0,
                "spot_expiry": s1,
                "vol_used": leg.vol_used,
                "short_strike": leg.short_strike,
                "long_strike": leg.long_strike,
                "net_premium": leg.net_premium,
                "net_intrinsic": leg.net_intrinsic(s1),
                "strategy_return": port_ret,
                "buy_hold_return": bh_ret,
                "income_yield": income,
            }
        )

    if not rows:
        raise ValueError("no complete monthly cycles produced — check date range")

    monthly = pd.DataFrame(rows).set_index("date")
    monthly["strategy_nav"] = metrics.equity_curve(monthly["strategy_return"])
    monthly["buy_hold_nav"] = metrics.equity_curve(monthly["buy_hold_return"])

    avg_income = _avg_income_per_year(monthly["income_yield"])

    strat_stats = metrics.summarize(
        monthly["strategy_return"],
        risk_free=config.risk_free,
        periods_per_year=_PERIODS_PER_YEAR,
        avg_income_yield=avg_income,
    )
    bh_stats = metrics.summarize(
        monthly["buy_hold_return"],
        risk_free=config.risk_free,
        periods_per_year=_PERIODS_PER_YEAR,
    )

    bench_curve, bench_label = _maybe_benchmark(config, monthly.index)

    return BacktestResult(
        config=config,
        monthly=monthly,
        strategy_stats=strat_stats,
        buy_hold_stats=bh_stats,
        benchmark_curve=bench_curve,
        benchmark_label=bench_label,
    )


def _avg_income_per_year(income_yield: pd.Series) -> float:
    """Sum premium income within each calendar year, then average the years."""
    by_year = income_yield.groupby(income_yield.index.year).sum()
    return float(by_year.mean()) if len(by_year) else float("nan")


def _maybe_benchmark(
    config: BacktestConfig, index: pd.DatetimeIndex
) -> tuple[pd.Series | None, str | None]:
    """Optionally fetch the real QQQI fund and align it as growth-of-$1.

    Handled gracefully: any failure / too-short history -> no overlay.
    """
    if not config.fetch_qqqi_benchmark:
        return None, None
    try:
        from .data import YFinanceProvider

        bench_prices = YFinanceProvider().get_prices(
            config.benchmark_ticker, config.start, config.end
        )
        if len(bench_prices) < 60:  # ~3 months of daily data minimum
            return None, None
        # Reindex onto strategy month-end dates, forward-fill, normalize.
        monthly_bench = bench_prices.reindex(
            bench_prices.index.union(index)
        ).ffill().reindex(index).dropna()
        if len(monthly_bench) < 2:
            return None, None
        curve = monthly_bench / monthly_bench.iloc[0]
        return curve, config.benchmark_ticker
    except Exception:
        # Network/ticker issues must never break the offline-capable run.
        return None, None
