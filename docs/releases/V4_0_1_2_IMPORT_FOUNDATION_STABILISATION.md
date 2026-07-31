# DartsEdge v4.0.1.2 — Import Foundation Stabilisation

## Fixed

- Warehouse Dashboard tests now use stable `data-testid` markers rather than
  case-sensitive display wording.
- The current `matches` table is recognised as the fixture lifecycle table
  when no separate fixtures table exists.
- The current `match_player_stats` table is recognised for statistics counts.
- Current historical import preview and batch tables are recognised for recent
  import activity.

## Scope

This release stabilises the read-only dashboard and establishes a clean
baseline before fixture commit correctness and real-data acceptance work.

## Safety

- No migrations.
- No live HTTP requests.
- No database writes by application code.
- Installer backs up every replaced file.
