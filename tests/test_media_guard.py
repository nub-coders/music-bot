import asyncio
import shutil
from unittest.mock import AsyncMock

import httpcore
import httpx
import pytest

import media_guard
import url_guard
import youtube


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/", "http://metadata.google.internal/", "file:///etc/passwd",
    "http://example.test:bad/", "http://example.test:0/",
])
async def test_reject_private_and_malformed_destinations(url):
    assert await url_guard.check_url(url)


async def test_connect_pins_validated_address(monkeypatch):
    resolve = AsyncMock(return_value=["8.8.8.8"])
    connect = AsyncMock(return_value=object())
    monkeypatch.setattr(url_guard, "resolve_all", resolve)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    await media_guard.PublicNetworkBackend().connect_tcp("media.test", 443)
    assert resolve.await_count == 1
    assert connect.call_args.args[:2] == ("8.8.8.8", 443)


async def test_mixed_dns_answers_are_rejected_before_connect(monkeypatch):
    monkeypatch.setattr(url_guard, "resolve_all", AsyncMock(return_value=["8.8.8.8", "127.0.0.1"]))
    connect = AsyncMock()
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    with pytest.raises(httpcore.ConnectError):
        await media_guard.PublicNetworkBackend().connect_tcp("media.test", 443)
    connect.assert_not_awaited()


async def test_size_probe_rejects_redirect_before_private_request(monkeypatch):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1:8080/private"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(youtube, "get_http_client", lambda: client)
        assert await youtube._get_remote_file_size("http://8.8.8.8/audio.mp3") is None
    assert requests == ["http://8.8.8.8/audio.mp3"]


@pytest.mark.parametrize("response_headers,expected", [({}, None), ({"Content-Length": "9999999999"}, 9999999999)])
async def test_size_probe_never_consumes_ignored_range_body(monkeypatch, response_headers, expected):
    class Body(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            raise AssertionError("The size probe must not read a response body")
            yield b""

        async def aclose(self):
            self.closed = True

    body = Body()

    def respond(request):
        if request.method == "HEAD":
            return httpx.Response(405)
        assert request.headers["range"] == "bytes=0-0"
        return httpx.Response(200, headers=response_headers, stream=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(youtube, "get_http_client", lambda: client)
        assert await youtube._get_remote_file_size("http://8.8.8.8/audio.mp3") == expected
    assert body.closed


async def test_proxy_checks_http_redirect_and_https_connect(allow_localhost, monkeypatch):
    requests = []

    async def origin(reader, writer):
        requests.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:1234/private\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(origin, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    original_addresses = media_guard.public_addresses

    async def addresses(host, port, **kwargs):
        if host == "public.test":
            return ["127.0.0.1"]  # Only this test origin is allowed onto loopback.
        return await original_addresses(host, port, **kwargs)

    monkeypatch.setattr(media_guard, "public_addresses", addresses)
    proxy = media_guard.MediaProxy()
    try:
        proxy_url = await proxy.start()
        async with httpx.AsyncClient(proxy=proxy_url, trust_env=False, follow_redirects=True) as client:
            response = await client.get(f"http://public.test:{port}/track.mp3")
            assert response.status_code == 403
            with pytest.raises(httpx.ProxyError):
                await client.get("https://127.0.0.1/private")
        assert len(requests) == 1
    finally:
        await proxy.close()
        server.close()
        await server.wait_closed()


async def test_extractor_and_seek_use_same_proxy(monkeypatch):
    monkeypatch.setattr(media_guard, "get_media_proxy", AsyncMock(return_value="http://127.0.0.1:9999"))
    options = await media_guard.media_options("https://media.test/audio.mp3", "-ss 30")
    assert "-http_proxy http://127.0.0.1:9999" in options["ffmpeg_parameters"]
    assert "-ss 30" in options["ffmpeg_parameters"]
    assert options["ytdlp_parameters"] == "--proxy http://127.0.0.1:9999"
    assert "file" not in options["ffmpeg_parameters"]
    assert await media_guard.media_options("/tmp/song.mp3", "-ss 30") == {"ffmpeg_parameters": "-protocol_whitelist file,pipe -ss 30"}


def test_direct_extractor_receives_proxy(monkeypatch):
    seen = []

    class Extractor:
        def __init__(self, opts):
            seen.append(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, *args, **kwargs):
            return {"url": "https://media.test/audio.mp3"}

    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", Extractor)
    youtube._extract_direct_info_sync("https://media.test/audio.mp3", "http://127.0.0.1:9999")
    assert seen[0]["proxy"] == "http://127.0.0.1:9999"


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe is not installed")
async def test_ffprobe_redirect_cannot_reach_private_origin(allow_localhost, monkeypatch):
    """Exercise the real subprocess, including PyTgCalls option placement."""
    from pytgcalls.ffmpeg import build_command
    from pytgcalls.types.raw import AudioParameters

    hits = []

    async def origin(reader, writer):
        data = await reader.readuntil(b"\r\n\r\n")
        hits.append(data.split(b"\r\n", 1)[0])
        writer.write(f"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:{port}/private\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(origin, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    addresses_orig = media_guard.public_addresses

    async def addresses(host, port, **kwargs):
        if host == "public.test":
            return ["127.0.0.1"]
        return await addresses_orig(host, port, **kwargs)

    monkeypatch.setattr(media_guard, "public_addresses", addresses)
    proxy = media_guard.MediaProxy()
    process = None
    try:
        proxy_url = await proxy.start()
        monkeypatch.setattr(media_guard, "get_media_proxy", AsyncMock(return_value=proxy_url))
        url = f"http://public.test:{port}/song.mp3"
        options = await media_guard.media_options(url)
        cmd = build_command("ffprobe", options["ffmpeg_parameters"], url, AudioParameters())
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(process.communicate(), timeout=10)
        assert process.returncode != 0
        assert hits == [b"GET /song.mp3 HTTP/1.1"]
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        await proxy.close()
        server.close()
        await server.wait_closed()


def test_safe_media_path():
    from plugins._common import safe_media_path

    assert not safe_media_path(None)
    assert not safe_media_path("")
    assert not safe_media_path("   ")
    assert not safe_media_path(123)
    assert not safe_media_path("/etc/passwd")
    assert not safe_media_path("../../secret.jpg")
    assert not safe_media_path("config.py")
    assert not safe_media_path("dangerous.sh")
    assert safe_media_path("music.jpg")
    assert safe_media_path("cache/sample.png")
    assert safe_media_path("downloads/track.mp4")

