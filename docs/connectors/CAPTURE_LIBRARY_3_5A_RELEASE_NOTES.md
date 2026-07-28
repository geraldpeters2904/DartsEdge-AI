# Sprint 3.5A — Capture Library

## Added

- Capture Library page.
- Recursive discovery of persisted MODUS capture sessions.
- Series/week/group grouping.
- Captured, expected and missing totals.
- Per-session progress bars.
- One-click Resume/Open links.
- Configurable capture root.
- Automatic progress refresh when the library is scanned.

## Safety

- No live HTTP requests.
- No database writes.
- Invalid or incomplete session folders are skipped rather than breaking the library.
