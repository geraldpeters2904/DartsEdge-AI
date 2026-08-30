# DartsEdge AI User Guide — Operational v1

DartsEdge AI is a darts prediction, value-analysis and decision-support application.

Operational v1 combines automated background monitoring with prediction analysis, bookmaker value assessment, strategy management, audit history and model-performance monitoring.

This guide describes the normal operating workflow and explains the main warnings and system states.

---

## 1. Normal daily workflow

A typical DartsEdge AI session should follow this sequence:

1. Open **Mission Control** for the overall operational picture.

2. Check **Daily Briefing** for the current day's information and priorities.

3. Check **Fixtures** to confirm that upcoming matches are available.

4. Review **Opportunities** for model-generated opportunities.

5. Use **Prediction Centre** when you want detailed analysis of a particular matchup.

6. Use **Value Scanner** and **Expected Value** when bookmaker prices are available.

7. Review **Portfolio Health** before acting on betting opportunities.

8. Use **AI Coach** and **Strategies** for decision support and strategy context.

9. Use **Diagnostics** if anything appears missing, delayed or unhealthy.

10. Review **Audit Trail**, **Shadow Comparison**, **Performance Lab** and **Accuracy** as results accumulate.

The system may legitimately have no opportunities when future fixtures or bookmaker prices are unavailable. No opportunity is preferable to manufacturing a weak signal.

---

## 2. Mission Control

**Mission Control** is the main operational overview.

Use it to assess:

- available opportunities;
- portfolio and exposure state;
- alerts;
- AI Coach actions;
- operational readiness.

Mission Control should normally be the first page checked when opening DartsEdge AI.

A lack of opportunities does not automatically indicate a fault. Check the fixture and acquisition states before investigating further.

---

## 3. Automatic background monitoring

Operational v1 automatically starts four background monitors when the application starts.

### Forward Schedule Monitor

Checks forward fixture availability and helps determine whether official future fixtures are available for processing.

### Live Edge Monitor

Refreshes the live opportunity pipeline and associated opportunity state.

### Model Trust Monitor

Periodically evaluates model reliability and reports:

- trust score;
- trust grade;
- sample size;
- monitor health.

Model Trust is a reliability indicator, not a guarantee that an individual prediction will be correct.

### Sparse Consensus Risk Monitor

Checks whether predictions are being supported by sufficiently broad underlying evidence.

An elevated or high sparse-consensus warning is a **model-quality warning**. It does not necessarily mean that the application itself is unhealthy.

All four monitors are started automatically through the application lifecycle. They do not need to be started manually from the Automation page.

---

## 4. Understanding WAITING states

DartsEdge AI distinguishes between an operational failure and a legitimate lack of source data.

For example:

**WAITING_FOR_FIXTURES**

means that the system is operational but there are currently no suitable published future fixtures for the acquisition or opportunity pipeline to process.

This is not the same as an error.

Similarly, an odds pipeline may wait when there are no relevant fixtures requiring bookmaker prices.

Do not attempt to repair the application simply because a pipeline is waiting.

Check **Diagnostics** to distinguish:

- healthy and active;
- healthy but waiting;
- degraded;
- failed.

---

## 5. Fixtures

Use **Fixtures** to inspect the match schedule known to DartsEdge AI.

Fixture data is fundamental to the automated pipeline.

Future fixtures can feed:

- prediction generation;
- opportunity detection;
- bookmaker-price acquisition;
- expected-value analysis;
- strategy processing.

Historical completed fixtures are also important for model development and performance measurement.

DartsEdge AI deliberately protects historical integrity. Existing completed records should not be manually rewritten simply to make the dataset appear complete.

---

## 6. Prediction Centre

Use **Prediction Centre** to compare two players and generate the official prediction.

A prediction should be interpreted as an estimated probability, not as a recommendation to place a bet.

For each prediction, consider:

- predicted winner;
- probability;
- prediction confidence;
- explanation coverage;
- Player Intelligence factors;
- model/profile information;
- available bookmaker price.

Expand **Why this prediction?** to inspect the evidence supporting the prediction.

