"""Tests for the yt-dlp search fallback in youtube.get_video_details.

Reached only when the InnerTube -> ytube API -> Data API chain yields nothing.
Like the direct-URL probe, the yt-dlp call must run off the event loop, and a
lookup that produces no playable stream must be reported as an error.
"""
import asyncio
import threading

import pytest

import youtube


@pytest.fixture
def chain_exhausted(monkeypatch):
    """Force the primary resolution chain to yield nothing so the fallback runs."""
    async def _nothing(video_id):
        return None
    monkeypatch.setattr(youtube, "get_video_info", _nothing)


def _entry(**overrides):
    entry = {
        "id": "abc123",
        "title": "Fallback Track",
        "duration": 200,
        "uploader": "Uploader",
        "view_count": 4321,
        "thumbnails": [{"url": "https://img/small"}, {"url": "https://img/big"}],
        "formats": [{
            "url": "https://cdn/audio.m4a",
            "acodec": "aac",
            "vcodec": "none",
            "protocol": "https",
            "ext": "m4a",
        }],
    }
    entry.update(overrides)
    return entry


async def test_search_runs_off_the_event_loop(monkeypatch, chain_exhausted):
    seen = {}
    main_thread = threading.get_ident()

    def _fake_search(query):
        seen["thread"] = threading.get_ident()
        seen["query"] = query
        return _entry()

    monkeypatch.setattr(youtube, "_ytdlp_search_first_sync", _fake_search)

    result = await youtube.get_video_details("some song name")

    assert seen["thread"] != main_thread
    assert seen["query"] == "some song name"
    assert result["title"] == "Fallback Track"
    assert result["platform"] == "YouTube"
    assert result["video_url"] == "https://www.youtube.com/watch?v=abc123"
    assert result["thumbnail"] == "https://img/big"
    assert result["stream_url"] == "https://cdn/audio.m4a"


async def test_no_search_results_returns_error(monkeypatch, chain_exhausted):
    monkeypatch.setattr(youtube, "_ytdlp_search_first_sync", lambda q: None)

    result = await youtube.get_video_details("nothing matches this")

    assert "error" in result


async def test_no_playable_format_returns_error(monkeypatch, chain_exhausted):
    """Regression: extract_best_format returns the string "N/A" when no format has
    a URL, which used to be handed back as a successful stream_url."""
    monkeypatch.setattr(youtube, "_ytdlp_search_first_sync", lambda q: _entry(formats=[]))

    result = await youtube.get_video_details("some song name")

    assert "error" in result
    assert result.get("stream_url") != "N/A"


async def test_search_timeout_returns_error(monkeypatch, chain_exhausted):
    def _hang(query):
        threading.Event().wait(0.5)
        return _entry()

    monkeypatch.setattr(youtube, "_ytdlp_search_first_sync", _hang)
    monkeypatch.setattr(youtube, "YTDLP_SEARCH_TIMEOUT", 0.1)

    result = await asyncio.wait_for(youtube.get_video_details("slow query"), timeout=5)

    assert "error" in result
    assert "timed out" in result["error"].lower()


async def test_extractor_error_is_surfaced(monkeypatch, chain_exhausted):
    def _boom(query):
        raise youtube.yt_dlp.utils.DownloadError("Video unavailable")

    monkeypatch.setattr(youtube, "_ytdlp_search_first_sync", _boom)

    result = await youtube.get_video_details("blocked song")

    assert "error" in result
    assert "Video unavailable" in result["error"]


async def test_bad_duration_does_not_crash(monkeypatch, chain_exhausted):
    monkeypatch.setattr(youtube, "_ytdlp_search_first_sync", lambda q: _entry(duration="junk"))

    result = await youtube.get_video_details("some song name")

    assert result["duration"] == "N/A"
    assert "error" not in result
