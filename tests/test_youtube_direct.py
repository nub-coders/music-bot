"""Tests for the direct-stream-URL path in youtube.py.

Covers the three regressions fixed alongside these tests:
  * the yt-dlp probe must not run on the event loop,
  * a failed probe must not be reported as a playable success, and
  * a timed-out yt-dlp child must be killed and reaped.
"""
import asyncio
import sys
import threading

import pytest

import youtube


# ── URL classification ────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://example.com/song.mp3",
    "http://example.com/live/stream.m3u8",
    "https://cdn.example.org/a/b/c.webm?token=1",
])
def test_is_direct_stream_url_accepts_non_youtube_http(url):
    assert youtube.is_direct_stream_url(url) is True


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/playlist?list=PL1",
    "https://open.spotify.com/track/abc",
    "never gonna give you up",
    "dQw4w9WgXcQ",
    "",
    None,
    12345,
])
def test_is_direct_stream_url_rejects_non_direct(url):
    assert youtube.is_direct_stream_url(url) is False


@pytest.mark.parametrize("url", [
    "https://example.com/song.mp3",
    "https://example.com/song.MP3",
    "https://example.com/a/b/clip.mp4",
    "https://example.com/live/index.m3u8",
    "https://example.com/manifest.mpd",
    "https://example.com/audio.opus?sig=xyz",
])
def test_looks_playable_direct_url_accepts_media_paths(url):
    assert youtube._looks_playable_direct_url(url) is True


@pytest.mark.parametrize("url", [
    "https://example.com/",
    "https://example.com/index.html",
    "https://example.com/api/v1/tracks",
    "http://169.254.169.254/latest/meta-data/",
    "https://example.com/song.mp3.html",
    "not a url",
])
def test_looks_playable_direct_url_rejects_non_media_paths(url):
    assert youtube._looks_playable_direct_url(url) is False


# ── get_video_details: direct URL branch ──────────────────────────────────────

@pytest.fixture
def allow_all_urls(monkeypatch):
    """Neutralise the SSRF gate for tests about other behaviour."""
    async def _ok(url, allow_private=False):
        return None
    monkeypatch.setattr(youtube, "check_stream_url", _ok)


@pytest.fixture
def no_size_check(monkeypatch, allow_all_urls):
    """Stop the 2 GB guard from touching the network."""
    async def _none(url):
        return None
    monkeypatch.setattr(youtube, "_get_remote_file_size", _none)


async def test_probe_runs_off_the_event_loop(monkeypatch, no_size_check):
    """A blocking yt-dlp call on the loop freezes every voice chat, so the probe
    must execute in a worker thread."""
    seen = {}
    main_thread = threading.get_ident()

    def _fake_probe(url):
        seen["thread"] = threading.get_ident()
        return {"title": "Probed", "duration": 90, "url": "https://cdn/x.mp3"}

    monkeypatch.setattr(youtube, "_extract_direct_info_sync", _fake_probe)

    result = await youtube.get_video_details("https://example.com/song.mp3")

    assert seen["thread"] != main_thread
    assert result["title"] == "Probed"
    assert result["platform"] == "Direct"


async def test_probe_result_is_mapped_to_details(monkeypatch, no_size_check):
    def _fake_probe(url):
        return {
            "title": "Real Title",
            "duration": 125,
            "uploader": "Some Channel",
            "thumbnails": [{"url": "https://img/small"}, {"url": "https://img/big"}],
            "url": "https://cdn/stream.mp3",
        }

    monkeypatch.setattr(youtube, "_extract_direct_info_sync", _fake_probe)

    result = await youtube.get_video_details("https://example.com/song.mp3")

    assert result["title"] == "Real Title"
    assert result["channel_name"] == "Some Channel"
    assert result["thumbnail"] == "https://img/big"
    assert result["stream_url"] == "https://cdn/stream.mp3"
    assert "error" not in result


async def test_probe_result_prefers_best_format_over_bare_url(monkeypatch, no_size_check):
    def _fake_probe(url):
        return {
            "title": "With Formats",
            "formats": [{"url": "https://cdn/best.mp4", "acodec": "aac", "vcodec": "h264", "protocol": "https", "ext": "mp4"}],
            "url": "https://cdn/fallback.mp4",
        }

    monkeypatch.setattr(youtube, "_extract_direct_info_sync", _fake_probe)

    result = await youtube.get_video_details("https://example.com/clip.mp4")

    assert result["stream_url"] == "https://cdn/best.mp4"


async def test_probe_with_no_playable_url_is_not_a_success(monkeypatch, no_size_check):
    """Regression: extract_best_format returns the string "N/A" on failure, which is
    truthy, so the old `or` chain produced stream_url == "N/A" and reported success."""
    monkeypatch.setattr(
        youtube, "_extract_direct_info_sync",
        lambda url: {"title": "Metadata only", "formats": []},
    )

    result = await youtube.get_video_details("https://example.com/api/v1/tracks")

    assert "error" in result
    assert result.get("stream_url") != "N/A"


