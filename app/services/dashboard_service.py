from datetime import date
from app.models.player import Player
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.paper_trade import PaperTrade

from app.services.value_board_service import build_value_board
from app.services.data_quality_service import get_data_quality
from app.services.paper_trade_service import get_portfolio_summary


def _confidence_label(probability):
    if probability >= 75:
        return "High Confidence"
    elif probability >= 65:
        return "Good Confidence"
    elif probability >= 55:
        return "Moderate Confidence"
    else:
        return "Low Confidence"


def _star_rating(probability):
    if probability >= 80:
        return 5
    elif probability >= 72:
        return 4
    elif probability >= 64:
        return 3
    elif probability >= 56:
        return 2
    else:
        return 1


def build_dashboard_data(db):
    today = date.today()

    player_count = db.query(Player).count()
    match_count = db.query(Match).count()
    prediction_count = db.query(Prediction).count()

    today_fixtures = (
        db.query(Match)
        .filter(
            Match.date == today,
            Match.status == "scheduled",
        )
        .order_by(Match.id.asc())
        .all()
    )

    today_fixture_count = len(today_fixtures)

    completed_predictions = (
        db.query(Prediction)
        .filter(Prediction.winner_correct.isnot(None))
        .all()
    )

    if completed_predictions:
        correct = sum(
            1
            for prediction in completed_predictions
            if prediction.winner_correct
        )

        winner_accuracy = round(
            correct / len(completed_predictions) * 100,
            1,
        )
    else:
        winner_accuracy = 0

    results_awaiting = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date < today,
        )
        .order_by(Match.date.desc())
        .limit(10)
        .all()
    )

    recent_matches = (
        db.query(Match)
        .filter(Match.status == "completed")
        .order_by(
            Match.date.desc(),
            Match.id.desc(),
        )
        .limit(10)
        .all()
    )

    player_rows = (
        db.query(Player)
        .order_by(Player.elo.desc())
        .limit(10)
        .all()
    )

    top_players = []

    for player in player_rows:
        elo = player.elo or 0
        average = player.average or 0
        checkout = player.checkout or 0
        one80_rate = player.one80_rate or 0

        rating = round(
            (elo * 0.60)
            + (average * 2.0)
            + checkout
            + (one80_rate * 20),
            1,
        )

        top_players.append(
            {
                "name": player.name,
                "elo": round(elo, 1),
                "dartsedge_rating": rating,
            }
        )

    top_players.sort(
        key=lambda item: item["dartsedge_rating"],
        reverse=True,
    )

    best_bets = []

    try:
        value_rows = build_value_board(db)

        for row in value_rows:
            probability = round(
                row["probability"],
                1,
            )

            best_bets.append(
                {
                    "player_a": row["player_a"],
                    "player_b": row["player_b"],
                    "selection": row["selection"],
                    "probability": probability,
                    "confidence": _confidence_label(
                        probability
                    ),
                    "stars": _star_rating(
                        probability
                    ),
                }
            )

        best_bets.sort(
            key=lambda item: item["probability"],
            reverse=True,
        )

        best_bets = best_bets[:4]

    except Exception as error:
        print(
            f"Dashboard value board warning: {error}"
        )
        best_bets = []

    try:
        quality = get_data_quality(db)
        database_health = quality.get(
            "health_score",
            0,
        )

    except Exception as error:
        print(
            f"Dashboard health warning: {error}"
        )
        database_health = 0

    latest_predictions = (
        db.query(Prediction)
        .order_by(Prediction.created_at.desc())
        .limit(5)
        .all()
    )

    paper_trades = db.query(PaperTrade).all()

    paper_trade_count = len(paper_trades)

    open_paper_trades = sum(
        1
        for trade in paper_trades
        if trade.status == "OPEN"
    )

    won_paper_trades = sum(
        1
        for trade in paper_trades
        if trade.status == "WON"
    )

    lost_paper_trades = sum(
        1
        for trade in paper_trades
        if trade.status == "LOST"
    )

    void_paper_trades = sum(
        1
        for trade in paper_trades
        if trade.status == "VOID"
    )

    settled_paper_trades = (
        won_paper_trades
        + lost_paper_trades
        + void_paper_trades
    )

    total_paper_stake = round(
        sum(
            float(trade.stake or 0)
            for trade in paper_trades
        ),
        2,
    )

    average_paper_odds = (
        round(
            sum(
                float(trade.odds or 0)
                for trade in paper_trades
            )
            / paper_trade_count,
            2,
        )
        if paper_trade_count
        else 0
    )

    paper_strike_rate = (
        round(
            won_paper_trades
            / (
                won_paper_trades
                + lost_paper_trades
            )
            * 100,
            1,
        )
        if won_paper_trades + lost_paper_trades
        else 0
    )

    portfolio_summary = get_portfolio_summary(
        db,
        starting_bankroll=5000.00,
    )

    best_bet = best_bets[0] if best_bets else None

    return {
        "today": today,

        "player_count": player_count,
        "match_count": match_count,
        "today_fixture_count": today_fixture_count,
        "prediction_count": prediction_count,

        "winner_accuracy": winner_accuracy,

        "best_bets": best_bets,
        "best_bet": best_bet,

        "today_fixtures": today_fixtures,
        "results_awaiting": results_awaiting,
        "top_players": top_players,
        "recent_matches": recent_matches,

        "database_health": database_health,
        "latest_predictions": latest_predictions,

        "paper_trade_count": paper_trade_count,
        "open_paper_trades": open_paper_trades,
        "settled_paper_trades": settled_paper_trades,
        "won_paper_trades": won_paper_trades,
        "lost_paper_trades": lost_paper_trades,
        "void_paper_trades": void_paper_trades,
        "total_paper_stake": total_paper_stake,
        "average_paper_odds": average_paper_odds,
        "paper_strike_rate": paper_strike_rate,

        "starting_bankroll": portfolio_summary[
            "starting_bankroll"
        ],
        "current_bankroll": portfolio_summary[
            "current_bankroll"
        ],
        "total_profit_loss": portfolio_summary[
            "total_profit_loss"
        ],
        "portfolio_roi": portfolio_summary[
            "portfolio_roi"
        ],
        "settled_stake": portfolio_summary[
            "settled_stake"
        ],
        "biggest_win": portfolio_summary[
            "biggest_win"
        ],
        "biggest_loss": portfolio_summary[
            "biggest_loss"
        ],
    }