# Hyperliquid Risk Index

A daily, public, timestamped risk rating of Hyperliquid accounts, built entirely
from public on-chain data.

Published by [Bitarrow Capital](https://bitarrow.capital). Every index file in
`indices/` is committed the day it is produced, so the dates are GitHub's, not ours.

---

## What this measures — and what it does not

It measures **one thing**: how much destruction risk an account is carrying,
given its position size, its distance to liquidation, and the actual volatility
and correlation of the assets it holds.

It is **not** investment advice. It does **not** predict prices or returns.
An `A` does not mean the account will make money. An `F` does not mean it will
lose money tomorrow. It means the account is sized such that an ordinary market
move can end it.

---

## Why this is not the liquidation price your exchange already shows you

Your exchange shows you *where* you get liquidated. That is free and we are not
selling it.

This measures something different: whether the **size of the bet** destroys the
account over time **even when the direction is right**.

The Kelly criterion (1956) says there is an optimal bet size, `f* = μ/σ²`, and
that above roughly twice that size, long-run compounded growth turns negative —
regardless of edge. The intuition: losing 50% requires gaining 100% to recover.
Past a certain size, the arithmetic of recovery beats you.

No exchange will ever compute this for you. Their revenue is your volume and
your liquidations. Telling you to size down works against their business model.

---

## Why the score barely uses Kelly

Kelly needs `μ`, the expected return, and `μ` is the hardest quantity to
estimate in finance. Measured on BTC, the ruin point comes out at **3.06x** or
**7.63x** depending only on the volatility window chosen. A score built on that
is fragile, so we do not build one.

**The core of the score uses no `μ` at all.** It rates on what is measurable:

| Component | What it is | Why |
|---|---|---|
| **Account volatility** | annualized portfolio volatility ÷ equity | uses real per-coin σ and the real correlation matrix; positions enter **signed**, so a long hedged by a short nets out |
| **Distance to liquidation** | how far price can move before forced closure | a fact, not an estimate |
| **Effective bets** | number of genuinely independent positions | with mean pairwise correlation of **0.64**, five altcoins are not five bets |

Kelly is **reported** as a reference with the assumed `μ` printed in every index
file, so any reader can substitute their own and recompute. It carries little
weight in the score.

### The defect this replaces

Version 1 applied **BTC's** ruin point to every wallet. Measured over 180 days:

```
BTC    38% vol   ruin at 7.63x
ETH    55% vol   ruin at 3.68x
HYPE   85% vol   ruin at 1.51x
ZEC   128% vol   ruin at 0.67x
```

An **11x spread**. Someone at 3x in BTC is fine; someone at 3x in ZEC is 4.5
times past their ruin point. Rating them identically was wrong.

Version 1 also rewarded holding several positions. With BTC–ETH correlated at
**0.90**, that reward was mostly unearned.

---

## Grades

| Grade | Points | Reading |
|---|---|---|
| **A** | 0–19 | sized to survive ordinary moves |
| **B** | 20–39 | aggressive but coherent |
| **C** | 40–59 | one bad week from serious damage |
| **D** | 60–79 | structurally fragile |
| **F** | 80–100 | an ordinary move ends this account |

---

## Verification — the part that matters

A rating that is never checked is worth nothing. `aciertos.py` compares every
past index against what actually happened.

The **primary metric is the destruction rate**: the share of wallets in each
grade that lost more than 30% of equity to *forced liquidations* — taken from
fills flagged `liquidation` with negative `closedPnl`. It is an on-chain fact
that requires valuing nothing.

Return is reported as secondary and is frequently marked unmeasurable, on purpose.

### Measurement errors already found and corrected

Published here because a rating agency that hides its own errors is worthless:

1. **A zeroed perp account was read as death.** It is usually someone who closed
   positions and moved to spot. One "destroyed" wallet held $2,205,079 USDC in spot.
2. **All `liquidation` fills were counted.** Hyperliquid also flags the side that
   *absorbs* a liquidation, and that side profits. This produced "liquidated grade-A
   wallets" with positive PnL.
3. **Spot was valued by array position.** `universe` (326) and `ctx` (718) do not
   correspond positionally — they must be matched by pair name. This produced
   portfolio values of $2,697,995,123.
4. **The `send` ledger type was silently ignored**, erasing entire withdrawals.

**Standing rule:** any ledger type not explicitly recognized marks the wallet
`NO MEDIBLE` and drops it from the sample. A smaller honest `n` beats a larger
false one.

---

## Our own wallet is in the index

Rated by the same criteria as everyone else, every day, including on the days
the grade is bad. No other trading account publishes its own bad marks.

---

## Reliability

Sample size and window are printed on every run. Below 50 wallets or 30 days,
results are explicitly marked **not statistically significant**. The record gets
more reliable with time and with nothing else.

## Can you copy this?

Yes. The data is public, the mathematics is from 1956, and the code is here.

What cannot be copied is the dated record. A copy started today begins at zero
days while this one keeps its history. That is the same moat every rating agency
has ever had — it is weak in year one and strong in year five.

---

## Files

```
mercado.py     per-coin volatility and correlations, measured from HL candles
scorer.py      the rating engine + the accumulating wallet universe
aciertos.py    verification of past indices against what actually happened
indices/       one dated JSON per day
```

Addresses are public and pseudonymous. A wallet is never linked to a person.

MIT licensed. If you find an error in the method, open an issue — it will be
published alongside the correction.
