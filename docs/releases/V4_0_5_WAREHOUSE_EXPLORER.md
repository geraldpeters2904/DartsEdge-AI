# DartsEdge v4.0.5 — Warehouse Explorer and Verification

## Added

- Read-only import batch list at `/admin/warehouse`.
- Batch details with audit items and resolved warehouse records.
- Provider external-ID mapping inspection.
- Field-level provenance inspection.
- Raw-ingestion retention inspection.
- Existing tracked rollback action exposed from batch detail.
- Navigation from Collector and Warehouse Dashboard.

## Purpose

This release makes the first real MODUS acceptance import inspectable before
loading complete historical groups and upcoming fixtures.

## Safety

- Explorer pages are read-only.
- Rollback continues to use the existing tracked batch operation.
- No migrations are required.
