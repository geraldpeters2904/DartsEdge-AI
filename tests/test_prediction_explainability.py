import unittest

from app.services.prediction_explainability_service import build_explanation_from_comparison


def component(key, label, weight, score, contribution, available=True):
    return {
        "key": key,
        "label": label,
        "weight": weight,
        "score": score,
        "contribution": contribution,
        "available": available,
    }


class PredictionExplainabilityTests(unittest.TestCase):
    def comparison(self):
        return {
            "profile": {"id": 1, "name": "Default", "version": 1},
            "rating_gap": 10.0,
            "player_a": {
                "player": "Alpha",
                "rating": 72.0,
                "data_matches": 24,
                "components": [
                    component("elo", "Elo strength", 50, 80, 40),
                    component("recent_form", "Recent form", 30, 70, 21),
                    component("head_to_head", "Head-to-head", 20, 50, 10, False),
                ],
            },
            "player_b": {
                "player": "Bravo",
                "rating": 62.0,
                "data_matches": 18,
                "components": [
                    component("elo", "Elo strength", 50, 60, 30),
                    component("recent_form", "Recent form", 30, 75, 22.5),
                    component("head_to_head", "Head-to-head", 20, 50, 10, False),
                ],
            },
        }

    def test_selects_official_favourite(self):
        result = build_explanation_from_comparison(self.comparison(), 0.67)
        self.assertEqual(result["selection"], "Alpha")
        self.assertEqual(result["official_probability"], 67.0)

    def test_positive_factors_are_ranked_by_impact(self):
        result = build_explanation_from_comparison(self.comparison(), 0.67)
        self.assertEqual(result["positive_factors"][0]["key"], "elo")

    def test_negative_factor_is_reported(self):
        result = build_explanation_from_comparison(self.comparison(), 0.67)
        self.assertEqual(result["negative_factors"][0]["key"], "recent_form")

    def test_unavailable_factor_reduces_explanation_confidence(self):
        result = build_explanation_from_comparison(self.comparison(), 0.67)
        self.assertEqual(result["explanation_confidence"]["coverage_percent"], 80.0)
        self.assertEqual(result["explanation_confidence"]["label"], "Medium")
        self.assertEqual(result["unavailable_factors"][0]["key"], "head_to_head")

    def test_shadow_mode_and_schema_are_explicit(self):
        result = build_explanation_from_comparison(self.comparison(), 0.67)
        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["mode"], "shadow")
        self.assertTrue(result["official_model_unchanged"])


if __name__ == "__main__":
    unittest.main()
