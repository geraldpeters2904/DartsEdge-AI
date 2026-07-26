# DartsEdge AI Developer Guide — v1.2.0

## Setup

```bash
cd ~/dartsedge-ai/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## Intelligence architecture

- `PlayerIntelligenceService` creates component and weighted scores using versioned JSON profiles.
- Explainability converts intelligence output into stable structured and UI-ready explanations.
- Prediction Audit stores immutable snapshots identified by UUID.
- Outcome events are append-only and provide settlement/correction history.
- Shadow Comparison and Performance Lab consume settled audit evidence; they do not alter predictions.
- The legacy engine remains official. Intelligence is model version `Intelligence-0.1-shadow`.

## Data integrity rules

1. Never overwrite an original prediction audit snapshot.
2. Record result corrections as new events.
3. Exclude unsettled predictions from evaluation metrics.
4. Preserve profile name and version with every snapshot.
5. Do not promote a shadow model solely from a small sample.

## Release checks

1. Run the full test suite.
2. Open `/health`, `/diagnostics`, `/mission-control`, `/audit-trail`, `/shadow-comparison` and `/model-performance-lab`.
3. Verify `app/version.py`, `CHANGELOG.md`, `ROADMAP.md` and release notes.
4. Back up the SQLite database.
5. Commit on `develop`, merge to the stable branch, then create an annotated tag.
