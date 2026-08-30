from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.collector.commit_helpers import find_match_by_external_id
from app.providers.adapters.modus_official.identifiers import (
    modus_match_external_id,
)
from app.providers.adapters.modus_official.urls import ModusUrlModel
from app.schemas.canonical import MatchStatus
from app.services.automatic_modus_fixture_import_service import (
    AutomaticModusFixtureImportResult,
    AutomaticModusFixtureImportService,
)
from app.services.browser_session import BrowserSession
from app.services.modus_fixture_lifecycle_service import (
    ModusFixtureCard,
    ModusFixtureLifecycleService,
)
from app.services.safari_browser_session import SafariBrowserSession


@dataclass(frozen=True)
class ModusFixtureDiscoveryResult:
    source_url: str
    current_url: str
    page_title: str
    checksum: str
    changed: bool
    action: str
    message: str
    import_result: Optional[AutomaticModusFixtureImportResult] = None
    enrichment_results: tuple = ()

    @property
    def imported(self) -> bool:
        return self.action == "imported"

    @property
    def unchanged(self) -> bool:
        return self.action == "unchanged"


class ModusFixtureDiscoveryService:
    """
    Fetch and safely process one official MODUS results/fixtures page.

    Scheduled cards may enter the fixture-only importer. Completed cards never
    do: they are resolved through the existing provider fixture mapping and
    sent through the result-aware current-match enrichment workflow.

    A page checksum is remembered only after every required operation succeeds,
    so a failed completed-match enrichment is retried on the next cycle.
    """

    def __init__(
        self,
        *,
        browser_session: Optional[BrowserSession] = None,
        fixture_import_service: Optional[
            AutomaticModusFixtureImportService
        ] = None,
        lifecycle_service: Optional[ModusFixtureLifecycleService] = None,
        enrichment_workflow_service=None,
        url_model: Optional[ModusUrlModel] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.browser_session = browser_session or SafariBrowserSession()
        self.fixture_import_service = (
            fixture_import_service or AutomaticModusFixtureImportService()
        )
        self.lifecycle_service = lifecycle_service or ModusFixtureLifecycleService()
        if enrichment_workflow_service is None:
            from app.services.current_match_enrichment_workflow_service import (
                CurrentMatchEnrichmentWorkflowService,
            )
            enrichment_workflow_service = (
                CurrentMatchEnrichmentWorkflowService()
            )
        self.enrichment_workflow_service = enrichment_workflow_service
        self.url_model = url_model or ModusUrlModel()
        self.timeout_seconds = timeout_seconds
        self._last_checksums: Dict[str, str] = {}

    def discover(
        self,
        db: Session,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> ModusFixtureDiscoveryResult:
        source_url = self.url_model.results_url(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )
        self.browser_session.goto(
            source_url,
            timeout_seconds=self.timeout_seconds,
        )
        self.browser_session.wait_for(
            self._fixture_cards_loaded,
            timeout_seconds=self.timeout_seconds,
            description="MODUS fixture cards",
        )

        html = self.browser_session.html()
        current_url = self.browser_session.current_url() or source_url
        title = self.browser_session.title()
        checksum = hashlib.sha256(html.encode("utf-8")).hexdigest()

        previous = self._last_checksums.get(source_url)
        if previous == checksum:
            return ModusFixtureDiscoveryResult(
                source_url=source_url,
                current_url=current_url,
                page_title=title,
                checksum=checksum,
                changed=False,
                action="unchanged",
                message=(
                    "The MODUS fixtures page has not changed "
                    "since the last discovery cycle."
                ),
            )

        cards = self.lifecycle_service.parse_cards(html)
        scheduled_cards = [
            card for card in cards
            if card.status == MatchStatus.SCHEDULED
        ]
        completed_cards = [
            card for card in cards
            if card.status == MatchStatus.COMPLETED
        ]

        import_result = None
        if scheduled_cards:
            scheduled_html = self._scheduled_only_html(
                html,
                completed_cards=completed_cards,
            )
            import_result = self.fixture_import_service.import_html(
                db,
                html_text=scheduled_html,
                source_name=(
                    f"modus-series-{series_id}-week-"
                    f"{week_id}-{group}.html"
                ),
            )

        enrichment_results: List[object] = []
        quarantined_completed_cards: List[ModusFixtureCard] = []
        already_completed_cards: List[ModusFixtureCard] = []

        for card in completed_cards:
            disposition, enrichment_result = (
                self._process_completed_card(db, card)
            )
            if disposition == "enriched":
                enrichment_results.append(enrichment_result)
            elif disposition == "quarantined":
                quarantined_completed_cards.append(card)
            elif disposition == "already_completed":
                already_completed_cards.append(card)

        # Do not suppress a retry unless all required work above succeeded.
        self._last_checksums[source_url] = checksum

        fixture_count = (
            int(import_result.fixture_count)
            if import_result is not None
            else 0
        )
        return ModusFixtureDiscoveryResult(
            source_url=source_url,
            current_url=current_url,
            page_title=title,
            checksum=checksum,
            changed=True,
            action="imported",
            message=(
                f"Processed {fixture_count} scheduled MODUS fixture(s), "
                f"enriched {len(enrichment_results)} completed match(es), "
                f"skipped {len(already_completed_cards)} already-canonical "
                f"completed match(es), and quarantined "
                f"{len(quarantined_completed_cards)} legacy incomplete "
                f"completed match(es)."
            ),
            import_result=import_result,
            enrichment_results=tuple(enrichment_results),
        )

    def close(self) -> None:
        self.browser_session.close()

    def _process_completed_card(
        self,
        db: Session,
        card: ModusFixtureCard,
    ):
        """
        Route a completed official card according to warehouse lifecycle state.

        Only a mapped match that is still scheduled may automatically enter
        result-aware enrichment. Existing completed matches are never repaired
        automatically here; legacy incomplete records require explicit backfill.
        """
        match_external_id = modus_match_external_id(card.match_id)
        match = find_match_by_external_id(
            db=db,
            provider="modus-official",
            match_external_id=match_external_id,
        )

        if match is None:
            raise ValueError(
                "No existing fixture mapping was found for "
                f"{match_external_id}; completed MODUS card "
                "cannot enter enrichment."
            )

        if match.status == "scheduled":
            return "enriched", self._enrich_completed_card(
                db,
                card,
                match=match,
            )

        if match.status == "completed":
            if match.winner is not None and match.score is not None:
                return "already_completed", None
            return "quarantined", None

        raise ValueError(
            f"Mapped match {match.id} has unsupported lifecycle status "
            f"{match.status!r}; completed MODUS card cannot enter enrichment."
        )

    def _enrich_completed_card(
        self,
        db: Session,
        card: ModusFixtureCard,
        *,
        match=None,
    ):
        if match is None:
            match_external_id = modus_match_external_id(card.match_id)
            match = find_match_by_external_id(
                db=db,
                provider="modus-official",
                match_external_id=match_external_id,
            )

            if match is None:
                raise ValueError(
                    "No existing fixture mapping was found for "
                    f"{match_external_id}; completed MODUS card "
                    "cannot enter enrichment."
                )

        from app.services.current_match_enrichment_discovery_service import (
            EnrichmentCandidate,
        )

        candidate = EnrichmentCandidate(
            internal_match_id=int(match.id),
            fixture_date=match.date,
            player_a=match.player_a,
            player_b=match.player_b,
            stage=match.stage,
            resolved_modus_match_id=int(card.match_id),
            candidate_modus_match_ids=(int(card.match_id),),
            status="resolved",
            message=(
                "Resolved directly from the official MODUS fixture mapping."
            ),
        )
        return self.enrichment_workflow_service.run(
            db,
            candidate,
            timeout_seconds=self.timeout_seconds,
        )

    @staticmethod
    def _scheduled_only_html(
        html_text: str,
        *,
        completed_cards: List[ModusFixtureCard],
    ) -> str:
        """
        Remove completed match articles while preserving selectors/page context.

        The fixture importer therefore receives only scheduled cards and cannot
        perform a fixture-only scheduled->completed transition.
        """
        import re

        completed_ids = {int(card.match_id) for card in completed_cards}
        seen_ids = set()
        article_pattern = re.compile(
            r"<article(?P<attrs>[^>]*)>(?P<body>.*?)</article>",
            re.IGNORECASE | re.DOTALL,
        )

        def keep_or_remove(match):
            article = match.group(0)
            id_match = re.search(
                r"match-db-stats\.php\?match_id=(\d+)",
                article,
                flags=re.IGNORECASE,
            )
            if not id_match:
                return article
            match_id = int(id_match.group(1))
            if match_id in completed_ids:
                seen_ids.add(match_id)
                return ""
            return article

        filtered = article_pattern.sub(keep_or_remove, html_text)
        missing = completed_ids - seen_ids
        if missing:
            raise ValueError(
                "Unable to isolate completed MODUS fixture card(s): "
                + ", ".join(str(value) for value in sorted(missing))
            )
        return filtered

    def _fixture_cards_loaded(self) -> bool:
        html = self.browser_session.html().casefold()
        return (
            "match-db-stats.php?match_id=" in html
            and 'id="seriesselect"' in html
            and 'id="weekselect"' in html
        )
