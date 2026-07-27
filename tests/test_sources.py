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


def test_spotify_link_parsing():
    # The regex must pull (kind, id) from the URL shapes Spotify hands out,
    # including the intl-xx locale prefix and trailing ?si= query.
    cases = {
        "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT": ("track", "4cOdK2wGLETKBW3PvgPWqT"),
        "https://open.spotify.com/intl-de/album/6akEvsycLGftJxYudPjmqK": ("album", "6akEvsycLGftJxYudPjmqK"),
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc": ("playlist", "37i9dQZF1DXcBWIGoYBM5M"),
    }
    for url, expected in cases.items():
        m = sources._SPOTIFY_RE.search(url)
        assert m is not None, url
        assert (m.group(1).lower(), m.group(2)) == expected


def test_track_query_formats_artist_and_title():
    track = {"name": "All I Want", "artists": [{"name": "Tania Bowra"}]}
    assert sources._track_query(track) == ("Tania Bowra - All I Want", "All I Want")
    # Missing title -> unusable, must be dropped by callers.
    assert sources._track_query({"artists": [{"name": "X"}]}) is None
