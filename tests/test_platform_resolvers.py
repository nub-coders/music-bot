"""tests/test_platform_resolvers.py — Comprehensive test suite for multi-platform music providers.

Tests URL validation, provider routing, metadata scraping/parsing, stream extraction,
and dispatcher error handling for Apple Music, Amazon Music, SoundCloud, JioSaavn,
and plain-text search fallbacks.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import resolvers
from resolvers import (
    EmptyPlaylistError,
    MalformedURLError,
    NetworkTimeoutError,
    PlatformHTTPError,
    ResolverError,
    detect_provider,
    get_audio_stream,
    is_amazon_music,
    is_apple_music,
    is_jiosaavn,
    is_plain_text_query,
    is_soundcloud,
    parse_apple_music_html,
    parse_jiosaavn_json,
    parse_odesli_response,
    resolve_amazon_music,
    resolve_apple_music,
    resolve_jiosaavn,
    resolve_soundcloud,
    resolve_to_playable_stream,
    select_highest_bitrate_url,
    strip_apple_music_branding,
)


# ── Helper for Mocking Aiohttp Responses ──────────────────────────────────────

class MockAiohttpResponse:
    """Mock aiohttp response context manager for testing network requests."""
    def __init__(self, status=200, text_data="", json_data=None):
        self.status = status
        self._text = text_data
        self._json = json_data or {}

    async def text(self):
        return self._text

    async def json(self, content_type=None):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# ==============================================================================
# Objective 1: URL Validation & Provider Routing
# ==============================================================================

class TestURLValidationAndRouting:
    """Validate regex patterns and routing logic for incoming URLs and text queries."""

    @pytest.mark.parametrize("url", [
        "https://music.apple.com/us/album/blinding-lights/1488408080?i=1488408081",
        "https://music.apple.com/us/playlist/todays-hits/pl.f4d106fed2bd41149aa18d34355d2f82",
        "https://music.apple.com/in/album/starboy/1440871397",
        "http://music.apple.com/gb/song/shape-of-you/1193701079",
    ])
    def test_apple_music_url_validation(self, url):
        """Verify Apple Music regex correctly matches track, album, and playlist URLs."""
        assert is_apple_music(url) is True
        assert detect_provider(url) == "apple_music"

    @pytest.mark.parametrize("url", [
        "https://music.amazon.com/albums/B07XQ7Y123",
        "https://music.amazon.com/tracks/B07XQ7Y456?trackId=B07XQ7Y456",
        "http://music.amazon.co.uk/albums/B000000000",
        "https://music.amazon.de/playlists/B081234567",
    ])
    def test_amazon_music_url_validation(self, url):
        """Verify Amazon Music regex correctly matches track and album links."""
        assert is_amazon_music(url) is True
        assert detect_provider(url) == "amazon_music"

    @pytest.mark.parametrize("url", [
        "https://soundcloud.com/artist-name/track-title",
        "https://soundcloud.com/user-123456/sets/my-favorite-playlist",
        "http://www.soundcloud.com/postmalone/rockstar",
    ])
    def test_soundcloud_url_validation(self, url):
        """Verify SoundCloud regex matches direct track and set links."""
        assert is_soundcloud(url) is True
        assert detect_provider(url) == "soundcloud"

    @pytest.mark.parametrize("url", [
        "https://www.jiosaavn.com/song/kesariya/X1A-ZB50W1k",
        "https://jiosaavn.com/album/brahmastra-original-motion-picture-soundtrack/3xZ1,cT-lWw_",
        "http://saavn.com/s/song/hindi/tum-hi-ho/12345678",
        "https://www.saavn.com/p/song/hindi/kal-ho-naa-ho/X1Y2Z3",
    ])
    def test_jiosaavn_url_validation(self, url):
        """Verify JioSaavn and Saavn regex matches song and album URLs."""
        assert is_jiosaavn(url) is True
        assert detect_provider(url) == "jiosaavn"

    @pytest.mark.parametrize("query", [
        "Daft Punk - Get Lucky",
        "Taylor Swift Anti-Hero",
        "Imagine Dragons Believer",
        "🎵 Kesariya - 💖 ⚡ (Remix) 🚀",
        "1234567890",
    ])
    def test_plain_text_query_detection(self, query):
        """Verify plain-text search queries route to search fallback behavior."""
        assert is_plain_text_query(query) is True
        assert detect_provider(query) == "text_search"

    @pytest.mark.parametrize("invalid_input", [
        "",
        "   ",
        None,
        123,
    ])
    def test_invalid_routing_inputs_raise_malformed_error(self, invalid_input):
        """Verify empty or non-string inputs raise MalformedURLError."""
        with pytest.raises(MalformedURLError):
            detect_provider(invalid_input)


# ==============================================================================
# Objective 2: Metadata Extraction & Scraper Parsing
# ==============================================================================

class TestAppleMusicExtraction:
    """Unit tests for Apple Music HTML scraper and metadata parsing."""

    def test_strip_apple_music_branding(self):
        """Verify branding suffixes like ' on Apple Music' and ' - Song by ...' are stripped."""
        assert strip_apple_music_branding("Blinding Lights - Song by The Weeknd on Apple Music") == "Blinding Lights by The Weeknd"
        assert strip_apple_music_branding("Starboy - Album by The Weeknd on Apple Music") == "Starboy by The Weeknd"
        assert strip_apple_music_branding("Today's Hits - Playlist by Apple Music on Apple Music") == "Today's Hits by Apple Music"
        assert strip_apple_music_branding("Shape of You - Single by Ed Sheeran") == "Shape of You by Ed Sheeran"
        assert strip_apple_music_branding("Cold Heart on Apple Music") == "Cold Heart"

    def test_parse_apple_music_html_single_track(self, apple_music_track_html):
        """Verify HTML parser extracts og:title, og:description, and track name."""
        parsed = parse_apple_music_html(apple_music_track_html)
        assert parsed["title"] == "Blinding Lights by The Weeknd"
        assert "Listen to Blinding Lights" in parsed["description"]
        assert parsed["tracks"] == ["Blinding Lights"]

    def test_parse_apple_music_html_playlist(self, apple_music_playlist_html):
        """Verify HTML parser extracts track titles from .songs-list-row__song-name containers."""
        parsed = parse_apple_music_html(apple_music_playlist_html)
        assert parsed["title"] == "Today's Hits by Apple Music"
        assert parsed["tracks"] == ["As It Was", "Heat Waves", "Stay"]

    async def test_resolve_apple_music_success(self, apple_music_track_html):
        """Test resolve_apple_music fetches and parses track metadata with mocked HTTP session."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=200, text_data=apple_music_track_html)

        res = await resolve_apple_music("https://music.apple.com/us/album/blinding-lights/1488408080", session=session)
        assert res["provider"] == "apple_music"
        assert res["title"] == "Blinding Lights by The Weeknd"
        assert res["tracks"] == ["Blinding Lights"]


