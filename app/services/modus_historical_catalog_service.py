from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import List, Optional, Tuple

from app.providers.adapters.modus_official.urls import (
    ModusUrlModel,
)


@dataclass(frozen=True)
class ModusCatalogOption:
    value: int
    label: str
    selected: bool = False


@dataclass(frozen=True)
class ModusHistoricalCaptureTarget:
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    group: str
    source_url: str


@dataclass(frozen=True)
class ModusHistoricalCatalog:
    series: Tuple[ModusCatalogOption, ...]
    weeks: Tuple[ModusCatalogOption, ...]
    groups: Tuple[str, ...]
    selected_series_id: Optional[int]
    selected_week_id: Optional[int]
    selected_group: Optional[str]

    @property
    def selected_series(
        self,
    ) -> Optional[ModusCatalogOption]:
        return next(
            (
                option
                for option in self.series
                if option.selected
            ),
            None,
        )

    @property
    def selected_week(
        self,
    ) -> Optional[ModusCatalogOption]:
        return next(
            (
                option
                for option in self.weeks
                if option.selected
            ),
            None,
        )

    @property
    def ready(self) -> bool:
        return bool(
            self.series
            and self.weeks
            and self.groups
            and self.selected_series_id
            and self.selected_week_id
            and self.selected_group
        )


class ModusHistoricalCatalogService:
    """Parse capture targets from rendered MODUS results HTML."""

    def __init__(
        self,
        *,
        url_model: Optional[ModusUrlModel] = None,
    ) -> None:
        self.url_model = url_model or ModusUrlModel()

    def parse(
        self,
        html_text: str,
    ) -> ModusHistoricalCatalog:
        text = str(html_text or "")

        if not text.strip():
            raise ValueError(
                "Rendered MODUS results HTML must not be blank."
            )

        parser = _CatalogParser()
        parser.feed(text)
        parser.close()

        if not parser.series:
            raise ValueError(
                "No MODUS series options were found."
            )

        if not parser.weeks:
            raise ValueError(
                "No MODUS week options were found."
            )

        groups = tuple(
            self._normalise_groups(parser.groups)
        )

        if not groups:
            raise ValueError(
                "No supported MODUS groups were found."
            )

        selected_series = next(
            (
                option
                for option in parser.series
                if option.selected
            ),
            None,
        )
        selected_week = next(
            (
                option
                for option in parser.weeks
                if option.selected
            ),
            None,
        )

        selected_group = (
            self.url_model.normalise_group(
                parser.selected_group
            )
            if parser.selected_group
            else None
        )

        return ModusHistoricalCatalog(
            series=tuple(parser.series),
            weeks=tuple(parser.weeks),
            groups=groups,
            selected_series_id=(
                selected_series.value
                if selected_series
                else None
            ),
            selected_week_id=(
                selected_week.value
                if selected_week
                else None
            ),
            selected_group=selected_group,
        )

    def targets_for_selected_series(
        self,
        html_text: str,
    ) -> Tuple[ModusHistoricalCaptureTarget, ...]:
        catalog = self.parse(html_text)
        series = catalog.selected_series

        if series is None:
            raise ValueError(
                "The MODUS results page has no selected series."
            )

        targets: List[
            ModusHistoricalCaptureTarget
        ] = []

        for week in catalog.weeks:
            for group in catalog.groups:
                targets.append(
                    ModusHistoricalCaptureTarget(
                        series_id=series.value,
                        series_label=series.label,
                        week_id=week.value,
                        week_label=week.label,
                        group=group,
                        source_url=(
                            self.url_model.results_url(
                                series_id=series.value,
                                week_id=week.value,
                                group=group,
                            )
                        ),
                    )
                )

        return tuple(targets)

    def selected_target(
        self,
        html_text: str,
    ) -> ModusHistoricalCaptureTarget:
        catalog = self.parse(html_text)
        series = catalog.selected_series
        week = catalog.selected_week

        if series is None:
            raise ValueError(
                "The MODUS results page has no selected series."
            )

        if week is None:
            raise ValueError(
                "The MODUS results page has no selected week."
            )

        if catalog.selected_group is None:
            raise ValueError(
                "The MODUS results page has no active group."
            )

        return ModusHistoricalCaptureTarget(
            series_id=series.value,
            series_label=series.label,
            week_id=week.value,
            week_label=week.label,
            group=catalog.selected_group,
            source_url=self.url_model.results_url(
                series_id=series.value,
                week_id=week.value,
                group=catalog.selected_group,
            ),
        )

    def _normalise_groups(
        self,
        groups: List[str],
    ) -> List[str]:
        unique = []

        for group in groups:
            try:
                normalised = (
                    self.url_model.normalise_group(group)
                )
            except ValueError:
                continue

            if normalised == "Averages":
                continue

            if normalised not in unique:
                unique.append(normalised)

        order = {
            "Group A": 1,
            "Group B": 2,
            "Group C": 3,
            "Final": 4,
        }

        return sorted(
            unique,
            key=lambda item: order.get(item, 99),
        )


class _CatalogParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.current_select: Optional[str] = None
        self.option_value: Optional[str] = None
        self.option_selected = False
        self.option_text: List[str] = []

        self.button_candidate = False
        self.button_active = False
        self.button_text: List[str] = []

        self.series: List[ModusCatalogOption] = []
        self.weeks: List[ModusCatalogOption] = []
        self.groups: List[str] = []
        self.selected_group: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set(
            (attributes.get("class") or "").split()
        )

        if tag == "select":
            select_id = attributes.get("id")

            if select_id in {
                "seriesSelect",
                "weekSelect",
            }:
                self.current_select = select_id

        elif (
            tag == "option"
            and self.current_select is not None
        ):
            self.option_value = attributes.get("value")
            self.option_selected = (
                "selected" in attributes
            )
            self.option_text = []

        elif tag == "button":
            onclick = attributes.get("onclick") or ""
            text_group = re.search(
                r"changeGroup\(['\"]([^'\"]+)['\"]\)",
                onclick,
                flags=re.IGNORECASE,
            )

            self.button_candidate = bool(
                text_group
                or "active" in classes
            )
            self.button_active = "active" in classes
            self.button_text = []

    def handle_data(self, data):
        if self.option_value is not None:
            self.option_text.append(data)

        if self.button_candidate:
            self.button_text.append(data)

    def handle_endtag(self, tag):
        if (
            tag == "option"
            and self.option_value is not None
        ):
            label = self._clean(self.option_text)

            if label:
                try:
                    value = int(self.option_value)
                except (TypeError, ValueError):
                    value = None

                if value is not None and value > 0:
                    option = ModusCatalogOption(
                        value=value,
                        label=label,
                        selected=self.option_selected,
                    )

                    if self.current_select == "seriesSelect":
                        self.series.append(option)
                    elif self.current_select == "weekSelect":
                        self.weeks.append(option)

            self.option_value = None
            self.option_selected = False
            self.option_text = []

        elif tag == "select":
            self.current_select = None

        elif tag == "button" and self.button_candidate:
            label = self._clean(self.button_text)

            if label:
                self.groups.append(label)

                if self.button_active:
                    self.selected_group = label

            self.button_candidate = False
            self.button_active = False
            self.button_text = []

    @staticmethod
    def _clean(values: List[str]) -> str:
        return re.sub(
            r"\s+",
            " ",
            "".join(values),
        ).strip()
