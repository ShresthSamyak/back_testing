"""Option pricing — the Phase-2 swap point.

Defines the :class:`OptionPricer` protocol and a :class:`BlackScholesPricer`
implementation: call price, greeks, and the delta->strike inversion the
strategy uses to pick strikes by target delta.

THE VOLATILITY SOURCE IS THE KEY SEAM
-------------------------------------
Phase 1 feeds Black-Scholes a *volatility* derived from trailing realized vol
plus a flat ``iv_premium`` (see :func:`implied_vol_proxy`). This is the single
line that makes the whole engine "illustrative, not validation": we are
*assuming* the price we sell at rather than reading it from a real option
chain.

Phase 2 should add a ``HistoricalOptionPricer`` that implements the same
:class:`OptionPricer` protocol but sources premium/greeks/strikes from real
historical option quotes (ORATS / Theta Data). Because ``strategy.py`` and
``engine.py`` only ever talk to the protocol, that drop-in requires NO changes
upstream. Keep this protocol narrow.

All normal-distribution work uses :class:`statistics.NormalDist` (no scipy).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Protocol, runtime_checkable

_N = NormalDist()  # standard normal; .cdf / .inv_cdf / pdf via .pdf


def _norm_cdf(x: float) -> float:
    return _N.cdf(x)


def _norm_pdf(x: float) -> float:
    # NormalDist.pdf exists in 3.8+, but spell it out for clarity/speed parity.
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_inv(p: float) -> float:
    return _N.inv_cdf(p)


@dataclass(frozen=True)
class CallQuote:
    """A priced European call: premium plus the greeks the book cares about."""

    strike: float
    price: float
    delta: float
    gamma: float
    vega: float


def implied_vol_proxy(realized_vol: float, iv_premium: float) -> float:
    """Phase-1 stand-in for implied volatility.

    Implied vol systematically trades richer than subsequently-realized vol
    (the volatility risk premium); we proxy that with a flat additive premium.

    TODO(phase-2): replace this with a real implied-vol read from a historical
    option-quote source (or a HAR-RV / GARCH forecast feeding a calibrated
    surface). Everything downstream only sees the returned scalar, so the swap
    is local to this function + a ``HistoricalOptionPricer``.
    """
    return max(realized_vol + iv_premium, 1e-6)


@runtime_checkable
class OptionPricer(Protocol):
    """Prices European calls and inverts delta to a strike.

    Phase 2's historical-quote pricer implements exactly this interface.
    """

    def call_quote(
        self,
        spot: float,
        strike: float,
        vol: float,
        t: float,
    ) -> CallQuote:
        """Price a European call and return premium + greeks."""
        ...

    def strike_for_delta(
        self,
        spot: float,
        target_delta: float,
        vol: float,
        t: float,
    ) -> float:
        """Return the strike whose call delta equals ``target_delta``."""
        ...


class BlackScholesPricer:
    """Black-Scholes-Merton European call pricer with continuous dividends.

    Conventions
    ------------
    * ``r`` continuously-compounded risk-free rate, ``q`` continuous dividend
      yield, ``t`` time to expiry in YEARS (calendar/365 — options decay on
      calendar time, not trading days).
    * ``vol`` is the annualized volatility actually fed to the model (in
      Phase 1, the realized-vol-plus-premium proxy).
    """

    def __init__(self, risk_free: float, dividend_yield: float) -> None:
        self._r = risk_free
        self._q = dividend_yield

    # -- core math ----------------------------------------------------------
    def _d1_d2(
        self, spot: float, strike: float, vol: float, t: float
    ) -> tuple[float, float]:
        # Guard the degenerate t->0 / vol->0 corner so callers can pass them.
        vsqrt = vol * math.sqrt(t)
        if vsqrt <= 0.0:
            # Effectively a forward comparison; push d1 to +/-inf.
            fwd = spot * math.exp((self._r - self._q) * t)
            sign = math.inf if fwd >= strike else -math.inf
            return sign, sign
        d1 = (
            math.log(spot / strike) + (self._r - self._q + 0.5 * vol * vol) * t
        ) / vsqrt
        d2 = d1 - vsqrt
        return d1, d2

    def call_quote(
        self, spot: float, strike: float, vol: float, t: float
    ) -> CallQuote:
        d1, d2 = self._d1_d2(spot, strike, vol, t)
        disc_q = math.exp(-self._q * t)
        disc_r = math.exp(-self._r * t)

        if math.isinf(d1):
            # vol*sqrt(t) == 0: option is its discounted intrinsic on the forward.
            fwd_price = max(spot * disc_q - strike * disc_r, 0.0)
            delta = disc_q if d1 > 0 else 0.0
            return CallQuote(strike, fwd_price, delta, 0.0, 0.0)

        price = spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
        delta = disc_q * _norm_cdf(d1)
        gamma = disc_q * _norm_pdf(d1) / (spot * vol * math.sqrt(t))
        vega = spot * disc_q * _norm_pdf(d1) * math.sqrt(t)  # per 1.00 vol
        return CallQuote(strike, max(price, 0.0), delta, gamma, vega)

    def strike_for_delta(
        self, spot: float, target_delta: float, vol: float, t: float
    ) -> float:
        """Invert call delta -> strike analytically.

        Call delta = e^{-q t} N(d1)  =>  d1 = N^{-1}(delta * e^{q t}).
        Then from d1's definition, solve for K:
            ln(S/K) = d1 * vol*sqrt(t) - (r - q + 0.5 vol^2) t
            K = S * exp((r - q + 0.5 vol^2) t - d1 * vol*sqrt(t)).
        """
        if not 0.0 < target_delta < 1.0:
            raise ValueError(f"target_delta must be in (0, 1), got {target_delta}")
        vsqrt = vol * math.sqrt(t)
        if vsqrt <= 0.0:
            return spot  # no time/vol: ATM is the only meaningful strike

        # delta * e^{q t} must stay < 1 for the inverse-CDF to be finite.
        adj = target_delta * math.exp(self._q * t)
        adj = min(adj, 1.0 - 1e-9)
        d1 = _norm_inv(adj)
        strike = spot * math.exp(
            (self._r - self._q + 0.5 * vol * vol) * t - d1 * vsqrt
        )
        return strike


# ---------------------------------------------------------------------------
# Phase-2 seam (do NOT implement now). Sketch only, kept here so the intended
# extension point is obvious and lives beside the protocol it must satisfy.
#
# class HistoricalOptionPricer:
#     """Phase 2: price from real historical option quotes (ORATS / Theta).
#
#     Implements the OptionPricer protocol by looking up the closest listed
#     strike/expiry to the requested (delta, t) and returning the *quoted*
#     premium + vendor greeks. strategy.py / engine.py need ZERO changes.
#     """
#     def call_quote(self, spot, strike, vol, t) -> CallQuote: ...
#     def strike_for_delta(self, spot, target_delta, vol, t) -> float: ...
# ---------------------------------------------------------------------------
