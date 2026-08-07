import unittest

from app.cli import build_parser


class ModelCompareOffsetLimitCliTests(
    unittest.TestCase
):
    def test_compare_offset_and_limit_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "compare",
            "--offset",
            "1000",
            "--limit",
            "100",
        ])

        self.assertEqual(
            args.model_command,
            "compare",
        )
        self.assertEqual(args.offset, 1000)
        self.assertEqual(args.limit, 100)

    def test_compare_defaults_cover_all_matches(self):
        args = build_parser().parse_args([
            "model",
            "compare",
        ])

        self.assertEqual(args.offset, 0)
        self.assertIsNone(args.limit)


if __name__ == "__main__":
    unittest.main()
