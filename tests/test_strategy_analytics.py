import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.models.strategy_profile import StrategyProfile
from app.services.decision_engine_service import decide
from app.services.strategy_analytics_service import analytics, record_decision, settle_decision
from app.services.strategy_service import seed_default_strategies


class StrategyAnalyticsTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        seed_default_strategies(self.db)
        self.strategy = self.db.query(StrategyProfile).filter_by(is_active=True).first()

    def tearDown(self):
        self.db.close()

    def _record(self, ev=10, edge=8, odds=2.0, stake=20):
        result = decide(
            self.db, official_decision='Consider', official_stake=stake,
            model_probability=70, confidence_percent=80, expected_value_percent=ev,
            edge_percent=edge, decimal_odds=odds, bankroll=1000,
            market='match_winner', competition='modus', sample_size=50,
            portfolio_exposure_percent=2,
        )
        return record_decision(
            self.db, result=result, strategy_uuid=self.strategy.strategy_uuid,
            bookmaker='TestBook', model_probability=70, confidence_percent=80,
            decimal_odds=odds, edge_percent=edge, expected_value_percent=ev,
            market='match_winner', competition='modus',
        )

    def test_record_and_aggregate_decision(self):
        self._record()
        report = analytics(self.db)
        self.assertEqual(report['total_decisions'], 1)
        self.assertEqual(report['metrics'][0].strategy_name, self.strategy.name)

    def test_settlement_calculates_profit_and_roi(self):
        row = self._record(odds=2.5, stake=20)
        settle_decision(self.db, row.id, 'win')
        metric = analytics(self.db)['metrics'][0]
        self.assertEqual(metric.profit_loss, 30.0)
        self.assertEqual(metric.roi_percent, 150.0)
        self.assertEqual(metric.win_rate_percent, 100.0)

    def test_loss_updates_drawdown(self):
        row = self._record(stake=15)
        settle_decision(self.db, row.id, 'loss')
        metric = analytics(self.db)['metrics'][0]
        self.assertEqual(metric.profit_loss, -15.0)
        self.assertEqual(metric.maximum_drawdown, 15.0)

    def test_unsettled_rows_do_not_create_roi(self):
        self._record()
        metric = analytics(self.db)['metrics'][0]
        self.assertIsNone(metric.roi_percent)
        self.assertIsNone(metric.win_rate_percent)

    def test_strategy_analytics_routes_render(self):
        client = TestClient(app)
        response = client.get('/strategy-analytics')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Strategy Analytics', response.text)
        api = client.get('/api/strategy-analytics')
        self.assertEqual(api.status_code, 200)
        self.assertIn('metrics', api.json())


if __name__ == '__main__':
    unittest.main()
