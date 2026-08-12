"""Offline self-check for the now-playing card cache (no network, no PIL render).

Guards the branch that makes repeat plays cheap: get_thumb must return the
per-song cached card immediately when it already exists on disk, WITHOUT
touching the network or re-rendering. The cache path get_thumb looks for must
also match the path render_thumb writes to (same {id}_{videoid}_premium.png
shape) — if those drift apart the cache silently never hits.

Run: python3 test_thumb_cache.py
"""
import asyncio
import hashlib
import os

import thumbnails as th


async def _cache_hit_short_circuits():
    videoid, title, dur = "VID12345678", "Some Song", "03:00"
    # Mirror get_thumb's key so we can pre-seed the file it will look for.
    key = hashlib.md5(f"{videoid}|{title}|{dur}|None|None".encode()).hexdigest()[:12]
    cached = f"cache/{key}_{videoid}_premium.png"
    os.makedirs("cache", exist_ok=True)
    with open(cached, "wb") as f:
        f.write(b"stub")  # pretend a prior render cached this card
    try:
        # An unreachable URL proves the hit returns before any download/render.
        got = await th.get_thumb(
            title, dur, "http://127.0.0.1:1/never.png", videoid=videoid
        )
        assert got == cached, f"expected cache hit {cached!r}, got {got!r}"
    finally:
        os.remove(cached)


if __name__ == "__main__":
    asyncio.run(_cache_hit_short_circuits())
    print("OK")
