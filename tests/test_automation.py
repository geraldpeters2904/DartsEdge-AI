import os
import tempfile
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.automation_job_run import AutomationJobRun
from app.services.automation_service import AutomationBusyError, AutomationService
from unittest.mock import patch


class AutomationTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        self.path = path
        engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False})
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_registers_four_jobs(self):
        service = AutomationService(self.db)
        self.assertEqual(len(service.jobs), 4)
        self.assertIn('paddy-power-live', service.jobs)

    @patch(
        'app.services.automation_service.'
        'capture_paddy_power_discovered_events_report_once'
    )
    def test_paddy_power_live_job_captures_one_cycle(self, capture_once):
        capture_once.return_value = type(
            'Report',
            (),
            {
                'extracted_prices': 26,
                'stored_prices': 8,
                'unchanged_prices': 18,
                'skipped_prices': 0,
                'challenge_detected': False,
            },
        )()

        run = AutomationService(self.db).run('paddy-power-live')

        capture_once.assert_called_once_with(self.db)
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.records_processed, 8)
        self.assertIn('Extracted 26', run.detail)
        self.assertIn('stored 8', run.detail)
        self.assertIn('unchanged 18', run.detail)

    def test_successful_job_is_persisted(self):
        service = AutomationService(self.db)
        service.jobs['daily-briefing'] = service.jobs['daily-briefing'].__class__('daily-briefing','Refresh daily briefing','test',lambda: (4,'ok'))
        run = service.run('daily-briefing')
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.records_processed, 4)

    def test_failure_is_recorded(self):
        service = AutomationService(self.db)
        def fail(): raise RuntimeError('feed unavailable')
        service.jobs['odds-preview'] = service.jobs['odds-preview'].__class__('odds-preview','Check odds feed','test',fail)
        run = service.run('odds-preview')
        self.assertEqual(run.status, 'failed')
        self.assertIn('feed unavailable', run.error)

    def test_unknown_job_rejected(self):
        with self.assertRaises(KeyError):
            AutomationService(self.db).run('missing')

    def test_busy_job_rejected(self):
        service = AutomationService(self.db)
        lock = service._locks['fixture-import']
        lock.acquire()
        try:
            with self.assertRaises(AutomationBusyError): service.run('fixture-import')
        finally:
            lock.release()


if __name__ == '__main__': unittest.main()
