"""Reporting: console table, equity-curve PNG, and monthly-results CSV."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: never require a display (CI-safe)
import matplotlib.pyplot as plt  # noqa: E402

import pandas as pd  # noqa: E402

from .engine import BacktestResult  # noqa: E402
from .metrics import PerformanceStats  # noqa: E402

_DISCLAIMER = (
    "ILLUSTRATIVE ONLY — options priced with realized vol + a flat IV premium, "
    "NOT real option quotes. Directional intuition, not a verified track record."
)


def _fmt_pct(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{x * 100:7.2f}%"


def _fmt_ratio(x: float) -> str:
    if pd.isna(x):
        return "n/a"
    if x == float("inf"):
        return "    inf"
    return f"{x:7.2f}"


def print_table(result: BacktestResult) -> None:
    """Print the strategy-vs-buy-&-hold comparison table to stdout."""
    cfg = result.config
    strat = result.strategy_stats
    bh = result.buy_hold_stats

    print()
    print("=" * 64)
    print(f" Human Instinct — covered-call backtest  ({cfg.ticker})")
    print(f" {cfg.start} → {cfg.end}   |   data: {cfg.data_source}")
    print("=" * 64)
    spread = (
        f"spread short Δ{cfg.short_delta:.2f}/long Δ{cfg.long_delta:.2f}"
        if cfg.use_spread
        else f"covered call short Δ{cfg.short_delta:.2f}"
    )
    print(f" overlay: {spread}, coverage {cfg.coverage:.0%}")
    print("-" * 64)

    metric_names = [
        ("CAGR", "cagr", _fmt_pct),
        ("Annual Vol", "annual_vol", _fmt_pct),
        ("Sharpe", "sharpe", _fmt_ratio),
        ("Sortino", "sortino", _fmt_ratio),
        ("Max Drawdown", "max_drawdown", _fmt_pct),
        ("Avg Income Yield/yr", "avg_income_yield", _fmt_pct),
    ]
    header = f"{'Metric':<22}{'Strategy':>12}{'Buy & Hold':>14}"
    print(header)
    print("-" * 64)
    for label, attr, fmt in metric_names:
        s_val = fmt(getattr(strat, attr))
        b_val = (
            fmt(getattr(bh, attr))
            if attr != "avg_income_yield"
            else "       —"  # buy & hold has no overlay income
        )
        print(f"{label:<22}{s_val:>12}{b_val:>14}")
    print("-" * 64)
    if result.benchmark_label is not None and result.benchmark_curve is not None:
        gain = result.benchmark_curve.iloc[-1] - 1.0
        print(
            f" benchmark overlay: {result.benchmark_label} "
            f"(growth of $1 → {result.benchmark_curve.iloc[-1]:.3f}, "
            f"{gain * 100:+.1f}%)"
        )
    print()
    print(f" NOTE: {_DISCLAIMER}")
    print("=" * 64)
    print()


def save_chart(result: BacktestResult, path: str | Path) -> Path:
    """Save the growth-of-$1 equity-curve chart to ``path`` (PNG)."""
    path = Path(path)
    monthly = result.monthly

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(monthly.index, monthly["strategy_nav"], label="Covered-call strategy", lw=2)
    ax.plot(
        monthly.index,
        monthly["buy_hold_nav"],
        label="Buy & hold",
        lw=2,
        ls="--",
    )
    if result.benchmark_curve is not None and result.benchmark_label is not None:
        ax.plot(
            result.benchmark_curve.index,
            result.benchmark_curve.values,
            label=f"{result.benchmark_label} (real)",
            lw=1.5,
            ls=":",
        )

    ax.set_title(
        f"Growth of $1 — {result.config.ticker} covered-call overlay\n"
        "ILLUSTRATIVE (synthetic option pricing)",
        fontsize=11,
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Growth of $1")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def save_csv(result: BacktestResult, path: str | Path) -> Path:
    """Save the monthly results frame (date, returns, NAVs, strikes, vol)."""
    path = Path(path)
    result.monthly.to_csv(path, index=True)
    return path


def write_outputs(
    result: BacktestResult,
    out_dir: str | Path = "output",
) -> tuple[Path, Path]:
    """Print table and write PNG + CSV into ``out_dir``; return their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print_table(result)
    chart = save_chart(result, out_dir / "equity_curve.png")
    csv = save_csv(result, out_dir / "monthly_results.csv")
    print(f" chart → {chart}")
    print(f" csv   → {csv}")
    return chart, csv


__all__ = ["print_table", "save_chart", "save_csv", "write_outputs", "PerformanceStats"]
