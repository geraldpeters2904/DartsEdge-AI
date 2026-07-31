# DartsEdge v4.2.1.4 — Prediction Audit Date Test Hotfix

## Fixed

- The prediction-audit date-filter test no longer relies on the machine's
  current local date.
- The test now derives `date_from` from the actual persisted audit timestamps.
- This removes midnight and UTC/local timezone boundary failures.

## Scope

Test-only change. No application code, migrations, or database records are
changed.