---

## 7. Prediction probability versus betting value

This distinction is fundamental to DartsEdge AI.

A player can be highly likely to win but still represent a poor bet if the bookmaker price is too short.

Likewise, a lower-probability outcome can potentially represent value if the offered price is sufficiently greater than the model's estimated fair price.

Therefore:

**Prediction strength is not the same as betting value.**

The normal decision sequence is:

**Model probability → bookmaker odds → implied probability → expected value → risk assessment → decision**

Do not treat an opportunity as confirmed betting value until bookmaker odds have been considered.

---

## 8. Value Scanner

Use **Value Scanner** to identify situations where the model probability and bookmaker price may create positive expected value.

A value signal should still be considered alongside:

- model trust;
- data coverage;
- sparse-consensus risk;
- market quality;
- portfolio exposure;
- strategy rules.

The objective is not simply to identify likely winners. It is to identify situations where the available price may be favourable relative to the estimated probability.

---

## 9. Expected Value

**Expected Value** provides the mathematical link between prediction probability and betting price.

Positive expected value indicates that the model believes the offered price is favourable over repeated comparable decisions.

It does not mean that the individual bet will win.

Short-term results can differ substantially from expected long-term performance.

---

## 10. Player Intelligence

Player Intelligence provides additional information used to understand predictions.

The initial profiles include:

- Default;
- Elo Heavy;
- Form Heavy;
- Experimental.

Enabled profile weights must total 100%.

Neutral factors indicate missing or not-yet-integrated data. They are shown honestly rather than being presented as evidence.

Player Intelligence and alternative profiles should be evaluated through controlled comparison rather than assumed to outperform the official model.

---

## 11. Explainability

DartsEdge AI reports two different confidence concepts.

### Prediction confidence

Describes the official model's certainty about the predicted outcome.

### Explanation confidence

Describes how complete the supporting factor data is.

These are deliberately separate.

A prediction can have relatively high prediction confidence while still having limited explanation coverage.

---

## 12. Strategies

Use **Strategies** to manage the decision rules applied to opportunities.

Use **Strategy Analytics** to evaluate how strategies perform rather than judging them from a small number of individual wins or losses.

Strategy evaluation should consider a meaningful sample and should remain separate from changes to the underlying prediction model.

---

## 13. Portfolio Health

**Portfolio Health** reports bankroll and betting-risk information including exposure and concentration.

A positive expected-value opportunity can still be inappropriate if taking it would create excessive portfolio risk.

Portfolio controls therefore sit after prediction and value assessment in the decision process.

---

## 14. AI Coach

**AI Coach** prioritises actions using available opportunity and portfolio information.

Treat AI Coach as decision support rather than an instruction to place a bet.

Its recommendations remain dependent on the quality and availability of the underlying fixture, prediction, odds and portfolio data.

---

## 15. Automation page

The **Automation** page is currently intentionally configured in **Manual mode**.

Jobs displayed there run only when **Run now** is selected.

The page provides:

- registered jobs;
- current running state;
- previous run status;
- duration;
- records processed;
- job history;
- failure details.

This manual job system is separate from the four automatic background monitors described earlier.

Do not assume that a job shown on the Automation page is scheduled automatically.

---

## 16. Audit Trail

Every audited prediction receives an immutable UUID and stores information including:

- model/profile versions;
- probabilities;
- inputs;
- explanation snapshot.

The original prediction snapshot is never overwritten.

This makes it possible to evaluate what the system genuinely predicted at the time rather than reconstructing predictions retrospectively.

---

## 17. Shadow Comparison

Use **Shadow Comparison** to settle audited predictions using the actual winner.

Corrections create new events rather than altering the original prediction.

Metrics exclude unsettled records.

Shadow comparison is important when evaluating alternative models or profiles without allowing experimental changes to contaminate the official prediction history.

---

## 18. Performance Lab

**Performance Lab** evaluates prediction performance using measures including:

- accuracy;
- Brier score;
- calibration;
- profile performance;
- tournament performance;
- confidence bands;
- recent drift.

