from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.fixture_service import (
    create_fixture,
    delete_fixture,
    duplicate_fixture,
    get_fixture_form_data,
    get_scheduled_fixtures,
    get_fixture,
    update_fixture,
)
from app.templates_config import templates


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


@router.post("/fixtures/delete/{fixture_id}")
def remove_fixture(fixture_id: int):
    db = SessionLocal()

    try:
        delete_fixture(db, fixture_id)

    finally:
        db.close()

    return RedirectResponse(
        "/fixtures",
        status_code=303,
    )
@router.post("/fixtures/duplicate/{fixture_id}")
def duplicate_fixture_route(fixture_id: int):
    db = SessionLocal()

    try:
        duplicate_fixture(db, fixture_id)

    finally:
        db.close()

    return RedirectResponse(
        "/fixtures",
        status_code=303,
    )
@router.get("/fixtures/edit/{fixture_id}")
def edit_fixture_page(
    request: Request,
    fixture_id: int,
):
    db = SessionLocal()

    try:
        fixture = get_fixture(db, fixture_id)
        form = get_fixture_form_data(db)

        if not fixture:
            return RedirectResponse(
                "/fixtures",
                status_code=303,
            )

        return templates.TemplateResponse(
            "fixture_edit.html",
            {
                "request": request,
                "fixture": fixture,
                "players": form["players"],
            },
        )

    finally:
        db.close()


@router.post("/fixtures/edit/{fixture_id}")
def save_fixture_changes(
    fixture_id: int,
    fixture_date: date = Form(...),
    tournament: str = Form(...),
    stage: str = Form(...),
    match_format: str = Form(...),
    player_a: str = Form(...),
    player_b: str = Form(...),
):
    db = SessionLocal()

    try:
        update_fixture(
            db,
            fixture_id,
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