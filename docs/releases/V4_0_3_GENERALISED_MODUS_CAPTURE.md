# DartsEdge v4.0.3 — Generalised MODUS Capture

## Added

- Capture sessions now support any valid MODUS Series and Week.
- Supported contexts are Group A, Group B, Group C and Final.
- Capture Wizard can create folders for later weeks without the old Week 1
  restriction.
- Rebuilding a session preserves already saved match pages.
- Capture Manager wording now reflects automatic page-context detection.

## Unchanged

- Capture remains fully browser-assisted and offline.
- No live MODUS requests are made.
- Match detail pages still use the stable `match_<id>.html` naming convention.
- Upcoming fixture-page import continues through the dedicated MODUS Fixtures
  workflow; capture sessions remain focused on match-detail pages.

## Safety

- No database writes.
- No migrations.
- Existing Series 14 Week 1 sessions remain compatible.
