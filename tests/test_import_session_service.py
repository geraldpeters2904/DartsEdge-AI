import unittest
from datetime import datetime

from app.services.import_session_service import (
    ImportSessionService,
    build_import_session,
)


def source(external_id="source-1"):
    return {
        "provider": "test-provider",
        "external_id": external_id,
        "retrieved_at": datetime(2026, 7, 27, 9, 0),
        "competition_code": "MODUS",
    }


def valid_fixture(external_id="match-1"):
    return {
        "external_id": external_id,
        "competition_code": "MODUS",
        "competition_name": "MODUS Super Series",
        "scheduled_at": datetime(2026, 7, 27, 10, 0),
        "player_a_external_id": "player-a",
        "player_a_name": "Player A",
        "player_b_external_id": "player-b",
        "player_b_name": "Player B",
        "source": source(external_id),
    }


class ImportSessionServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ImportSessionService()

    def test_valid_dry_run_is_ready_to_commit(self):
        result = self.service.validate(
            provider="test-provider",
            records_by_type={"fixtures": [valid_fixture()]},
            dry_run=True,
        )

        self.assertTrue(result.dry_run)
        self.assertTrue(result.ready_to_commit)
        self.assertEqual(result.total_received, 1)
        self.assertEqual(result.total_valid, 1)
        self.assertEqual(result.total_rejected, 0)
        self.assertEqual(result.quality_score, 100.0)

    def test_invalid_record_is_rejected(self):
        fixture = valid_fixture()
        fixture["player_b_external_id"] = "player-a"

        result = self.service.validate(
            provider="test-provider",
            records_by_type={"fixtures": [fixture]},
        )

        self.assertFalse(result.ready_to_commit)
        self.assertEqual(result.total_rejected, 1)
        self.assertGreater(result.error_count, 0)
        self.assertLess(result.quality_score, 100.0)

    def test_duplicate_fixture_is_skipped_with_warning(self):
        fixture = valid_fixture()

        result = self.service.validate(
            provider="test-provider",
            records_by_type={"fixtures": [fixture, fixture]},
        )

        self.assertEqual(result.total_received, 2)
        self.assertEqual(result.total_valid, 1)
        self.assertEqual(result.total_duplicates, 1)
        self.assertEqual(result.warning_count, 1)
        self.assertLess(result.quality_score, 100.0)

    def test_mixed_entity_types_are_validated(self):
        result_record = {
            "match_external_id": "match-1",
            "player_a_external_id": "player-a",
            "player_b_external_id": "player-b",
            "winner_external_id": "player-a",
            "player_a_legs": 4,
            "player_b_legs": 2,
            "first_180_player_external_id": "player-b",
            "source": source("result-1"),
        }

        statistics_record = {
            "match_external_id": "match-1",
            "player_external_id": "player-a",
            "three_dart_average": 94.25,
            "scores_180": 2,
            "checkout_percentage": 40.0,
            "highest_checkout": 121,
            "source": source("stats-1"),
        }

        result = self.service.validate(
            provider="test-provider",
            records_by_type={
                "fixtures": [valid_fixture()],
                "results": [result_record],
                "statistics": [statistics_record],
            },
        )

        self.assertTrue(result.ready_to_commit)
        self.assertEqual(result.total_valid, 3)
        self.assertEqual(result.quality_score, 100.0)

    def test_unsupported_entity_type_is_an_error(self):
        result = self.service.validate(
            provider="test-provider",
            records_by_type={"invented_records": [{}]},
        )

        self.assertFalse(result.ready_to_commit)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(
            result.issues[0].code,
            "unsupported_entity_type",
        )

    def test_blank_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.validate(
                provider=" ",
                records_by_type={"fixtures": [valid_fixture()]},
            )

    def test_empty_session_has_zero_quality(self):
        result = self.service.validate(
            provider="test-provider",
            records_by_type={},
        )

        self.assertFalse(result.ready_to_commit)
        self.assertEqual(result.quality_score, 0.0)

    def test_null_and_explicit_zero_remain_distinct(self):
        missing_stats = {
            "match_external_id": "match-1",
            "player_external_id": "player-a",
            "scores_180": None,
            "source": source("stats-missing"),
        }
        zero_stats = {
            "match_external_id": "match-2",
            "player_external_id": "player-a",
            "scores_180": 0,
            "source": source("stats-zero"),
        }

        result = self.service.validate(
            provider="test-provider",
            records_by_type={
                "statistics": [missing_stats, zero_stats],
            },
        )

        records = result.validated_records["statistics"]

        self.assertIsNone(records[0].scores_180)
        self.assertEqual(records[1].scores_180, 0)

    def test_result_dictionary_contains_summary(self):
        result = build_import_session(
            provider="test-provider",
            records_by_type={"fixtures": [valid_fixture()]},
        )

        payload = result.to_dict()

        self.assertEqual(payload["totals"]["received"], 1)
        self.assertEqual(payload["totals"]["valid"], 1)
        self.assertEqual(payload["entities"]["fixtures"]["valid"], 1)
        self.assertTrue(payload["ready_to_commit"])

    def test_service_performs_no_database_writes(self):
        result = self.service.validate(
            provider="test-provider",
            records_by_type={"fixtures": [valid_fixture()]},
            dry_run=False,
        )

        self.assertFalse(result.dry_run)
        self.assertTrue(result.ready_to_commit)
        self.assertEqual(result.total_valid, 1)


if __name__ == "__main__":
    unittest.main()
