# DartsEdge MODUS Official Connector Specification v0.1

## 1. Purpose

Define a safe, traceable connector for acquiring MODUS Super Series fixtures, results, match-level statistics and series-level summary statistics from the official MODUS website and passing them into the existing DartsEdge canonical Preview → Commit → Rollback pipeline.

This specification contains no automated scraping implementation. It defines the source model, URL patterns, field mappings, validation rules, provenance requirements, operating modes and safety controls required before implementation.

## 2. Source structure

### Results and fixtures

```text
https://modussuperseries.com/results
https://modussuperseries.com/results?series_id={series_id}&week_id={week_id}&group={group}
```

Known group values:

```text
Group+A
Group+B
Group+C
Final
Averages
```

Example:

```text
https://modussuperseries.com/results?series_id=15&week_id=178&group=Group+A
```

### Match statistics

Observed pattern:

```text
https://modussuperseries.com/match-db-stats.php?match_id={match_id}
```

Example:

```text
https://modussuperseries.com/match-db-stats.php?match_id=18195
```

Search engines also expose a newer route pattern:

```text
https://modussuperseries.com/match/statistics/{match_id}
```

The implementation must treat route patterns as configurable source metadata.

## 3. Domain hierarchy

```text
Competition
└── Series
    └── Week
        ├── Group A
        ├── Group B
        ├── Group C
        ├── Final
        └── Averages
            └── Match
                ├── Player A
                ├── Player B
                ├── Result
                └── Player match statistics
```

## 4. Observed source data

### Match list

- Match number/order
- Player A and Player B
- Player A and Player B leg scores
- Group
- Series
- Week
- league table / standings
- cumulative group average
- match-detail identifier/link

### Match detail

- Match ID
- Date/time
- Series
- Group
- Player A and Player B
- Final score
- Three-dart average
- 100+ scores
- 140+ scores
- 180s
- Checkout attempts
- Checkouts completed
- Checkout percentage
- Highest checkout
- Ton-plus checkouts

### Series averages

- Position
- Player
- Matches played
- Total points
- Total darts
- Cumulative three-dart average

Series averages are reference/validation observations and must not replace match-level statistics.

## 5. Canonical mapping

### Fixture

| Source | Canonical |
|---|---|
| match_id | external_id |
| MODUS | competition_code |
| MODUS Super Series | competition_name |
| series label/id | series |
| week label/id | week |
| group | group |
| group/final | stage |
| date/time | scheduled_at or actual_start_at |
| player A source ID/key | player_a_external_id |
| player A name | player_a_name |
| player B source ID/key | player_b_external_id |
| player B name | player_b_name |
| best of 7 | match_format |
| completed/scheduled | status |

### Result

| Source | Canonical |
|---|---|
| match_id | match_external_id |
| player A ID | player_a_external_id |
| player B ID | player_b_external_id |
| winner ID | winner_external_id |
| player A legs | player_a_legs |
| player B legs | player_b_legs |
| completion time | completed_at |

### Statistics

One canonical record per player per match.

| Source | Canonical |
|---|---|
| match_id | match_external_id |
| player ID | player_external_id |
| average | three_dart_average |
| 100+ | scores_100_plus |
| 140+ | scores_140_plus |
| 180s | scores_180 |
| checkout attempts | checkout_attempts |
| checkouts made | checkouts_completed |
| checkout % | checkout_percentage |
| high checkout | highest_checkout |
| legs won | legs_won |
| opponent legs | legs_lost |

Remain null unless explicitly supplied:

- first_nine_average
- legs_held
- legs_broken
- match_duration_seconds
- throwing_first_player_external_id
- first_leg_winner_external_id
- first_180_player_external_id

## 6. Stable identifiers

Match:

```text
modus-match-{match_id}
```

Provider source IDs:

```text
modus:fixture:{match_id}
modus:result:{match_id}
modus:statistics:{match_id}:{player_external_id}
modus:series-summary:{series_id}:{week_id}:{player_external_id}
```

Player ID preference:

1. Official player ID, when exposed.
2. Existing provider mapping.
3. Stable normalised provider key from name, followed by player reconciliation.

## 7. Provenance

Retain:

- provider: `modus-official`
- source URL
- match ID
- series ID
- week ID
- group
- retrieval timestamp
- source page type
- parser version
- connector version
- source confidence
- raw permitted snapshot or extracted-payload hash

## 8. Operating modes

### Mode A — Browser-assisted, default

