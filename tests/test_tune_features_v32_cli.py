import unittest

from app.cli import build_parser


class TuneFeaturesV32CliTests(
    unittest.TestCase
):
    def test_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "tune-features-v32",
            "--features",
            "scoring_consistency",
            "--training-offsets",
            "500",
            "1000",
            "1500",
            "--validation-offsets",
            "2000",
            "2500",
            "3000",
        ])

        self.assertEqual(
            args.model_command,
            "tune-features-v32",
        )

        self.assertEqual(
            args.features,
            ["scoring_consistency"],
        )


if __name__ == "__main__":
    unittest.main()
