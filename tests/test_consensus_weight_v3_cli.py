import unittest

from app.cli import build_parser


class ConsensusWeightV3CliTests(
    unittest.TestCase
):
    def test_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "consensus-weight-v3",
            "--feature",
            "recent_form",
            "--weights",
            "0.00",
            "0.03",
            "0.06",
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
            "consensus-weight-v3",
        )
        self.assertEqual(
            args.feature,
            "recent_form",
        )
        self.assertEqual(
            args.training_offsets,
            [500, 1000, 1500],
        )
        self.assertEqual(
            args.validation_offsets,
            [2000, 2500, 3000],
        )


if __name__ == "__main__":
    unittest.main()
