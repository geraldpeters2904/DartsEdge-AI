import unittest
from pathlib import Path


TEMPLATE_PATH = Path(
    "app/templates/prediction_centre.html"
)

CARD_COMPONENT_PATH = Path(
    "app/templates/components/pro_prediction_card.html"
)


class PredictionCentreInteractiveTests(unittest.TestCase):
    def read_centre_template(self) -> str:
        return TEMPLATE_PATH.read_text(
            encoding="utf-8"
        )

    def read_card_component(self) -> str:
        return CARD_COMPONENT_PATH.read_text(
            encoding="utf-8"
        )

    def test_template_contains_fixture_controls(self):
        text = self.read_centre_template()

        for control_id in (
            'id="pc-competition"',
            'id="pc-status"',
            'id="pc-sort"',
            'id="pc-positive-only"',
            'id="pc-reset"',
            'id="pc-visible-count"',
            'id="prediction-card-list"',
            'id="prediction-filter-empty"',
            'id="pc-empty-reset"',
        ):
            self.assertIn(
                control_id,
                text,
            )

    def test_template_contains_interactive_script(self):
        text = self.read_centre_template()

        for expected in (
            "card.dataset.competition",
            "card.dataset.status",
            "card.dataset.positive",
            "a.dataset.time",
            "b.dataset.time",
            "Number(b.dataset[key])",
            "positiveOnly.checked",
            "list.appendChild(card)",
        ):
            self.assertIn(
                expected,
                text,
            )

    def test_template_uses_professional_card_component(self):
        text = self.read_centre_template()

        self.assertIn(
            '{% include "components/pro_prediction_card.html" %}',
            text,
        )

    def test_template_contains_fixture_data_attributes(self):
        combined = (
            self.read_centre_template()
            + self.read_card_component()
        )

        for attribute in (
            "data-competition",
            "data-status",
            "data-positive",
            "data-time",
            "data-probability",
            "data-ev",
            "data-edge",
            "data-stake",
        ):
            self.assertIn(
                attribute,
                combined,
            )

    def test_professional_cards_keep_filter_class(self):
        text = self.read_card_component()

        self.assertIn(
            "prediction-centre-card",
            text,
        )


if __name__ == "__main__":
    unittest.main()
