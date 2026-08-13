import os
import unittest
from unittest.mock import patch

from app.services.mobile_access_service import (
    mobile_access_configured,
    mobile_session_token,
    valid_mobile_session,
    validate_mobile_credentials,
)


class MobileAccessServiceTests(
    unittest.TestCase
):
    @patch.dict(
        os.environ,
        {},
        clear=True,
    )
    def test_unconfigured_fails_closed(
        self,
    ):
        self.assertFalse(
            mobile_access_configured()
        )

        self.assertFalse(
            validate_mobile_credentials(
                username="gerald",
                password="anything",
            )
        )

        self.assertIsNone(
            mobile_session_token()
        )

        self.assertFalse(
            valid_mobile_session(
                "anything"
            )
        )

    @patch.dict(
        os.environ,
        {
            "DARTSEDGE_MOBILE_USERNAME": "gerald",
            "DARTSEDGE_MOBILE_PASSWORD": "correct-password",
        },
        clear=True,
    )
    def test_valid_credentials_and_session(
        self,
    ):
        self.assertTrue(
            mobile_access_configured()
        )

        self.assertTrue(
            validate_mobile_credentials(
                username="gerald",
                password="correct-password",
            )
        )

        token = (
            mobile_session_token()
        )

        self.assertTrue(
            token
        )

        self.assertTrue(
            valid_mobile_session(
                token
            )
        )

    @patch.dict(
        os.environ,
        {
            "DARTSEDGE_MOBILE_USERNAME": "gerald",
            "DARTSEDGE_MOBILE_PASSWORD": "correct-password",
        },
        clear=True,
    )
    def test_invalid_credentials_are_rejected(
        self,
    ):
        self.assertFalse(
            validate_mobile_credentials(
                username="gerald",
                password="wrong-password",
            )
        )

        self.assertFalse(
            valid_mobile_session(
                "not-the-right-token"
            )
        )


if __name__ == "__main__":
    unittest.main()
