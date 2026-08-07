import unittest

from app.cli import build_parser


class ModelBenchmarkCliTests(unittest.TestCase):
    def test_benchmark_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "model",
            "benchmark",
            "--offset",
            "500",
            "--window-size",
            "200",
            "--windows",
            "4",
            "--step",
            "500",
        ])

        self.assertEqual(
            args.model_command,
            "benchmark",
        )
        self.assertEqual(args.offset, 500)
        self.assertEqual(
            args.window_size,
            200,
        )
        self.assertEqual(args.windows, 4)
        self.assertEqual(args.step, 500)


if __name__ == "__main__":
    unittest.main()
