"""Phase 5 source seam: playlist detection + passthrough contract.

The yt-dlp expansion itself needs the network, so it is not unit-tested here
(ponytail: covered by manual/integration use). What matters for correctness is
that (a) plain video links and search text are NOT treated as playlists, and
(b) resolve_sources never returns empty — every caller relies on element [0].
"""
import asyncio

import sources


def test_playlist_detection():
    assert sources.is_youtube_playlist("https://www.youtube.com/playlist?list=PL123")
    assert sources.is_youtube_playlist("https://music.youtube.com/playlist?list=OLAK5")
    # A single video that merely carries a playlist context must NOT expand.
    assert not sources.is_youtube_playlist("https://www.youtube.com/watch?v=abc&list=PL123")
    assert not sources.is_youtube_playlist("https://youtu.be/abc123")
    assert not sources.is_youtube_playlist("never gonna give you up")
    assert not sources.is_youtube_playlist("")


def test_passthrough_never_empty_and_no_network():
    # Non-playlist input resolves synchronously (no yt-dlp call) to one element.
    for arg in ["some search text", "https://youtu.be/abc123"]:
        result = asyncio.run(sources.resolve_sources(arg))
        assert result == [(arg, None)]
