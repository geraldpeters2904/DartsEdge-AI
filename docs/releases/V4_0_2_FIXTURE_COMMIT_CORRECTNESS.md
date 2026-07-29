# DartsEdge v4.0.2 — Fixture Commit Correctness

## Fixed

- Fixtures are inserted and found by stable provider external ID.
- Scheduled fixtures no longer create fake zero-valued statistics.
- Repeated identical fixtures are duplicate-safe.
- Changed scheduled fixtures update the mapped Match rather than creating a
  second match.
- An already completed warehouse match is not downgraded by an older scheduled
  fixture page.
- Rollback restores fixture updates and still removes newly created fixtures.

## Safety

- No migration is required.
- Existing result and statistics committers remain unchanged.
- Raw records, mappings, provenance and batch audit items are preserved.
