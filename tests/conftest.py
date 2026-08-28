"""Shared test setup.

`config.py` raises SystemExit at import time when MONGODB_URI is unset, and it is
imported transitively by nearly everything. Set a dummy URI before any project
module is imported so the suite runs with no MongoDB and no `.env` present (as in
CI). Nothing here connects to Mongo -- motor builds its client lazily.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Must happen before `import config` (directly or transitively).
os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017/nub_music_bot_test")
# Pin the values the auth tests reason about, so a developer's real `.env`
# cannot change the outcome. load_dotenv() does not override existing vars.
os.environ["OWNER_ID"] = "1000"
os.environ["API_ID"] = "12345"
os.environ["API_HASH"] = "0" * 32
os.environ["BOT_TOKEN"] = ""
os.environ["STRING_SESSION"] = ""

import pytest  # noqa: E402


@pytest.fixture
def owner(monkeypatch):
    """Set the configured bot owner, defaulting to 1000. Returns a setter.

    `is_bot_owner` lives in `config.py` and reads config's own OWNER_ID/HAS_OWNER,
    so monkeypatching a plugin module's star-imported copies of those names has no
    effect on it. Patch here instead.
    """
    import config

    def _set(owner_id):
        monkeypatch.setattr(config, "OWNER_ID", owner_id)
        monkeypatch.setattr(config, "HAS_OWNER", owner_id > 0)

    _set(1000)
    return _set


@pytest.fixture
def fake_client():
    """Minimal stand-in for a Pyrogram Client: just the `.me.id` the handlers read."""

    class _Me:
        id = 777

    class _Client:
        me = _Me()

    return _Client()
