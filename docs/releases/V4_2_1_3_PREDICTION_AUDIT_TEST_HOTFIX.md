# DartsEdge v4.2.1.3 — Prediction Audit Test Isolation Hotfix

## Fixed

- Registers both the Player and Match models before the isolated test calls
  `Base.metadata.create_all(...)`.
- Resolves the foreign-key dependency from
  `player_match_performances.match_id` to `matches.id`.

## Scope

Test-only change. No application code, migrations, or database records are
changed.
