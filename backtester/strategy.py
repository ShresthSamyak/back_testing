"""Covered-call (spread) strategy logic.

Pure, stateless functions that, given a pricer and the month's market inputs,
decide strikes, collect net premium, and settle at expiry. The engine drives
these; keeping them side-effect-free makes them trivially testable and means a
different *decision* layer (Phase-2 regime/Kelly logic) can wrap them without
touching the math.

The strategy talks ONLY to the :class:`~backtester.pricing.OptionPricer`
protocol, never to a concrete pricer — so swapping in real option prices later
is invisible here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import BacktestConfig
from .pricing import OptionPricer, implied_vol_proxy


@dataclass(frozen=True)
class MonthlyLeg:
    """The overwrite position entered for one monthly cycle.

    Premiums/intrinsics are expressed *per share of the underlying* (i.e. per
    1.0 of spot), before applying coverage. The engine scales by coverage.
    """

    entry_date: object  # pd.Timestamp; kept loose to avoid a pandas import here
    spot_entry: float
    vol_used: float
    short_strike: float
    long_strike: float | None
    net_premium: float  # short premium - long premium (per share)

    def net_intrinsic(self, spot_expiry: float) -> float:
        """Cash owed back at expiry (per share): short payoff minus long payoff."""
        short_payoff = max(spot_expiry - self.short_strike, 0.0)
        long_payoff = (
            max(spot_expiry - self.long_strike, 0.0)
            if self.long_strike is not None
            else 0.0
        )
        return short_payoff - long_payoff


def enter_overlay(
    pricer: OptionPricer,
    config: BacktestConfig,
    entry_date: object,
    spot: float,
    realized_vol: float,
    t: float,
) -> MonthlyLeg:
    """Choose strikes by target delta and collect net premium at entry.

    Steps (mirrors the spec):
      1. Build the pricing vol = realized vol + flat IV premium (the proxy).
      2. Short strike at ``short_delta``; if ``use_spread``, long strike at
         ``long_delta`` (further OTM).
      3. Net premium = short premium - long premium, priced at entry.
    """
    vol = implied_vol_proxy(realized_vol, config.iv_premium)

    short_strike = pricer.strike_for_delta(spot, config.short_delta, vol, t)
    short = pricer.call_quote(spot, short_strike, vol, t)

    long_strike: float | None = None
    long_premium = 0.0
    if config.use_spread:
        long_strike = pricer.strike_for_delta(spot, config.long_delta, vol, t)
        long_premium = pricer.call_quote(spot, long_strike, vol, t).price

    net_premium = short.price - long_premium
    return MonthlyLeg(
        entry_date=entry_date,
        spot_entry=spot,
        vol_used=vol,
        short_strike=short_strike,
        long_strike=long_strike,
        net_premium=net_premium,
    )


def monthly_return(
    leg: MonthlyLeg,
    spot_expiry: float,
    coverage: float,
    dividend_yield: float,
    t: float,
) -> tuple[float, float]:
    """Compute the strategy's monthly return and the income yield.

    Portfolio return = stock total return
                       + coverage * (net_premium - net_intrinsic) / S0.

    The overlay P&L is expressed as a fraction of entry spot ``S0`` because
    premiums/intrinsics are per-share and the underlying notional is S0.

    Returns
    -------
    (portfolio_return, income_yield) where income_yield is the gross premium
    collected as a fraction of the underlying for this cycle (used to report
    income; it is the *gross* carry, not net of buy-backs).
    """
    s0 = leg.spot_entry
    # Stock total return over the holding period (price + continuous dividend).
    price_return = spot_expiry / s0 - 1.0
    div_return = dividend_yield * t
    stock_return = price_return + div_return

    overlay_pnl = leg.net_premium - leg.net_intrinsic(spot_expiry)
    portfolio_return = stock_return + coverage * overlay_pnl / s0

    income_yield = coverage * leg.net_premium / s0
    return portfolio_return, income_yield
