# Sprint 3.3 — Generic Import Wizard

## Added

- Provider-agnostic Collector import entry point.
- Connector catalogue with availability states.
- MODUS Official folder validation.
- Validation report UI.
- Canonical payload generation through Sprint 3.2.
- Direct hand-off to the existing Collector Preview.
- Existing commit, cancel and rollback flow remains unchanged.

## Safety

- Validation makes no database writes.
- Preview only creates the existing pending preview record.
- No live MODUS requests are made.
