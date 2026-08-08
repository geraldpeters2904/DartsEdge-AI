from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional


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


def resolve_capture_callable(
    *,
    modules: Iterable[str] = CANDIDATE_MODULES,
    function_names: Iterable[str] = CANDIDATE_FUNCTIONS,
) -> PaddyPowerBridgeResolution:
    import_errors = []

    for module_name in modules:
        try:
            module = importlib.import_module(
                module_name
            )
        except Exception as exc:
            import_errors.append(
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
        "; ".join(import_errors)
        if import_errors
        else "modules imported but no compatible callable was found"
    )

    raise RuntimeError(
        "Could not resolve an existing Paddy Power capture callable. "
        f"Checked modules {tuple(modules)} and functions "
        f"{tuple(function_names)}. Details: {details}"
    )


def _as_rows(
    raw: Any,
) -> list[dict]:
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
        try:
            raw = list(raw)
        except TypeError as exc:
            raise ValueError(
                "Paddy Power capture result is not iterable."
            ) from exc

    rows = []

    for item in raw:
        if isinstance(item, Mapping):
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
            if hasattr(item, name):
                row[name] = getattr(
                    item,
                    name,
                )

        if row:
            rows.append(row)
        else:
            raise ValueError(
                "Unsupported Paddy Power quote row type."
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
            str(source_reference)
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

    raw = resolution.callable()

    rows = _as_rows(
        raw
    )

    return [
        _normalise_row(
            row
        )
        for row in rows
    ]
