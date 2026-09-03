from datetime import datetime

from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction


VALID_SETTLEMENT_STATUSES = {
    "WON",
    "LOST",
    "VOID",
}


def get_all_paper_trades(db):
    return (
        db.query(PaperTrade)
        .order_by(PaperTrade.created_at.desc())
        .all()
    )


def paper_trade_exists(
    db,
    prediction_id,
    market,
    selection,
):
    return (
        db.query(PaperTrade)
        .filter(
            PaperTrade.prediction_id == prediction_id,
            PaperTrade.market == market,
            PaperTrade.selection == selection,
        )
        .first()
        is not None
    )


def open_trade_exists_for_match(
    db,
    prediction,
    market,
    selection,
):
    return (
        db.query(PaperTrade)
        .join(
            Prediction,
            PaperTrade.prediction_id == Prediction.id,
        )
        .filter(
            PaperTrade.status == "OPEN",
            PaperTrade.market == market,
            PaperTrade.selection == selection,
        )
        .filter(
            (
                (Prediction.player_a == prediction.player_a)
                & (Prediction.player_b == prediction.player_b)
            )
            |
            (
                (Prediction.player_a == prediction.player_b)
                & (Prediction.player_b == prediction.player_a)
            )
        )
        .first()
        is not None
    )


def get_portfolio_summary(
    db,
    starting_bankroll=5000.00,
):
    trades = db.query(PaperTrade).all()

    settled_trades = [
        trade
        for trade in trades
        if trade.status in VALID_SETTLEMENT_STATUSES
    ]

    total_profit_loss = round(
        sum(
            float(trade.profit_loss or 0)
            for trade in settled_trades
        ),
        2,
    )

    settled_stake = round(
        sum(
            float(trade.stake or 0)
            for trade in settled_trades
        ),
        2,
    )

    current_bankroll = round(
        float(starting_bankroll) + total_profit_loss,
        2,
    )

    if settled_stake > 0:
        roi = round(
            (total_profit_loss / settled_stake) * 100,
            2,
        )
    else:
        roi = 0.0

    profit_values = [
        float(trade.profit_loss or 0)
        for trade in settled_trades
    ]

    biggest_win = round(
        max(
            [
                value
                for value in profit_values
                if value > 0
            ],
            default=0.0,
        ),
        2,
    )

    biggest_loss = round(
        min(
            [
                value
                for value in profit_values
                if value < 0
            ],
            default=0.0,
        ),
        2,
    )

    return {
        "starting_bankroll": round(
            float(starting_bankroll),
            2,
        ),
        "current_bankroll": current_bankroll,
        "total_profit_loss": total_profit_loss,
        "portfolio_roi": roi,
        "settled_stake": settled_stake,
        "biggest_win": biggest_win,
        "biggest_loss": biggest_loss,
    }


def settle_paper_trade(
    db,
    trade_id,
    status,
):
    status = status.strip().upper()

    if status not in VALID_SETTLEMENT_STATUSES:
        raise ValueError(
            "Status must be WON, LOST or VOID"
        )

    trade = (
        db.query(PaperTrade)
        .filter(PaperTrade.id == trade_id)
        .first()
    )

    if trade is None:
        return None

    if trade.status != "OPEN":
        raise ValueError(
            "Only OPEN paper trades can be settled"
        )

    stake = float(trade.stake or 0)
    odds = float(trade.odds or 0)

    if status == "WON":
        profit_loss = stake * (odds - 1)

    elif status == "LOST":
        profit_loss = -stake

    else:
        profit_loss = 0

    trade.status = status
    trade.profit_loss = round(
        profit_loss,
        2,
    )
    trade.settled_at = datetime.utcnow()

    db.commit()
    db.refresh(trade)

    return trade


def _settle_trade_as_win_or_loss(
    trade,
    *,
    winning_selection,
):
    stake = float(trade.stake or 0)
    odds = float(trade.odds or 0)

    if trade.selection == winning_selection:
        trade.status = "WON"
        trade.profit_loss = round(
            stake * (odds - 1),
            2,
        )
    else:
        trade.status = "LOST"
        trade.profit_loss = round(
            -stake,
            2,
        )

    trade.settled_at = datetime.utcnow()


