# Human Instinct — From Backtest to Fund

**A research-grounded plan for turning the covered-call thesis into something
profitable and legitimate, not just a theory.**

This document separates what is a *software/quant* problem (which this repo can
actually solve) from what is a *capital, legal, and business* problem (which code
cannot solve and which determines whether this becomes a real fund). It is
deliberately blunt where the research contradicts the marketing instinct —
because that honesty is the only thing that protects you and future investors.

Status of this repo today: a **Phase-1 illustrative backtester** (synthetic
option pricing). It is a good simulator of the *decision logic*. It is **not**
evidence the strategy makes money. The gap between those two statements is the
whole job.

---

## 0. The one-paragraph reality check

Covered-call income is a **real, durable, but modest and cyclical edge** — it is
a risk-reduction and cash-flow trade, **not an alpha machine that beats the
index**. The published evidence (CBOE BXM buy-write index) is roughly *index-like
total return at ~two-thirds the volatility* over multi-decade windows: better
Sharpe, lower drawdown, but it **underperforms in bull markets and outperforms
in flat/bear markets**. NEOS QQQI itself confirms this in the live tape: over the
trailing year it returned ~26% total return vs QQQ's ~35%, and a large slice of
its headline ~13–14% "yield" has printed as **return of capital** (one recent
distribution was ~98% ROC). So the honest pitch is: *"durable tax-advantaged cash
flow and lower risk, in exchange for capped upside"* — never *"14% free yield."*
Build the whole business on that sentence and it can be legit; build it on
"high yield" and it is a marketing trap that the SEC and disappointed investors
will both punish.

---

## 1. What the research says (grounded)

| Finding | Implication for Human Instinct |
|---|---|
| **BXM ≈ S&P total return at ~2/3 the risk** (11.77% vs 11.67% CAGR, 9.29% vs 13.89% vol, 1988–2006). Outperforms in flat/down markets, lags in bull runs. | The edge is **risk-adjusted**, not absolute. Your KPI is Sharpe/Sortino and drawdown, *not* beating QQQ. Sell risk reduction + income. |
| **QQQI live: ~26% vs QQQ ~35% TTM; YTD ~10% vs ~17%.** Distributions heavily **return of capital** (up to ~98% in a month). Expense ratio 0.68%. | "Yield" ≠ "return." A 14% distribution that is mostly ROC is partly *handing investors their own NAV back*. You must report **total return** honestly and explain ROC. |
| **QQQI mechanism** = own NDX-100 equities + sell **NDX index call spreads** (net credit), Section 1256 → **60/40 tax** treatment. | Your Phase-1 spread design already mirrors this. The tax edge is real and material — but it comes from **cash-settled index options (NDX/SPX)**, not single-stock options on ASTS/HIVE/BOTZ (those are equity options, *not* 1256, and far less liquid). |
| **Historical option data is affordable**: ThetaData ~$40–160/mo; CBOE LiveVol EOD ~$500/mo; ORATS by quote. | The single biggest credibility upgrade — real option prices — costs **tens of dollars/month**, not a barrier. This is the first thing to buy. |
| **VRP (implied > realized vol) is real but thin and time-varying**; it collapses exactly when you most want it (vol spikes → premiums rise but so does assignment risk). | Justifies *dynamic* coverage/strike logic (your Phase-2 Kelly/regime ideas) — but those are refinements on a real edge, not the source of the edge. |

Sources at the bottom.

---

## 2. The four tracks — only one of them is code

This is the most important framing in the document. The vision doc mixes nine
different problems. They live on four independent tracks, and **three of the four
cannot be solved by writing software**:

1. **Quant / Software** *(this repo — I can build all of this)*
   Validation-grade backtester → live signal engine → execution. This is
   necessary but **not sufficient** for a fund.

2. **Capital & Track Record** *(time + money, not code)*
   You cannot raise outside money without an **audited, real-money track
   record**. A backtest — however good — raises nothing on its own and is
   legally not a track record. Path: backtest → paper trade → trade your *own*
   money for 12–24 months with real fills → get it audited (GIPS-style).

3. **Legal / Regulatory** *(licensed professionals, non-negotiable)*
   Managing other people's money in the US = **Investment Advisers Act** (RIA
   registration) and, for a pooled vehicle, the **Investment Company Act / '40
   Act** or a private-fund exemption (3(c)(1)/3(c)(7), accredited/QP investors
   only). Launching an actual ETF like QQQI requires a '40 Act fund, a board, a
   custodian, an authorized participant, and an exemptive framework. **See §6 on
   tokenization — that path is materially harder, not easier.**

