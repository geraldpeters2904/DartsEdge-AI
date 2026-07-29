# Sprint 3.5D.1 — Fixture Lifecycle Hotfix

## Fixed

- Scheduled canonical fixtures no longer fail validation when MODUS does not
  expose a scheduled datetime.
- The existing CanonicalFixture schema always receives a valid datetime.
- Scheduled fixtures still have no fabricated scores, results or statistics.
- Completed fixtures receive a consistent actual_start_at value.

## Safety

- No live HTTP requests.
- No database writes.
- Installer backs up the previous lifecycle service.
