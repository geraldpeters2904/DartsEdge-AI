"""Keep pytest database operations separate from the live DartsEdge database."""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_test_directory = tempfile.mkdtemp(prefix="dartsedge-pytest-")
_test_database = Path(_test_directory) / "test_dartsedge.db"

os.environ["DATABASE_URL"] = f"sqlite:///{_test_database}"

atexit.register(shutil.rmtree, _test_directory, ignore_errors=True)
