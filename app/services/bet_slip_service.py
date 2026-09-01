from __future__ import annotations

from app.models.bet_slip_item import BetSlipItem
from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction


def list_bet_slip_items(db):
    return (
        db.query(BetSlipItem, Match)
        .join(Match, BetSlipItem.fixture_id == Match.id)
        .order_by(BetSlipItem.created_at.desc())
        .all()
    )


def add_bet_slip_item(
    db,
    *,
    fixture_id: int,
    market: str,
    selection: str,
    bookmaker: str,
    odds: float,
    stake: float,
    model_probability: float | None = None,
    expected_value: float | None = None,
    kelly_stake: float | None = None,
    strategy_name: str | None = None,
):
    fixture = db.query(Match).filter(Match.id == fixture_id).first()
    if fixture is None:
        raise ValueError("Fixture not found")
    if selection not in {fixture.player_a, fixture.player_b}:
        raise ValueError("Selection must be one of the fixture players")
    if odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.00")
    if stake <= 0:
        raise ValueError("Stake must be greater than zero")

    existing = (
        db.query(BetSlipItem)
        .filter(
            BetSlipItem.fixture_id == fixture_id,
            BetSlipItem.market == market,
            BetSlipItem.selection == selection,
        )
        .first()
    )
    if existing:
        existing.bookmaker = bookmaker
        existing.odds = odds
        existing.stake = stake
        existing.model_probability = model_probability
        existing.expected_value = expected_value
        existing.kelly_stake = kelly_stake
        existing.strategy_name = strategy_name
        db.commit()
        db.refresh(existing)
        return existing, False

    item = BetSlipItem(
        fixture_id=fixture_id,
        market=market.strip() or "Match Winner",
        selection=selection,
        bookmaker=bookmaker.strip() or "Best available",
        odds=odds,
        stake=stake,
        model_probability=model_probability,
        expected_value=expected_value,
        kelly_stake=kelly_stake,
        strategy_name=strategy_name,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, True


def update_bet_slip_stake(
    db,
    item_id: int,
    stake: float,
) -> BetSlipItem:
    if stake <= 0:
        raise ValueError("Stake must be greater than zero")

    item = (
        db.query(BetSlipItem)
        .filter(BetSlipItem.id == item_id)
        .first()
    )
    if item is None:
        raise ValueError("Bet slip item not found")

    item.stake = stake
    db.commit()
    db.refresh(item)
    return item


def remove_bet_slip_item(db, item_id: int) -> bool:
    item = db.query(BetSlipItem).filter(BetSlipItem.id == item_id).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def _prediction_for_fixture(db, fixture: Match, item: BetSlipItem) -> Prediction:
    prediction = (
        db.query(Prediction)
        .filter(Prediction.player_a == fixture.player_a, Prediction.player_b == fixture.player_b)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    if prediction:
        return prediction

    probability = float(item.model_probability or 50.0)
    if probability > 1:
        probability /= 100.0
    probability = min(max(probability, 0.0), 1.0)
    prediction = Prediction(
        player_a=fixture.player_a,
        player_b=fixture.player_b,
        predicted_winner=item.selection,
        win_prob_a=probability if item.selection == fixture.player_a else 1 - probability,
        win_prob_b=probability if item.selection == fixture.player_b else 1 - probability,
        confidence=int(round(abs(probability - 0.5) * 20)),
        rating_a=0,
        rating_b=0,
        first_180_a=0,
        first_180_b=0,
    )
    db.add(prediction)
    db.flush()
    return prediction


def confirm_as_paper_trade(db, item_id: int) -> PaperTrade:
    row = (
        db.query(BetSlipItem, Match)
        .join(Match, BetSlipItem.fixture_id == Match.id)
        .filter(BetSlipItem.id == item_id)
        .first()
    )
    if row is None:
        raise ValueError("Bet slip item not found")
    item, fixture = row
    prediction = _prediction_for_fixture(db, fixture, item)
    trade = PaperTrade(
        prediction_id=prediction.id,
        market=item.market,
        selection=item.selection,
        bookmaker=item.bookmaker,
        odds=item.odds,
        stake=item.stake,
        status="OPEN",
    )
    db.add(trade)
    db.delete(item)
    db.commit()
    db.refresh(trade)
    return trade


def bet_slip_summary(db):
    items = db.query(BetSlipItem).all()
    return {
        "count": len(items),
        "total_stake": round(sum(float(item.stake or 0) for item in items), 2),
        "average_odds": round(sum(float(item.odds or 0) for item in items) / len(items), 2) if items else 0.0,
    }
