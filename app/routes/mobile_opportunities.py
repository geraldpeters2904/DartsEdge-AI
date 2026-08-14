from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import (
    RedirectResponse,
    Response,
)

from app.db import SessionLocal
from app.services.live_opportunity_centre_service import (
    build_live_opportunity_centre,
)
from app.services.live_opportunity_pipeline_readiness_service import (
    build_live_opportunity_pipeline_readiness,
)
from app.services.mobile_access_service import (
    COOKIE_NAME,
    consume_mobile_pairing_token,
    mobile_access_configured,
    mobile_session_token,
    valid_mobile_session,
    validate_mobile_credentials,
)
from app.services.mobile_pairing_display_service import (
    build_mobile_pairing_display,
)
from app.services.trusted_mobile_device_service import (
    TRUSTED_DEVICE_COOKIE_NAME,
    TRUSTED_DEVICE_DAYS,
    create_trusted_device,
    revoke_trusted_device,
    valid_trusted_device,
)
from app.templates_config import templates


router = APIRouter()

_LOCAL_CLIENTS = {
    "127.0.0.1",
    "::1",
}


def _set_mobile_session_cookie(
    response,
):
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


def _set_trusted_device_cookie(
    response,
):
    token = create_trusted_device()

    response.set_cookie(
        key=TRUSTED_DEVICE_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=(
            TRUSTED_DEVICE_DAYS
            * 24
            * 60
            * 60
        ),
        path="/",
    )

    return response


def _request_has_mobile_access(
    request: Request,
) -> bool:
    if valid_trusted_device(
        request.cookies.get(
            TRUSTED_DEVICE_COOKIE_NAME
        )
    ):
        return True

    return valid_mobile_session(
        request.cookies.get(
            COOKIE_NAME
        )
    )


@router.get("/mobile-pairing")
def mobile_pairing_page(
    request: Request,
):
    client_host = (
        request.client.host
        if request.client is not None
        else ""
    )

    if client_host not in _LOCAL_CLIENTS:
        return Response(
            content=(
                "Mobile pairing can only be "
                "generated on the DartsEdge Mac."
            ),
            status_code=403,
            media_type="text/plain",
        )

    if not mobile_access_configured():
        return Response(
            content=(
                "Mobile access credentials "
                "are not configured."
            ),
            status_code=503,
            media_type="text/plain",
        )

    try:
        pairing = (
            build_mobile_pairing_display()
        )
    except RuntimeError as exc:
        return Response(
            content=str(exc),
            status_code=503,
            media_type="text/plain",
        )

    response = templates.TemplateResponse(
        "mobile_pairing.html",
        {
            "request": request,
            "pairing": pairing,
        },
    )

    response.headers[
        "Cache-Control"
    ] = (
        "no-store, no-cache, "
        "must-revalidate"
    )

    return response


@router.get("/mobile-pair/{token}")
def mobile_pair_preview(
    request: Request,
    token: str,
):
    if not mobile_access_configured():
        return RedirectResponse(
            url="/mobile-login",
            status_code=303,
        )

    return templates.TemplateResponse(
        "mobile_pair_confirm.html",
        {
            "request": request,
            "token": token,
        },
    )


@router.post("/mobile-pair/{token}")
def mobile_pair_confirm(
    token: str,
):
    if not mobile_access_configured():
        return RedirectResponse(
            url="/mobile-login",
            status_code=303,
        )

    if not consume_mobile_pairing_token(
        token
    ):
        return RedirectResponse(
            url="/mobile-login?pairing=invalid",
            status_code=303,
        )

    response = RedirectResponse(
        url="/mobile-opportunities",
        status_code=303,
    )

    _set_mobile_session_cookie(
        response
    )

    return _set_trusted_device_cookie(
        response
    )


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

    _set_mobile_session_cookie(
        response
    )

    return _set_trusted_device_cookie(
        response
    )


@router.get("/mobile-logout")
def mobile_logout(
    request: Request,
):
    revoke_trusted_device(
        request.cookies.get(
            TRUSTED_DEVICE_COOKIE_NAME
        )
    )

    response = RedirectResponse(
        url="/mobile-login",
        status_code=303,
    )

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )

    response.delete_cookie(
        key=TRUSTED_DEVICE_COOKIE_NAME,
        path="/",
    )

    return response


@router.get("/mobile-opportunities")
def mobile_opportunities_page(
    request: Request,
):
    if not _request_has_mobile_access(
        request
    ):
        return RedirectResponse(
            url="/mobile-login",
            status_code=303,
        )

    db = SessionLocal()

    try:
        payload = (
            build_live_opportunity_centre(
                db,
                limit=30,
                persist=True,
            )
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
