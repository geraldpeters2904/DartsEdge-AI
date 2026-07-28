import os
import unittest
from unittest.mock import patch

from app.providers.adapters.modus_official.policy import ModusConnectorPolicy


class ModusConnectorPolicyTests(unittest.TestCase):
    def test_automation_is_disabled_by_default(self):
        policy = ModusConnectorPolicy()
        self.assertFalse(policy.automation_allowed)
        with self.assertRaises(RuntimeError):
            policy.assert_automation_allowed()

    def test_permission_and_enablement_are_both_required(self):
        self.assertFalse(
            ModusConnectorPolicy(
                enabled=True,
                permission_confirmed=False,
            ).automation_allowed
        )
        self.assertTrue(
            ModusConnectorPolicy(
                enabled=True,
                permission_confirmed=True,
            ).automation_allowed
        )

    def test_environment_configuration(self):
        env = {
            "DARTSEDGE_MODUS_CONNECTOR_ENABLED": "true",
            "DARTSEDGE_MODUS_PERMISSION_CONFIRMED": "true",
            "DARTSEDGE_MODUS_MIN_REQUEST_INTERVAL_SECONDS": "7",
            "DARTSEDGE_MODUS_MAX_MATCHES_PER_RUN": "25",
        }
        with patch.dict(os.environ, env, clear=False):
            policy = ModusConnectorPolicy.from_environment()
        self.assertTrue(policy.automation_allowed)
        self.assertEqual(policy.minimum_interval_seconds, 7.0)
        self.assertEqual(policy.max_matches_per_run, 25)


if __name__ == "__main__":
    unittest.main()
