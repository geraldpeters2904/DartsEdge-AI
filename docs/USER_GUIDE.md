# DartsEdge AI User Guide — v1.2.0

## Daily workflow

1. Open **Mission Control** for opportunities, portfolio risk, alerts and AI Coach actions.
2. Use **Prediction Centre** to compare two players and generate the official prediction.
3. Expand **Why this prediction?** to inspect Player Intelligence factors, active profile and data coverage.
4. Open **Audit Trail** to review immutable prediction snapshots or export them to CSV.
5. Enter actual results in **Shadow Comparison** as outcomes become known.
6. Review **Performance Lab** after settling predictions to compare models and profiles.

## Player Intelligence

Player Intelligence is experimental and operates in shadow mode. The four initial profiles are Default, Elo Heavy, Form Heavy and Experimental. Enabled profile weights must total 100%.

Neutral factors indicate missing or not-yet-integrated data. They are shown honestly rather than being presented as evidence.

## Explainability

The application reports two different confidence measures:

- **Prediction confidence** describes the official model's certainty.
- **Explanation confidence** describes how complete the supporting factor data is.

A confident prediction can still have limited explanation coverage.

## Audit Trail

Every generated prediction receives an immutable UUID and stores the model/profile versions, probabilities, inputs and explanation snapshot. The original snapshot is never overwritten.

## Shadow Comparison

Settle audited predictions using the actual winner. Corrections create new events rather than changing the original prediction. Metrics exclude unsettled records.

## Performance Lab

The Lab reports accuracy, Brier score, calibration, profile performance, tournament performance, confidence bands and recent drift. Treat results as provisional until at least 25 predictions are settled.

## Existing operational pages

- **Opportunities** ranks model signals. A signal is not confirmed betting value without bookmaker odds.
- **Portfolio Health** reports bankroll, exposure and concentration risk.
- **AI Coach** prioritises actions based on available opportunities and portfolio state.
- **Diagnostics** confirms application, database and intelligence-service health.
