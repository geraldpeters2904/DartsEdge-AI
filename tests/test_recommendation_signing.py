import unittest
from unittest.mock import patch


class RecommendationSigningTests(unittest.TestCase):

    def test_missing_secret_disables_signing(self):
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(
                sign_recommendation(
                    fixture_id=123,
                    market="Match Winner",
                    selection="Player A",
                    odds=2.1,
                    effective_stake=5.0,
                )
            )

    def test_valid_recommendation_can_be_verified(self):
        from app.services.recommendation_signing_service import (
            sign_recommendation,
            verify_recommendation,
        )

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "dartsedge-test-signing-key-32-bytes-minimum"},
        ):
            token = sign_recommendation(
                fixture_id=123,
                market="Match Winner",
                selection="Player A",
                odds=2.1,
                effective_stake=5.0,
            )

            self.assertIsNotNone(token)

            result = verify_recommendation(token)

            self.assertIsNotNone(result)
            self.assertEqual(result["fixture_id"], 123)
            self.assertEqual(result["effective_stake"], 5.0)

    def test_tampered_token_is_rejected(self):
        from app.services.recommendation_signing_service import (
            sign_recommendation,
            verify_recommendation,
        )

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "dartsedge-test-signing-key-32-bytes-minimum"},
        ):
            token = sign_recommendation(
                fixture_id=123,
                market="Match Winner",
                selection="Player A",
                odds=2.1,
                effective_stake=5.0,
            )

            self.assertIsNone(
                verify_recommendation(token + "tampered")
            )

    def test_expired_token_is_rejected(self):
        from app.services.recommendation_signing_service import (
            sign_recommendation,
            verify_recommendation,
        )

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "dartsedge-test-signing-key-32-bytes-minimum"},
        ):
            with patch(
                "app.services.recommendation_signing_service.time.time",
                return_value=1000,
            ):
                token = sign_recommendation(
                    fixture_id=123,
                    market="Match Winner",
                    selection="Player A",
                    odds=2.1,
                    effective_stake=5.0,
                )

            with patch(
                "app.services.recommendation_signing_service.time.time",
                return_value=5000,
            ):
                self.assertIsNone(verify_recommendation(token))


if __name__ == "__main__":
    unittest.main()
