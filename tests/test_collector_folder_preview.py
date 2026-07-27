import tempfile
import unittest
from pathlib import Path

from app.collector.folder_preview import (
    CollectorFolderPreviewService,
)


FIXTURES = (
    "external_id,competition_code,competition_name,"
    "scheduled_at,player_a_external_id,player_a_name,"
    "player_b_external_id,player_b_name\n"
    "match-1,MODUS,MODUS Super Series,"
    "2026-07-28T10:00:00,player-a,Player A,"
    "player-b,Player B\n"
)

RESULTS = (
    "match_external_id,player_a_external_id,"
    "player_b_external_id,winner_external_id,"
    "player_a_legs,player_b_legs\n"
    "match-1,player-a,player-b,player-a,4,2\n"
)


class CollectorFolderPreviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = CollectorFolderPreviewService()

    def write_file(self, folder, name, content):
        path = Path(folder) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_preview_discovers_supported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_file(directory, "fixtures.csv", FIXTURES)
            self.write_file(directory, "results.csv", RESULTS)

            preview = self.service.preview(
                folder=Path(directory),
                provider="manual-research",
            )

        self.assertEqual(
            set(preview.discovered_files),
            {"fixtures", "results"},
        )
        self.assertEqual(
            set(preview.missing_files),
            {"statistics.csv", "odds.csv"},
        )

    def test_valid_folder_is_ready_to_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_file(directory, "fixtures.csv", FIXTURES)
            self.write_file(directory, "results.csv", RESULTS)

            preview = self.service.preview(
                folder=Path(directory),
                provider="manual-research",
            )

        self.assertTrue(preview.ready_to_commit)
        self.assertEqual(preview.session.total_received, 2)
        self.assertEqual(preview.session.total_valid, 2)
        self.assertEqual(preview.mapping_error_count, 0)
        self.assertEqual(preview.session.quality_score, 100.0)

    def test_empty_folder_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.service.preview(
                folder=Path(directory),
                provider="manual-research",
            )

        self.assertFalse(preview.ready_to_commit)
        self.assertEqual(preview.discovered_files, {})
        self.assertEqual(preview.session.total_received, 0)

    def test_invalid_csv_blocks_commit(self):
        invalid_fixtures = (
            "external_id,competition_code\n"
            "match-1,MODUS\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            self.write_file(
                directory,
                "fixtures.csv",
                invalid_fixtures,
            )

            preview = self.service.preview(
                folder=Path(directory),
                provider="manual-research",
            )

        self.assertFalse(preview.ready_to_commit)
        self.assertGreater(preview.mapping_error_count, 0)

    def test_missing_folder_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.service.preview(
                folder=Path("/tmp/dartsedge-folder-does-not-exist"),
                provider="manual-research",
            )

    def test_file_path_raises_not_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_file(
                directory,
                "fixtures.csv",
                FIXTURES,
            )

            with self.assertRaises(NotADirectoryError):
                self.service.preview(
                    folder=path,
                    provider="manual-research",
                )

    def test_blank_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.service.preview(
                    folder=Path(directory),
                    provider=" ",
                )

    def test_report_dictionary_contains_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_file(directory, "fixtures.csv", FIXTURES)

            preview = self.service.preview(
                folder=Path(directory),
                provider="manual-research",
            )
            payload = preview.to_dict()

        self.assertEqual(payload["provider"], "manual-research")
        self.assertEqual(payload["totals"]["received"], 1)
        self.assertEqual(payload["totals"]["valid"], 1)
        self.assertTrue(payload["ready_to_commit"])


if __name__ == "__main__":
    unittest.main()
