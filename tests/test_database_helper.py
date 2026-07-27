import unittest

from app.models.player import Player
from tests.helpers.database import create_test_session


class DatabaseHelperTests(unittest.TestCase):
    def test_fresh_database_is_empty(self):
        db = create_test_session()

        try:
            self.assertEqual(db.query(Player).count(), 0)
        finally:
            db.close()

    def test_sessions_are_isolated(self):
        db1 = create_test_session()

        db1.add(
            Player(
                name="Test Player",
                elo=1500,
                average=90,
                checkout=40,
                one80_rate=0.25,
            )
        )
        db1.commit()

        db2 = create_test_session()

        try:
            self.assertEqual(db2.query(Player).count(), 0)
        finally:
            db1.close()
            db2.close()


if __name__ == "__main__":
    unittest.main()