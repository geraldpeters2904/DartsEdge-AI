import json
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.connectors import ConnectorRegistry, FeedConnectorError
from app.db import Base
from app.models.match import Match
from app.models.player import Player
from app.services.feed_connector_service import FeedConnectorService


class _Response:
    def __init__(self, text): self.text = text
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.text.encode()


class FeedConnectorFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False); self.tmp.close()
        engine = create_engine(f"sqlite:///{self.tmp.name}")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.service = FeedConnectorService(self.db)

    def tearDown(self):
        self.db.close(); os.unlink(self.tmp.name)

    def configure(self, connector_type='json'):
        return self.service.save(name='Test', connector_type=connector_type, feed_url='https://example.test/feed',
            auth_token='secret', enabled=True, competitions='', timeout_seconds=5, retry_count=1,
            refresh_interval_minutes=30)

    def test_registry_has_json_and_csv(self):
        self.assertEqual(ConnectorRegistry().types(), ('csv', 'json'))

    def test_disabled_connector_reports_failure(self):
        result = self.service.test_connection()
        self.assertEqual(result.status, 'unhealthy')

    @patch('app.connectors.urlopen')
    def test_json_preview_and_secret_masking(self, mocked):
        self.configure(); mocked.return_value = _Response(json.dumps([{"date": date.today().isoformat(), "tournament":"MODUS", "player_a":"A", "player_b":"B"}]))
        preview = self.service.preview(days=1)
        self.assertEqual(preview['new_count'], 1)
        diagnostics = self.service.diagnostics()['connector']
        self.assertTrue(diagnostics['token_configured'])
        self.assertNotIn('secret', json.dumps(diagnostics))

    @patch('app.connectors.urlopen')
    def test_sync_is_duplicate_safe(self, mocked):
        self.configure(); mocked.return_value = _Response(json.dumps([{"date": date.today().isoformat(), "tournament":"MODUS", "player_a":"A", "player_b":"B"}]))
        first = self.service.sync(days=1); second = self.service.sync(days=1)
        self.assertEqual(first['created'], 1); self.assertEqual(second['created'], 0)

    @patch('app.connectors.urlopen')
    def test_sync_canonicalises_player_display_names(self, mocked):
        self.configure()
        mocked.return_value = _Response(json.dumps([
            {
                "date": date.today().isoformat(),
                "tournament": "MODUS",
                "player_a": "Noa-Lynn van_Leuven_",
                "player_b": "B",
            }
        ]))
        self.service.sync(days=1)
        player = (
            self.db.query(Player)
            .filter(Player.name.like("Noa-Lynn%"))
            .one()
        )
        self.assertEqual(player.name, "Noa-Lynn van Leuven")
        match = self.db.query(Match).one()
        self.assertEqual(match.player_a, "Noa-Lynn van Leuven")

    @patch('app.connectors.urlopen')
    def test_preview_treats_canonical_name_variant_as_duplicate(self, mocked):
        self.configure()
        self.db.add(Match(
            date=date.today(),
            tournament="MODUS",
            player_a="Noa-Lynn van_Leuven_",
            player_b="B",
            status="scheduled",
        ))
        self.db.commit()
        mocked.return_value = _Response(json.dumps([
            {
                "date": date.today().isoformat(),
                "tournament": "MODUS",
                "player_a": "Noa-Lynn van Leuven",
                "player_b": "B",
            }
        ]))
        preview = self.service.preview(days=1)
        self.assertEqual(preview['new_count'], 0)

    @patch('app.connectors.urlopen')
    def test_invalid_payload_is_recorded(self, mocked):
        self.configure(); mocked.return_value = _Response('{}')
        with self.assertRaises(FeedConnectorError): self.service.preview(days=1)
        self.assertEqual(self.service.history(1)[0].status, 'failed')


if __name__ == '__main__': unittest.main()
