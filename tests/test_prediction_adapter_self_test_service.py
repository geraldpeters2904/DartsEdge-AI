
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.services.prediction_adapter_self_test_service import (
    run_prediction_adapter_self_test,
)


class PredictionAdapterSelfTestServiceTests(unittest.TestCase):
    def test_no_fixture_returns_clean_not_ready_report(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            report = run_prediction_adapter_self_test(
                db
            )

            self.assertFalse(
                report.ready
            )
            self.assertIsNone(
                report.fixture_id
            )
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
