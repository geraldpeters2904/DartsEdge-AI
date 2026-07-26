import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.prediction_audit import PredictionAudit
from app.services.model_performance_lab_service import build_model_performance_lab
from app.services.shadow_comparison_service import record_outcome


class ModelPerformanceLabTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def add_audit(self, idx, legacy, intelligence, winner, profile='Default', tournament='Modus'):
        audit = PredictionAudit(audit_uuid=f'00000000-0000-0000-0000-{idx:012d}', source='test', tournament=tournament,
            player_a='A', player_b='B', official_selection='A', official_probability=legacy,
            legacy_probability_a=legacy, intelligence_probability_a=intelligence,
            prediction_confidence='High', explanation_confidence='High', profile_name=profile,
            profile_version=1, model_version='Intelligence-0.1', application_version='1.1.1', shadow_mode=True,
            snapshot_json='{}')
        self.db.add(audit); self.db.commit()
        record_outcome(self.db, audit.audit_uuid, winner, source='test')

    def test_empty_lab_is_safe(self):
        lab = build_model_performance_lab(self.db)
        self.assertEqual(lab['settled_count'], 0)
        self.assertFalse(lab['sample_ready'])

    def test_leaderboard_uses_brier(self):
        self.add_audit(1, .55, .80, 'A')
        lab = build_model_performance_lab(self.db)
        self.assertEqual(lab['leaderboard'][0]['name'], 'Player Intelligence')

    def test_profile_grouping(self):
        self.add_audit(1, .6, .7, 'A', profile='Default')
        self.add_audit(2, .6, .4, 'B', profile='Form Heavy')
        names = {r['name'] for r in build_model_performance_lab(self.db)['profile_metrics']}
        self.assertEqual(names, {'Default', 'Form Heavy'})

    def test_tournament_grouping(self):
        self.add_audit(1, .6, .7, 'A', tournament='Modus')
        self.assertEqual(build_model_performance_lab(self.db)['tournament_metrics'][0]['name'], 'Modus')

    def test_sample_ready_at_25(self):
        for i in range(25):
            self.add_audit(i+1, .6, .7, 'A')
        self.assertTrue(build_model_performance_lab(self.db)['sample_ready'])


if __name__ == '__main__':
    unittest.main()
