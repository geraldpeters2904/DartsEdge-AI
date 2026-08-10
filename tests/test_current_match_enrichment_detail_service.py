import unittest
from dataclasses import dataclass
from datetime import date

from app.services.current_match_enrichment_detail_service import (
    CurrentMatchEnrichmentDetailService,
)
from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)


@dataclass
class FakeDetail:
    match_id: int = 19001
    player_a_name: str = "Player A"
    player_b_name: str = "Player B"
    player_a_legs: int = 4
    player_b_legs: int = 2


class FakeParser:
    def __init__(self, detail=None):
        self.detail = detail or FakeDetail()
        self.calls = []

    def parse(self, html, *, match_id=None):
        self.calls.append(
            (html, match_id)
        )
        return self.detail


class FakeBrowser:
    def __init__(self):
        self.visited = []
        self.closed = False

    def goto(
        self,
        url,
        *,
        timeout_seconds,
    ):
        self.visited.append(
            (url, timeout_seconds)
        )

    def html(self):
        return "<html>official match</html>"

    def close(self):
        self.closed = True


class BrowserFactory:
    def __init__(self):
        self.instances = []

    def __call__(self):
        browser = FakeBrowser()
        self.instances.append(browser)
        return browser


def resolved_candidate():
    return EnrichmentCandidate(
        internal_match_id=101,
        fixture_date=date(2026, 8, 1),
        player_a="Player A",
        player_b="Player B",
        stage="Group A",
        resolved_modus_match_id=19001,
        candidate_modus_match_ids=(19001,),
        status="resolved",
        message="Resolved.",
    )


class CurrentMatchEnrichmentDetailServiceTests(
    unittest.TestCase
):
    def test_resolved_candidate_fetches_and_validates(self):
        factory = BrowserFactory()
        parser = FakeParser()

        service = CurrentMatchEnrichmentDetailService(
            browser_factory=factory,
            parser=parser,
        )

        result = service.fetch(
            resolved_candidate()
        )

        self.assertEqual(
            result.status,
            "validated",
        )
        self.assertEqual(
            result.internal_match_id,
            101,
        )
        self.assertEqual(
            result.modus_match_id,
            19001,
        )
        self.assertEqual(
            result.player_a_legs,
            4,
        )
        self.assertEqual(
            result.player_b_legs,
            2,
        )

        self.assertEqual(
            parser.calls[0][1],
            19001,
        )

        self.assertIn(
            "match_id=19001",
            factory.instances[0].visited[0][0],
        )

        self.assertTrue(
            factory.instances[0].closed
        )

    def test_player_order_is_allowed(self):
        parser = FakeParser(
            FakeDetail(
                player_a_name="Player B",
                player_b_name="Player A",
            )
        )

        service = CurrentMatchEnrichmentDetailService(
            browser_factory=BrowserFactory(),
            parser=parser,
        )

        result = service.fetch(
            resolved_candidate()
        )

        self.assertEqual(
            result.status,
            "validated",
        )

    def test_different_players_are_rejected(self):
        parser = FakeParser(
            FakeDetail(
                player_a_name="Wrong Player",
                player_b_name="Player B",
            )
        )

        service = CurrentMatchEnrichmentDetailService(
            browser_factory=BrowserFactory(),
            parser=parser,
        )

        with self.assertRaisesRegex(
            ValueError,
            "do not match",
        ):
            service.fetch(
                resolved_candidate()
            )

    def test_ambiguous_candidate_is_not_fetched(self):
        candidate = EnrichmentCandidate(
            internal_match_id=101,
            fixture_date=date(2026, 8, 1),
            player_a="Player A",
            player_b="Player B",
            stage="Group A",
            resolved_modus_match_id=None,
            candidate_modus_match_ids=(
                19001,
                19002,
            ),
            status="ambiguous",
            message="Ambiguous.",
        )

        factory = BrowserFactory()

        service = CurrentMatchEnrichmentDetailService(
            browser_factory=factory,
            parser=FakeParser(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Only resolved",
        ):
            service.fetch(candidate)

        self.assertEqual(
            factory.instances,
            [],
        )


if __name__ == "__main__":
    unittest.main()
