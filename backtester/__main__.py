"""CLI: ``python -m backtester`` runs a backtest with config defaults.

Every config field is exposed as a flag so the whole run is tunable from the
shell without editing code. With no flags it runs the offline synthetic default
(no network), which is also what CI exercises.
"""

from __future__ import annotations

import argparse
from dataclasses import fields

from .config import BacktestConfig
from .engine import run_backtest
from .report import write_outputs


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backtester",
        description=(
            "Human Instinct covered-call income backtester (Phase-1 MVP). "
            "ILLUSTRATIVE: synthetic option pricing, not a verified track record."
        ),
    )
    defaults = BacktestConfig()
    p.add_argument("--ticker", default=defaults.ticker)
    p.add_argument("--start", default=defaults.start)
    p.add_argument("--end", default=defaults.end)
    p.add_argument("--risk-free", type=float, default=defaults.risk_free)
    p.add_argument("--dividend-yield", type=float, default=defaults.dividend_yield)
    p.add_argument("--coverage", type=float, default=defaults.coverage)
    p.add_argument("--short-delta", type=float, default=defaults.short_delta)
    p.add_argument("--long-delta", type=float, default=defaults.long_delta)
    p.add_argument(
        "--no-spread",
        dest="use_spread",
        action="store_false",
        default=defaults.use_spread,
        help="write a plain covered call instead of a spread (no tail cap)",
    )
    p.add_argument("--vol-window", type=int, default=defaults.vol_window)
    p.add_argument("--iv-premium", type=float, default=defaults.iv_premium)
    p.add_argument(
        "--data-source",
        choices=["yfinance", "synthetic"],
        default=defaults.data_source,
    )
    p.add_argument("--seed", type=int, default=defaults.seed)
    p.add_argument(
        "--fetch-qqqi",
        dest="fetch_qqqi_benchmark",
        action="store_true",
        default=defaults.fetch_qqqi_benchmark,
        help="overlay the real QQQI ETF (requires network; skipped if missing)",
    )
    p.add_argument("--out-dir", default="output")
    return p


def _config_from_args(args: argparse.Namespace) -> BacktestConfig:
    # Map only the fields BacktestConfig knows about (keeps CLI/config in sync).
    valid = {f.name for f in fields(BacktestConfig)}
    kwargs = {k: v for k, v in vars(args).items() if k in valid}
    return BacktestConfig(**kwargs)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = _config_from_args(args)
    result = run_backtest(config)
    write_outputs(result, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
