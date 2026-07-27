import unittest
from pathlib import Path

from app.collector.canonical_mapper import CanonicalCsvMapper


TEMPLATE_DIR = Path("data_templates/canonical")


class CollectorTemplateTests(unittest.TestCase):
    def setUp(self):
        self.mapper = CanonicalCsvMapper()

    def read_template(self, name):
        return (TEMPLATE_DIR / name).read_text(encoding="utf-8")

    def test_expected_template_files_exist(self):
        expected = {
            "fixtures.csv",
            "results.csv",
            "statistics.csv",
            "odds.csv",
            "README.md",
        }

        existing = {
            path.name
            for path in TEMPLATE_DIR.iterdir()
            if path.is_file()
        }

        self.assertTrue(expected.issubset(existing))

    def test_fixtures_template_maps(self):
        result = self.mapper.map_text(
            entity_type="fixtures",
            csv_text=self.read_template("fixtures.csv"),
            provider="manual-research",
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)

    def test_results_template_maps(self):
        result = self.mapper.map_text(
            entity_type="results",
            csv_text=self.read_template("results.csv"),
            provider="manual-research",
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(
            result.records[0].first_180_player_external_id,
            "player-scott-taylor",
        )

    def test_statistics_template_maps(self):
        result = self.mapper.map_text(
            entity_type="statistics",
            csv_text=self.read_template("statistics.csv"),
            provider="manual-research",
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 2)

    def test_odds_template_maps(self):
        result = self.mapper.map_text(
            entity_type="odds",
            csv_text=self.read_template("odds.csv"),
            provider="manual-odds",
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 2)


if __name__ == "__main__":
    unittest.main()


class CollectorTemplateSessionTests(unittest.TestCase):
    def setUp(self):
        self.mapper = CanonicalCsvMapper()

    def read_template(self, name):
        return (TEMPLATE_DIR / name).read_text(encoding="utf-8")

    def test_all_templates_create_clean_import_session(self):
        mappings, session = self.mapper.preview_texts(
            provider="manual-research",
            csv_by_type={
                "fixtures": self.read_template("fixtures.csv"),
                "results": self.read_template("results.csv"),
                "statistics": self.read_template("statistics.csv"),
                "odds": self.read_template("odds.csv"),
            },
        )

        self.assertTrue(
            all(mapping.valid for mapping in mappings.values())
        )
        self.assertTrue(session.ready_to_commit)
        self.assertEqual(session.total_received, 6)
        self.assertEqual(session.total_valid, 6)
        self.assertEqual(session.total_rejected, 0)
        self.assertEqual(session.total_duplicates, 0)
        self.assertEqual(session.error_count, 0)
        self.assertEqual(session.warning_count, 0)
        self.assertEqual(session.quality_score, 100.0)
