# ADR 0005: Shadow comparison uses append-only outcome events

## Decision
Keep prediction snapshots immutable. Store each result or correction as a separate `prediction_audit_outcomes` event. The latest event is used for evaluation while the complete correction history remains available.

## Why
This preserves what the model knew at prediction time, prevents silent historical rewrites, and gives the Model Performance Lab reproducible evidence.

## Consequences
The official model remains unchanged. Shadow metrics use settled records only. A minimum sample warning remains visible until at least 25 settled comparisons exist.
