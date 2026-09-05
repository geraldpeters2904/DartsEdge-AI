import unittest

from fastapi.testclient import TestClient

from app.main import app


class ValueBoardUITests(unittest.TestCase):

    def test_template_exposes_live_value_fields(self):
        with open(
            "app/templates/value_board.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn("Bookmaker", text)
        self.assertIn("EV", text)
        self.assertIn("Status", text)
        self.assertIn('row.action == "Consider"', text)
        self.assertIn("🟢 Consider", text)

    def test_route_still_renders(self):
        response = TestClient(app).get("/value-board")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Daily Value Board", response.text)


if __name__ == "__main__":
    unittest.main()
