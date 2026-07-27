import subprocess
import sys
import unittest


class CollectorCliTests(unittest.TestCase):

    def test_help_command(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.collector.cli",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("preview", result.stdout)

    def test_preview_command_runs(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.collector.cli",
                "preview",
                "--folder",
                "data_templates/canonical",
                "--provider",
                "manual-research",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)

        self.assertIn(
            "DartsEdge Collector Preview",
            result.stdout,
        )

        self.assertIn(
            "Quality Score",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
