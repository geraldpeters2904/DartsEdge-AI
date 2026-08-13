import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.mobile_pairing_display_service import (
    build_mobile_pairing_display,
)


class MobilePairingDisplayServiceTests(
    unittest.TestCase
):
    @patch(
        "app.services."
        "mobile_pairing_display_service."
        "local_network_ip",
        return_value="192.168.0.37",
    )
    @patch(
        "app.services."
        "mobile_pairing_display_service."
        "create_mobile_pairing_token",
        return_value="abc123",
    )
    def test_display_contains_pairing_url_and_qr(
        self,
        token,
        ip,
    ):
        display = (
            build_mobile_pairing_display()
        )

        self.assertEqual(
            display.pairing_url,
            (
                "http://192.168.0.37:8000/"
                "mobile-pair/abc123"
            ),
        )

        self.assertTrue(
            display.qr_data_uri.startswith(
                "data:image/png;base64,"
            )
        )

        self.assertEqual(
            display.expires_minutes,
            10,
        )


class MobilePairingTemplateTests(
    unittest.TestCase
):
    def test_template_contains_pairing_qr(self):
        text = Path(
            "app/templates/mobile_pairing.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Pair iPhone / iPad",
            text,
        )

        self.assertIn(
            "pairing.qr_data_uri",
            text,
        )

        self.assertIn(
            "works once",
            text,
        )


if __name__ == "__main__":
    unittest.main()
