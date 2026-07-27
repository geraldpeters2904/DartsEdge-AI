# Canonical Data Validation Rules

## General

- Unknown fields are rejected.
- Required identifiers must be non-empty.
- Provider names and external IDs are retained.
- A fixture must contain two different players.
- Provider timestamps must include enough information to identify the event
  date and time.

## Result rules

- A completed match requires a winner.
- The winner must be one of the two participants.
- The final leg totals must not be tied.
- The declared winner must agree with the leg score.
- First-leg and first-180 players must be match participants.

## Statistics rules

- Three-dart and first-nine averages: 0 to 180.
- Checkout percentage: 0 to 100.
- Highest checkout: 0 to 170.
- Score counts must be non-negative integers.
- Completed checkouts cannot exceed checkout attempts.

## Odds rules

- Decimal odds must be greater than 1.00.
- Every odds observation requires a bookmaker and capture timestamp.
- Prices are append-only observations.

## Null versus zero

`NULL` means the source did not provide the field.

`0` means the source explicitly reported that the event did not occur.

Examples:

- `scores_180 = NULL`: the provider supplied no 180 data.
- `scores_180 = 0`: the provider confirmed the player hit no 180s.
- `highest_checkout = NULL`: the provider supplied no checkout statistic.
- `highest_checkout = 0`: the provider explicitly reported no completed
  checkout.
