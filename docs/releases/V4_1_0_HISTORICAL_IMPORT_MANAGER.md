# DartsEdge v4.1.0 — Historical Import Manager Foundation

## Added

- Recursive discovery of folders containing `results.html`.
- Series, Week and Group context display.
- Captured/validated page totals.
- Warehouse comparison by stable MODUS fixture external ID.
- Folder states: ready, incomplete, imported, partially imported and error.
- Direct links into the existing Import Wizard.
- Read-only progress dashboard at `/admin/historical-imports`.

## Next increment

v4.1.1 will add a managed preview/commit queue after this discovery layer has
been tested against the real Series folder structure.

## Safety

- No database writes.
- No live HTTP requests.
- No migrations.