1. User selects Series, Week and Group.
2. DartsEdge opens the official page.
3. User confirms the source page.
4. DartsEdge processes pasted table/page data or browser-exported content.
5. Canonical preview is produced.
6. User commits manually.

No automated HTTP retrieval is required.

### Mode B — Low-rate connector, disabled by default

Enable only after permitted use is confirmed.

Controls:

- explicit environment flag
- descriptive user agent
- minimum interval between requests
- local cache
- no repeat fetch of unchanged match IDs
- bounded series/week selection
- stop on 403, 429 or challenge
- no concurrency in v1
- full run audit
- manual preview before commit

Suggested settings:

```text
DARTSEDGE_MODUS_CONNECTOR_ENABLED=false
DARTSEDGE_MODUS_MIN_REQUEST_INTERVAL_SECONDS=5
DARTSEDGE_MODUS_MAX_MATCHES_PER_RUN=50
DARTSEDGE_MODUS_CACHE_TTL_HOURS=168
```

## 9. Access and compliance gate

No clearly indexed public Terms of Use or robots policy was identified during initial research. This is not permission to automate.

Before Mode B:

- review any current site terms and privacy/access pages
- seek written permission where practical
- record the decision and date
- keep traffic minimal
- do not bypass access controls or rate limits
- stop immediately if requested
- retain Mode A as fallback

## 10. Validation

Fixtures:

- match ID required
- both player names required and different
- series, week and group required
- duplicate match IDs rejected in-session

Results:

- fixture must exist or be in the same session
- scores are non-negative integers
- winner must match higher score
- players must match fixture
- no tied completed match

Statistics:

- fixture must exist
- player must be a participant
- average 0–180
- count stats non-negative
- completed checkouts cannot exceed attempts
- checkout percentage 0–100
- percentage should match made/attempts within tolerance
- highest checkout 0–170
- legs won/lost should agree with result

Series summaries:

- points and darts non-negative
- average should approximately equal points ÷ darts × 3
- discrepancies create warnings, never silent corrections

## 11. Duplicate policy

- Fixtures: one canonical fixture per MODUS match ID.
- Results: identical repeat is duplicate; changed completed result is conflict.
- Statistics: immutable per player-match; identical repeat is duplicate; changed record is conflict.
- Series summaries: versioned observations by retrieval time.

## 12. Error classes

- source unavailable
- access denied
- rate limited
- page structure changed
- missing match ID
- incomplete match page
- invalid statistic
- unresolved player
- duplicate
- immutable-record conflict

Each failed run records:

- run ID
- selected scope
- error category and message
- last successful URL
- matches discovered/parsed/rejected
- duration

## 13. UI workflow

```text
MODUS Connector
→ Select Series
→ Select Week
→ Select Group
→ Discover matches
→ Review match IDs
→ Fetch or paste match details
→ Canonical validation
→ Combined preview
→ Resolve aliases
→ Commit
→ Verify batch
→ Roll back if needed
```

Selection screen:

- Series dropdown
- Week dropdown
- Group selector
- include fixtures/results/statistics
- acquisition mode
- estimated request count
- cache status

Discovery screen:

- match ID
- players
- score/status
- detail-page availability
- cached/fresh
- selected/excluded
- warnings

## 14. Proposed code structure

```text
app/providers/adapters/modus_official/
    __init__.py
    adapter.py
    client.py
    parser.py
    identifiers.py
    cache.py
    policy.py
    schemas.py

app/services/modus_connector_service.py
app/routes/modus_connector.py
app/templates/modus_connector.html
app/templates/modus_connector_discovery.html

tests/test_modus_url_model.py
tests/test_modus_results_parser.py
tests/test_modus_match_parser.py
tests/test_modus_connector_policy.py
tests/test_modus_connector_service.py
tests/test_modus_connector_routes.py
```

## 15. Testing policy

Tests use saved, sanitised HTML fixtures or structured snapshots and never call the live site.

Required cases:

- Group A, Group B, Group C and Final URL generation
- completed and scheduled matches
- all observed statistics
- zero 180s
- zero checkout attempts
- player-name variation
- missing statistic
- changed HTML
- duplicate match
- conflicting result
- cache hit
- rate-limit response
- disabled connector

## 16. Definition of done

- Series, Week and Group can be selected.
- Match IDs are discovered.
- Fixtures, results and observed statistics map to canonical records.
- Everything enters the existing preview pipeline.
- Nothing commits without preview.
- Duplicate and immutable-history rules pass.
- Provenance includes source URLs and IDs.
- Browser-assisted mode works without automation.
- Automated mode stays disabled unless explicitly authorised.
- Focused and full regression suites pass.
