from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode


_ALLOWED_GROUPS = {
    "Group A": "Group A",
    "Group B": "Group B",
    "Group C": "Group C",
    "Final": "Final",
    "Averages": "Averages",
}


@dataclass(frozen=True)
class ModusUrlModel:
    """Build stable official MODUS page URLs from source identifiers."""

    base_url: str = "https://modussuperseries.com"

    def results_url(
        self,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> str:
        series_id = self._positive_int(series_id, "series_id")
        week_id = self._positive_int(week_id, "week_id")
        group = self.normalise_group(group)

        query = urlencode(
            {
                "series_id": series_id,
                "week_id": week_id,
                "group": group,
            }
        )
        return f"{self.base_url.rstrip('/')}/results?{query}"

    def match_stats_url(self, match_id: int) -> str:
        match_id = self._positive_int(match_id, "match_id")
        query = urlencode({"match_id": match_id})
        return (
            f"{self.base_url.rstrip('/')}/match-db-stats.php?"
            f"{query}"
        )

    @staticmethod
    def normalise_group(group: str) -> str:
        value = " ".join(str(group or "").replace("+", " ").split())
        lookup = {key.lower(): value for key, value in _ALLOWED_GROUPS.items()}
        normalised = lookup.get(value.lower())
        if normalised is None:
            allowed = ", ".join(_ALLOWED_GROUPS)
            raise ValueError(
                f"Unsupported MODUS group '{group}'. Allowed: {allowed}."
            )
        return normalised

    @staticmethod
    def _positive_int(value, field_name: str) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc
        if result <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return result
