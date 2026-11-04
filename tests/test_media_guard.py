import asyncio
import io
import math
import shlex
import shutil
import ssl
import struct
import wave
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


async def test_size_probe_follows_private_redirect_without_opt_in(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_STREAM_URLS", "False")
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if request.url.host == "8.8.8.8":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1:8080/private"})
        return httpx.Response(200, headers={"Content-Length": "1234"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(youtube, "get_http_client", lambda: client)
        assert await youtube._get_remote_file_size("http://8.8.8.8/audio.mp3") == 1234
    assert requests == ["http://8.8.8.8/audio.mp3", "http://127.0.0.1:8080/private"]


@pytest.mark.skipif(
    not all(shutil.which(binary) for binary in ("ffprobe", "ffmpeg")),
    reason="ffprobe and ffmpeg are required",
)
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "media.internal"])
@pytest.mark.parametrize("legacy_setting", [None, "False"])
async def test_private_streams_work_without_environment_switch(allow_localhost, monkeypatch, host, legacy_setting):
    from tools import make_media_stream

    if legacy_setting is None:
        monkeypatch.delenv("ALLOW_PRIVATE_STREAM_URLS", raising=False)
    else:
        monkeypatch.setenv("ALLOW_PRIVATE_STREAM_URLS", legacy_setting)
    monkeypatch.setattr(media_guard, "_proxy", None)
    monkeypatch.setattr(youtube, "_http_client", None)

    resolve = url_guard.resolve_all

    async def resolve_media_host(name, port):
        if name == "media.internal":
            return ["127.0.0.1"]
        return await resolve(name, port)

    monkeypatch.setattr(url_guard, "resolve_all", resolve_media_host)
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        # Keep enough input for FFmpeg's analysis before its EOF reconnects.
        wav.writeframes(b"\x00\x10" * 480000)
    body = audio.getvalue()
    requests = []

    async def origin(reader, writer):
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            requests.append(request.split(b"\r\n", 1)[0])
            writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: audio/wav\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode())
            if not request.startswith(b"HEAD "):
                writer.write(body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(origin, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    process = None
    try:
        url = f"http://{host}:{port}/song.wav"
        assert await youtube._get_remote_file_size(url) == len(body)
        media = await make_media_stream(url)
        await asyncio.wait_for(media.check_stream(), 10)
        assert media.microphone is not None
        command = shlex.split(media.microphone.path)
        command[-1:-1] = ["-t", "0.05"]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        pcm, error = await asyncio.wait_for(process.communicate(), 10)
        assert process.returncode == 0, error.decode()
        assert len(pcm) > 1000 and any(pcm)
        assert any(request.startswith(b"HEAD ") for request in requests)
        assert sum(request.startswith(b"GET ") for request in requests) >= 2
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        await youtube.close_http_client()
        await media_guard.close_media_proxy()
        server.close()
        await server.wait_closed()


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
    from tools import make_media_stream

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
        media = await make_media_stream(url)
        assert media._ytdlp_parameters == f"--proxy {proxy_url}"
        cmd = build_command("ffprobe", media._ffmpeg_parameters, url, AudioParameters())
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


@pytest.mark.skipif(
    not all(shutil.which(binary) for binary in ("ffprobe", "ffmpeg", "openssl")),
    reason="ffprobe, ffmpeg and openssl are required",
)
async def test_https_stream_keeps_audio_and_decodes_through_proxy(allow_localhost, monkeypatch, tmp_path):
    """Exercise HTTPS CONNECT with the actual probe and player commands."""
    from tools import make_media_stream

    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    openssl = await asyncio.create_subprocess_exec(
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=public.test", "-keyout", str(key), "-out", str(cert),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, error = await asyncio.wait_for(openssl.communicate(), 10)
        assert openssl.returncode == 0, error.decode()
    finally:
        if openssl.returncode is None:
            openssl.kill()
            await openssl.wait()

    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        # Keep enough input for FFmpeg's stream analysis before EOF reconnects.
        wav.writeframes(b"".join(
            struct.pack("<h", int(10000 * math.sin(2 * math.pi * 440 * i / 48000)))
            for i in range(48000)
        ) * 10)
    body = audio.getvalue()
    requests = []

    async def origin(reader, writer):
        try:
            requests.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: audio/wav\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(origin, "127.0.0.1", 0, ssl=tls)
    port = server.sockets[0].getsockname()[1]
    original_addresses = media_guard.public_addresses

    async def addresses(host, port, **kwargs):
        if host == "public.test":
            return ["127.0.0.1"]  # Only the test TLS origin is allowed onto loopback.
        return await original_addresses(host, port, **kwargs)

    monkeypatch.setattr(media_guard, "public_addresses", addresses)
    proxy = media_guard.MediaProxy()
    process = None
    try:
        proxy_url = await proxy.start()
        monkeypatch.setattr(media_guard, "get_media_proxy", AsyncMock(return_value=proxy_url))
        media = await make_media_stream(f"https://public.test:{port}/song.wav")
        await asyncio.wait_for(media.check_stream(), 10)
        assert media.microphone is not None, "HTTPS probing must retain the audio input"

        command = shlex.split(media.microphone.path)
        command[-1:-1] = ["-t", "0.25"]  # Bound the output of the actual player command.
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        pcm, error = await asyncio.wait_for(process.communicate(), 10)
        assert process.returncode == 0, error.decode()
        assert len(pcm) > 1000 and any(pcm), "HTTPS playback must produce non-silent PCM"
        assert len(requests) >= 2  # The probe and the player both reached the TLS origin.
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

