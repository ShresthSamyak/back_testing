# Human Instinct Covered-Call Income Backtester

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-Phase%201%20MVP-orange.svg)

A clean, modular, **offline-capable** backtest of a monthly covered-call *spread* overlay on a single underlying (default **QQQ**). Modeled after NEOS-style QQQI / SPYI income funds.

> **ILLUSTRATIVE, NOT VALIDATION**
> This Phase-1 engine prices options with **Black-Scholes using trailing realized volatility plus a flat implied-vol premium** as a stand-in for true implied volatility. **No real option prices are used.** The equity curves are *directional intuition*, **not** a verified track record.
>
> A real backtest requires **historical OPTION prices** (e.g., ORATS / Theta Data). The code is structured so a `HistoricalOptionPricer` drops in behind the same interface **without touching `strategy.py` or `engine.py`** (see [Phase 2: Real Option Data](#phase-2-real-option-data)).

---

## What It Does

Each calendar month, on the last trading day, the engine performs the following:

1. Estimates **volatility**: trailing realized vol (default 21-day, annualized) **+ `iv_premium`** (default `0.03` vol points), proxying the volatility risk premium — implied vol systematically trades richer than realized.
2. Picks a **short call strike** by target delta (default `0.30`) and, if `use_spread` is active, a **long call strike** by target delta (default `0.10`), via Black-Scholes **delta -> strike inversion**.
3. Collects **net premium** (short - long), priced with Black-Scholes at entry.
4. Holds the underlying in full; the overlay is written on **`coverage`** (default `0.75`) of the book.
5. At month-end **settles options at intrinsic value** and rolls.

**Returns formula:**
```text
monthly portfolio return = stock total return + coverage * (net_premium - net_intrinsic) / S0
income yield (per cycle) = coverage * net_premium / S0   (summed per year)
```

---

## Install & Run

Install dependencies (or use `pip install -e .[test]` if packaging is set up):
```bash
pip install -r requirements.txt
```

**Basic Runs:**

```bash
# Default run (Fully OFFLINE, synthetic GBM prices, no network needed):
python -m backtester

# Real QQQ prices from yfinance:
python -m backtester --data-source yfinance --ticker QQQ --start 2015-01-01 --end 2024-12-31

# Plain covered call (no spread / no tail cap), heavier coverage:
python -m backtester --no-spread --coverage 1.0

# Overlay the real QQQI ETF as a benchmark (requires network; gracefully skipped if missing):
python -m backtester --data-source yfinance --fetch-qqqi
```

Outputs are saved in the `output/` directory (override with `--out-dir`):
- **Console comparison table**: strategy vs. buy-&-hold (CAGR, annual vol, Sharpe, Sortino, max drawdown, avg income yield/yr)
- `equity_curve.png`: Growth of $1 (strategy vs buy-&-hold [vs QQQI if available])
- `monthly_results.csv`: Date, returns, NAVs, strikes, vol used.

Run `python -m backtester --help` to see all available flags.

---

## Configuration

Settings live in [backtester/config.py](backtester/config.py) as a frozen `BacktestConfig` dataclass. Every field is exposed as a CLI flag.

| Field | Default | Meaning |
|---|---|---|
| `ticker` | `QQQ` | underlying held + overwritten |
| `start` / `end` | `2015-01-01` / `2024-12-31` | backtest window |
| `risk_free` | `0.03` | annual risk-free (Black-Scholes) |
| `dividend_yield` | `0.006` | continuous div yield (carry + total return) |
| `coverage` | `0.75` | fraction of book overwritten |
| `short_delta` | `0.30` | sold-call target delta |
| `long_delta` | `0.10` | bought-call target delta (spread tail cap) |
| `use_spread` | `True` | spread vs. plain covered call |
| `vol_window` | `21` | realized-vol lookback (trading days) |
| `iv_premium` | `0.03` | flat vol premium over realized (the proxy) |
| `data_source` | `synthetic` | `synthetic` (offline) or `yfinance` |

**Using Programmatically:**
```python
from backtester import BacktestConfig
from backtester.engine import run_backtest
from backtester.report import write_outputs

cfg = BacktestConfig(ticker="QQQ", data_source="yfinance", coverage=0.6)
result = run_backtest(cfg)
write_outputs(result, out_dir="output")
```

---

## Architecture

```text
backtester/
  config.py     # BacktestConfig dataclass (all tunables + validation)
  data.py       # PriceProvider protocol (YFinanceProvider + SyntheticGBMProvider)
  pricing.py    # OptionPricer protocol (BlackScholesPricer: delta->strike, price, greeks)
  strategy.py   # covered-call-spread logic (strikes, premium, settlement, roll)
  metrics.py    # CAGR, annual vol, Sharpe, Sortino, max drawdown, income yield
  engine.py     # monthly loop -> BacktestResult (NAV paths + monthly frame)
  report.py     # console table + equity-curve PNG + monthly CSV
  __main__.py   # CLI entrypoint
tests/          # pytest checks
```

The codebase relies on **narrow protocols** (`PriceProvider`, `OptionPricer`). [strategy.py](backtester/strategy.py) and [engine.py](backtester/engine.py) only interact with interfaces, ensuring backend swaps (e.g., synthetic to distinct historical options data) are seamless.

---

## Phase 2: Real Option Data

To upgrade this illustrative model to use real historical option prices:

1. Implement a `HistoricalOptionPricer` in [pricing.py](backtester/pricing.py) to satisfy the `OptionPricer` protocol (`call_quote` + `strike_for_delta`), backed by an option-quote vendor (e.g., ORATS).
2. Inject it: `run_backtest(cfg, pricer=HistoricalOptionPricer(...))`

No changes to [strategy.py](backtester/strategy.py) or [engine.py](backtester/engine.py) are required.

---

## Extended Roadmap

Future enhancements to fully actualize a production math stack:

- **Volatility forecast:** Use HAR-RV / GJR-GARCH.
- **Market regime sensing:** Implement HMM + VIX structure.
- **Coverage sizing:** Fractional Kelly based on edge/variance vs fixed coverage.
- **Strike selection:** Best return-per-CVaR instead of simple delta bands.
- **Stress Testing:** Historical bootstrap + Extreme Value Theory (EVT).
- **Validation:** Purged / walk-forward CV.

---

## Testing

Run the test suite using pytest (works offline thanks to `SyntheticGBMProvider`):
```bash
pytest
```
Covers Black-Scholes sanity checks, delta->strike round-trips, spread structure/settlement, and a full synthetic smoke test.

---

## Limitations & Caveats

- **Synthetic pricing:** Premiums come from a model, not a market. Over-simplifies term structure and real-world IV skew.
- **Frictionless:** Assumes no transaction costs, slippage, early assignment, or liquidity limits.
- **Settlement:** Uses European-style settlement at month-end intrinsic value.
- **Distributions:** Total return uses a continuous dividend yield, not actual ex-div cash distributions.
- **Thin Tails:** The synthetic GBM world does not account for real market crashes. DO NOT use this standard to project stress-scenario survival without enabling EVT.