def settle_open_match_winner_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN Match Winner paper trades for one completed fixture.

    This function deliberately does not commit. Transaction ownership belongs
    to the caller so settlement can participate atomically in canonical result
    persistence.
    """
    from app.models.match import Match

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if (
        match is None
        or match.status != "completed"
        or not match.winner
    ):
        return []

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "Match Winner",
        )
        .all()
    )

    settled = []

    for trade in trades:
        if trade.selection not in {
            match.player_a,
            match.player_b,
        }:
            continue

        _settle_trade_as_win_or_loss(
            trade,
            winning_selection=match.winner,
        )
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_first_180_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN First 180 paper trades for one completed fixture.

    Missing First 180 result data is not inferred. Such trades remain OPEN.
    This function deliberately does not commit.
    """
    from app.models.match import Match

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if (
        match is None
        or match.status != "completed"
        or not match.first_180_player
        or match.first_180_player not in {
            match.player_a,
            match.player_b,
        }
    ):
        return []

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "First 180",
        )
        .all()
    )

    settled = []

    for trade in trades:
        if trade.selection not in {
            match.player_a,
            match.player_b,
        }:
            continue

        _settle_trade_as_win_or_loss(
            trade,
            winning_selection=match.first_180_player,
        )
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_handicap_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN Handicap paper trades for one completed fixture.

    Match.score is canonical player A legs-player B legs. Handicap selections
    are canonical fixture player names followed by a signed half-leg line.
    Missing or malformed result data is not inferred. Such trades remain OPEN.

    This function deliberately does not commit.
    """
    from app.models.match import Match

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if (
        match is None
        or match.status != "completed"
        or not match.score
        or match.player_a == match.player_b
        or match.winner not in {
            match.player_a,
            match.player_b,
        }
    ):
        return []

    score_parts = match.score.split("-")
    if (
        len(score_parts) != 2
        or not all(part.isdigit() for part in score_parts)
    ):
        return []

    player_a_legs = int(score_parts[0])
    player_b_legs = int(score_parts[1])

    if player_a_legs == player_b_legs:
        return []

    expected_winner = (
        match.player_a
        if player_a_legs > player_b_legs
        else match.player_b
    )
    if match.winner != expected_winner:
        return []

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "Handicap",
        )
        .all()
    )

    settled = []
    for trade in trades:
        if not trade.selection:
            continue

        selected_player = None
        handicap = None

        for player in (match.player_a, match.player_b):
            prefix = f"{player} "
            if not trade.selection.startswith(prefix):
                continue

            line_text = trade.selection[len(prefix):]
            if len(line_text) < 4 or line_text[0] not in {"+", "-"}:
                continue

            try:
                parsed_line = float(line_text)
            except ValueError:
                continue

            if (
                parsed_line == 0
                or abs(parsed_line) % 1 != 0.5
                or line_text != f"{parsed_line:+.1f}"
            ):
                continue

            selected_player = player
            handicap = parsed_line
            break

        if selected_player is None or handicap is None:
            continue

        if selected_player == match.player_a:
            selected_margin = player_a_legs - player_b_legs
        else:
            selected_margin = player_b_legs - player_a_legs

        adjusted_margin = selected_margin + handicap
        stake = float(trade.stake or 0)
        odds = float(trade.odds or 0)

        if adjusted_margin > 0:
            trade.status = "WON"
            trade.profit_loss = round(
                stake * (odds - 1),
                2,
            )
        elif adjusted_margin < 0:
            trade.status = "LOST"
            trade.profit_loss = round(
                -stake,
                2,
            )
        else:
            continue

        trade.settled_at = datetime.utcnow()
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_correct_score_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN Correct Score paper trades for one completed fixture.

    Match.score is canonical player A legs-player B legs. Missing or malformed
    result data is not inferred. Such trades remain OPEN.

    This function deliberately does not commit.
    """
    from app.models.match import Match

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if (
        match is None
        or match.status != "completed"
        or not match.score
        or match.player_a == match.player_b
        or match.winner not in {
            match.player_a,
            match.player_b,
        }
    ):
        return []

    score_parts = match.score.split("-")
    if (
        len(score_parts) != 2
        or not all(part.isdigit() for part in score_parts)
    ):
        return []

    player_a_legs = int(score_parts[0])
    player_b_legs = int(score_parts[1])

    if player_a_legs == player_b_legs:
        return []

    expected_winner = (
        match.player_a
        if player_a_legs > player_b_legs
        else match.player_b
    )
    if match.winner != expected_winner:
        return []

    winning_selection = f"{player_a_legs}-{player_b_legs}"

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "Correct Score",
        )
        .all()
    )

    settled = []
    for trade in trades:
        if not trade.selection:
            continue

        selection_parts = trade.selection.split("-")
        if (
            len(selection_parts) != 2
            or not all(part.isdigit() for part in selection_parts)
        ):
            continue

        selection_a = int(selection_parts[0])
        selection_b = int(selection_parts[1])

        if selection_a == selection_b:
            continue

        canonical_selection = f"{selection_a}-{selection_b}"
        if trade.selection != canonical_selection:
            continue

        _settle_trade_as_win_or_loss(
            trade,
            winning_selection=winning_selection,
        )
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_most_180s_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN Most 180s paper trades for one completed fixture.

    Settlement requires an exact canonical performance for both fixture
    participants and a non-null scores_180 value for each. Missing statistics
    are never inferred as zero. Equal counts settle the three-way market as
    Draw.

    This function deliberately does not commit.
    """
    from app.models.match import Match
    from app.models.player import Player
    from app.models.player_match_performance import PlayerMatchPerformance

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if match is None or match.status != "completed":
        return []

    if match.player_a == match.player_b:
        return []

    players = (
        db.query(Player)
        .filter(
            Player.name.in_(
                {
                    match.player_a,
                    match.player_b,
                }
            )
        )
        .all()
    )
    players_by_name = {
        player.name: player
        for player in players
    }

    if set(players_by_name) != {
        match.player_a,
        match.player_b,
    }:
        return []

    player_a = players_by_name[match.player_a]
    player_b = players_by_name[match.player_b]

    performances = (
        db.query(PlayerMatchPerformance)
        .filter(
            PlayerMatchPerformance.match_id == fixture_id,
            PlayerMatchPerformance.player_id.in_(
                {
                    player_a.id,
                    player_b.id,
                }
            ),
        )
        .all()
    )
    performances_by_player_id = {
        performance.player_id: performance
        for performance in performances
    }

    if set(performances_by_player_id) != {
        player_a.id,
        player_b.id,
    }:
        return []

    player_a_performance = performances_by_player_id[player_a.id]
    player_b_performance = performances_by_player_id[player_b.id]

    if (
        player_a_performance.scores_180 is None
        or player_b_performance.scores_180 is None
    ):
        return []

    if (
        player_a_performance.scores_180
        > player_b_performance.scores_180
    ):
        winning_selection = match.player_a
    elif (
        player_b_performance.scores_180
        > player_a_performance.scores_180
    ):
        winning_selection = match.player_b
    else:
        winning_selection = "Draw"

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "Most 180s",
        )
        .all()
    )

    valid_selections = {
        match.player_a,
        match.player_b,
        "Draw",
    }

    settled = []
    for trade in trades:
        if trade.selection not in valid_selections:
            continue

        _settle_trade_as_win_or_loss(
            trade,
            winning_selection=winning_selection,
        )
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle all currently supported OPEN markets for one exact fixture.

    Transaction ownership remains with the caller.
    """
    settled = []
    settled.extend(
        settle_open_match_winner_trades_for_fixture(
            db,
            fixture_id,
        )
    )
    settled.extend(
        settle_open_first_180_trades_for_fixture(
            db,
            fixture_id,
        )
    )
    settled.extend(
        settle_open_handicap_trades_for_fixture(
            db,
            fixture_id,
        )
    )
    settled.extend(
        settle_open_correct_score_trades_for_fixture(
            db,
            fixture_id,
        )
    )
    return settled
