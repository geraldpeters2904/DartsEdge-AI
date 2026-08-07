import unittest

from app.cli import build_parser


class TransparentV3ContributionCliTests(
    unittest.TestCase
):
    def test_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "contribution-v3",
            "--offset",
            "1000",
            "--limit",
            "200",
        ])

        self.assertEqual(
            args.model_command,
            "contribution-v3",
        )
        self.assertEqual(args.offset, 1000)
        self.assertEqual(args.limit, 200)


if __name__ == "__main__":
    unittest.main()
