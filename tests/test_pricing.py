"""Black-Scholes sanity + delta->strike round-trip tests."""

from __future__ import annotations

import math

from statistics import NormalDist

from backtester.pricing import BlackScholesPricer, implied_vol_proxy

_N = NormalDist()


def _put_price_via_parity(call: float, s: float, k: float, r: float, q: float, t: float) -> float:
    # C - P = S e^{-qT} - K e^{-rT}  =>  P = C - S e^{-qT} + K e^{-rT}
    return call - s * math.exp(-q * t) + k * math.exp(-r * t)


def test_call_delta_in_unit_interval() -> None:
    pricer = BlackScholesPricer(risk_free=0.03, dividend_yield=0.01)
    for k in (50, 80, 100, 120, 150):
        q = pricer.call_quote(spot=100.0, strike=float(k), vol=0.2, t=0.25)
        assert 0.0 <= q.delta <= 1.0
        assert q.price >= 0.0
        assert q.gamma >= 0.0
        assert q.vega >= 0.0


def test_atm_call_price_is_sane() -> None:
    # ATM call ≈ 0.4 * S * vol * sqrt(t) for small carry (rule of thumb).
    pricer = BlackScholesPricer(risk_free=0.0, dividend_yield=0.0)
    s, vol, t = 100.0, 0.2, 1.0
    q = pricer.call_quote(spot=s, strike=s, vol=vol, t=t)
    approx = 0.4 * s * vol * math.sqrt(t)
    assert abs(q.price - approx) / approx < 0.10
    # Deep ITM call ≈ discounted intrinsic; deep OTM ≈ 0.
    itm = pricer.call_quote(spot=200.0, strike=100.0, vol=0.2, t=1.0)
    assert itm.price > 95.0
    otm = pricer.call_quote(spot=100.0, strike=300.0, vol=0.2, t=0.1)
    assert otm.price < 0.5


def test_put_call_parity() -> None:
    pricer = BlackScholesPricer(risk_free=0.04, dividend_yield=0.015)
    s, k, vol, t = 105.0, 100.0, 0.25, 0.5
    r, q = 0.04, 0.015
    call = pricer.call_quote(s, k, vol, t).price
    # Price the put directly via BSM and check parity holds.
    d1 = (math.log(s / k) + (r - q + 0.5 * vol**2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    put = k * math.exp(-r * t) * _N.cdf(-d2) - s * math.exp(-q * t) * _N.cdf(-d1)
    parity_put = _put_price_via_parity(call, s, k, r, q, t)
    assert abs(put - parity_put) < 1e-9


def test_delta_to_strike_round_trip() -> None:
    """strike_for_delta then re-pricing should recover the target delta."""
    pricer = BlackScholesPricer(risk_free=0.03, dividend_yield=0.01)
    s, vol, t = 100.0, 0.22, 30 / 365
    for target in (0.10, 0.20, 0.30, 0.45):
        k = pricer.strike_for_delta(s, target, vol, t)
        recovered = pricer.call_quote(s, k, vol, t).delta
        assert abs(recovered - target) < 1e-6


def test_higher_delta_means_lower_strike() -> None:
    # A 0.30-delta call is closer to the money (lower strike) than a 0.10-delta.
    pricer = BlackScholesPricer(risk_free=0.03, dividend_yield=0.0)
    s, vol, t = 100.0, 0.2, 30 / 365
    k_short = pricer.strike_for_delta(s, 0.30, vol, t)
    k_long = pricer.strike_for_delta(s, 0.10, vol, t)
    assert k_short < k_long
    assert k_short > s  # both OTM for a call


def test_implied_vol_proxy_adds_premium() -> None:
    assert implied_vol_proxy(0.18, 0.03) == 0.21
    # Floors at a tiny positive number rather than going non-positive.
    assert implied_vol_proxy(-1.0, 0.0) > 0.0
