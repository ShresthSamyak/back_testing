"""Central configuration for the backtest.

All tunable parameters live here in a single frozen dataclass with sensible
defaults so the whole run is reproducible and a one-line change flips behaviour
(e.g. ``data_source`` toggles synthetic vs. real data for offline CI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DataSource = Literal["yfinance", "synthetic"]


@dataclass(frozen=True)
class BacktestConfig:
    """Tunable parameters for a single backtest run.

    Attributes
    ----------
    ticker:
        Underlying symbol held in full and overwritten with calls.
    start, end:
        ISO date strings (``YYYY-MM-DD``) bounding the backtest window.
    risk_free:
        Continuously-compounded annual risk-free rate used by Black-Scholes.
    dividend_yield:
        Continuous annual dividend yield of the underlying. Feeds both the
        option pricer (carry) and the buy-&-hold / strategy total return.
    coverage:
        Fraction of the book the call overlay is written against (0..1).
        Phase 2 replaces this fixed value with fractional-Kelly sizing.
    short_delta:
        Target Black-Scholes delta of the short (sold) call. ~0.30 ≈ a
        near-the-money OTM call.
    long_delta:
        Target delta of the long (bought) call that caps the tail. Only used
        when ``use_spread`` is True. Must be < ``short_delta`` (further OTM).
    use_spread:
        If True, write a call *spread* (short higher-delta, long lower-delta).
        If False, write a plain covered call (no long leg / no tail cap).
    vol_window:
        Trailing window (trading days) for realized-volatility estimation.
    iv_premium:
        Flat volatility-point premium added to realized vol to proxy that
        implied vol trades richer than realized (the volatility risk premium).
        ISOLATED here and in ``pricing`` so a real IV source replaces it later.
    data_source:
        ``"yfinance"`` for real prices, ``"synthetic"`` for the offline
        GBM provider (tests/CI).
    trading_days_per_year:
        Annualization factor for realized vol and vol-derived quantities.
    seed:
        RNG seed for the synthetic data provider (reproducibility).
    fetch_qqqi_benchmark:
        If True, attempt to pull the real QQQI ETF via yfinance and overlay it.
        Handled gracefully when missing / too short.
    benchmark_ticker:
        Symbol used for the optional real-fund overlay.
    """

    # --- universe / window -------------------------------------------------
    ticker: str = "QQQ"
    start: str = "2015-01-01"
    end: str = "2024-12-31"

    # --- market / carry assumptions ---------------------------------------
    risk_free: float = 0.03
    dividend_yield: float = 0.006  # ~QQQ trailing yield

    # --- strategy knobs ----------------------------------------------------
    coverage: float = 0.75
    short_delta: float = 0.30
    long_delta: float = 0.10
    use_spread: bool = True

    # --- volatility / pricing input (the Phase-2 swap point) --------------
    vol_window: int = 21
    iv_premium: float = 0.03

    # --- data plumbing -----------------------------------------------------
    data_source: DataSource = "synthetic"
    trading_days_per_year: int = 252
    seed: int = 7

    # --- optional real-fund overlay ---------------------------------------
    fetch_qqqi_benchmark: bool = False
    benchmark_ticker: str = "QQQI"

    # --- synthetic-provider GBM params (only used when data_source=synthetic)
    synthetic_mu: float = 0.10
    synthetic_sigma: float = 0.20
    synthetic_s0: float = 100.0

    def validate(self) -> None:
        """Cheap invariant checks; raise early on nonsensical configs."""
        if not 0.0 <= self.coverage <= 1.0:
            raise ValueError(f"coverage must be in [0, 1], got {self.coverage}")
        if not 0.0 < self.short_delta < 1.0:
            raise ValueError(f"short_delta must be in (0, 1), got {self.short_delta}")
        if self.use_spread and not 0.0 < self.long_delta < self.short_delta:
            raise ValueError(
                "long_delta must be in (0, short_delta) so the long leg sits "
                f"further OTM; got long={self.long_delta}, short={self.short_delta}"
            )
        if self.vol_window < 2:
            raise ValueError(f"vol_window must be >= 2, got {self.vol_window}")
        if self.data_source not in ("yfinance", "synthetic"):
            raise ValueError(f"unknown data_source {self.data_source!r}")
