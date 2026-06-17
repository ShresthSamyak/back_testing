"""Smoke test: a full backtest on offline synthetic data must run end-to-end."""

from __future__ import annotations

import numpy as np

from backtester.config import BacktestConfig
from backtester.engine import run_backtest
from backtester.metrics import cagr, max_drawdown


def _synthetic_config(**overrides: object) -> BacktestConfig:
    base: dict[str, object] = {
        "data_source": "synthetic",
        "start": "2016-01-01",
        "end": "2021-12-31",
        "fetch_qqqi_benchmark": False,
    }
    base.update(overrides)
    return BacktestConfig(**base)  # type: ignore[arg-type]


def test_full_backtest_smoke() -> None:
    result = run_backtest(_synthetic_config())
    m = result.monthly

    # Produced a reasonable number of monthly cycles (~6 years -> ~60+).
    assert len(m) > 40
    # NAV columns are finite and start near 1.
    assert np.isfinite(m["strategy_nav"]).all()
    assert np.isfinite(m["buy_hold_nav"]).all()
    # Strikes are above spot (OTM calls) and ordered when spread is on.
    assert (m["short_strike"] > m["spot_entry"]).all()
    assert (m["long_strike"] > m["short_strike"]).all()
    # Stats are finite.
    assert np.isfinite(result.strategy_stats.cagr)
    assert np.isfinite(result.buy_hold_stats.cagr)
    # No benchmark requested -> none attached.
    assert result.benchmark_curve is None


def test_covered_call_dampens_drawdown_in_synthetic_world() -> None:
    # With positive drift + premium income, the overlay should not increase
    # drawdown versus buy & hold in the synthetic GBM world.
    result = run_backtest(_synthetic_config())
    strat_dd = max_drawdown(result.monthly["strategy_return"])
    bh_dd = max_drawdown(result.monthly["buy_hold_return"])
    assert strat_dd >= bh_dd - 1e-9  # less negative (or equal)


def test_plain_vs_spread_runs() -> None:
    # Both overlay modes complete and yield finite CAGR.
    for use_spread in (True, False):
        result = run_backtest(_synthetic_config(use_spread=use_spread))
        assert np.isfinite(cagr(result.monthly["strategy_return"]))


def test_income_yield_is_positive_on_average() -> None:
    result = run_backtest(_synthetic_config())
    assert result.strategy_stats.avg_income_yield > 0.0
