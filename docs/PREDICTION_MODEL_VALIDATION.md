# DartsEdge AI Prediction Model Validation

## Purpose

This document records the evidence, methodology, and decisions used to
develop and validate the DartsEdge AI transparent prediction models.

Its purpose is to prevent accidental reuse of holdout data, make model
changes reproducible, and provide an audit trail for future model
promotion decisions.

---

## Current Status

### Production / research baseline

**transparent-v3.3**

Transparent v3.3 remains the current production/research baseline.

### Registered challengers

- transparent-v3.4
- transparent-v3.5

Neither challenger should be treated as the production model until an
explicit promotion decision is made.

### Current leading challenger

**transparent-v3.5**

v3.5 has produced the strongest out-of-sample evidence so far.

---

## Validation Principles

Model development follows these rules:

1. Historical predictions must use pre-match information only.
2. The result of the match being predicted must not enter its snapshot.
3. Candidate models must be compared on identical historical matches.
4. Probability quality is evaluated using Brier score and log loss as
   well as winner accuracy.
5. Lower Brier score is better.
6. Lower log loss is better.
7. Higher winner accuracy is better.
8. Model changes should show improvement across multiple chronological
   windows rather than one favourable sample.
9. Holdout data used to make a model decision must not subsequently be
   described as untouched.
10. A separate reserve dataset should remain unseen until a deliberate
    final validation or promotion decision.

---

## Historical Data Split

Completed matches are ordered chronologically by:

1. Match date ascending
2. Match ID ascending

The principal development split is:

| Purpose | Offsets | Approximate dates |
|---|---:|---|
| Initial tuning | 0-4499 | 24 Oct 2022 - 11 Sep 2023 |
| Development confirmation | 4500-7499 | 11 Sep 2023 - 26 Apr 2024 |
| Secondary holdout | 7500-10499 | 26 Apr 2024 - 2 Dec 2024 |
| Final validation | 10500-13499 | 2 Dec 2024 - 19 Sep 2025 |
| Untouched reserve | 13500 onward | 19 Sep 2025 onward |

At the time v3.5 was formalised there were approximately 4,100 completed
matches in the untouched reserve, extending to 30 Aug 2026.

**Do not use the reserve beginning at offset 13500 for routine tuning or
exploratory model development.**

---

## transparent-v3.3

v3.3 removed the older `overall_strength` and `recent_form` contributions.

Effective weights:

| Feature | Weight |
|---|---:|
| overall_strength | 0.00 |
| recent_form | 0.00 |
| scoring_power | 0.15 |
| finishing_strength | 0.12 |
| maximums_strength | 0.08 |
| recent_win_rate | 0.10 |
| checkout_trend | 0.07 |
| deciding_strength | 0.06 |
| scoring_consistency | 0.05 |

Logistic strength: **3.0**

A 3,000-match baseline produced:

- Accuracy: 56.300%
- Brier: 0.247573
- Log loss: 0.689324

This established that the model had predictive signal, but also showed
that substantial reliability improvement remained possible.

---

## Feature Investigation

Feature ablation on the initial 3,000-match sample indicated:

### Strongest useful feature

`scoring_power`

Removing it reduced accuracy by approximately 1.13 percentage points and
worsened both Brier score and log loss.

### Useful / mildly useful features

- finishing_strength
- scoring_consistency
- deciding_strength

### Features showing aggregate negative contribution

- recent_win_rate
- checkout_trend
- maximums_strength

Ablation results were treated as diagnostic evidence rather than an
instruction to remove features automatically.

Each important change was subsequently tested chronologically.

---

## transparent-v3.4

v3.4 was created as a conservative challenger to v3.3.

Changes from v3.3:

| Feature | v3.3 | v3.4 |
|---|---:|---:|
| finishing_strength | 0.12 | 0.08 |
| maximums_strength | 0.08 | 0.00 |

All other feature weights and logistic mechanics remained unchanged.

Across the original tuning and validation windows, this combination
improved probability quality consistently, although winner accuracy was
mixed.

v3.4 was therefore registered as a challenger rather than promoted.

---

## Further v3.5 Investigation

### recent_win_rate

Reducing `recent_win_rate` from 0.10 to 0.00 improved Brier score and
log loss across the initial training window and both validation windows.

When combined with v3.4, removing the feature improved accuracy, Brier
score and log loss across all three initial windows relative to v3.4.

### checkout_trend

Reducing `checkout_trend` from 0.07 to 0.00 improved Brier score and log
loss across all three initial windows.

When combined with the other prospective v3.5 changes, accuracy improved
in two windows and fell only slightly in one.

### scoring_consistency

Testing removal of `scoring_consistency` produced only tiny early gains
and worsened the third validation window.

Decision:

**Retain scoring_consistency at 0.05.**

### deciding_strength

A lower value improved probability metrics when tested independently,
but when applied to the combined prospective v3.5 model it worsened
accuracy, Brier score and log loss.

Decision:

**Retain deciding_strength at 0.06.**

### logistic strength

Values around the existing 3.0 setting were tested.

The mathematical optimum on the training sample was approximately 3.1,
but the difference from 3.0 was negligible:

