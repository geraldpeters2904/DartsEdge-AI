from app.routes.provider_admin import router as provider_admin_router
from app.models.historical_import import HistoricalImportBatch, HistoricalImportItem, PlayerAlias
from app.routes.historical_import import router as historical_import_router
from app.models.canonical_data import RawIngestionRecord, ProviderEntityMapping, DataProvenance
from app.routes.canonical_data import router as canonical_data_router
from app.models.bet_slip_item import BetSlipItem
from app.routes.bet_slip import router as bet_slip_router
from app.routes.demo_data import router as demo_data_router
from app.routes.match_intelligence import router as match_intelligence_router
from app.routes.prediction_centre import router as prediction_centre_router
from app.models.feed_connector import FeedConnectorConfig, FeedSyncRun
from app.routes.feed_connectors import router as feed_connectors_router
from app.models.strategy_decision import StrategyDecision
from app.routes.strategy_analytics import router as strategy_analytics_router
from app.models.strategy_profile import StrategyProfile
from app.routes.strategies import router as strategies_router
from app.models.automation_job_run import AutomationJobRun
from app.routes.automation import router as automation_router
from app.routes.daily_briefing import router as daily_briefing_router
from app.routes.expected_value import router as expected_value_router
from app.routes.odds_providers import router as odds_providers_router
from app.routes.data_providers import router as data_providers_router
from app.routes.model_performance_lab import router as model_performance_lab_router
from app.models.prediction_audit import PredictionAudit
from app.models.prediction_audit_outcome import PredictionAuditOutcome
from app.routes.shadow_comparison import router as shadow_comparison_router
from app.routes.audit_trail import router as audit_trail_router
from app.routes.player_intelligence import router as player_intelligence_router
from app.routes.diagnostics import router as diagnostics_router
from app.version import APP_NAME, VERSION
from app.routes.ai_coach import router as ai_coach_router
from app.routes.portfolio_health import router as portfolio_health_router
from app.routes.settings import router as settings_router
from app.routes.mission_control import router as mission_control_router
from app.routes.opportunities import router as opportunities_router
from app.routes.new_paper_trade import router as new_paper_trade_router
from app.models.paper_trade import PaperTrade
from app.routes.paper_trades import router as paper_trades_router
from app.routes.collector import router as collector_router
from app.routes.warehouse_dashboard import router as warehouse_dashboard_router
from app.routes.warehouse_explorer import router as warehouse_explorer_router
from app.routes.historical_import_manager import router as historical_import_manager_router
from app.routes.import_wizard import router as import_wizard_router
from app.routes.modus_fixture_import import router as modus_fixture_import_router
from app.routes.modus_capture_manager import router as modus_capture_manager_router
from app.routes.capture_library import router as capture_library_router
from app.routes.capture_discovery import router as capture_discovery_router
from app.routes.capture_wizard import router as capture_wizard_router
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes.fixtures import router as fixtures_router
from app.db import SessionLocal, create_database
from app.models.player import Player
from app.routes.accuracy import router as accuracy_router
from app.routes.dashboard import router as dashboard_router
from app.routes.importer import router as importer_router
from app.routes.player_profile import router as player_profile_router
from app.routes.predict import router as predict_router
from app.routes.prediction_history import router as prediction_history_router
from app.routes.rankings import router as rankings_router
from app.routes.statistics import router as statistics_router
from app.routes.update_prediction import router as update_prediction_router
from app.services.form_service import weighted_expected_180s
from app.services.markets_service import one80_markets
from app.routes.players import router as players_router
from app.routes.value_board import router as value_board_router
from app.routes.data_quality import router as data_quality_router
from app.services.match_engine import (
    leg_win_probability,
    value_edge,
    win_probability,
)


app = FastAPI(title=APP_NAME, version=VERSION)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

create_database()
app.include_router(canonical_data_router)
app.include_router(historical_import_router)
app.include_router(bet_slip_router)
app.include_router(demo_data_router)
app.include_router(match_intelligence_router)
app.include_router(prediction_centre_router)
app.include_router(feed_connectors_router)
app.include_router(strategy_analytics_router)
app.include_router(strategies_router)
app.include_router(automation_router)
app.include_router(daily_briefing_router)
app.include_router(data_providers_router)
app.include_router(odds_providers_router)
app.include_router(expected_value_router)
app.include_router(audit_trail_router)
app.include_router(shadow_comparison_router)
app.include_router(model_performance_lab_router)
app.include_router(player_intelligence_router)
app.include_router(diagnostics_router)
app.include_router(paper_trades_router)
app.include_router(ai_coach_router)
app.include_router(mission_control_router)
app.include_router(opportunities_router)
app.include_router(portfolio_health_router)
app.include_router(dashboard_router)
app.include_router(update_prediction_router)
app.include_router(predict_router)
app.include_router(accuracy_router)
app.include_router(rankings_router)
app.include_router(player_profile_router)
app.include_router(statistics_router)
app.include_router(prediction_history_router)
app.include_router(importer_router)
app.include_router(fixtures_router)
app.include_router(players_router)
app.include_router(value_board_router)
app.include_router(data_quality_router)
app.include_router(new_paper_trade_router)
app.include_router(settings_router)
app.include_router(provider_admin_router)
app.include_router(collector_router)
app.include_router(warehouse_dashboard_router)
app.include_router(warehouse_explorer_router)
app.include_router(historical_import_manager_router)
app.include_router(import_wizard_router)
app.include_router(modus_fixture_import_router)
app.include_router(modus_capture_manager_router)
app.include_router(capture_library_router)
app.include_router(capture_discovery_router)
app.include_router(capture_wizard_router)


@app.get("/")
def home():
    return {"status": "DartsEdge AI running"}


@app.get("/match")
def match(player_a: str, player_b: str):
    db = SessionLocal()

    try:
        a = db.query(Player).filter(Player.name == player_a).first()
        b = db.query(Player).filter(Player.name == player_b).first()

        if not a or not b:
            return {"error": "Player not found"}

        elo_prob = win_probability(a.elo, b.elo)
        sim_prob = leg_win_probability(a, b)
        final_prob_a = (elo_prob * 0.6) + (sim_prob * 0.4)

        form_180_a = weighted_expected_180s(db, player_a)
        form_180_b = weighted_expected_180s(db, player_b)

        exp_180_a = form_180_a["expected"]
        exp_180_b = form_180_b["expected"]

        return {
            "player_a": player_a,
            "player_b": player_b,
            "win_prob_a": round(final_prob_a, 3),
            "win_prob_b": round(1 - final_prob_a, 3),
            "expected_180s_a": round(exp_180_a, 2),
            "expected_180s_b": round(exp_180_b, 2),
            "form_180_a": form_180_a,
            "form_180_b": form_180_b,
            "markets_180": one80_markets(exp_180_a, exp_180_b),
            "value_bet": value_edge(final_prob_a),
        }

    finally:
        db.close()
