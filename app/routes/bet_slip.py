from fastapi import APIRouter, Form, HTTPException, Request
from app.services.recommendation_signing_service import verify_recommendation
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.bet_slip_service import (
    add_bet_slip_item,
    bet_slip_summary,
    confirm_as_paper_trade,
    list_bet_slip_items,
    remove_bet_slip_item,
    update_bet_slip_stake,
)
from app.templates_config import templates

router = APIRouter()


@router.get("/bet-slip")
def bet_slip_page(request: Request, message: str = ""):
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            request,
            "bet_slip.html",
            {
                "items": list_bet_slip_items(db),
                "summary": bet_slip_summary(db),
                "message": message,
            },
        )
    finally:
        db.close()


@router.post("/bet-slip/add")
def add_to_bet_slip(
    fixture_id: int = Form(...),
    market: str = Form("Match Winner"),
    selection: str = Form(...),
    bookmaker: str = Form("Best available"),
    odds: float = Form(...),
    stake: float = Form(...),
    model_probability: float = Form(0),
    expected_value: float = Form(0),
    kelly_stake: float = Form(0),
    strategy_name: str = Form(""),
    recommendation_token: str = Form(""),
):
    db = SessionLocal()
    try:
        authorised_row = None
        payload = verify_recommendation(recommendation_token) if recommendation_token else None

        if payload is not None:
            from app.services.value_board_service import build_value_board

            if (
                payload["fixture_id"] == fixture_id
                and payload["market"] == market
                and payload["selection"] == selection
                and abs(float(payload["odds"]) - odds) < 0.000001
                and abs(float(payload["effective_stake"]) - stake) < 0.000001
            ):
                for row in build_value_board(db):
                    decision = row.get("decision_engine")
                    if (
                        row.get("fixture_id") == fixture_id
                        and row.get("market") == market
                        and row.get("selection") == selection
                        and abs(float(row.get("market_odds") or 0) - odds) < 0.000001
                        and abs(float(row.get("effective_stake") or 0) - stake) < 0.000001
                        and stake > 0
                        and decision is not None
                        and decision.qualifies is True
                    ):
                        authorised_row = row
                        break

        if authorised_row is not None:
            bookmaker = str(authorised_row.get("bookmaker") or "Best available")
            model_probability = float(authorised_row.get("probability") or 0)
            expected_value = float(authorised_row.get("expected_value_percent") or 0)
            kelly_stake = float(authorised_row.get("kelly_stake") or 0)
            strategy_name = "Daily Value Board"

        item, created = add_bet_slip_item(
            db,
            fixture_id=fixture_id,
            market=market,
            selection=selection,
            bookmaker=bookmaker,
            odds=odds,
            stake=stake,
            model_probability=model_probability,
            expected_value=expected_value,
            kelly_stake=kelly_stake,
            strategy_name=strategy_name,
        )
        if authorised_row is not None:
            item.stake_source = "authorised"
            db.commit()

        message = "Selection added to bet slip" if created else "Bet slip selection updated"
        return RedirectResponse(f"/bet-slip?message={message}", status_code=303)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        db.close()


@router.post("/bet-slip/{item_id}/stake")
def update_stake(
    item_id: int,
    stake: float = Form(...),
):
    db = SessionLocal()
    try:
        update_bet_slip_stake(
            db,
            item_id,
            stake,
        )
        return RedirectResponse(
            "/bet-slip?message=Stake updated",
            status_code=303,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    finally:
        db.close()


@router.post("/bet-slip/{item_id}/remove")
def remove_from_bet_slip(item_id: int):
    db = SessionLocal()
    try:
        if not remove_bet_slip_item(db, item_id):
            raise HTTPException(status_code=404, detail="Bet slip item not found")
        return RedirectResponse("/bet-slip?message=Selection removed", status_code=303)
    finally:
        db.close()


@router.post("/bet-slip/{item_id}/paper")
def save_as_paper_trade(item_id: int):
    db = SessionLocal()
    try:
        trade = confirm_as_paper_trade(db, item_id)
        return RedirectResponse(
            f"/paper-trades?saved=1&trade_id={trade.id}",
            status_code=303,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        db.close()


@router.get("/api/bet-slip")
def bet_slip_api():
    db = SessionLocal()
    try:
        rows = list_bet_slip_items(db)
        return {
            "summary": bet_slip_summary(db),
            "items": [
                {
                    "id": item.id,
                    "fixture_id": fixture.id,
                    "match": f"{fixture.player_a} v {fixture.player_b}",
                    "market": item.market,
                    "selection": item.selection,
                    "odds": item.odds,
                    "stake": item.stake,
                    "expected_value": item.expected_value,
                    "strategy": item.strategy_name,
                }
                for item, fixture in rows
            ],
        }
    finally:
        db.close()
