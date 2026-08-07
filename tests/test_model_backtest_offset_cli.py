import unittest

from app.cli import build_parser


class ModelBacktestOffsetCliTests(unittest.TestCase):
    def test_backtest_offset_is_parsed(self):
        args = build_parser().parse_args([
            "model",
            "backtest",
            "--model",
            "transparent",
            "--offset",
            "1000",
            "--limit",
            "100",
        ])

        self.assertEqual(args.offset, 1000)
        self.assertEqual(args.limit, 100)


if __name__ == "__main__":
    unittest.main()
