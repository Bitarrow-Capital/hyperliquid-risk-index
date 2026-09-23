# Hyperliquid Risk Index

A daily, public, timestamped risk rating of Hyperliquid accounts, built entirely
from public on-chain data.

Published by [Bitarrow Capital](https://bitarrow.capital). Every index in
`indices/` is committed the day it is produced, so the dates are GitHub's, not ours.

---

## What this measures — and what it does not

It measures **one thing**: how much destruction risk an account carries, given its
position size, its distance to liquidation, and the measured volatility and
correlation of the assets it holds.

It is **not** investment advice and it does **not** predict prices or returns.
An `A` does not mean the account will make money. An `F` does not mean it will lose
money tomorrow — it means an ordinary market move can end it.

## Why this is not the liquidation price your exchange already shows you

Your exchange shows *where* you get liquidated. That is free, and we are not
selling it.

This measures whether the **size of the bet** destroys the account over time **even
when the direction is right**. The Kelly criterion says there is an optimal bet
size, `f* = μ/σ²`, and that above roughly twice it, long-run compounded growth turns
negative regardless of edge — because losing 50% requires gaining 100% to recover.

No exchange will ever compute this for you. Their revenue is your volume and your
liquidations; telling you to size down works against their business model.

---

## The score uses no `μ`

Kelly needs `μ`, the expected return, and `μ` is the least estimable quantity in
finance. Measured on BTC, the ruin point comes out at **3.06x** or **7.63x**
depending only on the volatility window chosen. A score built on that is fragile,
so the score does not use it. Kelly is reported as a **field**, with the assumed
`μ` printed in every index, and contributes **zero points**.

The score rates on what is measurable:

| Component | What it is |
|---|---|
| **Account volatility** | annualized portfolio volatility ÷ equity, from measured per-coin σ and the real correlation matrix. Positions enter **signed**, so a long hedged by a short nets out |
| **Distance to liquidation** | how far price can move before forced closure — a fact, not an estimate |
| **Effective bets** | genuinely independent positions. With mean pairwise correlation of **0.64**, five altcoins are not five bets |

### Grades

Cut-offs are **calibrated against measured liquidation rates**, not picked as round
numbers. See the validation section.

| Grade | Points | Measured 90-day liquidation rate |
|---|---|---|
| **A** | 0–19 | 0.5% |
| **B** | 20–39 | 6.5% |
| **C** | 40–49 | 43.3% |
| **D** | 50–89 | 57.1% |
| **F** | 90–100 | 74.5% |

Every wallet carries its own `tasa_historica`, so a grade `D` does not say "bad" —
it says *57% of portfolios like this were liquidated in a 90-day window of real prices*.

---

## Validation

### What could not be tested, and why

The obvious test — score wallets as they stood 280 days ago, then see what happened
— **is impossible.** Hyperliquid caps fill history by *count*, not time. An active
trader's full reconstructable history is about six days. This is documented rather
than faked.

### What was tested

Historical simulation: each wallet's **real current portfolio** made to live through
**real past prices**, unrebalanced. Three safeguards against fooling ourselves:

- **No leakage.** Volatilities and correlations estimated using **only data before
  2025-11-30**. The model never sees the period it is scored on.
- **Many paths.** 13 rolling 90-day windows, rising and falling markets.
- **One formula.** The audit **imports** `scorer.puntuar()` rather than
  reimplementing it, so calibration cannot drift from production.

### Result

```
grade   wallets   simulations   liquidated    rate
  A         179         1,739            8     0.5%
  B         144         1,430           93     6.5%
  C         133         1,399          606    43.3%
  D         239         2,669        1,525    57.1%
  F          29           364          271    74.5%

A+B 3.2%   |   D+F 59.2%   |   discrimination 18.6x
```

It holds in **rising** markets, which is the test that matters — otherwise the grade
is just a proxy for being long:

```
window start      BTC        A     B     C     D     F
2026-02-13     +15.2%       0%    1%   32%   34%   65%
2026-02-28      +9.9%       0%    1%   32%   37%   49%
2026-05-29      +7.6%       0%    3%   58%   64%   80%
```

Net direction is balanced across grades (52% net long for A, 61% for F).

### What the audit broke

The original cut-offs were round numbers picked by hand, and they were wrong.
Measured rate by point band showed the cliff is at **40** points, not 60, and that
between 50 and 89 the rate is flat — grades C, D and the lower half of F described
the *same* risk. The scale promised five levels and delivered three. Cut-offs were
recalibrated to the measured cliffs.

### Limits — stated, not buried

1. **13 overlapping windows over 280 days are only ~3 independent market paths.**
   Confidence is far lower than the simulation count suggests.
2. **10 of 13 windows were falling markets.** Rising-market evidence is thinner.
3. **Portfolios are held constant** — no margin top-ups, no stops. Real traders do
   both, so absolute rates are upper bounds. The **relative ordering** is the result.
4. These are today's portfolios in past prices, not a prediction of behaviour.
5. **Survivorship.** The universe comes from current trade feeds, so accounts that
   blew up and quit are absent. This pushes measured rates *down* — conservative.
6. **The calibration will drift.** `TASA_HISTORICA` was measured under one
   volatility regime. It must be re-run as history accumulates; the date it was
   calibrated is stamped in every index.

### Two validations that answer different questions

`aciertos.py` measures what **actually happened** to previously graded wallets —
real, but a tiny sample so far. The historical simulation measures what **would have
happened** to today's portfolios in past markets — hypothetical, but a large sample.
They are not interchangeable and their numbers will differ. Both are published.

---

## Errors found and corrected

Published here because a rating agency that quietly patches its own mistakes is
worth nothing. Each was found by checking our output against Hyperliquid's own
reported values rather than trusting the model.

1. **A zeroed perp account was read as death.** Usually it is someone who closed
   positions and moved to spot. One "destroyed" wallet held $2,205,079 in spot.
2. **All `liquidation` fills were counted.** Hyperliquid also flags the side that
   *absorbs* a liquidation, and that side profits — producing "liquidated grade-A
   wallets" with positive PnL.
3. **Spot was valued by array position.** `universe` (326) and `ctx` (718) do not
   correspond positionally; they must be matched by pair name. This produced
   portfolio values of $2,697,995,123.
4. **The `send` ledger type was silently ignored**, erasing entire withdrawals.
5. **Volatility was measured for the top 40 coins only**, while portfolios hold
   177. Forty-seven percent of accounts were scored using an invented 120%
   default for at least one position. All 193 listed perps are now measured.
6. **Equity was read from the perpetual account alone.** Hyperliquid runs a
   *unified* account: USDC held in spot **is** the collateral backing perpetual
   positions. Reading `marginSummary.accountValue` understated equity — in one
   case $527 against a real $1,478 — inflating leverage and shrinking the
   apparent distance to liquidation across much of the index.
7. **A materiality filter suppressed real danger.** Positions under 5% of equity
   were skipped when computing account liquidation distance. But in **cross
   margin every position threatens the whole account**: `liquidationPx` for a
   coin is the price at which that coin's move liquidates the *entire* account.
   The filter reported accounts as "100% safe" that Hyperliquid placed **1% from
   liquidation**.

8. **The verification read equity differently from the index.** After error 6
   was fixed in the scorer, `aciertos.py` still read the perpetual account alone.
   It compared a unified starting equity against a partial ending equity: grade-A
   wallets showed a **−69% median return in ten days** while BTC fell 6.7%. The
   destruction rate (which values nothing) was unaffected. Fixed on 2026-09-16;
   the equity definition now lives in **one function that both files import**.
9. **Equity ignored the account mode.** Hyperliquid has several: *unified* and
   *portfolio margin* (spot USDC is the collateral), and *standard* (`disabled` /
   `default`: spot and perp are separate). In a sample of 300 rated wallets the
   mode is reported by the API and each formula was checked against Hyperliquid's
   own `liquidationPx`: standard accounts match `accountValue` in 11 of 11. The old
   code added unrealized PnL **on top of** `accountValue`, which already includes it.
10. **Spot holdings other than USDC were ignored.** BTC, HYPE and other tokens are
    equity *and* price risk. In a sample of 200, **16%** of rated wallets held such
    spot worth over 10% of recorded equity; some held 8× to 236× it. They now count
    as equity and as long positions in the volatility calculation. Loans appear as
    negative balances, so debt is netted automatically.
11. **Large isolated positions were ignored.** The rule "isolated positions cannot
    sink the account" is true only while their margin is small. **334 of 4,283**
    accounts had isolated positions using over 30% of equity as margin and were
    reported "100% from liquidation" (71 graded B, 6 graded A). Losing over 30% of
    equity in liquidations is exactly what the verification counts as destruction —
    the scorer ignored what the validation measures. Isolated positions with margin
    ≥ 30% of equity now set the distance.
12. **A missing liquidation price was read as safety.** Hyperliquid returns
    `liquidationPx: null` for some cross positions, mostly portfolio-margin accounts.
    **286** accounts above 1.5× leverage were rated as if they could not be
    liquidated (164 B, 65 A) — including one at loan health 1.13, about 12% from
    liquidation. Now: loan health gives the distance when there is a loan
    (`1 − 1/health`), and otherwise it is **estimated** from a common market move and
    **flagged** in the rating.

Errors 9–12 were measured by scoring the same 297 wallets at the same moment with
both formulas: **84% keep their grade**, 29 get worse, 19 get better. Every change
traces to one of the four causes above. They are fixed in **methodology 2.1**, in
effect from the index of **2026-09-24**. Earlier indices were produced with 2.0 and
are kept unchanged; each index file states its methodology, and the verification
only compares an index against equity measured with the same definition.

Errors 6 and 7 were caught by auditing 14 randomly selected rated wallets against
Hyperliquid's own `liquidationPx`: **7 of 14 deviated by more than 5 percentage
points**, several by more than 90. After the fix, **0 of 14 deviate at all**.
Grades moved substantially — `D→A`, `C→A`, `F→A` — because the old reading rated
accounts as far more leveraged than they actually were.

The index dated 2026-09-05 carries errors 6 and 7. It is **kept, not deleted**,
and superseded by a corrected run.

**Rules adopted from this:**
- Distance to liquidation is taken from the exchange's own `liquidationPx`. Isolated
  positions are excluded **only when their margin is under 30% of equity**; nothing
  else is filtered. When the exchange reports no liquidation price, the distance is
  estimated and the rating says so — a missing number is never read as safety.
- Any ledger movement type not explicitly recognised marks a wallet `NO MEDIBLE`
  and drops it from the sample. A smaller honest `n` beats a larger false one.

---

## Assumptions, all of them

| Constant | Value | Why |
|---|---|---|
| `MU_SUPUESTO` | 0.55 | round assumption for the Kelly *reference field only*; contributes no points |
| `VOL_DESCONOCIDA` | 1.20 | coins without enough history are assumed very volatile — deliberately conservative. Wallets holding them are **flagged**, not silently defaulted |
| `CORR_DESCONOCIDA` | 0.70 | unknown pairs assumed highly correlated — conservative |
| `MATERIAL` | 0.30 | share of equity whose loss counts as destruction: isolated positions with at least this much margin set the liquidation distance, and a perp side smaller than this cannot "destroy" an account that is mostly spot |
| `COBERTURA` | 0.50 | when estimating a missing liquidation price, a hedged book (long one coin, short another) is credited with at most halving its gross exposure — hedges fail too |
| `PATRIMONIO_MIN` | $100 | accounts below this are excluded from the index |

Small isolated-margin positions do not set the account's liquidation distance: their
loss is capped at their own margin. A `$42,647` account was once flagged at "12% from
liquidation" because of an isolated `$21` position. But "small" matters — see error
11: an isolated position holding most of the account's equity can destroy it.

The earlier 5% materiality filter for cross positions was **removed** (error 7); an
older version of this table still listed it.

If the correlation matrix comes back non–positive-semidefinite, the portfolio
volatility is not trustworthy; the wallet is flagged and floored, never silently
clamped to zero.

---

## Our own wallet is in the index

Rated by the same criteria, every day, including on the days the grade is bad.
Marked `<-CASA` in the run log. No other trading account publishes its own bad marks.

## Can you copy this?

Yes. The data is public, the mathematics is from 1956, the code is here. What cannot
be copied is the dated record: a copy started today begins at zero days. That is the
same moat every rating agency has ever had — weak in year one, strong in year five.

---

## Files

```
mercado.py               per-coin volatility and correlations, all listed perps
scorer.py                the rating engine; puntuar() is the single scoring formula
aciertos.py              verification of past indices against what actually happened
auditoria_historica.py   the out-of-sample simulation; imports scorer.puntuar()
indices/                 one dated JSON per day
mercado.json             the measured volatilities and correlations, published
universo.json            the accumulating wallet universe, with first-seen dates
```

Addresses are public and pseudonymous. A wallet is never linked to a person.

MIT licensed. If you find an error in the method, open an issue — it will be
published alongside the correction, as the ones above were.
