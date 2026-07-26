import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


class ShadowComparisonTemplateTests(unittest.TestCase):
    def test_template_does_not_require_python_max_global(self):
        template_path = Path("app/templates/shadow_comparison.html")
        source = template_path.read_text(encoding="utf-8")
        self.assertNotIn("max(row.", source)

    def test_template_compiles_with_strict_undefined(self):
        env = Environment(
            loader=FileSystemLoader("app/templates"),
            undefined=StrictUndefined,
            autoescape=True,
        )
        env.filters["display_name"] = lambda value: value
        env.get_template("shadow_comparison.html")


if __name__ == "__main__":
    unittest.main()
