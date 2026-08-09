import unittest
from dataclasses import dataclass

from app.services.forward_schedule_discovery_service import (
    _latest_week,
)


@dataclass
class FakeWeek:
    value: int
    label: str


class FakeCatalog:
    def __init__(self):
        self.weeks = (
            FakeWeek(177, "Week 12"),
            FakeWeek(178, "Week 13"),
            FakeWeek(179, "Week 14"),
        )


class ForwardScheduleDiscoveryTests(
    unittest.TestCase
):
    def test_latest_week_uses_highest_week_id(self):
        week = _latest_week(
            FakeCatalog()
        )

        self.assertEqual(
            week.value,
            179,
        )


if __name__ == "__main__":
    unittest.main()
