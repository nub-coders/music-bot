"""Tests for the on-disk stream-URL cache in youtube.py.

Two properties are covered:

* Each entry holds a fully signed CDN URL, so anyone able to read the file can
  stream the media until the URL's own `expire` passes. The files used to be
  written through a plain `open()`, taking whatever the process umask allowed.
* The cache sits on the /play hot path. The blocking work now lives in `*_sync`
  helpers that the public coroutines dispatch to a worker thread; it used to run
  directly on the event loop.
"""
import asyncio
import inspect
import json
import os
import stat
import time

import youtube


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _signed_url(ttl=3600):
    return f"https://rr1---sn-test.googlevideo.com/videoplayback?expire={int(time.time()) + ttl}&sig=SECRET"


# ── file permissions ──────────────────────────────────────────────────────────

def test_cache_file_is_owner_readable_only(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))

    youtube._write_cache_sync("https://youtu.be/abc", _signed_url(), prefix="audio_")

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert _mode(written[0]) == 0o600, "signed stream URL left readable beyond the owner"


def test_existing_loose_permissions_are_tightened(tmp_path, monkeypatch):
    """O_TRUNC reuses an existing file, so the open mode alone is not enough."""
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))
    path = youtube._cache_path("https://youtu.be/abc", "audio_")
    with open(path, "w") as f:
        f.write("{}")
    os.chmod(path, 0o644)

    youtube._write_cache_sync("https://youtu.be/abc", _signed_url(), prefix="audio_")

    assert _mode(path) == 0o600


# ── read/write behaviour ──────────────────────────────────────────────────────

def test_cache_roundtrip_still_works(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))
    url = _signed_url()

    youtube._write_cache_sync("https://youtu.be/abc", url, prefix="audio_")

    assert youtube._read_cache_sync("https://youtu.be/abc", prefix="audio_") == url


def test_unexpiring_url_is_not_written(tmp_path, monkeypatch):
    """No `expire=` means the lifetime is unknown, so nothing is cached."""
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))

    youtube._write_cache_sync("https://youtu.be/abc", "https://example.com/a.m3u8", prefix="audio_")

    assert list(tmp_path.glob("*.json")) == []


def test_expired_entry_is_removed_on_read(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))
    path = youtube._cache_path("https://youtu.be/abc", "audio_")
    with open(path, "w") as f:
        json.dump({"url": "https://stale", "expire": int(time.time()) - 10}, f)

    assert youtube._read_cache_sync("https://youtu.be/abc", prefix="audio_") is None
    assert not os.path.exists(path)


def test_corrupt_entry_is_discarded_and_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))
    path = youtube._cache_path("https://youtu.be/abc", "audio_")
    with open(path, "w") as f:
        f.write("{not json")

    assert youtube._read_cache_sync("https://youtu.be/abc", prefix="audio_") is None
    assert not os.path.exists(path)


# ── the hot path stays off the event loop ─────────────────────────────────────

def test_public_cache_helpers_are_coroutines():
    assert inspect.iscoroutinefunction(youtube._read_cache)
    assert inspect.iscoroutinefunction(youtube._write_cache)


async def test_async_roundtrip_runs_in_a_worker_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))
    seen = []
    real_to_thread = asyncio.to_thread

    async def _tracking_to_thread(func, *args, **kwargs):
        seen.append(func.__name__)
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(youtube.asyncio, "to_thread", _tracking_to_thread)
    url = _signed_url()

    await youtube._write_cache("https://youtu.be/abc", url, prefix="audio_")
    assert await youtube._read_cache("https://youtu.be/abc", prefix="audio_") == url
    assert seen == ["_write_cache_sync", "_read_cache_sync"]
