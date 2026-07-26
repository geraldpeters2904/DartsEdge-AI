import json
import unittest
from types import SimpleNamespace

from app.services.player_intelligence_service import DEFAULT_PROFILES, FACTOR_LABELS, profile_weights, validate_weights


class PlayerIntelligenceTests(unittest.TestCase):
    def test_all_default_profiles_total_100(self):
        for _, _, weights, _ in DEFAULT_PROFILES:
            validate_weights(weights)
            self.assertEqual(sum(weights.values()), 100)

    def test_invalid_total_is_rejected(self):
        weights = {key: 0 for key in FACTOR_LABELS}
        with self.assertRaises(ValueError):
            validate_weights(weights)

    def test_missing_factor_is_rejected(self):
        weights = dict(DEFAULT_PROFILES[0][2])
        weights.pop("elo")
        with self.assertRaises(ValueError):
            validate_weights(weights)

    def test_json_profile_round_trip(self):
        weights = DEFAULT_PROFILES[0][2]
        profile = SimpleNamespace(weights_json=json.dumps(weights))
        self.assertEqual(profile_weights(profile), {key: float(value) for key, value in weights.items()})

    def test_shadow_mode_route_registered(self):
        from app.main import app
        paths = {route.path for route in app.routes}
        self.assertIn("/player-intelligence", paths)


if __name__ == "__main__":
    unittest.main()