class TestAmazonMusicOdesliExtraction:
    """Unit tests for Amazon Music (Odesli / Songlink API) metadata extraction."""

    def test_parse_odesli_response_with_youtube(self, odesli_response_with_youtube):
        """Verify parsing entityUniqueId, title, artistName, and direct YouTube URL."""
        parsed = parse_odesli_response(odesli_response_with_youtube)
        assert parsed["entity_id"] == "AMAZON_SONG::B07XQ7Y123"
        assert parsed["title"] == "Bohemian Rhapsody"
        assert parsed["artist"] == "Queen"
        assert parsed["youtube_url"] == "https://www.youtube.com/watch?v=fJ9rUzIMcZQ"
        assert parsed["search_query"] == "Bohemian Rhapsody Queen"

    def test_parse_odesli_response_without_youtube_fallback(self, odesli_response_without_youtube):
        """Verify fallback search query '{title} {artist}' when linksByPlatform lacks YouTube."""
        parsed = parse_odesli_response(odesli_response_without_youtube)
        assert parsed["title"] == "Stairway to Heaven"
        assert parsed["artist"] == "Led Zeppelin"
        assert parsed["youtube_url"] is None
        assert parsed["search_query"] == "Stairway to Heaven Led Zeppelin"

    async def test_resolve_amazon_music_http_call(self, odesli_response_with_youtube):
        """Test resolve_amazon_music invokes Odesli API and extracts stream link."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=200, json_data=odesli_response_with_youtube)

        url = "https://music.amazon.com/tracks/B07XQ7Y123"
        res = await resolve_amazon_music(url, session=session)
        assert res["provider"] == "amazon_music"
        assert res["title"] == "Bohemian Rhapsody"
        assert res["artist"] == "Queen"
        assert res["youtube_url"] == "https://www.youtube.com/watch?v=fJ9rUzIMcZQ"


class TestJioSaavnExtraction:
    """Unit tests for JioSaavn JSON parsing and highest bitrate audio selection."""

    def test_select_highest_bitrate_url_from_list(self):
        """Verify selection of 320kbps URL over 160kbps, 96kbps, 48kbps, 12kbps."""
        media_list = [
            {"quality": "12kbps", "link": "http://cdn/audio_12.mp4"},
            {"quality": "48kbps", "link": "http://cdn/audio_48.mp4"},
            {"quality": "96kbps", "link": "http://cdn/audio_96.mp4"},
            {"quality": "160kbps", "link": "http://cdn/audio_160.mp4"},
            {"quality": "320kbps", "link": "http://cdn/audio_320.mp4"},
        ]
        selected = select_highest_bitrate_url(media_list)
        assert selected == "http://cdn/audio_320.mp4"

    def test_select_highest_bitrate_url_from_dict(self):
        """Verify selection of highest bitrate link when media data is a dictionary."""
        media_dict = {
            "128kbps": "http://cdn/audio_128.mp4",
            "320kbps": "http://cdn/audio_320.mp4",
            "64kbps": "http://cdn/audio_64.mp4",
        }
        selected = select_highest_bitrate_url(media_dict)
        assert selected == "http://cdn/audio_320.mp4"

    def test_parse_jiosaavn_json_track(self, jiosaavn_track_json):
        """Verify JSON payload parsing for title, artists, duration, and stream URL."""
        parsed = parse_jiosaavn_json(jiosaavn_track_json)
        assert parsed["title"] == "Kesariya"
        assert parsed["artist"] == "Arijit Singh, Pritam"
        assert parsed["duration"] == 268
        assert parsed["stream_url"] == "https://aac.saavncdn.com/123/kesariya_320.mp4"
        assert parsed["search_query"] == "Kesariya Arijit Singh, Pritam"

    async def test_resolve_jiosaavn_success(self, jiosaavn_track_json):
        """Test resolve_jiosaavn returns full audio metadata dict with mocked HTTP call."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=200, json_data=jiosaavn_track_json)

        url = "https://www.jiosaavn.com/song/kesariya/X1A-ZB50W1k"
        res = await resolve_jiosaavn(url, session=session)
        assert res["provider"] == "jiosaavn"
        assert res["title"] == "Kesariya"
        assert res["stream_url"] == "https://aac.saavncdn.com/123/kesariya_320.mp4"