Performance should be judged over meaningful samples rather than isolated results.

Very small samples can produce misleading conclusions.

---

## 19. Rankings, Statistics and Prediction History

**Rankings** provides player-ranking information used for analysis.

**Statistics** provides broader statistical information about the stored dataset.

**Prediction History** provides access to previous predictions and their outcomes.

These pages are useful when investigating why a prediction or model-performance result looks unusual.

---

## 20. Data Providers and Odds Providers

**Data Providers** shows the state of configured match-data sources.

**Odds Providers** shows the state of bookmaker/price acquisition.

These are separate data dependencies.

It is therefore possible for fixture acquisition to be healthy while odds acquisition is waiting, particularly when no relevant future fixtures are currently available.

---

## 21. Data Quality

Use **Data Quality** when assessing whether stored information is sufficiently complete and reliable for analysis.

Data quality is particularly important for historical model training and validation.

Missing information should not automatically be replaced with assumed values.

Historical corrections should use a controlled, source-backed process.

---

## 22. Diagnostics

**Diagnostics** is the primary operational troubleshooting page.

It should be checked before attempting repairs.

Operational v1 monitors:

- application health;
- database connectivity;
- prediction services;
- intelligence services;
- acquisition readiness;
- fixture hygiene;
- opportunity pipeline readiness;
- Forward Schedule Monitor;
- Live Edge Monitor;
- Model Trust Monitor;
- Sparse Consensus Risk Monitor.

A healthy monitor should normally show:

- running;
- recent activity;
- no unresolved error;
- not stale.

Overall system health may become **degraded** when a required monitor is stopped, stale or unhealthy.

---

## 23. Model Trust warnings

Model Trust measures evidence about the reliability of the prediction system.

The trust score should be interpreted alongside its:

- grade;
- sample size;
- calibration evidence;
- recent performance.

Do not interpret the score as the probability that the next prediction will be correct.

Model Trust should improve or deteriorate based on measured evidence rather than subjective confidence in the model.

---

## 24. Sparse-consensus warnings

Sparse-consensus monitoring identifies situations where model decisions may rely on a relatively small or concentrated body of supporting evidence.

Possible elevated/high warnings are therefore important for prediction reliability.

However:

**A sparse-consensus warning is not automatically an application failure.**

If Diagnostics reports the monitor itself as healthy but its risk state as elevated or high, the application is operating correctly and reporting a model-quality concern.

That concern should feed model-reliability work rather than operational repair.

---

## 25. What to do when something looks wrong

Use this order:

1. Open **Diagnostics**.

2. Check the overall health state.

3. Determine whether the affected component is **failed**, **degraded**, or merely **waiting**.

4. Check fixture acquisition if opportunities are absent.

5. Check odds acquisition if fixtures exist but value information is unavailable.

6. Check the four background monitor states.

7. Review the relevant error or status message before restarting anything.

Avoid repeatedly restarting the application when the system is simply waiting for external data.

---

## 26. Operational v1 safety principles

DartsEdge AI follows several important operating principles:

- Do not manufacture missing data.
- Do not confuse missing opportunities with system failure.
- Do not confuse prediction confidence with betting value.
- Do not treat positive expected value as a guaranteed win.
- Preserve historical prediction snapshots.
- Preserve historical result integrity.
- Keep experimental models separate from the official model until validated.
- Prefer measured performance over subjective impressions.
- Treat model-quality warnings separately from infrastructure failures.
- Investigate Diagnostics before making operational changes.

---

## 27. Current Operational v1 status

The Operational v1 runtime has been verified through a genuine cold application restart.

The verified lifecycle includes automatic startup of:

- Forward Schedule Monitor;
- Live Edge Monitor;
- Model Trust Monitor;
- Sparse Consensus Risk Monitor.

The system has demonstrated that these monitors restart with the application and complete their first operational cycles successfully.

The health system also correctly distinguishes an absence of published fixtures from an application failure.

This establishes the Operational v1 runtime baseline from which prediction reliability can now be improved systematically.
