# DartsEdge v4.0.4 — Partial Acceptance and Warehouse Validation

## Added

- Explicit Partial Acceptance mode in the Import Wizard.
- Missing uncaptured match pages become warnings only in partial mode.
- Every included match page still receives full player, score and parser validation.
- Canonical Preview contains only validated captured matches.
- Full-folder validation remains unchanged and is still required for normal imports.
- Partial mode never marks the capture session itself complete.

## Intended use

This mode supports controlled real-data acceptance tests with a small number of
captured matches before importing an entire 45-match group.

## Safety

- Validation and preview remain read-only.
- Database writes still require explicit Collector Preview approval.
- Unexpected pages, invalid filenames and failed match validation remain errors.
