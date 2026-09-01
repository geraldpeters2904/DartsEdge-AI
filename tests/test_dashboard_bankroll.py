import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.settings import Settings
from app.services.dashboard_service import build_dashboard_data


class DashboardBankrollTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Settings(bankroll=1234.0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch(
        "app.services.dashboard_service.get_data_quality",
        return_value={"health_score": 100},
    )
    @patch(
        "app.services.dashboard_service.build_value_board",
        return_value=[],
    )
    def test_dashboard_uses_configured_bankroll(
        self,
        _value_board,
        _data_quality,
    ):
        result = build_dashboard_data(self.db)

        self.assertEqual(result["starting_bankroll"], 1234.0)
        self.assertEqual(result["current_bankroll"], 1234.0)
        self.assertEqual(result["equity_curve"], [])


if __name__ == "__main__":
    unittest.main()