- Brier improvement: approximately 0.000002
- Log-loss improvement: approximately 0.000010

Changing this parameter would therefore represent unnecessary
fine-tuning.

Decision:

**Retain logistic strength at 3.0.**

---

## transparent-v3.5 Configuration

v3.5 inherits v3.4 and makes two additional changes.

Effective configuration:

| Feature | Weight |
|---|---:|
| overall_strength | 0.00 |
| recent_form | 0.00 |
| scoring_power | 0.15 |
| finishing_strength | 0.08 |
| maximums_strength | 0.00 |
| recent_win_rate | 0.00 |
| checkout_trend | 0.00 |
| deciding_strength | 0.06 |
| scoring_consistency | 0.05 |

Logistic strength: **3.0**

---

## Later Out-of-Sample Validation

After the v3.5 configuration had been selected, it was tested on three
consecutive later chronological windows that had not been used to choose
the v3.5 changes.

Each window contained 3,000 usable historical matches.

### Window 1 — Development Confirmation

Offsets: **4500-7499**

| Model | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| v3.3 | 58.400% | 0.244082 | 0.682443 |
| v3.4 | 58.967% | 0.242030 | 0.677298 |
| **v3.5** | **60.700%** | **0.239009** | **0.670949** |

v3.5 beat both v3.3 and v3.4 on all three metrics.

---

### Window 2 — Secondary Holdout

Offsets: **7500-10499**

| Model | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| v3.3 | 57.467% | 0.244355 | 0.682450 |
| v3.4 | 57.267% | 0.241606 | 0.676109 |
| **v3.5** | **58.800%** | **0.239269** | **0.671395** |

v3.5 again beat both v3.3 and v3.4 on all three metrics.

---

### Window 3 — Final Validation

Offsets: **10500-13499**

| Model | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| v3.3 | 57.367% | 0.243383 | 0.680571 |
| v3.4 | 57.900% | 0.240275 | 0.673458 |
| **v3.5** | **59.300%** | **0.238399** | **0.669641** |

v3.5 again beat both models on all three metrics.

---

## Combined Out-of-Sample Evidence

The three later windows provide **9,000 matches** of chronological
out-of-sample evidence.

v3.5 beat both v3.3 and v3.4 on:

- accuracy in all three windows
- Brier score in all three windows
- log loss in all three windows

Accuracy improvement versus v3.3:

- Window 1: +2.300 percentage points
- Window 2: +1.333 percentage points
- Window 3: +1.933 percentage points

Accuracy improvement versus v3.4:

- Window 1: +1.733 percentage points
- Window 2: +1.533 percentage points
- Window 3: +1.400 percentage points

This consistency is materially stronger evidence than improvement on a
single tuning window.

---

## Benchmark Laboratory Compatibility

After v3.4 and v3.5 were registered, the existing
`ModelPerformanceLaboratory` initially evaluated zero matches for those
models because its advanced-historical-snapshot version list stopped at
v3.3.

The laboratory was updated to recognise:

- transparent-v3.4
- transparent-v3.5

A five-match compatibility test then evaluated all five matches for all
three models with zero skips.

A subsequent 100-match benchmark at offset 4500 produced:

| Model | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| v3.3 | 62.0% | 0.228688 | 0.648534 |
| v3.4 | 64.0% | **0.226467** | **0.644975** |
| v3.5 | **68.0%** | 0.231170 | 0.654950 |

The small window demonstrates that the common benchmark path is
operational. It should not outweigh the much larger 9,000-match
out-of-sample evidence.

---

## Current Decision

**transparent-v3.5 is the leading challenger.**

Evidence is sufficiently strong to stop further feature tuning on the
data already examined.

However:

**v3.5 has not yet been promoted to the production/research default.**

Promotion should be an explicit decision with a defined rollback point.

---

## Untouched Reserve

The chronological reserve begins at:

**offset 13500**

Approximate date range at the time of v3.5 formalisation:

**19 Sep 2025 - 30 Aug 2026**

Approximately **4,100 completed matches** were available.

This reserve must remain untouched during ordinary model refinement.

It should only be opened for a deliberately defined final test, such as
a formal production-promotion decision or comparison against a future
external/simple benchmark.

---

## Future Reliability Work

Potential next stages include:

- benchmark against a simple Elo model
- benchmark against market probabilities when reliable bookmaker data
  becomes available
- calibration analysis
- rolling / blocked temporal validation
- recent-period weighting experiments on development data
- strength-of-schedule analysis
- competition / venue effects
- scoring, checkout and 180 feature improvements
- uncertainty and sample-size handling
- separation of probability estimation from betting-value decisions

Any future work must preserve a clean distinction between:

1. development data
2. validation data
3. genuinely untouched data

---

## Promotion Rule

No challenger should become the production model merely because it
performs better on one sample.

A promotion decision should consider:

- multiple chronological windows
- winner accuracy
- Brier score
- log loss
- calibration
- stability
- comparison with simple baselines
- operational compatibility
- rollback capability

As of this record, v3.5 has passed the multi-window accuracy and
probability-quality tests and is the strongest transparent-model
candidate, but production remains on v3.3 pending an explicit promotion
decision.
