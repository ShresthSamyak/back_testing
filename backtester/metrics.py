"""Performance metrics computed from a monthly return series.

All functions take a ``pd.Series`` of *periodic* (monthly) simple returns and a
``periods_per_year`` (12 for monthly). Kept separate from the engine so they
can be reused on any return stream (strategy, buy-&-hold, or a real fund).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceStats:
    """Headline stats for one return stream."""

    cagr: float
    annual_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    avg_income_yield: float  # average premium income per year (strategy only)

    def as_row(self) -> dict[str, float]:
        return {
            "CAGR": self.cagr,
            "Annual Vol": self.annual_vol,
            "Sharpe": self.sharpe,
            "Sortino": self.sortino,
            "Max Drawdown": self.max_drawdown,
            "Avg Income Yield/yr": self.avg_income_yield,
        }


def equity_curve(returns: pd.Series) -> pd.Series:
    """Growth of $1: cumulative product of (1 + r)."""
    return (1.0 + returns).cumprod()


def cagr(returns: pd.Series, periods_per_year: int = 12) -> float:
    if len(returns) == 0:
        return float("nan")
    growth = float((1.0 + returns).prod())
    years = len(returns) / periods_per_year
    if years <= 0 or growth <= 0:
        return float("nan")
    return growth ** (1.0 / years) - 1.0


def annual_vol(returns: pd.Series, periods_per_year: int = 12) -> float:
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1)) * np.sqrt(periods_per_year)


def sharpe(
    returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = 12
) -> float:
    """Annualized Sharpe using a per-period risk-free deduction."""
    if len(returns) < 2:
        return float("nan")
    rf_period = risk_free / periods_per_year
    excess = returns - rf_period
    sd = float(excess.std(ddof=1))
    if sd == 0:
        return float("nan")
    return float(excess.mean()) / sd * np.sqrt(periods_per_year)


def sortino(
    returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = 12
) -> float:
    """Annualized Sortino: excess return over downside deviation only."""
    if len(returns) < 2:
        return float("nan")
    rf_period = risk_free / periods_per_year
    excess = returns - rf_period
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf")  # no losing months
    # Downside deviation uses the full count in the denominator (target = 0).
    dd = np.sqrt(float((downside**2).sum()) / len(excess))
    if dd == 0:
        return float("nan")
    return float(excess.mean()) / dd * np.sqrt(periods_per_year)


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline of the equity curve (negative number)."""
    if len(returns) == 0:
        return float("nan")
    curve = equity_curve(returns)
    running_max = curve.cummax()
    drawdown = curve / running_max - 1.0
    return float(drawdown.min())


def summarize(
    returns: pd.Series,
    *,
    risk_free: float = 0.0,
    periods_per_year: int = 12,
    avg_income_yield: float = float("nan"),
) -> PerformanceStats:
    """Bundle all headline metrics for one return stream."""
    return PerformanceStats(
        cagr=cagr(returns, periods_per_year),
        annual_vol=annual_vol(returns, periods_per_year),
        sharpe=sharpe(returns, risk_free, periods_per_year),
        sortino=sortino(returns, risk_free, periods_per_year),
        max_drawdown=max_drawdown(returns),
        avg_income_yield=avg_income_yield,
    )
