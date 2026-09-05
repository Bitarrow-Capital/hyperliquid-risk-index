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

## Assumptions, all of them

| Constant | Value | Why |
|---|---|---|
| `MU_SUPUESTO` | 0.55 | round assumption for the Kelly *reference field only*; contributes no points |
| `VOL_DESCONOCIDA` | 1.20 | coins without enough history are assumed very volatile — deliberately conservative. Wallets holding them are **flagged**, not silently defaulted |
| `CORR_DESCONOCIDA` | 0.70 | unknown pairs assumed highly correlated — conservative |
| `MATERIALIDAD` | 0.05 | positions under 5% of equity do not set account liquidation distance |
| `PATRIMONIO_MIN` | $100 | accounts below this are excluded from the index |

Isolated-margin positions never set the account's liquidation distance: their loss
is capped at their own margin. A `$42,647` account was once flagged at "12% from
liquidation" because of an isolated `$21` position — fixing that moved 48 wallets
out of grade F.

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
