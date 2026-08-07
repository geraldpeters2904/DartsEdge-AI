import unittest

from app.cli import build_parser


class WarehouseHealthCliTests(unittest.TestCase):
    def test_health_arguments_are_parsed(self):
        args = build_parser().parse_args([
            "warehouse",
            "health",
            "--catalog",
            "/tmp/results.html",
        ])

        self.assertEqual(args.warehouse_command, "health")
        self.assertEqual(args.catalog, "/tmp/results.html")


if __name__ == "__main__":
    unittest.main()
