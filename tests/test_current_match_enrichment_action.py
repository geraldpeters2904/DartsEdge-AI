import unittest
from dataclasses import dataclass
from datetime import date

from app.routes.current_match_enrichment_discovery import (
    _resolved_candidate_for_match,
)
from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)


@dataclass
class FakeReport:
    candidates: tuple


def candidate(
    *,
    internal_match_id=101,
    status="resolved",
    modus_match_id=19001,
):
    return EnrichmentCandidate(
        internal_match_id=internal_match_id,
        fixture_date=date(2026, 8, 1),
        player_a="Player A",
        player_b="Player B",
        stage="Group A",
        resolved_modus_match_id=modus_match_id,
        candidate_modus_match_ids=(
            (modus_match_id,)
            if modus_match_id is not None
            else ()
        ),
        status=status,
        message="Candidate.",
    )


class CurrentMatchEnrichmentActionTests(
    unittest.TestCase
):
    def test_resolved_candidate_is_selected_by_internal_id(self):
        expected = candidate()

        report = FakeReport(
            candidates=(
                candidate(
                    internal_match_id=99,
                ),
                expected,
            )
        )

        result = _resolved_candidate_for_match(
            report,
            101,
        )

        self.assertIs(
            result,
            expected,
        )

    def test_missing_candidate_is_rejected(self):
        report = FakeReport(
            candidates=()
        )

        with self.assertRaisesRegex(
            ValueError,
            "no longer present",
        ):
            _resolved_candidate_for_match(
                report,
                101,
            )

    def test_ambiguous_candidate_is_rejected(self):
        report = FakeReport(
            candidates=(
                candidate(
                    status="ambiguous",
                    modus_match_id=None,
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "not currently resolved",
        ):
            _resolved_candidate_for_match(
                report,
                101,
            )

    def test_resolved_candidate_without_modus_id_is_rejected(self):
        report = FakeReport(
            candidates=(
                candidate(
                    modus_match_id=None,
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "has no official MODUS match ID",
        ):
            _resolved_candidate_for_match(
                report,
                101,
            )


if __name__ == "__main__":
    unittest.main()
