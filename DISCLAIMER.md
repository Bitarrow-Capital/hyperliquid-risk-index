# Disclaimer

**This is not investment advice.** Nothing published in this repository is a
recommendation to buy, sell, or hold any asset, nor an offer to manage anyone's
funds. Bitarrow Capital, S.A. de C.V. is not authorized by the CNBV, CNSF, or
any other financial regulator, and does not carry out any activity reserved to
authorized institutions. It does not receive, hold, custody, or manage third-party
funds under any circumstance.

**What the index measures.** A single thing: how much destruction risk an account
carries, given its position size, its distance to liquidation, and the measured
volatility and correlation of the assets it holds. It does not predict prices or
returns. A high grade does not mean an account will be profitable.

**The assumptions are written down and arguable.** The Kelly ruin point depends on
the assumed expected return (`μ`) and volatility (`σ`). Both are published in every
index file and both change with the measurement window. Readers are expected to
substitute their own and recompute.

**Reliability is measured, not asserted.** Every index is later compared against
what actually happened, and that record is published in full, including errors.
Below 50 wallets or a 30-day window, results are marked as not statistically
significant.

**Addresses are public and pseudonymous.** No wallet is ever linked to a person,
and no attempt is made to deanonymize any address. All data comes from
Hyperliquid's public API.

**Corrections.** Errors found in the methodology are published alongside the
correction rather than quietly patched. See the "Measurement errors already found
and corrected" section of the README.
