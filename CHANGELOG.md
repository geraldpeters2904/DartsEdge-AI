# Changelog

All notable changes to DartsEdge AI are recorded here.

## [1.4.0] - 2026-07-26

### Added
- Versioned strategy framework and five seeded strategy profiles.
- Validated strategy rules for EV, edge, confidence, Kelly, exposure, stake, sample, odds, markets and competitions.
- Strategy editor with immutable version history, duplication and JSON import/export.
- Guarded Decision Engine with shadow and active enforcement.
- Strategy Analytics with acceptance, rejection, settlement, ROI, win rate and drawdown.
- GitHub Actions regression workflow for Python 3.9 and 3.12.

### Changed
- Updated application metadata to v1.4.0, build 001 — Strategy Engine.
- Added dynamic version information to the sidebar footer.
- Normalised legacy template rendering through the modern Starlette request-first API.
- Organised documentation under architecture, API, user, developer, release and roadmap sections.

### Fixed
- Removed unclosed-file ResourceWarnings in Daily Briefing tests.
- Removed TemplateResponse deprecation warnings under application control.
- Made strategy tests independent of the user's persisted active-strategy choice.

### Safety and compatibility
- Intelligence remains in shadow mode.
- Strategy enforcement is not enabled automatically.
- Unsettled decisions remain excluded from performance results.

## [1.2.0] - 2026-07-26

### Added
- Configurable, versioned Player Intelligence weight profiles.
- Multi-factor Player Intelligence ratings operating in shadow mode.
- Structured prediction explainability with separate prediction and explanation confidence.
- Immutable UUID-backed prediction audit snapshots and CSV export.
- Append-only outcome and correction events for audited predictions.
- Shadow Comparison metrics for accuracy, Brier score and calibration.
- Model Performance Lab with profile, tournament, confidence-band and drift analysis.
- Independent model version metadata (`Intelligence-0.1-shadow`).

### Changed
- Updated application metadata to v1.2.0, build 001 — Intelligence Engine.
- Expanded diagnostics to verify the Intelligence Engine services.
- Updated navigation and documentation for the complete intelligence workflow.

### Fixed
- Replaced unsupported Python `max()` calls in the Shadow Comparison Jinja template.
- Added template regression coverage for the Shadow Comparison page.

### Safety and compatibility
- The legacy prediction model remains the official production model.
- Intelligence results remain in shadow mode until sufficient settled evidence supports promotion.
- Unsettled predictions are excluded from performance metrics.

## [1.1.1] - 2026-07-25

### Added
- Mission Control command centre.
- Opportunity ranking with explicit model-signal versus confirmed-value states.
- Portfolio Health analytics and settings-driven risk warnings.
- AI Coach prioritised operational recommendations.
- System diagnostics page plus `/version` and `/health` endpoints.
- Reproducible runtime and development dependency files.

### Changed
- Consolidated dashboard styling and responsive navigation.
- Added active navigation states and accessibility improvements.
- Added visible release and build information.

### Fixed
- Declared `httpx` as a development dependency for FastAPI TestClient tests.

## [0.5]
- Added Monte Carlo simulation, correct-score, handicap and total-legs markets.

## [0.4]
- Added player profiles, weighted 180 form, 180 markets and match intelligence.

## [0.3]
- Added dashboard, CSV import, duplicate protection and statistics.

## [0.2]
- Added SQLite database, players, matches, Elo and player statistics.

## [0.1]
- Initial FastAPI application and prediction endpoint.
