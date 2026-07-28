import csv
import io
import unittest
from pathlib import Path

from app.collector.canonical_mapper import CanonicalCsvMapper
from app.services.modus_canonical_builder import ModusCanonicalBuilder


FIXTURE_FOLDER = Path("tests/fixtures/modus_folder_complete")
INCOMPLETE_FOLDER = Path("tests/fixtures/modus_folder_incomplete")


class ModusCanonicalBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = ModusCanonicalBuilder()

    def test_builds_expected_record_counts(self):
        build = self.builder.build(FIXTURE_FOLDER)

        self.assertTrue(build.ready)
        self.assertEqual(len(build.fixtures), 2)
        self.assertEqual(len(build.results), 2)
        self.assertEqual(len(build.statistics), 4)

    def test_builds_stable_ids(self):
        build = self.builder.build(FIXTURE_FOLDER)
        fixture = build.fixtures[0]

        self.assertEqual(fixture.external_id, "modus-match-18195")
        self.assertEqual(
            fixture.player_a_external_id,
            "modus-player-derek-coulson",
        )
        self.assertEqual(
            fixture.player_b_external_id,
            "modus-player-david-evans",
        )

    def test_builds_completed_fixture_context(self):
        fixture = self.builder.build(FIXTURE_FOLDER).fixtures[0]

        self.assertEqual(fixture.competition_code.value, "MODUS")
        self.assertEqual(fixture.series, "Series 14")
        self.assertEqual(fixture.week, "Week 13")
        self.assertEqual(fixture.group, "Group A")
        self.assertEqual(fixture.stage, "Group A")
        self.assertEqual(fixture.status.value, "completed")
        self.assertEqual(fixture.match_format, "Best of 7")

    def test_result_winner_matches_score(self):
        result = self.builder.build(FIXTURE_FOLDER).results[0]

        self.assertEqual(result.player_a_legs, 4)
        self.assertEqual(result.player_b_legs, 2)
        self.assertEqual(
            result.winner_external_id,
            "modus-player-derek-coulson",
        )

    def test_statistics_include_match_score_context(self):
        build = self.builder.build(FIXTURE_FOLDER)
        stats_a, stats_b = build.statistics[:2]

        self.assertEqual(stats_a.legs_won, 4)
        self.assertEqual(stats_a.legs_lost, 2)
        self.assertEqual(stats_b.legs_won, 2)
        self.assertEqual(stats_b.legs_lost, 4)

    def test_incomplete_folder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not ready"):
            self.builder.build(INCOMPLETE_FOLDER)

    def test_generates_all_three_csv_payloads(self):
        build = self.builder.build(FIXTURE_FOLDER)

        self.assertEqual(
            set(build.csv_by_type),
            {"fixtures", "results", "statistics"},
        )
        self.assertIn("external_id", build.csv_by_type["fixtures"])
        self.assertIn("winner_external_id", build.csv_by_type["results"])
        self.assertIn("scores_180", build.csv_by_type["statistics"])

    def test_generated_csv_is_accepted_by_collector_mapper(self):
        build = self.builder.build(FIXTURE_FOLDER)
        mappings, session = CanonicalCsvMapper().preview_texts(
            provider="modus-official",
            csv_by_type=build.csv_by_type,
        )

        self.assertTrue(session.ready_to_commit)
        self.assertTrue(all(mapping.valid for mapping in mappings.values()))
        self.assertEqual(len(mappings["fixtures"].records), 2)
        self.assertEqual(len(mappings["results"].records), 2)
        self.assertEqual(len(mappings["statistics"].records), 4)

    def test_csv_contains_source_provenance(self):
        build = self.builder.build(FIXTURE_FOLDER)
        rows = list(csv.DictReader(io.StringIO(build.csv_by_type["fixtures"])))

        self.assertEqual(rows[0]["source_provider"], "modus-official")
        self.assertEqual(
            rows[0]["source_external_id"],
            "modus:fixture:18195",
        )
        self.assertEqual(rows[0]["source_competition_code"], "MODUS")
        self.assertEqual(rows[0]["source_confidence"], "verified")

    def test_build_summary_serialises(self):
        payload = self.builder.build(FIXTURE_FOLDER).to_dict()

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["fixture_count"], 2)
        self.assertEqual(payload["statistics_count"], 4)


if __name__ == "__main__":
    unittest.main()
