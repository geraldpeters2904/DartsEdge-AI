import unittest
from dataclasses import dataclass
from datetime import date

from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)
from app.services.current_match_enrichment_workflow_service import (
    CurrentMatchEnrichmentWorkflowService,
)


def candidate(status="resolved"):
    return EnrichmentCandidate(
        internal_match_id=101,
        fixture_date=date(2026, 8, 1),
        player_a="Player A",
        player_b="Player B",
        stage="Group A",
        resolved_modus_match_id=(
            19001
            if status == "resolved"
            else None
        ),
        candidate_modus_match_ids=(19001,),
        status=status,
        message="Resolved.",
    )


@dataclass
class FakeDetailResult:
    internal_match_id: int = 101
    modus_match_id: int = 19001
    status: str = "validated"


@dataclass
class FakeStatisticsResult:
    internal_match_id: int = 101
    modus_match_id: int = 19001
    status: str = "canonicalized"


@dataclass
class FakePersistenceResult:
    internal_match_id: int = 101
    modus_match_id: int = 19001
    batch_id: int = 55
    status: str = "persisted"


class FakeDetailService:
    def __init__(self):
        self.calls = []

    def fetch(
        self,
        candidate,
        *,
        timeout_seconds,
    ):
        self.calls.append(
            (candidate, timeout_seconds)
        )
        return FakeDetailResult()


class FakeStatisticsService:
    def __init__(self):
        self.calls = []

    def build(self, detail):
        self.calls.append(detail)
        return FakeStatisticsResult()


class FakePersistenceService:
    def __init__(self):
        self.calls = []

    def persist(
        self,
        db,
        statistics,
    ):
        self.calls.append(
            (db, statistics)
        )
        return FakePersistenceResult()


class FakeDb:
    pass


class CurrentMatchEnrichmentWorkflowServiceTests(
    unittest.TestCase
):
    def test_runs_validated_pipeline_in_order(self):
        detail = FakeDetailService()
        statistics = FakeStatisticsService()
        persistence = FakePersistenceService()

        service = CurrentMatchEnrichmentWorkflowService(
            detail_service=detail,
            statistics_service=statistics,
            persistence_service=persistence,
        )

        db = FakeDb()

        result = service.run(
            db,
            candidate(),
            timeout_seconds=12.5,
        )

        self.assertEqual(
            result.status,
            "completed",
        )
        self.assertEqual(
            result.detail_status,
            "validated",
        )
        self.assertEqual(
            result.statistics_status,
            "canonicalized",
        )
        self.assertEqual(
            result.persistence_status,
            "persisted",
        )
        self.assertEqual(
            result.batch_id,
            55,
        )

        self.assertEqual(
            detail.calls[0][1],
            12.5,
        )
        self.assertEqual(
            statistics.calls[0].status,
            "validated",
        )
        self.assertIs(
            persistence.calls[0][0],
            db,
        )

    def test_unresolved_candidate_is_rejected_before_fetch(self):
        detail = FakeDetailService()

        service = CurrentMatchEnrichmentWorkflowService(
            detail_service=detail,
            statistics_service=FakeStatisticsService(),
            persistence_service=FakePersistenceService(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Only resolved",
        ):
            service.run(
                FakeDb(),
                candidate(
                    status="ambiguous",
                ),
            )

        self.assertEqual(
            detail.calls,
            [],
        )

    def test_detail_error_stops_before_statistics(self):
        class BrokenDetailService:
            def fetch(
                self,
                candidate,
                *,
                timeout_seconds,
            ):
                raise ValueError(
                    "Official MODUS players do not match."
                )

        statistics = FakeStatisticsService()
        persistence = FakePersistenceService()

        service = CurrentMatchEnrichmentWorkflowService(
            detail_service=BrokenDetailService(),
            statistics_service=statistics,
            persistence_service=persistence,
        )

        with self.assertRaisesRegex(
            ValueError,
            "do not match",
        ):
            service.run(
                FakeDb(),
                candidate(),
            )

        self.assertEqual(
            statistics.calls,
            [],
        )
        self.assertEqual(
            persistence.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
