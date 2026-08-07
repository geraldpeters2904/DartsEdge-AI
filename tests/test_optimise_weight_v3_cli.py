import unittest

from app.cli import build_parser


class OptimiseWeightV3CliTests(
    unittest.TestCase
):
    def test_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "optimise-weight-v3",
            "--feature",
            "scoring_power",
            "--weights",
            "0.10",
            "0.15",
            "0.20",
        ])

        self.assertEqual(
            args.model_command,
            "optimise-weight-v3",
        )
        self.assertEqual(
            args.feature,
            "scoring_power",
        )
        self.assertEqual(
            args.weights,
            [0.10, 0.15, 0.20],
        )


if __name__ == "__main__":
    unittest.main()
