import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.models.strategy_profile import StrategyProfile
from app.services.strategy_service import (
    create_strategy,
    duplicate_strategy,
    export_strategy,
    import_strategy,
    strategy_history,
    strategy_rules,
    update_strategy,
)


class StrategyEditorTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_create_and_version_strategy(self):
        db = self.Session()
        try:
            created = create_strategy(db, name="My Strategy", description="Test", rules={})
            updated = update_strategy(db, created.id, name="My Strategy", description="Updated", rules={"minimum_ev_percent": 4})
            self.assertEqual(updated.strategy_uuid, created.strategy_uuid)
            self.assertEqual(updated.version, 2)
            self.assertEqual(len(strategy_history(db, created.strategy_uuid)), 2)
            self.assertEqual(strategy_rules(updated)["minimum_ev_percent"], 4)
        finally:
            db.close()

    def test_duplicate_gets_new_uuid(self):
        db = self.Session()
        try:
            created = create_strategy(db, name="Original", description="", rules={})
            copied = duplicate_strategy(db, created.id)
            self.assertNotEqual(created.strategy_uuid, copied.strategy_uuid)
            self.assertEqual(copied.version, 1)
        finally:
            db.close()

    def test_export_import_round_trip(self):
        db = self.Session()
        try:
            created = create_strategy(db, name="Portable", description="Export me", rules={"minimum_edge_percent": 8})
            payload = export_strategy(created)
            imported = import_strategy(db, json.loads(json.dumps(payload)))
            self.assertNotEqual(created.strategy_uuid, imported.strategy_uuid)
            self.assertEqual(strategy_rules(imported)["minimum_edge_percent"], 8)
        finally:
            db.close()

    def test_invalid_import_rejected(self):
        db = self.Session()
        try:
            with self.assertRaises(ValueError):
                import_strategy(db, {"format": "unknown", "rules": {}})
        finally:
            db.close()

    def test_editor_routes_render(self):
        client = TestClient(app)
        response = client.get("/strategy-editor")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Strategy Editor", response.text)
        strategies = client.get("/strategies")
        self.assertEqual(strategies.status_code, 200)
        self.assertIn("Import strategy", strategies.text)


if __name__ == "__main__":
    unittest.main()
