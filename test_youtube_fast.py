"""Offline self-checks for the /play latency optimizations (no network).

Guards the pure logic that can silently regress:
  * get_http_client() must return ONE shared, pooled client (connection reuse)
    and only recreate it once closed;
  * duration formatting must roll seconds into MM:SS (InnerTube gives raw
    lengthSeconds; a raw parse_dur("PT213S") would wrongly render "0:213").

Run: python3 test_youtube_fast.py
"""
import asyncio

import youtube as yt


def test_duration_rollover():
    # InnerTube path formats lengthSeconds via format_duration, not parse_dur.
    assert yt.format_duration(213) == "03:33", yt.format_duration(213)
    assert yt.format_duration(59) == "00:59"
    assert yt.format_duration(3661) == "01:01:01"


async def _client_singleton():
    a = yt.get_http_client()
    b = yt.get_http_client()
    assert a is b, "must reuse one pooled client for keep-alive/connection reuse"
    assert a.is_closed is False
    await a.aclose()
    c = yt.get_http_client()  # recreated after close
    assert c is not a and c.is_closed is False
    await c.aclose()


def test_search_cache_key_isolated():
    # query->video_id cache must not collide with the ("audio"/"video", url) keys.
    yt._mem_cache_set(("search", "some query"), "VIDID123456")
    assert yt._MEM_CACHE.get(("search", "some query")) == "VIDID123456"
    assert yt._MEM_CACHE.get(("audio", "some query")) is None


if __name__ == "__main__":
    test_duration_rollover()
    test_search_cache_key_isolated()
    asyncio.run(_client_singleton())
    print("OK")
