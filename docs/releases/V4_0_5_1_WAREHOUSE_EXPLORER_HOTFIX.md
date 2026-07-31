# DartsEdge v4.0.5.1 — Warehouse Explorer Installer Hotfix

## Fixed

- The installer no longer assumes that
  `tests.test_collector_preview_commit` exists.
- Focused tests are discovered from a safe candidate list.
- Missing optional test modules are skipped with a visible message.
- Application code from v4.0.5 is not changed.

## Safety

- No application source files are replaced.
- No database writes.
- No migrations.
- The complete regression suite still runs after focused tests.
