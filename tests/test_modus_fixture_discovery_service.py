import unittest
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.schemas.canonical import MatchStatus
from app.services.modus_fixture_discovery_service import (
    ModusFixtureDiscoveryService,
)
from app.services.modus_fixture_lifecycle_service import ModusFixtureCard


UPCOMING_HTML = Path(
    "tests/fixtures/modus_fixture_lifecycle/upcoming.html"
).read_text(encoding="utf-8")


class FakeBrowserSession:
    def __init__(self, html=UPCOMING_HTML):
        self.page_html = html
        self.goto_calls = []
        self.wait_calls = []
        self.closed = False

    @property
    def running(self):
        return True

    def open(self):
        pass

    def goto(self, url, *, timeout_seconds=30.0):
        self.goto_calls.append((url, timeout_seconds))

    def wait_for(
        self,
        predicate,
        *,
        timeout_seconds=30.0,
        description="browser condition",
    ):
        self.wait_calls.append((timeout_seconds, description))
        if not predicate():
            raise TimeoutError(description)

    def html(self):
        return self.page_html

    def title(self):
        return "MODUS Fixtures"

    def current_url(self):
        return (
            "https://modussuperseries.com/results?"
            "series_id=15&week_id=178&group=Group+A"
        )

    def close(self):
        self.closed = True


@dataclass
class FakeImportResult:
    fixture_count: int = 3


class FakeFixtureImporter:
    def __init__(self):
        self.calls = []

    def import_html(self, db, *, html_text, source_name):
        self.calls.append((db, html_text, source_name))
        return FakeImportResult()


class FakeLifecycleService:
    def __init__(self, cards):
        self.cards = cards

    def parse_cards(self, html_text):
        return list(self.cards)


@dataclass
class FakeWorkflowResult:
    internal_match_id: int
    modus_match_id: int


class FakeWorkflow:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def run(self, db, candidate, *, timeout_seconds=30.0):
        self.calls.append((db, candidate, timeout_seconds))
        if self.fail:
            raise RuntimeError("detail fetch failed")
        return FakeWorkflowResult(
            internal_match_id=candidate.internal_match_id,
            modus_match_id=candidate.resolved_modus_match_id,
        )


@dataclass
class FakeMatch:
    id: int = 77
    date: date = date(2026, 8, 30)
    player_a: str = "Player A"
    player_b: str = "Player B"
    stage: str = "Group A"
    status: str = "scheduled"


def card(match_id, status):
    return ModusFixtureCard(
        match_id=match_id,
        match_number=1,
        player_a_name="Player A",
        player_b_name="Player B",
        player_a_legs=None if status == MatchStatus.SCHEDULED else 4,
        player_b_legs=None if status == MatchStatus.SCHEDULED else 2,
        status=status,
        series_id=15,
        series_label="Series 15",
        week_id=178,
        week_label="Week 4",
        group="Group A",
    )


class ModusFixtureDiscoveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.browser = FakeBrowserSession()
        self.importer = FakeFixtureImporter()
        self.workflow = FakeWorkflow()
        self.service = ModusFixtureDiscoveryService(
            browser_session=self.browser,
            fixture_import_service=self.importer,
            enrichment_workflow_service=self.workflow,
            timeout_seconds=5,
        )

    def test_discovers_and_imports_fixture_page(self):
        db = object()
        result = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.assertTrue(result.imported)
        self.assertTrue(result.changed)
        self.assertEqual(result.import_result.fixture_count, 3)
        self.assertEqual(len(self.importer.calls), 1)
        self.assertEqual(
            self.browser.goto_calls[0][0],
            (
                "https://modussuperseries.com/results?"
                "series_id=15&week_id=178&group=Group+A"
            ),
        )

    def test_unchanged_page_is_not_reimported(self):
        db = object()
        first = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )
        second = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.assertTrue(first.imported)
        self.assertTrue(second.unchanged)
        self.assertFalse(second.changed)
        self.assertEqual(len(self.importer.calls), 1)

    def test_changed_html_is_imported_again(self):
        db = object()
        self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.browser.page_html = UPCOMING_HTML + "<!-- changed -->"
        second = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.assertTrue(second.imported)
        self.assertEqual(len(self.importer.calls), 2)

    def test_close_closes_browser(self):
        self.service.close()
        self.assertTrue(self.browser.closed)

    def test_invalid_group_is_rejected_before_browser(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported MODUS group",
        ):
            self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Unknown",
            )
        self.assertEqual(self.browser.goto_calls, [])

    def test_completed_card_uses_result_aware_workflow_not_fixture_import(self):
        completed = card(19001, MatchStatus.COMPLETED)
        self.service.lifecycle_service = FakeLifecycleService([completed])

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=FakeMatch(),
        ) as lookup:
            result = self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Group A",
            )

        self.assertEqual(self.importer.calls, [])
        self.assertEqual(len(self.workflow.calls), 1)
        candidate = self.workflow.calls[0][1]
        self.assertEqual(candidate.internal_match_id, 77)
        self.assertEqual(candidate.resolved_modus_match_id, 19001)
        self.assertEqual(candidate.status, "resolved")
        self.assertEqual(len(result.enrichment_results), 1)
        lookup.assert_called_once()

    def test_mixed_page_imports_only_scheduled_cards_and_enriches_completed(self):
        # Use a compact realistic page so we can assert the completed article
        # is physically absent from the HTML passed to the fixture importer.
        self.browser.page_html = """
        <select id="seriesSelect"><option value="15" selected>Series 15</option></select>
        <select id="weekSelect"><option value="178" selected>Week 4</option></select>
        <button class="active">Group A</button>
        <article class="fixture-card-upcoming">
          <a href="match-db-stats.php?match_id=19000"></a>
        </article>
        <article class="fixture-card">
          <a href="match-db-stats.php?match_id=19001"></a>
        </article>
        """
        cards = [
            card(19000, MatchStatus.SCHEDULED),
            card(19001, MatchStatus.COMPLETED),
        ]
        self.service.lifecycle_service = FakeLifecycleService(cards)

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=FakeMatch(),
        ):
            result = self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Group A",
            )

        self.assertEqual(len(self.importer.calls), 1)
        imported_html = self.importer.calls[0][1]
        self.assertIn("match_id=19000", imported_html)
        self.assertNotIn("match_id=19001", imported_html)
        self.assertEqual(len(self.workflow.calls), 1)
        self.assertEqual(len(result.enrichment_results), 1)

    def test_failed_enrichment_does_not_cache_checksum(self):
        completed = card(19001, MatchStatus.COMPLETED)
        self.service.lifecycle_service = FakeLifecycleService([completed])
        self.service.enrichment_workflow_service = FakeWorkflow(fail=True)

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=FakeMatch(),
        ):
            with self.assertRaisesRegex(RuntimeError, "detail fetch failed"):
                self.service.discover(
                    object(),
                    series_id=15,
                    week_id=178,
                    group="Group A",
                )
            with self.assertRaisesRegex(RuntimeError, "detail fetch failed"):
                self.service.discover(
                    object(),
                    series_id=15,
                    week_id=178,
                    group="Group A",
                )

        self.assertEqual(
            len(self.service.enrichment_workflow_service.calls),
            2,
        )

    def test_completed_card_with_existing_canonical_result_is_skipped(self):
        completed = card(19001, MatchStatus.COMPLETED)
        self.service.lifecycle_service = FakeLifecycleService([completed])
        existing = FakeMatch(status="completed")
        existing.winner = "Player A"
        existing.score = "4-2"

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=existing,
        ):
            result = self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Group A",
            )

        self.assertEqual(self.importer.calls, [])
        self.assertEqual(self.workflow.calls, [])
        self.assertEqual(result.enrichment_results, ())
        self.assertIn(
            "skipped 1 already-canonical completed match(es)",
            result.message,
        )
        self.assertIn(
            "quarantined 0 legacy incomplete completed match(es)",
            result.message,
        )

    def test_legacy_completed_card_without_result_is_quarantined(self):
        completed = card(19001, MatchStatus.COMPLETED)
        self.service.lifecycle_service = FakeLifecycleService([completed])
        existing = FakeMatch(status="completed")
        existing.winner = None
        existing.score = None

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=existing,
        ):
            result = self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Group A",
            )

        self.assertEqual(self.importer.calls, [])
        self.assertEqual(self.workflow.calls, [])
        self.assertEqual(result.enrichment_results, ())
        self.assertIn(
            "skipped 0 already-canonical completed match(es)",
            result.message,
        )
        self.assertIn(
            "quarantined 1 legacy incomplete completed match(es)",
            result.message,
        )

    def test_completed_card_with_partial_result_is_quarantined(self):
        completed = card(19001, MatchStatus.COMPLETED)
        self.service.lifecycle_service = FakeLifecycleService([completed])
        existing = FakeMatch(status="completed")
        existing.winner = "Player A"
        existing.score = None

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=existing,
        ):
            result = self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Group A",
            )

        self.assertEqual(self.workflow.calls, [])
        self.assertEqual(result.enrichment_results, ())
        self.assertIn(
            "quarantined 1 legacy incomplete completed match(es)",
            result.message,
        )

    def test_completed_card_without_fixture_mapping_is_quarantined(self):
        completed = card(19001, MatchStatus.COMPLETED)
        self.service.lifecycle_service = FakeLifecycleService([completed])

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=None,
        ), patch.object(
            self.service,
            "_find_unique_scheduled_fixture_for_card",
            return_value=None,
        ):
            result = self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Group A",
            )

        self.assertEqual(self.importer.calls, [])
        self.assertEqual(self.workflow.calls, [])
        self.assertEqual(result.enrichment_results, ())
        self.assertIn(
            "quarantined 1 legacy incomplete completed match(es)",
            result.message,
        )

    def test_completed_card_can_reconcile_to_unique_scheduled_fixture(self):
        completed = card(
            19715,
            MatchStatus.COMPLETED,
        )

        scheduled_match = type(
            "ScheduledMatch",
            (),
            {
                "id": 17702,
                "status": "scheduled",
                "date": None,
                "stage": "Group A",
                "player_a": completed.player_a_name,
                "player_b": completed.player_b_name,
            },
        )()

        enrichment_result = object()

        with patch(
            "app.services.modus_fixture_discovery_service."
            "find_match_by_external_id",
            return_value=None,
        ), patch.object(
            self.service,
            "_find_unique_scheduled_fixture_for_card",
            return_value=scheduled_match,
        ) as fallback, patch(
            "app.services.modus_fixture_discovery_service.map_entity",
        ) as mapper, patch.object(
            self.service,
            "_enrich_completed_card",
            return_value=enrichment_result,
        ) as enrich:
            disposition, result = self.service._process_completed_card(
                object(),
                completed,
            )

        self.assertEqual(disposition, "enriched")
        self.assertIs(result, enrichment_result)

        fallback.assert_called_once_with(
            unittest.mock.ANY,
            completed,
        )

        mapper.assert_called_once_with(
            unittest.mock.ANY,
            provider="modus-official",
            entity_type="fixture",
            external_id="modus-match-19715",
            internal_id=17702,
            competition_code="MODUS",
        )

        enrich.assert_called_once_with(
            unittest.mock.ANY,
            completed,
            match=scheduled_match,
        )


if __name__ == "__main__":
    unittest.main()
