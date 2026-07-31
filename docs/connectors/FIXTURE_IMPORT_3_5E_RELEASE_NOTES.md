# Sprint 3.5E — Fixture Import Acceptance

## Added

- Fixture-only MODUS import page.
- Upload of a saved upcoming/completed fixture page.
- Canonical fixtures CSV generation.
- Direct hand-off to the existing Collector Preview.
- Stable match IDs across scheduled and completed states.
- Acceptance tests for fixture-only preview creation.

## Safety

- No live HTTP requests.
- No automatic downloads.
- No direct database commit.
- Collector Preview remains the approval gate.
