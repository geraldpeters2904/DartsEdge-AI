# Developer Guide

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

## Release checks
1. Run the full test suite.
2. Open `/health`, `/diagnostics`, `/mission-control` and `/dashboard`.
3. Update `app/version.py`, `CHANGELOG.md` and release notes.
4. Commit and create an annotated Git tag.
