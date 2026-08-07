import unittest

from app.cli import build_parser


class ModularCliTests(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_existing_warehouse_sync_syntax_is_preserved(self):
        args = self.parser.parse_args([
            "warehouse",
            "sync-all",
            "--catalog",
            "/tmp/results.html",
        ])

        self.assertEqual(
            args.command,
            "warehouse",
        )
        self.assertEqual(
            args.warehouse_command,
            "sync-all",
        )
        self.assertEqual(
            args.catalog,
            "/tmp/results.html",
        )

    def test_existing_warehouse_status_syntax_is_preserved(self):
        args = self.parser.parse_args([
            "warehouse",
            "status",
            "--catalog",
            "/tmp/results.html",
        ])

        self.assertEqual(
            args.warehouse_command,
            "status",
        )

    def test_model_backtest_parser(self):
        args = self.parser.parse_args([
            "model",
            "backtest",
            "--model",
            "transparent",
            "--limit",
            "100",
        ])

        self.assertEqual(
            args.model_command,
            "backtest",
        )
        self.assertEqual(
            args.model,
            "transparent",
        )
        self.assertEqual(
            args.limit,
            100,
        )

    def test_model_compare_parser(self):
        args = self.parser.parse_args([
            "model",
            "compare",
            "--models",
            "transparent",
        ])

        self.assertEqual(
            args.model_command,
            "compare",
        )
        self.assertEqual(
            args.models,
            ["transparent"],
        )

    def test_model_laboratory_match_parser(self):
        args = self.parser.parse_args([
            "model",
            "laboratory",
            "--match",
            "18195",
        ])

        self.assertEqual(
            args.model_command,
            "laboratory",
        )
        self.assertEqual(
            args.match,
            18195,
        )


if __name__ == "__main__":
    unittest.main()
