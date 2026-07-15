from datetime import date
from app.templates_config import templates
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from app.db import SessionLocal
from app.services.fixture_service import (
    create_fixture,
    get_fixture_form_data,
    get_scheduled_fixtures,
)

router = APIRouter()

@router.get("/fixtures")
def fixtures_page(request: Request):

    db = SessionLocal()

    try:

        form = get_fixture_form_data(db)

        fixtures = get_scheduled_fixtures(db)

        return templates.TemplateResponse(
            "fixtures.html",
            {
                "request": request,
                "players": form["players"],
                "today": form["today"],
                "fixtures": fixtures,
            },
        )

    finally:
        db.close()


@router.post("/fixtures/add")
def add_fixture(
    fixture_date: date = Form(...),
    tournament: str = Form(...),
    stage: str = Form(...),
    match_format: str = Form(...),
    player_a: str = Form(...),
    player_b: str = Form(...),
):

    db = SessionLocal()

    try:

        create_fixture(
            db,
            fixture_date,
            tournament,
            stage,
            match_format,
            player_a,
            player_b,
        )

    finally:
        db.close()

    return RedirectResponse(
        "/fixtures",
        status_code=303,
    )