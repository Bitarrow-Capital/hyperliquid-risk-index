# Superseded method (v1) — kept, not deleted

These indices were produced 2026-08-31 through 2026-09-04 with the first version
of the scoring engine, which had two defects found before any of this was published:

1. It applied **BTC's** Kelly ruin point to every wallet, regardless of what the
   wallet actually held. Real ruin points range from 7.63x (BTC) to 0.67x (ZEC).
2. It rewarded holding several positions without accounting for correlation.
   Mean pairwise correlation among major crypto is 0.64; BTC–ETH is 0.90.

A third defect was found in the v2 engine itself before publication: any position,
however small, could set the account's liquidation distance. A $42,647 account was
being flagged at "liquidation 12% away" because of an **isolated $21 position**
whose maximum loss was $27. Fixing it moved **48 wallets out of grade F**.

These files are kept because a rating agency that quietly deletes its old marks is
worthless. They should not be used to evaluate the current method.
