from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.live_opportunity_centre_service import (
    build_live_opportunity_centre,
)
from app.services.live_opportunity_pipeline_readiness_service import (
    build_live_opportunity_pipeline_readiness,
)
from app.services.mobile_access_service import (
    COOKIE_NAME,
    mobile_access_configured,
    mobile_session_token,
    valid_mobile_session,
    validate_mobile_credentials,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/mobile-login")
def mobile_login_page(
    request: Request,
):
    return templates.TemplateResponse(
        "mobile_login.html",
        {
            "request": request,
            "configured": (
                mobile_access_configured()
            ),
            "error": None,
        },
    )


@router.post("/mobile-login")
async def mobile_login_submit(
    request: Request,
):
    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="replace",
    )

    values = parse_qs(
        body,
        keep_blank_values=True,
    )

    username = (
        values.get(
            "username",
            [""],
        )[0]
    )

    password = (
        values.get(
            "password",
            [""],
        )[0]
    )

    if not mobile_access_configured():
        return templates.TemplateResponse(
            "mobile_login.html",
            {
                "request": request,
                "configured": False,
                "error": (
                    "Mobile access credentials "
                    "are not configured."
                ),
            },
            status_code=503,
        )

    if not validate_mobile_credentials(
        username=username,
        password=password,
    ):
        return templates.TemplateResponse(
            "mobile_login.html",
            {
                "request": request,
                "configured": True,
                "error": (
                    "Incorrect username or password."
                ),
            },
            status_code=401,
        )

    response = RedirectResponse(
        url="/mobile-opportunities",
        status_code=303,
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=(
            mobile_session_token()
            or ""
        ),
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=60 * 60 * 12,
        path="/",
    )

    return response


@router.get("/mobile-logout")
def mobile_logout():
    response = RedirectResponse(
        url="/mobile-login",
        status_code=303,
    )

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )

    return response


@router.get("/mobile-opportunities")
def mobile_opportunities_page(
    request: Request,
):
    if not valid_mobile_session(
        request.cookies.get(
            COOKIE_NAME
        )
    ):
        return RedirectResponse(
            url="/mobile-login",
            status_code=303,
        )

    db = SessionLocal()

    try:
        payload = build_live_opportunity_centre(
            db,
            limit=30,
            persist=True,
        )

        readiness = (
            build_live_opportunity_pipeline_readiness(
                db,
                limit=30,
            )
        )

        return templates.TemplateResponse(
            "mobile_opportunities.html",
            {
                "request": request,
                **payload,
                "readiness": readiness,
            },
        )

    finally:
        db.close()
