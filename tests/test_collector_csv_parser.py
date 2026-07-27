import tempfile
import unittest
from pathlib import Path

from app.collector.csv_parser import CanonicalCsvParser


class CanonicalCsvParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = CanonicalCsvParser()

    def test_valid_csv_is_parsed(self):
        csv_text = (
            "external_id,player_a,player_b\n"
            "match-1,Lewis Pride,Scott Taylor\n"
        )

        result = self.parser.parse_text(
            csv_text,
            required_headers=(
                "external_id",
                "player_a",
                "player_b",
            ),
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(
            result.records[0]["external_id"],
            "match-1",
        )

    def test_headers_are_normalised(self):
        csv_text = (
            "External ID,Player-A,Player B\n"
            "match-1,Player A,Player B\n"
        )

        result = self.parser.parse_text(csv_text)

        self.assertEqual(
            result.headers,
            ["external_id", "player_a", "player_b"],
        )

    def test_missing_required_header_is_reported(self):
        result = self.parser.parse_text(
            "external_id\nmatch-1\n",
            required_headers=("external_id", "player_a"),
        )

        self.assertFalse(result.valid)
        self.assertTrue(
            any(
                issue.code == "missing_required_header"
                for issue in result.issues
            )
        )

    def test_unknown_header_is_rejected(self):
        result = self.parser.parse_text(
            "external_id,invented\nmatch-1,value\n",
            allowed_headers=("external_id",),
        )

        self.assertFalse(result.valid)
        self.assertEqual(
            result.issues[0].code,
            "unknown_header",
        )

    def test_missing_required_value_is_reported(self):
        result = self.parser.parse_text(
            "external_id,player_a\nmatch-1,\n",
            required_headers=("external_id", "player_a"),
        )

        self.assertFalse(result.valid)
        self.assertEqual(len(result.records), 0)
        self.assertEqual(
            result.issues[0].row_number,
            2,
        )

    def test_blank_rows_are_ignored(self):
        result = self.parser.parse_text(
            "external_id,player_a\n"
            "match-1,Player A\n"
            ",\n"
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)

    def test_null_words_become_none(self):
        result = self.parser.parse_text(
            "external_id,first_180\n"
            "match-1,N/A\n"
        )

        self.assertIsNone(
            result.records[0]["first_180"]
        )

    def test_empty_file_returns_warning(self):
        result = self.parser.parse_text(
            "external_id,player_a\n"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(
            result.issues[0].code,
            "empty_file",
        )

    def test_file_parser_reads_utf8_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.csv"
            path.write_text(
                "external_id,player_a\n"
                "match-1,Player A\n",
                encoding="utf-8",
            )

            result = self.parser.parse_file(path)

        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)

    def test_duplicate_headers_are_rejected(self):
        result = self.parser.parse_text(
            "external_id,external_id\nmatch-1,match-2\n"
        )

        self.assertFalse(result.valid)
        self.assertEqual(
            result.issues[0].code,
            "duplicate_header",
        )


if __name__ == "__main__":
    unittest.main()
