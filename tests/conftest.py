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


# ── Reusable Platform Scraper Fixtures ────────────────────────────────────────

@pytest.fixture
def apple_music_track_html():
    """Mock Apple Music HTML layout for a single track page."""
    return """<!DOCTYPE html>
<html>
<head>
    <meta property="og:title" content="Blinding Lights - Song by The Weeknd on Apple Music" />
    <meta property="og:description" content="Listen to Blinding Lights by The Weeknd on Apple Music. 2020. Duration: 3:20." />
</head>
<body>
    <div class="songs-list-row__song-name">Blinding Lights</div>
</body>
</html>"""


@pytest.fixture
def apple_music_playlist_html():
    """Mock Apple Music HTML layout for a playlist page with multiple track rows."""
    return """<!DOCTYPE html>
<html>
<head>
    <meta property="og:title" content="Today's Hits - Playlist by Apple Music on Apple Music" />
    <meta property="og:description" content="The biggest songs in music right now." />
</head>
<body>
    <div class="songs-list-row">
        <span class="songs-list-row__song-name">As It Was</span>
    </div>
    <div class="songs-list-row">
        <span class="songs-list-row__song-name">Heat Waves</span>
    </div>
    <div class="songs-list-row">
        <span class="songs-list-row__song-name">Stay</span>
    </div>
</body>
</html>"""


@pytest.fixture
def apple_music_empty_playlist_html():
    """Mock Apple Music HTML layout with no track rows."""
    return """<!DOCTYPE html>
<html>
<head>
</head>
<body>
    <div class="empty-state">No songs available</div>
</body>
</html>"""


@pytest.fixture
def odesli_response_with_youtube():
    """Mock Odesli API response containing direct YouTube stream link."""
    return {
        "entityUniqueId": "AMAZON_SONG::B07XQ7Y123",
        "userCountry": "US",
        "entitiesByUniqueId": {
            "AMAZON_SONG::B07XQ7Y123": {
                "id": "B07XQ7Y123",
                "type": "song",
                "title": "Bohemian Rhapsody",
                "artistName": "Queen",
                "thumbnailUrl": "https://m.media-amazon.com/images/I/51abc.jpg"
            }
        },
        "linksByPlatform": {
            "youtube": {
                "url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ"
            },
            "amazonMusic": {
                "url": "https://music.amazon.com/albums/B07XQ7Y123"
            }
        }
    }


@pytest.fixture
def odesli_response_without_youtube():
    """Mock Odesli API response lacking a direct YouTube stream link."""
    return {
        "entityUniqueId": "AMAZON_SONG::B07XQ7Y456",
        "userCountry": "US",
        "entitiesByUniqueId": {
            "AMAZON_SONG::B07XQ7Y456": {
                "id": "B07XQ7Y456",
                "type": "song",
                "title": "Stairway to Heaven",
                "artistName": "Led Zeppelin"
            }
        },
        "linksByPlatform": {}
    }


@pytest.fixture
def jiosaavn_track_json():
    """Mock JioSaavn API track response with multiple bitrate download links."""
    return {
        "id": "saavn_track_001",
        "song": "Kesariya",
        "singers": "Arijit Singh, Pritam",
        "duration": "268",
        "image": "https://c.saavncdn.com/123/Kesariya-Hindi-2022-50x50.jpg",
        "download_url": [
            {"quality": "12kbps", "link": "https://aac.saavncdn.com/123/kesariya_12.mp4"},
            {"quality": "48kbps", "link": "https://aac.saavncdn.com/123/kesariya_48.mp4"},
            {"quality": "96kbps", "link": "https://aac.saavncdn.com/123/kesariya_96.mp4"},
            {"quality": "160kbps", "link": "https://aac.saavncdn.com/123/kesariya_160.mp4"},
            {"quality": "320kbps", "link": "https://aac.saavncdn.com/123/kesariya_320.mp4"}
        ]
    }