async def test_failed_probe_on_non_media_url_returns_error(monkeypatch, no_size_check):
    """Regression: this used to return a success dict with stream_url set to the
    URL that had just failed, so playback silently died instead of erroring."""
    def _boom(url):
        raise RuntimeError("Unsupported URL")

    monkeypatch.setattr(youtube, "_extract_direct_info_sync", _boom)

    result = await youtube.get_video_details("http://169.254.169.254/latest/meta-data/")

    assert "error" in result
    assert "stream_url" not in result


async def test_failed_probe_returning_none_on_non_media_url_returns_error(monkeypatch, no_size_check):
    monkeypatch.setattr(youtube, "_extract_direct_info_sync", lambda url: None)

    result = await youtube.get_video_details("https://example.com/api/v1/tracks")

    assert "error" in result


async def test_failed_probe_on_media_url_still_passes_through(monkeypatch, no_size_check):
    """ffmpeg can play a plain .mp3 that yt-dlp could not parse, so this path must
    stay working -- the fix narrows the passthrough, it does not remove it."""
    monkeypatch.setattr(youtube, "_extract_direct_info_sync", lambda url: None)

    result = await youtube.get_video_details("https://example.com/song.mp3")

    assert result["stream_url"] == "https://example.com/song.mp3"
    assert result["title"] == "song.mp3"
    assert "error" not in result


async def test_failed_probe_on_hls_manifest_passes_through(monkeypatch, no_size_check):
    monkeypatch.setattr(youtube, "_extract_direct_info_sync", lambda url: None)

    result = await youtube.get_video_details("https://example.com/live/index.m3u8")

    assert result["duration"] == "Live Stream"
    assert "error" not in result


async def test_probe_timeout_does_not_block_forever(monkeypatch, no_size_check):
    """A hung probe must surface within the budget rather than pinning the caller."""
    def _hang(url):
        threading.Event().wait(30)
        return {"title": "too late"}

    monkeypatch.setattr(youtube, "_extract_direct_info_sync", _hang)
    monkeypatch.setattr(youtube, "DIRECT_PROBE_TIMEOUT", 0.1)

    result = await asyncio.wait_for(
        youtube.get_video_details("https://example.com/song.mp3"), timeout=5
    )

    # Timed out probe -> no info -> media-path passthrough, never a hang.
    assert result["stream_url"] == "https://example.com/song.mp3"


async def test_oversized_file_is_rejected(monkeypatch, allow_all_urls):
    async def _huge(url):
        return youtube.MAX_FILE_SIZE_BYTES + 1
    monkeypatch.setattr(youtube, "_get_remote_file_size", _huge)
    monkeypatch.setattr(youtube, "_extract_direct_info_sync", lambda url: None)

    result = await youtube.get_video_details("https://example.com/huge.mp4")

    assert "error" in result
    assert "2 GB" in result["error"]


# ── SSRF gate wiring ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
    "http://127.0.0.1:6379/",
    "http://192.168.1.1/admin",
    "http://[::1]:8080/",
    "http://metadata.google.internal/computeMetadata/v1/",
])
async def test_ssrf_targets_are_refused_before_any_fetch(monkeypatch, url):
    """The gate must run before the probe and before the size check, so neither
    yt-dlp nor httpx ever sees the URL."""
    def _must_not_probe(_url):
        raise AssertionError("yt-dlp probe reached for a blocked URL")

    async def _must_not_fetch(_url):
        raise AssertionError("size check reached for a blocked URL")

    monkeypatch.setattr(youtube, "_extract_direct_info_sync", _must_not_probe)
    monkeypatch.setattr(youtube, "_get_remote_file_size", _must_not_fetch)

    result = await youtube.get_video_details(url)

    assert "error" in result
    assert "private or non-routable" in result["error"]


async def test_public_url_passes_the_gate(monkeypatch):
    """Uses the real guard with DNS stubbed, so the wiring is exercised end to end."""
    import url_guard

    async def _resolve(host, port):
        return ["93.184.216.34"]

    monkeypatch.setattr(url_guard, "resolve_all", _resolve)
    monkeypatch.setattr(youtube, "_extract_direct_info_sync", lambda url: None)

    async def _none(url):
        return None
    monkeypatch.setattr(youtube, "_get_remote_file_size", _none)

    result = await youtube.get_video_details("https://example.com/song.mp3")

    assert "error" not in result
    assert result["stream_url"] == "https://example.com/song.mp3"


async def test_remote_file_size_refuses_blocked_url(monkeypatch):
    """Defence in depth: the helper that issues the request checks too."""
    def _must_not_be_used():
        raise AssertionError("HTTP client used for a blocked URL")

    monkeypatch.setattr(youtube, "get_http_client", _must_not_be_used)

    assert await youtube._get_remote_file_size("http://169.254.169.254/latest/") is None


# ── subprocess reaping ────────────────────────────────────────────────────────

async def test_kill_process_reaps_live_child():
    """Regression: wait_for() only cancels our side of communicate(); without an
    explicit kill the yt-dlp child and its pipes leak on every timeout."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time; time.sleep(30)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.returncode is None

    await asyncio.wait_for(youtube._kill_process(proc), timeout=10)

    assert proc.returncode is not None, "child should be dead and reaped"


async def test_kill_process_is_safe_on_none_and_exited():
    await youtube._kill_process(None)

    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
    await proc.wait()
    await youtube._kill_process(proc)  # already exited; must not raise
