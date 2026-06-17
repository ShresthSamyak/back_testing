"""Human Instinct — covered-call income backtesting engine (Phase 1, MVP).

A modular, offline-capable backtest of a monthly covered-call *spread* overlay
on a single underlying (default QQQ).

IMPORTANT — ILLUSTRATIVE, NOT VALIDATION
----------------------------------------
This Phase-1 engine prices options with Black-Scholes using *trailing realized
volatility plus a flat implied-vol premium* as a stand-in for true implied vol.
Real option prices are NOT used. The resulting equity curves are DIRECTIONAL
intuition pumps, not a verified track record. A real backtest requires
historical OPTION prices (see ``pricing.HistoricalOptionPricer`` seam and the
README). Do not present synthetic output as a validated return stream.

The package is deliberately split along the production pipeline seams
(data -> pricing -> strategy -> engine -> metrics/report) so Phase-2 components
(real option data, HAR-RV / GARCH vol, HMM regime, fractional-Kelly coverage,
EVT stress) drop in without rewrites. See module docstrings for the exact
extension points.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .config import BacktestConfig

__all__ = ["BacktestConfig", "__version__"]
