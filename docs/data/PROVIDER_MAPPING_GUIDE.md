# Provider Mapping Guide

Each provider adapter converts provider-specific fields into canonical
DartsEdge fields.

## Example aliases

| Provider field | Canonical field |
|---|---|
| avg | three_dart_average |
| threeDartAverage | three_dart_average |
| first9Avg | first_nine_average |
| maximums | scores_180 |
| oneEighties | scores_180 |
| checkoutPct | checkout_percentage |
| highestFinish | highest_checkout |
| firstMaximumPlayer | first_180_player_external_id |

## Adapter responsibilities

A provider adapter may:

- authenticate with its source
- fetch records
- parse provider payloads
- map provider fields
- validate canonical records
- return validation errors

A provider adapter must not:

- calculate Elo
- calculate prediction probability
- calculate expected value
- make strategy decisions
- place or settle paper trades

## Mapping workflow

1. Retain the raw payload.
2. Identify entity type and external identifier.
3. Convert provider names to canonical field names.
4. Preserve unavailable fields as `None`.
5. Validate with the Pydantic canonical schema.
6. reconcile player aliases and provider IDs.
7. import into existing DartsEdge tables.
8. record provenance for important fields.
