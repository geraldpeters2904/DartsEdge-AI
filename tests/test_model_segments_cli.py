import unittest

from app.cli import build_parser


class ModelSegmentsCliTests(unittest.TestCase):
    def test_segments_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "segments",
            "--offset",
            "1000",
            "--limit",
            "500",
        ])

        self.assertEqual(
            args.model_command,
            "segments",
        )
        self.assertEqual(args.offset, 1000)
        self.assertEqual(args.limit, 500)


if __name__ == "__main__":
    unittest.main()
