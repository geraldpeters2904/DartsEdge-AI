# DartsEdge AI Master Data Dictionary

## Purpose

This document defines the provider-independent data contracts used by
DartsEdge AI.

All MODUS, Sportradar, Statorium, iDarts, PDC, WDF, ADC, CDC, CSV and JSON
sources must be normalised into these contracts before reaching prediction,
strategy or portfolio services.

## Core rules

1. Provider adapters fetch, parse, validate and normalise data.
2. Prediction services never read provider-specific fields.
3. Original provider payloads are retained in `raw_ingestion_records`.
4. External identifiers are mapped through `provider_entity_mappings`.
5. Important field origins are recorded in `data_provenance`.
6. Missing values remain `NULL`.
7. Zero is stored only where a provider explicitly reports zero.
8. Derived values are calculated by DartsEdge and are not accepted as provider
   truth.

## Supported competition families

- MODUS
- PDC
- WDF
- ADC
- CDC
- OTHER

## Canonical entities

### Player

| Field | Priority | Meaning |
|---|---|---|
| external_id | Essential | Stable provider player identifier |
| name | Essential | Display name |
| country_code | Desirable | ISO-style country code |
| nickname | Optional | Player nickname |
| date_of_birth | Future | Date of birth |
| handedness | Future | Left, right or unknown |

### Competition

| Field | Priority | Meaning |
|---|---|---|
| external_id | Essential | Stable provider competition identifier |
| competition_code | Essential | MODUS, PDC, WDF, ADC, CDC or OTHER |
| name | Essential | Competition name |
| season | Essential where available | Season or calendar year |
| series | Essential for MODUS | MODUS series |
| week | Essential for MODUS | Tournament week |
| group | Desirable | Group A, B or C |
| stage | Desirable | Group, semi-final, final, etc. |

### Fixture

| Field | Priority | Meaning |
|---|---|---|
| external_id | Essential | Stable match identifier |
| scheduled_at | Essential | Scheduled date and time |
| status | Essential | Scheduled, live, completed, postponed, etc. |
| match_format | Essential | Best of 7, best of 11, etc. |
| player_a | Essential | First participant |
| player_b | Essential | Second participant |
| throwing_first_player | Desirable | Player with first throw |
| board | Desirable | Board or stream |
| session | Desirable | Morning, afternoon or evening session |

### Result

| Field | Priority | Meaning |
|---|---|---|
| winner | Essential | Winning player |
| player_a_legs | Essential | Player A final leg total |
| player_b_legs | Essential | Player B final leg total |
| completed_at | Desirable | Completion timestamp |
| first_leg_winner | Desirable | First-leg winner |
| first_180_player | Essential for first-180 modelling | First player to hit 180 |

### Player match statistics

| Field | Priority |
|---|---|
| three_dart_average | Essential |
| scores_180 | Essential |
| checkout_percentage | Essential |
| highest_checkout | Essential |
| first_nine_average | Desirable |
| scores_100_plus | Desirable |
| scores_140_plus | Desirable |
| checkout_attempts | Desirable |
| checkouts_completed | Desirable |
| legs_held | Future |
| legs_broken | Future |
| match_duration_seconds | Future |

### Odds snapshot

Each price observation stores:

- match identifier
- market
- selection
- bookmaker
- decimal odds
- capture timestamp
- source provider

Price history is append-only. Existing snapshots must not be overwritten.

## Derived metrics

DartsEdge calculates these values from canonical history:

- Elo
- rolling win rate
- rolling three-dart average
- rolling first-nine average
- checkout trend
- 180s per match
- 180s per leg
- first-180 rate
- streaks
- head-to-head summaries
- rest and fatigue indicators
- model probability
- fair odds
- expected value
- Kelly stake

These calculations remain independent of the source provider.
