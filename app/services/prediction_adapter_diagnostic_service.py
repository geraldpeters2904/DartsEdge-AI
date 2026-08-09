
from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class PredictionAdapterCandidate:
    module_name: str
    function_name: str
    import_ok: bool
    callable_found: bool
    compatible_signature: bool
    error: Optional[str]


@dataclass(frozen=True)
class PredictionAdapterDiagnostic:
    ready: bool
    module_name: Optional[str]
    function_name: Optional[str]
    candidates: tuple[PredictionAdapterCandidate, ...]
    message: str


CANDIDATES = (
    (
        "app.services.prediction_centre_service",
        (
            "predict_fixture",
            "prediction_for_fixture",
            "build_fixture_prediction",
        ),
    ),
    (
        "app.services.predictor",
        (
            "predict_match",
            "predict",
        ),
    ),
    (
        "app.services.prediction_service",
        (
            "predict_fixture",
            "predict_match",
            "predict",
        ),
    ),
)


def _signature_compatible(
    fn: Callable[..., Any],
) -> bool:
    try:
        signature = inspect.signature(fn)
    except Exception:
        return False

    names = set(signature.parameters)

    has_db = bool(
        names.intersection(
            {
                "db",
                "session",
            }
        )
    )

    has_fixture = bool(
        names.intersection(
            {
                "fixture_id",
                "match_id",
            }
        )
    )

    has_players = (
        "player_a" in names
        and "player_b" in names
    )

    return bool(
        has_db
        or has_fixture
        or has_players
    )


def diagnose_prediction_adapter(
) -> PredictionAdapterDiagnostic:
    candidate_rows = []

    for module_name, function_names in CANDIDATES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            for function_name in function_names:
                candidate_rows.append(
                    PredictionAdapterCandidate(
                        module_name=module_name,
                        function_name=function_name,
                        import_ok=False,
                        callable_found=False,
                        compatible_signature=False,
                        error=str(exc),
                    )
                )
            continue

        for function_name in function_names:
            fn = getattr(
                module,
                function_name,
                None,
            )

            if not callable(fn):
                candidate_rows.append(
                    PredictionAdapterCandidate(
                        module_name=module_name,
                        function_name=function_name,
                        import_ok=True,
                        callable_found=False,
                        compatible_signature=False,
                        error=None,
                    )
                )
                continue

            compatible = _signature_compatible(
                fn
            )

            candidate_rows.append(
                PredictionAdapterCandidate(
                    module_name=module_name,
                    function_name=function_name,
                    import_ok=True,
                    callable_found=True,
                    compatible_signature=compatible,
                    error=None,
                )
            )

            if compatible:
                return PredictionAdapterDiagnostic(
                    ready=True,
                    module_name=module_name,
                    function_name=function_name,
                    candidates=tuple(
                        candidate_rows
                    ),
                    message=(
                        "A compatible prediction callable was resolved."
                    ),
                )

    return PredictionAdapterDiagnostic(
        ready=False,
        module_name=None,
        function_name=None,
        candidates=tuple(
            candidate_rows
        ),
        message=(
            "No compatible prediction callable was resolved."
        ),
    )
