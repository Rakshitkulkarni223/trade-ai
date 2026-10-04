import os
import sys
from pathlib import Path

# Tests get a database of their own so they can never touch (or leave rows in) the local app database.
_DB = Path(__file__).resolve().parents[1] / ".pytest_tradeai.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
if _DB.exists():
    _DB.unlink()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_sessionfinish(session, exitstatus):
    try:
        _DB.unlink()
    except OSError:
        pass
