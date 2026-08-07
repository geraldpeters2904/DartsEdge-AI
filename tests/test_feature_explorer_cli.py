import unittest

from app.cli import build_parser


class FeatureExplorerCliTests(unittest.TestCase):
    def test_feature_player_parser(self):
        args = build_parser().parse_args([
            "feature",
            "player",
            "--name",
            "Scott Taylor",
        ])

        self.assertEqual(
            args.command,
            "feature",
        )
        self.assertEqual(
            args.feature_command,
            "player",
        )
        self.assertEqual(
            args.name,
            "Scott Taylor",
        )


if __name__ == "__main__":
    unittest.main()
