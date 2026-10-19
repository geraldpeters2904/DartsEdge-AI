import unittest

from starlette.requests import Request

from app.templates_config import templates


class DiagnosticsCapturePanelTests(unittest.TestCase):

    def render(self, results):
        diagnostics = {
            "overall_status": "healthy",
            "release": {
                "version": "test",
                "build": "test",
                "release": "test",
                "name": "Test",
            },
            "runtime": {
                "python": "test",
                "fastapi": "test",
                "starlette": "test",
                "sqlalchemy": "test",
                "httpx": "test",
                "platform": "test",
            },
            "checks": [],
            "monitors": {
                "unified_sync": {
                    "successful_cycles": 0,
                    "failed_cycles": 0,
                    "last_results": results,
                },
            },
        }

        return templates.env.get_template(
            "diagnostics.html"
        ).render(
            diagnostics=diagnostics,
            request=Request({
                "type": "http",
                "method": "GET",
                "path": "/diagnostics",
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "scheme": "http",
            }),
        )

    def test_failed_capture_is_displayed(self):
        html = self.render([
            {
                "name": "bookmaker-capture",
                "success": False,
                "message": "Paddy Power: 2 event(s) failed.",
            },
        ])

        self.assertIn("Bookmaker Capture Status", html)
        self.assertIn("Paddy Power: 2 event(s) failed.", html)
        self.assertIn("Capture failed", html)

    def test_successful_capture_is_displayed(self):
        html = self.render([
            {
                "name": "bookmaker-capture",
                "success": True,
                "message": "Paddy Power capture completed.",
            },
        ])

        self.assertIn("Bookmaker Capture Status", html)
        self.assertIn("Capture successful", html)
        self.assertIn("Paddy Power capture completed.", html)

    def test_no_capture_results_is_not_reported_as_success(self):
        html = self.render([])

        self.assertIn("Bookmaker Capture Status", html)
        self.assertIn("No capture result available", html)
        self.assertNotIn("Capture successful", html)


if __name__ == "__main__":
    unittest.main()
