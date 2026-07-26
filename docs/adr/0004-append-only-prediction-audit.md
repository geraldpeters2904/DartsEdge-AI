# ADR 0004: Append-only prediction audit snapshots

## Decision

Store each generated prediction as a new immutable UUID-backed snapshot. Preserve official model outputs, experimental shadow outputs, profile versions, explanation data and relevant inputs in one JSON payload.

## Rationale

Historical model evaluation requires knowing exactly what the application knew at prediction time. Updating old rows would destroy reproducibility and weaken calibration, shadow-comparison and performance analysis.

## Consequences

- Prediction snapshots are never overwritten.
- Future results, settlements and corrections will be represented as separate events.
- Storage grows over time but remains auditable and exportable.
