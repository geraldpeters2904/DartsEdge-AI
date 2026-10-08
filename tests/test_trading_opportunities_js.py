import unittest
from pathlib import Path


class TradingOpportunitiesJavaScriptTests(unittest.TestCase):

    def test_stale_evaluations_are_ignored(self):
        script = Path(
            "app/static/js/trading_opportunities.js"
        ).read_text(encoding="utf-8")

        self.assertIn("let evaluationVersion = 0;", script)
        self.assertIn("const version = ++evaluationVersion;", script)
        self.assertIn("if (version !== evaluationVersion)", script)


if __name__ == "__main__":
    unittest.main()
