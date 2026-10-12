"""Run the DartsEdge AI regression suite against an isolated SQLite database."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.engine import make_url


def main():
    with tempfile.TemporaryDirectory(prefix="dartsedge_tests_") as directory:
        test_database = Path(directory) / "test_dartsedge.db"
        database_url = "sqlite:///" + str(test_database)

        parsed = make_url(database_url)
        live_database = (Path(__file__).resolve().parent / "dartsedge.db").resolve()
        configured_database = Path(parsed.database).resolve()

        if configured_database == live_database:
            raise RuntimeError("Refusing to run tests against the live database")

        if "app.db" in sys.modules:
            raise RuntimeError("Application database was imported before test isolation")

        os.environ["DATABASE_URL"] = database_url

        print("Test database:", configured_database, flush=True)
        print("Live database:", live_database, "(protected)", flush=True)

        loader = unittest.TestLoader()
        suite = loader.discover(start_dir="tests", pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)

        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
