# DartsEdge v4.0.1 — Warehouse Dashboard

## Added

- Read-only warehouse summary cards.
- Dynamic table discovery for existing DartsEdge schemas.
- Scheduled and completed fixture counts.
- Capture Library progress summary.
- Warehouse health indicators.
- Recent import/preview activity where a recognised table exists.
- SQLite path and size details.
- Dedicated `/admin/warehouse-dashboard` route.

## Safety

- No database writes.
- No migrations.
- No live HTTP requests.
- Unknown table layouts are handled gracefully.
