import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.current_match_enrichment_persistence_service import (
    CurrentMatchEnrichmentPersistenceService,
)
from app.services.current_match_enrichment_statistics_service import (
    CurrentMatchEnrichmentStatisticsResult,
)


class CurrentMatchEnrichmentResultIntegrityTests(unittest.TestCase):
    def test_persistence_refuses_statistics_without_canonical_result(self):
        statistics = (
            SimpleNamespace(
                match_external_id="modus-match-20001",
                source=SimpleNamespace(provider="modus-official"),
            ),
            SimpleNamespace(
                match_external_id="modus-match-20001",
                source=SimpleNamespace(provider="modus-official"),
            ),
        )
        payload = CurrentMatchEnrichmentStatisticsResult(
            internal_match_id=1,
            modus_match_id=20001,
            match_external_id="modus-match-20001",
            statistics=statistics,
            status="canonicalized",
            message="test",
            result=None,
        )
        service = CurrentMatchEnrichmentPersistenceService(
            statistics_committer=Mock(),
            result_committer=Mock(),
        )
        with self.assertRaisesRegex(
            ValueError,
            "without a canonical match result",
        ):
            service.persist(Mock(), payload)


if __name__ == "__main__":
    unittest.main()
