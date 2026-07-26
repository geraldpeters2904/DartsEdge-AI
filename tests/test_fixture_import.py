import json
import os
import tempfile
import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.match import Match
from app.models.player import Player
from app.providers.remote_json import RemoteJsonFixtureProvider
from app.providers.registry import ProviderRegistry
from app.services.fixture_import_service import FixtureImportService


class StubProviderService:
    def __init__(self, provider):
        self.registry = ProviderRegistry()
        self.registry.register(provider)


class FixtureImportTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        event_date = (date.today() + timedelta(days=1)).isoformat()
        json.dump({"fixtures": [
            {"external_id": "m1", "date": event_date, "tournament": "MODUS", "stage": "Group A", "match_format": "Best of 7", "player_a": "Alpha", "player_b": "Beta"},
            {"external_id": "m2", "date": event_date, "tournament": "MODUS", "stage": "Group A", "match_format": "Best of 7", "player_a": "Gamma", "player_b": "Delta"},
        ]}, self.temp)
        self.temp.close()
        self.provider = RemoteJsonFixtureProvider(feed_url=f"file://{self.temp.name}")

    def tearDown(self):
        os.unlink(self.temp.name)

    def test_remote_provider_parses_feed(self):
        fixtures = list(self.provider.fetch_fixtures(date.today(), date.today() + timedelta(days=7)))
        self.assertEqual(len(fixtures), 2)
        self.assertEqual(fixtures[0].tournament, "MODUS")

    def test_preview_marks_duplicates(self):
        db = self.Session()
        try:
            db.add(Match(date=date.today() + timedelta(days=1), tournament="MODUS", player_a="Alpha", player_b="Beta", status="scheduled"))
            db.commit()
            preview = FixtureImportService(db, StubProviderService(self.provider)).preview("remote-json", 7)
            self.assertEqual(preview["count"], 2)
            self.assertEqual(preview["new_count"], 1)
        finally:
            db.close()

    def test_import_creates_fixtures_and_players(self):
        db = self.Session()
        try:
            report = FixtureImportService(db, StubProviderService(self.provider)).import_fixtures("remote-json", 7)
            self.assertEqual(report.created, 2)
            self.assertEqual(report.players_created, 4)
            self.assertEqual(db.query(Match).count(), 2)
            self.assertEqual(db.query(Player).count(), 4)
        finally:
            db.close()

    def test_repeated_import_is_duplicate_safe(self):
        db = self.Session()
        try:
            service = FixtureImportService(db, StubProviderService(self.provider))
            service.import_fixtures("remote-json", 7)
            second = service.import_fixtures("remote-json", 7)
            self.assertEqual(second.created, 0)
            self.assertEqual(second.skipped_duplicates, 2)
            self.assertEqual(db.query(Match).count(), 2)
        finally:
            db.close()

    def test_missing_required_field_is_rejected(self):
        bad = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump([{"date": date.today().isoformat(), "player_a": "Alpha"}], bad)
        bad.close()
        try:
            provider = RemoteJsonFixtureProvider(feed_url=f"file://{bad.name}")
            with self.assertRaises(ValueError):
                list(provider.fetch_fixtures(date.today(), date.today()))
        finally:
            os.unlink(bad.name)


if __name__ == "__main__":
    unittest.main()
