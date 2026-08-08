from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional

from sqlalchemy.orm import Session

from app.services.bookmaker_capture_types import BookmakerCaptureReport
from app.services.paddy_power_live_capture import build_paddy_power_capture_once


CANDIDATE_MODULES = (
    "app.services.paddy_power_live_capture",
    "app.services.paddy_power_capture_service",
    "app.services.paddy_power_modus_extractor",
)

CANDIDATE_FUNCTIONS = (
    "fetch_paddy_power_quotes",
    "capture_modus_quotes",
    "capture_quotes",
    "extract_modus_quotes",
    "extract_quotes",
    "capture",
    "extract",
)


@dataclass(frozen=True)
class PaddyPowerBridgeResolution:
    module_name: str
    function_name: str
    callable: Callable[..., Any]


@dataclass(frozen=True)
class PaddyPowerLiveRun:
    ready: bool
    report: Optional[BookmakerCaptureReport]
    message: str
    error: Optional[str] = None


def resolve_capture_callable(
    *,
    modules: Iterable[str] = CANDIDATE_MODULES,
    function_names: Iterable[str] = CANDIDATE_FUNCTIONS,
) -> PaddyPowerBridgeResolution:
    try:
        capture_once, service = build_paddy_power_capture_once()
        try:
            if callable(capture_once):
                return PaddyPowerBridgeResolution(
                    module_name="app.services.paddy_power_live_capture",
                    function_name="build_paddy_power_capture_once",
                    callable=capture_once,
                )
        finally:
            service.close()
    except Exception:
        pass

    errors = []

    for module_name in modules:
        try:
            module = importlib.import_module(
                module_name
            )
        except Exception as exc:
            errors.append(
                f"{module_name}: {exc}"
            )
            continue

        for function_name in function_names:
            candidate = getattr(
                module,
                function_name,
                None,
            )

            if callable(candidate):
                return PaddyPowerBridgeResolution(
                    module_name=module_name,
                    function_name=function_name,
                    callable=candidate,
                )

    details = (
        "; ".join(errors)
        if errors
        else "modules imported but no compatible callable was found"
    )

    raise RuntimeError(
        "Could not resolve an existing Paddy Power capture callable. "
        f"Checked modules {tuple(modules)} and functions "
        f"{tuple(function_names)}. Details: {details}"
    )


def _as_rows(raw: Any) -> list[dict]:
    if raw is None:
        return []

    if isinstance(raw, Mapping):
        if "quotes" in raw:
            raw = raw["quotes"]
        elif "rows" in raw:
            raw = raw["rows"]
        elif "markets" in raw:
            raw = raw["markets"]
        else:
            raw = [raw]

    if hasattr(raw, "quotes"):
        raw = raw.quotes

    if not isinstance(
        raw,
        (list, tuple),
    ):
        raw = list(
            raw
        )

    rows = []

    for item in raw:
        if isinstance(
            item,
            Mapping,
        ):
            rows.append(
                dict(item)
            )
            continue

        row = {}

        for name in (
            "fixture_id",
            "market",
            "selection",
            "decimal_odds",
            "odds",
            "price",
            "source_reference",
            "url",
        ):
            if hasattr(
                item,
                name,
            ):
                row[name] = getattr(
                    item,
                    name,
                )

        if not row:
            raise ValueError(
                "Unsupported Paddy Power quote row type."
            )

        rows.append(
            row
        )

    return rows


def _normalise_row(
    row: dict,
) -> dict:
    fixture_id = (
        row.get("fixture_id")
        or row.get("match_id")
        or row.get("event_id")
    )

    selection = (
        row.get("selection")
        or row.get("player")
        or row.get("runner")
        or row.get("name")
    )

    decimal_odds = (
        row.get("decimal_odds")
        or row.get("odds")
        or row.get("price")
    )

    market = (
        row.get("market")
        or row.get("market_name")
        or "match_winner"
    )

    source_reference = (
        row.get("source_reference")
        or row.get("url")
        or row.get("source")
    )

    if fixture_id is None:
        raise ValueError(
            "Paddy Power quote is missing fixture_id."
        )

    if not selection:
        raise ValueError(
            "Paddy Power quote is missing selection."
        )

    if decimal_odds is None:
        raise ValueError(
            "Paddy Power quote is missing decimal odds."
        )

    return {
        "fixture_id": int(
            fixture_id
        ),
        "market": str(
            market
        ),
        "selection": str(
            selection
        ),
        "decimal_odds": float(
            decimal_odds
        ),
        "source_reference": (
            str(
                source_reference
            )
            if source_reference
            else None
        ),
    }


def fetch_existing_paddy_power_quotes(
    *,
    resolver: Optional[
        Callable[[], PaddyPowerBridgeResolution]
    ] = None,
) -> list[dict]:
    resolution = (
        resolver()
        if resolver is not None
        else resolve_capture_callable()
    )

    if (
        resolver is None
        and resolution.function_name
        == "build_paddy_power_capture_once"
    ):
        raise RuntimeError(
            "The real Paddy Power capture path requires a database session. "
            "Use run_existing_paddy_power_capture(db)."
        )

    raw = resolution.callable()

    return [
        _normalise_row(
            row
        )
        for row in _as_rows(
            raw
        )
    ]


def run_existing_paddy_power_capture(
    db: Session,
) -> PaddyPowerLiveRun:
    capture_once = None
    service = None

    try:
        capture_once, service = (
            build_paddy_power_capture_once()
        )

        report = capture_once(
            db
        )

        if report.challenge_detected:
            return PaddyPowerLiveRun(
                ready=False,
                report=report,
                message=(
                    "Paddy Power presented an access or "
                    "verification challenge."
                ),
                error=report.message,
            )

        return PaddyPowerLiveRun(
            ready=True,
            report=report,
            message=(
                "Paddy Power live capture completed."
            ),
        )

    except Exception as exc:
        return PaddyPowerLiveRun(
            ready=False,
            report=None,
            message=(
                "Paddy Power live capture failed."
            ),
            error=str(
                exc
            ),
        )

    finally:
        if service is not None:
            service.close()
