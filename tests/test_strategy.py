"""Strategy-mechanics tests: spread structure, settlement, premium signs."""

from __future__ import annotations

from backtester.config import BacktestConfig
from backtester.pricing import BlackScholesPricer
from backtester.strategy import enter_overlay, monthly_return


def _pricer(cfg: BacktestConfig) -> BlackScholesPricer:
    return BlackScholesPricer(cfg.risk_free, cfg.dividend_yield)


def test_spread_strikes_ordered_and_positive_premium() -> None:
    cfg = BacktestConfig(use_spread=True)
    leg = enter_overlay(_pricer(cfg), cfg, "d0", spot=100.0, realized_vol=0.18, t=30 / 365)
    assert leg.long_strike is not None
    assert leg.short_strike < leg.long_strike  # long leg is further OTM
    assert leg.net_premium > 0.0  # selling the nearer strike nets credit


def test_plain_covered_call_has_no_long_leg() -> None:
    cfg = BacktestConfig(use_spread=False)
    leg = enter_overlay(_pricer(cfg), cfg, "d0", spot=100.0, realized_vol=0.2, t=30 / 365)
    assert leg.long_strike is None
    # Plain short call collects at least as much premium as the spread.
    cfg_spread = BacktestConfig(use_spread=True)
    leg_spread = enter_overlay(
        _pricer(cfg_spread), cfg_spread, "d0", spot=100.0, realized_vol=0.2, t=30 / 365
    )
    assert leg.net_premium >= leg_spread.net_premium


def test_net_intrinsic_spread_is_capped() -> None:
    cfg = BacktestConfig(use_spread=True)
    leg = enter_overlay(_pricer(cfg), cfg, "d0", spot=100.0, realized_vol=0.18, t=30 / 365)
    assert leg.long_strike is not None
    width = leg.long_strike - leg.short_strike
    # Far above the long strike, the spread payoff is capped at the width.
    huge = leg.long_strike * 5
    assert abs(leg.net_intrinsic(huge) - width) < 1e-9
    # Below the short strike, nothing is owed.
    assert leg.net_intrinsic(leg.short_strike - 1.0) == 0.0


def test_flat_market_keeps_premium_as_profit() -> None:
    # If spot is unchanged and below the short strike, overlay P&L = premium.
    cfg = BacktestConfig(use_spread=True, coverage=0.75, dividend_yield=0.0)
    leg = enter_overlay(_pricer(cfg), cfg, "d0", spot=100.0, realized_vol=0.18, t=30 / 365)
    port_ret, income = monthly_return(leg, 100.0, cfg.coverage, 0.0, 30 / 365)
    expected = cfg.coverage * leg.net_premium / 100.0
    assert abs(port_ret - expected) < 1e-12
    assert abs(income - expected) < 1e-12


def test_upside_is_capped_relative_to_buy_hold() -> None:
    # In a strong rally the strategy underperforms buy & hold (gave up upside).
    cfg = BacktestConfig(use_spread=True, coverage=1.0, dividend_yield=0.0)
    leg = enter_overlay(_pricer(cfg), cfg, "d0", spot=100.0, realized_vol=0.18, t=30 / 365)
    s1 = 130.0
    port_ret, _ = monthly_return(leg, s1, cfg.coverage, 0.0, 30 / 365)
    bh_ret = s1 / 100.0 - 1.0
    assert port_ret < bh_ret
