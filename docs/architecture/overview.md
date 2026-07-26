# DartsEdge AI Architecture

## Backend

FastAPI

### Routes

- predict.py
- dashboard.py
- rankings.py
- accuracy.py
- statistics.py
- import.py
- update_prediction.py

---

## Services

- elo_service
- simulation_service
- markets_service
- dashboard_service
- accuracy_service
- explanation_service
- player_profile_service

---

## Models

- Player
- Match
- Prediction
- PlayerStats
- MatchPlayerStats

---

## Templates

base.html

Pages

- dashboard
- predict
- predict_v2
- rankings
- player_profile
- statistics
- accuracy

Components

- ai_panel
- player_comparison

---

## Database

SQLite

Tables

- players
- matches
- predictions
- player_stats
- match_player_stats