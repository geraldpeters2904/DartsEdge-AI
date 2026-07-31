# DartsEdge v4.2.1.2 — Prediction Audit Test Isolation Hotfix

## Fixed

- The isolated prediction-audit test now imports the Player model.
- This registers the `players` table before `Base.metadata.create_all(...)`.
- Resolves `NoReferencedTableError` for `player_aliases.player_id`.

## Scope

This is a test-isolation correction only. Application code and database data
are unchanged.