4. **Business / Distribution** *(content, brand, ops)*
   The newsletter, the NASDAQ/AI thesis, the "Human Instinct" philosophy. This
   is real and valuable as **audience-building** *now* (it's legal to publish
   research and opinions), and it de-risks fundraising later. Keep it cleanly
   separated from anything that looks like soliciting investment.

> **The trap to avoid:** spending all your energy on Track 1 (it's the fun part)
> and Track 4 (it's the visible part) while Tracks 2 and 3 — the ones that
> actually gate "legit" — go untouched. The code is the easy 20%.

---

## 3. Critical path to "legit"

```
 [Phase-1 illustrative backtest]   <-- you are here
        |
        v
 [Validation-grade backtest]       real option prices + costs + walk-forward CV
        |                          => is the edge real AFTER frictions?
        v
 [Paper trading]                   Alpaca / IBKR paper, live signals, 3-6 months
        |                          => does live data + latency break it?
        v
 [Proprietary capital, real money] your own money, 12-24 months, real fills
        |                          => the ONLY thing that becomes a track record
        v
 [Audit + legal structure]         RIA / private-fund counsel, audited returns
        |
        v
 [Outside capital]                 SMAs -> private fund -> (maybe) ETF
```

Each arrow is a go/no-go gate. If the strategy dies at the "validation-grade"
gate (edge disappears after real spreads, commissions, and slippage), you have
saved yourself years and a lot of money — that is a *win*, not a failure.

---

## 4. Technical roadmap (what I can build, in priority order)

Built on the existing seams (`OptionPricer`, `PriceProvider`, the monthly
engine). Ordered by **return-on-effort**, not by how advanced it sounds.

### Tier 1 — Turns "illustrative" into "validation-grade" (do these first)
1. **`HistoricalOptionPricer`** implementing the existing `OptionPricer`
   protocol, fed by ThetaData/ORATS EOD option chains. *This is the single
   highest-value change in the whole project* — it replaces the synthetic
   `implied_vol_proxy` with real premiums and removes the "illustrative" asterisk.
   No changes to `strategy.py`/`engine.py` required (that's why the seam exists).
2. **Transaction-cost & slippage model** — bid/ask spread, commissions, and a
   fill assumption (e.g. mid minus X%). *Most fake backtests die here.* Covered
   calls trade frequently; costs are not a rounding error.
3. **Cash-settled index-option settlement** on NDX/SPX (matches QQQI and the
   Section 1256 tax treatment) instead of treating QQQ equity options as the
   tradeable. Model the 60/40 tax drag explicitly so net yield is *net*.
4. **Walk-forward / purged cross-validation** harness around `run_backtest` so
   every parameter (delta, coverage, window) is chosen out-of-sample. This is
   what separates a strategy from an overfit curve.

### Tier 2 — Earns its keep once Tier 1 says the edge is real
5. **HAR-RV volatility forecast** (simple OLS on daily/weekly/monthly realized
   vol) replacing the trailing-vol input. Cheap, robust, documented to beat
   GARCH out-of-sample. Drop-in at the `implied_vol_proxy` seam.
6. **Variance-gap trade signal** `gamma * (IV^2 - forecastRV^2)` to *score* which
   strikes/months to actually write, instead of writing every month blindly.
7. **Dynamic coverage** via **fractional Kelly** on the estimated edge/variance,
   replacing the fixed `coverage` scalar. Use a *small* fraction (¼–½ Kelly);
   full Kelly blows up on estimation error.

### Tier 3 — Risk & robustness (before any real money)
8. **EVT / historical-bootstrap stress** replacing GBM for tail tests — answer
   "what happens in a -50% NDX year" honestly (GBM literally cannot produce
   real crashes). This is your IV.C "how would QQQI do if the market falls 50%."
9. **Greeks + CVaR risk limits** at the book level (net delta/vega/gamma caps).
10. **HMM regime overlay** (calm vs stressed) gating coverage — *last*, because
    it's the most overfit-prone and adds the least if Tiers 1–2 are solid.

### Tier 4 — Productionization
11. **Alpaca / IBKR paper-trading adapter** behind a new `Broker` protocol
    (same pattern as `PriceProvider`). Live signals, no real money.
12. Logging, monitoring, daily NAV reconciliation, alerting.

> Multi-underlying baskets (ASTS, RKLB, HIVE, BOTZ, BE, CLSK): architecturally
> trivial (loop the engine per ticker). **But** single-stock options are *not*
> Section 1256, are far less liquid, and carry idiosyncratic blow-up risk. Treat
> these as a *separate, later* research question, not part of the core QQQI-clone.
> The core income engine should stay on liquid index options (NDX/SPX).

---

## 5. The "Math Stack" — what's worth it vs. over-engineering

Your math-stack slide is genuinely well-chosen. The honest ranking by *marginal
value for a Phase-2 build*:

- **Worth it early:** real option data (#1), costs (#2), walk-forward CV (#4),
  HAR-RV (#5). These move you from fiction to evidence.
- **Worth it once the edge is proven:** variance-gap signal, fractional Kelly,
  EVT stress. These improve a real edge.
- **Easy to over-invest in:** HMM regime detection and SVI surface fitting are
  intellectually attractive and the *most* likely to overfit on limited data.
  Add them only if simpler versions are already profitable out-of-sample. A
  strategy that needs an HMM to be profitable probably isn't.

Rule of thumb: **every model you add must demonstrably improve out-of-sample
Sharpe net of costs, or it comes out.** Complexity is a cost, not a feature.

---

## 6. Hard flags (read before you build the business)

- **"Yield" is the dangerous word.** Marketing 13–14% yield when much of it is
  return of capital is the fastest way to attract a regulator and angry
  investors. Lead with **total return, risk reduction, and tax efficiency.**
  Report ROC % every period. This is both ethically right and legally safer.
- **Tokenization + "global investors" is the hardest path, not a shortcut.**
  A tokenized fund interest is still a **security**. Selling it cross-border to
  retail adds *every* jurisdiction's securities law on top of US law. People
  assume tokens route around regulation; they route *into more of it*. Do not
  build this without securities counsel who has done tokenized funds. For an
  MVP, a US **private fund (3(c)(1), accredited investors)** or **SMAs under an
  RIA** is the realistic legitimate entry point.
- **You cannot solicit investment off a backtest.** Showing simulated returns to
  prospective investors without prominent hypothetical-performance disclaimers
  (and ideally not at all pre-registration) is a compliance landmine. The
  newsletter can build an *audience*; it must not become an *offering*.
- **Day-trading VIX as a hedge (IV.B)** is a different, harder strategy with its
  own term-structure/roll-cost pitfalls. Park it; it is not part of the core
  income engine and will eat focus.

None of this is legal advice — it is a map of where you *need* licensed counsel
(securities attorney + fund administrator + auditor) before touching outside
money. Budget for them; they are not optional.

---

## 7. Concrete next steps

**This week (code — I can do these now):**
1. Pick a data vendor (ThetaData is the cheap, fast start at ~$40–160/mo) and I
   build the `HistoricalOptionPricer` + a data-loader behind the existing
   protocol. *Deliverable: the same backtest, run on real QQQ/NDX option prices.*
2. Add the transaction-cost/slippage model and an honest net-of-cost results
   line to the report.
3. Re-run and compare: does the edge survive real spreads? **This is the first
   real go/no-go.**

**This month (you — not code):**
4. Talk to a securities attorney about the SMA/private-fund path *before*
   investing further in the fund concept. One consult will reframe the whole plan.
5. Keep publishing the thesis/newsletter to build audience — clearly as
   research/opinion, not as an offering.

**Then:** walk-forward validation → paper trading on Alpaca → proprietary
capital → audit. One gate at a time.

---

## Sources
- NEOS QQQI strategy & spread mechanics — <https://neosfunds.com/qqqi/> ;
  prospectus <https://neosfunds.com/wp-content/uploads/QQQI-Prospectus.pdf>
- QQQI total return vs QQQ & return-of-capital reality —
  <https://247wallst.com/investing/2026/05/25/qqqis-14-percent-yield-was-98-percent-return-of-capital-in-a-recent-distribution-and-thats-the-real-story/>
  ; <https://finance.yahoo.com/markets/options/articles/qqqi-13-8-percent-monthly-190537609.html>
- CBOE BXM buy-write long-term risk/return (Callan / Ibbotson) —
  <https://www.borntosell.com/covered-call-blog/evaluation-of-buy-write-strategy>
  ; <https://en.wikipedia.org/wiki/CBOE_S%26P_500_BuyWrite_Index>
- Historical option data vendors & pricing —
  <https://www.fxoptions.com/where-to-buy-historical-options-chain-data-sources-and-pricing/>
  ; <https://datashop.cboe.com/data-products>
- Reference repos (plumbing patterns, not copy) — alpacahq/options-wheel ;
  doddpronter/cc_optimizer ; hamedasgari20/covered-call-strategy
