# Sprint 3.5D — Fixture Lifecycle Acceptance Pack

## Added

- Saved-page parsing for upcoming and completed fixture cards.
- Scheduled fixtures do not receive fabricated scores or statistics.
- Canonical fixture generation for scheduled and completed states.
- Stable match/player/source IDs.
- Lifecycle decisions: insert, update, skip and reject.
- Acceptance fixtures for scheduled and completed versions of the same match.

## Safety

- No live HTTP requests.
- No automatic downloads.
- No database writes.
- This pack adds lifecycle logic and tests only; Collector integration follows after acceptance.
