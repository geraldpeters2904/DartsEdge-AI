from app.models.player import Player
from app.services.confidence_service import build_confidence_breakdown
from app.services.explanation_service import build_match_explanation
from app.services.first180_service import first_180_market
from app.services.head_to_head_service import get_head_to_head
from app.services.markets_service import one80_markets
from app.services.match_engine import leg_win_probability, win_probability
from app.services.match_intelligence_service import compare_players
from app.services.player_profile_service import get_player_profile
from app.services.recommendation_service import build_recommendation
from app.services.simulation_service import simulate_match


def build_prediction(db, player_a, player_b):
    profile_a = get_player_profile(db, player_a)
    profile_b = get_player_profile(db, player_b)

    if not profile_a or not profile_b:
        return None

    player_a_record = (
        db.query(Player)
        .filter(Player.name == player_a)
        .first()
    )

    player_b_record = (
        db.query(Player)
        .filter(Player.name == player_b)
        .first()
    )

    if not player_a_record or not player_b_record:
        return None

    intelligence = compare_players(
        profile_a,
        profile_b,
    )

    elo_prob = win_probability(
        profile_a["elo"],
        profile_b["elo"],
    )

    leg_prob = leg_win_probability(
        player_a_record,
        player_b_record,
    )

    final_prob_a = (elo_prob * 0.6) + (leg_prob * 0.4)

    exp_180_a = profile_a["form"]["expected"]
    exp_180_b = profile_b["form"]["expected"]

    markets_180 = one80_markets(
        exp_180_a,
        exp_180_b,
    )

    first_180 = first_180_market(
        db,
        player_a,
        player_b,
    )

    head_to_head = get_head_to_head(
        db,
        player_a,
        player_b,
    )

    simulation = simulate_match(
        profile_a,
        profile_b,
    )

    confidence_breakdown = build_confidence_breakdown(
        profile_a,
        profile_b,
        simulation,
        max(final_prob_a, 1 - final_prob_a),
        head_to_head,
    )

    explanation = build_match_explanation(
        profile_a,
        profile_b,
        simulation,
    )

    result = {
        "player_a": player_a,
        "player_b": player_b,
        "win_prob_a": round(final_prob_a, 3),
        "win_prob_b": round(1 - final_prob_a, 3),
        "expected_180s_a": round(exp_180_a, 2),
        "expected_180s_b": round(exp_180_b, 2),
        "profile_a": profile_a,
        "profile_b": profile_b,
        "markets_180": markets_180,
        "first_180": first_180,
        "simulation": simulation,
        "intelligence": intelligence,
        "explanation": explanation,
        "confidence": confidence_breakdown,
        "confidence_breakdown": confidence_breakdown,
        "head_to_head": head_to_head,
    }

    result["recommendation"] = build_recommendation(result)

    return result