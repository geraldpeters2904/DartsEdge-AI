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

    def test_diagnostics_route_includes_live_capture_result(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        from app.routes.diagnostics import diagnostics_page

        capture_result = SimpleNamespace(
            name="bookmaker-capture",
            success=False,
            message="Paddy Power: 2 event(s) failed.",
        )
        worker_status = SimpleNamespace(
            successful_cycles=0,
            failed_cycles=1,
            last_results=[capture_result],
        )
        response = MagicMock()

        with patch(
            "app.routes.diagnostics.build_diagnostics",
            return_value={"overall_status": "healthy"},
        ), patch(
            "app.routes.diagnostics.unified_sync_worker.status",
            return_value=worker_status,
        ), patch(
            "app.routes.diagnostics.templates.TemplateResponse",
            return_value=response,
        ) as render:
            result = diagnostics_page(
                request=MagicMock(),
                db=MagicMock(),
            )

        self.assertIs(result, response)
        render.assert_called_once()
        self.assertEqual(
            render.call_args.args[0],
            "diagnostics.html",
        )

        diagnostics = render.call_args.args[1]["diagnostics"]
        sync = diagnostics["monitors"]["unified_sync"]

        self.assertEqual(sync["failed_cycles"], 1)
        self.assertEqual(
            sync["last_results"],
            [{
                "name": "bookmaker-capture",
                "success": False,
                "message": "Paddy Power: 2 event(s) failed.",
            }],
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
