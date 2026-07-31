# DartsEdge v4.2.2 — Capture Session Manager

## Added

- Opening the MODUS Capture Manager automatically restores the most recently updated unfinished capture session.
- The active queue, match list, progress and next-match controls are shown immediately.
- A visible auto-resume notification explains which session was restored.
- `Start New Capture` bypasses auto-resume when a new queue is required.
- `Launch Capture Assistant` passes the active destination folder directly to the assistant form.

## Safety

- Existing capture session JSON remains the source of truth.
- No database writes.
- No live HTTP requests.
- No migration required.
