# DartsEdge v4.2.1 — MODUS Capture Assistant

## Added

- Local Downloads-folder monitoring.
- Validation against the next expected MODUS match ID and player names.
- Automatic rename to `match_<id>.html`.
- Automatic move into the active capture folder.
- Duplicate and conflict protection.
- Accepted/rejected event log.
- Start/stop web controls.

## Safety

- No live HTTP requests.
- Wrong pages remain untouched in the watch folder.
- Existing destination files are never overwritten.
- The assistant stops automatically when the capture queue is complete.
