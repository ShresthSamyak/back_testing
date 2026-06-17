"""Price data providers.

Defines the :class:`PriceProvider` protocol and two implementations:

* :class:`YFinanceProvider` — real adjusted-close prices via ``yfinance``.
* :class:`SyntheticGBMProvider` — geometric Brownian motion, fully offline,
  so the whole engine (and CI) runs without a network. Swapping providers is a
  one-line config change (``data_source``).

Every provider returns the *same shape*: a ``pd.Series`` of daily closing
prices indexed by a ``DatetimeIndex`` (business days), name = ticker. Keeping
this contract narrow is what lets Phase-2 data sources (option-chain-aware
providers, alternative vendors) drop in behind the same protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from .config import BacktestConfig


@runtime_checkable
class PriceProvider(Protocol):
    """Anything that can hand back a daily close-price series for a ticker."""

    def get_prices(self, ticker: str, start: str, end: str) -> pd.Series:
        """Return daily close prices indexed by date for ``ticker``.

        The series must be sorted ascending by date, contain no NaNs, and be
        named ``ticker``. May be empty if no data is available for the window.
        """
        ...


class SyntheticGBMProvider:
    """Offline geometric-Brownian-motion price generator.

    Produces a deterministic (seeded) GBM path so tests and CI never touch the
    network. Drift ``mu`` and vol ``sigma`` come from the config. This is the
    default provider; flip ``data_source="yfinance"`` for real data.
    """

    def __init__(self, config: BacktestConfig) -> None:
        self._cfg = config

    def get_prices(self, ticker: str, start: str, end: str) -> pd.Series:
        cfg = self._cfg
        # Business-day calendar for the requested window.
        dates = pd.bdate_range(start=start, end=end)
        n = len(dates)
        if n == 0:
            return pd.Series(dtype=float, name=ticker)

        dt = 1.0 / cfg.trading_days_per_year
        rng = np.random.default_rng(cfg.seed)
        mu, sigma = cfg.synthetic_mu, cfg.synthetic_sigma

        # Exact GBM increments: log-return ~ N((mu - 0.5 sigma^2) dt, sigma^2 dt).
        shocks = rng.normal(
            loc=(mu - 0.5 * sigma**2) * dt,
            scale=sigma * np.sqrt(dt),
            size=n - 1,
        )
        log_path = np.concatenate([[0.0], np.cumsum(shocks)])
        prices = cfg.synthetic_s0 * np.exp(log_path)
        return pd.Series(prices, index=dates, name=ticker)


class YFinanceProvider:
    """Real daily prices via ``yfinance`` (adjusted close).

    Network-dependent; used only when ``data_source="yfinance"``. Adjusted
    close folds dividends/splits into the price, so we set the pricer's
    ``dividend_yield`` to model option carry but treat the price series itself
    as a total-return-ish proxy. (Phase 2 can separate clean price + cash
    dividends if needed.)
    """

    def get_prices(self, ticker: str, start: str, end: str) -> pd.Series:
        import yfinance as yf  # local import keeps offline runs import-free

        raw = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
        )
        if raw is None or raw.empty:
            return pd.Series(dtype=float, name=ticker)

        # yfinance may return a single- or multi-index column frame.
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna()
        close.name = ticker
        close.index = pd.to_datetime(close.index)
        return close.sort_index()


def make_provider(config: BacktestConfig) -> PriceProvider:
    """Factory: return the provider selected by ``config.data_source``."""
    if config.data_source == "synthetic":
        return SyntheticGBMProvider(config)
    if config.data_source == "yfinance":
        return YFinanceProvider()
    raise ValueError(f"unknown data_source {config.data_source!r}")