class TestSoundCloudResolution:
    """Unit tests for SoundCloud resolution behavior."""

    def test_soundcloud_bypasses_search(self):
        """Ensure direct SoundCloud URLs bypass search scrapers and route to yt-dlp extractor."""
        url = "https://soundcloud.com/postmalone/rockstar"
        res = resolve_soundcloud(url)
        assert res["provider"] == "soundcloud"
        assert res["bypass_search"] is True
        assert res["stream_url"] == url


# ==============================================================================
# Objective 3: Error Handling & Dispatcher Robustness
# ==============================================================================

class TestMasterDispatcherAndErrorHandling:
    """Robustness & error-handling tests for resolve_to_playable_stream / get_audio_stream."""

    async def test_http_404_raises_platform_http_error(self):
        """Verify HTTP 404 response raises PlatformHTTPError."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=404, text_data="Not Found")

        with pytest.raises(PlatformHTTPError) as exc_info:
            await resolve_to_playable_stream("https://music.apple.com/us/album/not-found/999999", session=session)
        assert exc_info.value.status_code == 404

    async def test_http_429_rate_limit_raises_platform_http_error(self):
        """Verify HTTP 429 rate limit response raises PlatformHTTPError."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=429, text_data="Too Many Requests")

        with pytest.raises(PlatformHTTPError) as exc_info:
            await resolve_to_playable_stream("https://music.amazon.com/tracks/B07XQ7Y123", session=session)
        assert exc_info.value.status_code == 429

    async def test_empty_playlist_raises_empty_playlist_error(self, apple_music_empty_playlist_html):
        """Verify empty playlist HTML response raises EmptyPlaylistError."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=200, text_data=apple_music_empty_playlist_html)

        with pytest.raises(EmptyPlaylistError):
            await resolve_to_playable_stream("https://music.apple.com/us/playlist/empty/pl.12345", session=session)

    async def test_upstream_network_timeout_raises_network_timeout_error(self):
        """Verify network timeout during platform fetch raises NetworkTimeoutError."""
        session = MagicMock()
        session.get.side_effect = asyncio.TimeoutError()

        with pytest.raises(NetworkTimeoutError):
            await resolve_to_playable_stream("https://www.jiosaavn.com/song/kesariya/X1A-ZB50W1k", session=session)

    @pytest.mark.parametrize("special_query", [
        "🎵 Kesariya - 💖 ⚡ (Remix) 🚀",
        "🔥 Fireball! -- Single by Pitbull",
        "こんにちは - 日本語タイトル Track 1",
    ])
    async def test_special_characters_and_unicode_handling(self, special_query):
        """Verify titles with emojis, symbols, and Unicode are preserved without decoding errors."""
        res = await resolve_to_playable_stream(special_query)
        assert res["provider"] == "text_search"
        assert res["search_query"] == special_query
        assert res["bypass_search"] is False

    async def test_pure_text_search_routes_directly_without_scrapers(self):
        """Verify pure text queries bypass provider scrapers and route to fallback extractor."""
        mock_extractor = AsyncMock()
        mock_extractor.return_value = {
            "title": "Imagine Dragons - Believer",
            "stream_url": "https://googlevideo.com/videoplayback?id=123",
        }

        res = await get_audio_stream("Imagine Dragons Believer", yt_dlp_extractor=mock_extractor)
        mock_extractor.assert_called_once_with("Imagine Dragons Believer")
        assert res["title"] == "Imagine Dragons - Believer"

    async def test_dispatcher_alias_get_audio_stream(self, jiosaavn_track_json):
        """Verify get_audio_stream is an exact functional alias to resolve_to_playable_stream."""
        session = MagicMock()
        session.get.return_value = MockAiohttpResponse(status=200, json_data=jiosaavn_track_json)

        res = await get_audio_stream("https://www.jiosaavn.com/song/kesariya/X1A-ZB50W1k", session=session)
        assert res["provider"] == "jiosaavn"
        assert res["title"] == "Kesariya"
        assert res["stream_url"] == "https://aac.saavncdn.com/123/kesariya_320.mp4"
