from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass(frozen=True)
class CheckoutPercentageResolution:
    percentage: float
    displayed_percentage: Optional[float]
    calculated_percentage: float
    recovered: bool
    recovery_reason: Optional[str]


class ModusDataQualityPolicy:
    """
    Resolve known inconsistencies in official MODUS statistics.

    Valid completed/attempted checkout counts are authoritative.
    Missing or conflicting displayed percentages are recovered from
    those counts. Malformed numeric values remain validation errors.
    """

    MISSING_PERCENTAGE_MARKERS = {
        "",
        "-",
        "--",
        "—",
    }

    def resolve_checkout_percentage(
        self,
        *,
        completed: int,
        attempts: int,
        displayed_value: str,
    ) -> CheckoutPercentageResolution:
        calculated = (
            completed / attempts * 100
            if attempts
            else 0.0
        )

        text = (
            str(displayed_value or "")
            .replace("%", "")
            .strip()
        )

        if text in self.MISSING_PERCENTAGE_MARKERS:
            return CheckoutPercentageResolution(
                percentage=round(calculated, 3),
                displayed_percentage=None,
                calculated_percentage=round(
                    calculated,
                    6,
                ),
                recovered=True,
                recovery_reason=(
                    "missing_checkout_percentage"
                ),
            )

        if not re.fullmatch(
            r"\d+(?:\.\d+)?",
            text,
        ):
            raise ValueError(
                "Checkout percentage must be a number "
                "between 0 and 100."
            )

        displayed = float(text)

        if not 0 <= displayed <= 100:
            raise ValueError(
                "Checkout percentage must be between "
                "0 and 100."
            )

        decimal_places = (
            len(text.split(".", 1)[1])
            if "." in text
            else 0
        )

        expected = (
            float(int(calculated))
            if decimal_places == 0
            else round(
                calculated,
                decimal_places,
            )
        )

        if expected != displayed:
            return CheckoutPercentageResolution(
                percentage=round(calculated, 3),
                displayed_percentage=displayed,
                calculated_percentage=round(
                    calculated,
                    6,
                ),
                recovered=True,
                recovery_reason=(
                    "conflicting_checkout_percentage"
                ),
            )

        return CheckoutPercentageResolution(
            percentage=displayed,
            displayed_percentage=displayed,
            calculated_percentage=round(
                calculated,
                6,
            ),
            recovered=False,
            recovery_reason=None,
        )


modus_data_quality_policy = (
    ModusDataQualityPolicy()
)
