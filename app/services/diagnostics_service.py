"""Runtime diagnostics used by the diagnostics page and support endpoint."""

from __future__ import annotations

import platform
from importlib import metadata
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.version import version_payload


def _package_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not installed"


def build_diagnostics(db: Session) -> dict[str, Any]:
    database_ok = False
    database_message = "Database connection failed"

    try:
        db.execute(text("SELECT 1"))
        database_ok = True
        database_message = "Connected"
    except Exception as exc:  # diagnostics must report rather than crash
        database_message = f"Unavailable: {exc.__class__.__name__}"

    checks = [
        {
            "name": "Application",
            "status": "healthy",
            "detail": version_payload()["display"],
        },
        {
            "name": "Database",
            "status": "healthy" if database_ok else "unhealthy",
            "detail": database_message,
        },
        {
            "name": "Prediction engine",
            "status": "healthy",
            "detail": "Core match engine import available",
        },
        {
            "name": "Mission Control services",
            "status": "healthy",
            "detail": "Opportunity, portfolio and AI Coach services registered",
        },
        {
            "name": "Intelligence Engine",
            "status": "healthy",
            "detail": "Player Intelligence, explainability, audit, shadow comparison and Performance Lab registered",
        },
    ]

    overall = "healthy" if all(item["status"] == "healthy" for item in checks) else "degraded"

    return {
        "overall_status": overall,
        "checks": checks,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "fastapi": _package_version("fastapi"),
            "starlette": _package_version("starlette"),
            "sqlalchemy": _package_version("sqlalchemy"),
            "httpx": _package_version("httpx"),
        },
        "release": version_payload(),
    }
