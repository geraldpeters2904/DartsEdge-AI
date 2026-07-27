import unittest
from datetime import datetime

from app.collector.canonical_mapper import CanonicalCsvMapper


FIXTURES = (
    "external_id,competition_code,competition_name,"
    "scheduled_at,player_a_external_id,player_a_name,"
    "player_b_external_id,player_b_name\n"
    "match-1,MODUS,MODUS Super Series,"
    "2026-07-28T10:00:00,player-a,Player A,"
    "player-b,Player B\n"
)


class CanonicalCsvMapperTests(unittest.TestCase):
    def setUp(self):
        self.mapper = CanonicalCsvMapper()

    def test_fixture_maps_to_canonical_model(self):
        result = self.mapper.map_text(
            entity_type="fixtures",
            csv_text=FIXTURES,
            provider="manual-research",
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(
            result.records[0].external_id,
            "match-1",
        )

    def test_source_is_created_automatically(self):
        result = self.mapper.map_text(
            entity_type="fixtures",
            csv_text=FIXTURES,
            provider="manual-research",
            retrieved_at=datetime(2026, 7, 27, 9, 0),
        )

        source = result.records[0].source
        self.assertEqual(
            source.provider,
            "manual-research",
        )
        self.assertEqual(
            source.external_id,
            "match-1",
        )

    def test_invalid_integer_is_reported(self):
        results = (
            "match_external_id,player_a_external_id,"
            "player_b_external_id,winner_external_id,"
            "player_a_legs,player_b_legs\n"
            "match-1,player-a,player-b,player-a,"
            "four,2\n"
        )

        result = self.mapper.map_text(
            entity_type="results",
            csv_text=results,
            provider="manual-research",
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.error_count, 1)

    def test_statistics_preserve_null_and_zero(self):
        statistics = (
            "match_external_id,player_external_id,scores_180\n"
            "match-1,player-a,\n"
            "match-2,player-a,0\n"
        )

        result = self.mapper.map_text(
            entity_type="statistics",
            csv_text=statistics,
            provider="manual-research",
        )

        self.assertTrue(result.valid)
        self.assertIsNone(result.records[0].scores_180)
        self.assertEqual(result.records[1].scores_180, 0)

    def test_first_180_is_supported(self):
        results = (
            "match_external_id,player_a_external_id,"
            "player_b_external_id,winner_external_id,"
            "player_a_legs,player_b_legs,"
            "first_180_player_external_id\n"
            "match-1,player-a,player-b,player-a,"
            "4,2,player-b\n"
        )

        result = self.mapper.map_text(
            entity_type="results",
            csv_text=results,
            provider="manual-research",
        )

        self.assertTrue(result.valid)
        self.assertEqual(
            result.records[0].first_180_player_external_id,
            "player-b",
        )

    def test_invalid_checkout_percentage_is_rejected(self):
        statistics = (
            "match_external_id,player_external_id,"
            "checkout_percentage\n"
            "match-1,player-a,120\n"
        )

        result = self.mapper.map_text(
            entity_type="statistics",
            csv_text=statistics,
            provider="manual-research",
        )

        self.assertFalse(result.valid)

    def test_odds_are_converted_to_float(self):
        odds = (
            "match_external_id,market,selection_name,"
            "bookmaker,decimal_odds,captured_at\n"
            "match-1,match_winner,Player A,"
            "Example Bookmaker,1.80,"
            "2026-07-28T09:00:00\n"
        )

        result = self.mapper.map_text(
            entity_type="odds",
            csv_text=odds,
            provider="manual-odds",
        )

        self.assertTrue(result.valid)
        self.assertEqual(
            result.records[0].decimal_odds,
            1.8,
        )

    def test_unknown_csv_header_is_rejected(self):
        text = FIXTURES.replace(
            "player_b_name",
            "player_b_name,invented_field",
        ).replace(
            "player-b,Player B",
            "player-b,Player B,value",
        )

        result = self.mapper.map_text(
            entity_type="fixtures",
            csv_text=text,
            provider="manual-research",
        )

        self.assertFalse(result.valid)

    def test_multiple_files_feed_import_session(self):
        results = (
            "match_external_id,player_a_external_id,"
            "player_b_external_id,winner_external_id,"
            "player_a_legs,player_b_legs\n"
            "match-1,player-a,player-b,player-a,4,2\n"
        )

        mappings, session = self.mapper.preview_texts(
            provider="manual-research",
            csv_by_type={
                "fixtures": FIXTURES,
                "results": results,
            },
        )

        self.assertTrue(mappings["fixtures"].valid)
        self.assertTrue(mappings["results"].valid)
        self.assertTrue(session.ready_to_commit)
        self.assertEqual(session.total_valid, 2)

    def test_duplicate_records_reach_import_session(self):
        duplicate_csv = FIXTURES + (
            "match-1,MODUS,MODUS Super Series,"
            "2026-07-28T10:00:00,player-a,Player A,"
            "player-b,Player B\n"
        )

        _, session = self.mapper.preview_texts(
            provider="manual-research",
            csv_by_type={"fixtures": duplicate_csv},
        )

        self.assertEqual(session.total_duplicates, 1)


if __name__ == "__main__":
    unittest.main()
