# Sprint 3.4A1 — MODUS Capture Backend

## Added

- Browser-assisted capture queue service.
- Real Series 14, Week 1, Group A queue with 45 matches.
- Stable official match URLs.
- Standard `match_<id>.html` destination names.
- Persistent `.modus_capture_session.json` session file.
- Captured, missing and next-match progress.
- Resume support by rescanning the destination folder.

## Safety

- No live HTTP requests.
- No automatic downloads.
- No database writes.
- Scope is limited to Series 14, Week 1, Group A.
