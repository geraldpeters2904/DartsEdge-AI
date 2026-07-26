# DartsEdge AI

DartsEdge AI is a FastAPI-based darts analytics and decision-support platform.

## v1.4.0 — Strategy Engine

The platform includes prediction intelligence, explainability, immutable audit records, model comparison, provider frameworks, expected-value analysis, automation, versioned strategies, guarded decision enforcement and settled strategy analytics.

## Run locally

```bash
cd ~/dartsedge-ai/backend
source venv/bin/activate
uvicorn app.main:app --reload
```

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Development dependencies are declared in `requirements-dev.txt`. CI runs the suite on Python 3.9 and 3.12.
