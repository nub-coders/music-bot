import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import youtube


@pytest.mark.asyncio
async def test_get_video_info_api_call_without_mode():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "title": "Test Song",
        "video_id": "12345",
        "duration": "3:30",
        "youtube_link": "https://youtube.com/watch?v=12345",
        "channel_name": "Test Channel",
        "views": "100",
        "stream_url": "https://stream.test.com",
        "thumbnail": "https://thumb.test.com",
    }

    with (
        patch("youtube.API_TOKEN", "test-token"),
        patch("youtube.BASE_URL", "https://api.test.com"),
        patch("youtube._api_breaker_open", return_value=False),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp) as mock_get,
    ):
        result = await youtube.get_video_info("test query", mode="audio")

        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        params = mock_get.call_args[1].get("params")

        assert url == "https://api.test.com/info"
        assert params == {"q": "test query"}
        assert "mode" not in params
        assert result[0] == "Test Song"
        assert result[8] == "api"


def test_is_direct_stream_url():
    assert youtube.is_direct_stream_url("https://example.com/audio.mp3") is True
    assert youtube.is_direct_stream_url("http://radio.example.com/live.m3u8") is True
    assert youtube.is_direct_stream_url("https://rr5---sn-qxaelnl6.googlevideo.com/videoplayback?expire=12345") is True
    assert youtube.is_direct_stream_url("https://www.youtube.com/watch?v=abc") is False
    assert youtube.is_direct_stream_url("https://open.spotify.com/track/abc") is False
    assert youtube.is_direct_stream_url("just a query") is False


@pytest.mark.asyncio
async def test_direct_stream_url_details_fallback():
    url = "https://example.com/streams/live.mp3"
    with patch("youtube.API_TOKEN", ""):
        details = await youtube.get_video_details(url)
        assert details["platform"] == "Direct"
        assert details["stream_url"] == url
        assert details["title"] == "live.mp3"


@pytest.mark.asyncio
async def test_googlevideo_direct_stream_url_bypasses_api():
    url = "https://rr5---sn-qxaelnl6.googlevideo.com/videoplayback?expire=12345"
    assert youtube.is_direct_stream_url(url) is True

    with (
        patch("youtube.API_TOKEN", "test-token"),
        patch("youtube.BASE_URL", "https://api.test.com"),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
    ):
        details = await youtube.get_video_details(url)
        mock_get.assert_not_called()
        assert details["platform"] == "Direct"
        assert details["stream_url"] == url
