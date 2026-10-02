"""Guard network connections made by HTTPX, yt-dlp, and FFmpeg.

HTTPX uses a backend that connects to validated IP literals while retaining the
original hostname for Host and TLS SNI. Subprocesses use a loopback HTTP proxy;
every HTTP request and HTTPS CONNECT is checked independently, including those
caused by redirects or playlist entries. No external proxy or credentials needed.
"""

import asyncio
import contextlib
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

import httpcore
import httpx

from url_guard import check_url_shape, public_addresses


class PublicNetworkBackend(httpcore.AnyIOBackend):
    def __init__(self, allow_private=False):
        self.allow_private = allow_private

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            addresses = await public_addresses(host, port, allow_private=self.allow_private)
        except (ValueError, OSError, asyncio.TimeoutError) as exc:
            raise httpcore.ConnectError(f"Blocked media destination: {exc}") from exc
        error = None
        for address in addresses:
            try:
                return await super().connect_tcp(address, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                error = exc
        raise error


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        async for part in self.stream:
            yield part

    async def aclose(self):
        await self.stream.aclose()


class PublicHTTPTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, allow_private=False):
        self.allow_private = allow_private
        self.pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=PublicNetworkBackend(allow_private),
            max_connections=20,
        )

    async def handle_async_request(self, request):
        reason = check_url_shape(str(request.url), allow_private=self.allow_private)
        if reason:
            raise httpx.ConnectError(f"Blocked media destination: {reason}", request=request)
        try:
            response = await self.pool.handle_async_request(httpcore.Request(
                method=request.method,
                url=httpcore.URL(
                    scheme=request.url.raw_scheme, host=request.url.raw_host,
                    port=request.url.port, target=request.url.raw_path,
                ),
                headers=request.headers.raw, content=request.stream, extensions=request.extensions,
            ))
        except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
            raise httpx.ConnectError(str(exc), request=request) from exc
        return httpx.Response(
            response.status, headers=response.headers,
            stream=_ResponseStream(response.stream), extensions=response.extensions,
        )

    async def aclose(self):
        await self.pool.aclose()


class MediaProxy:
    """Private, local egress proxy. Never resolve an upstream name twice."""
    def __init__(self, *, allow_private=False):
        self.allow_private = allow_private
        self.server = None
        self.tasks = set()
        self.lock = asyncio.Lock()

    async def start(self):
        async with self.lock:
            if self.server is None:
                self.server = await asyncio.start_server(self._accept, "127.0.0.1", 0, limit=16384)
        return f"http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect(self, host, port):
        addresses = await public_addresses(host, port, allow_private=self.allow_private)
        error = None
        for address in addresses:
            try:
                family = socket.AF_INET6 if ipaddress.ip_address(address).version == 6 else socket.AF_INET
                return await asyncio.wait_for(asyncio.open_connection(address, port, family=family), 8)
            except (OSError, asyncio.TimeoutError) as exc:
                error = exc
        raise error

    @staticmethod
    async def _copy(reader, writer):
        while data := await asyncio.wait_for(reader.read(65536), 300):
            writer.write(data)
            await writer.drain()

    async def _accept(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        upstream = None
        pumps = []
        response_started = False
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
            lines = head.decode("iso-8859-1").split("\r\n")
            method, target, _version = lines[0].split(" ", 2)
            if method not in ("GET", "HEAD", "CONNECT"):
                raise ValueError("Unsupported proxy method")
            url = f"https://{target}/" if method == "CONNECT" else target
            reason = check_url_shape(url, allow_private=self.allow_private)
            if reason:
                raise ValueError(reason)
            parsed = urlsplit(url)
            if parsed.username or parsed.password:
                raise ValueError("Credentials in media URLs are not supported")
            # CONNECT is HTTPS only; all other requests must use absolute HTTP URLs.
            if method != "CONNECT" and parsed.scheme != "http":
                raise ValueError("Use CONNECT for HTTPS")
            upstream_reader, upstream = await self._connect(
                parsed.hostname, parsed.port or (443 if method == "CONNECT" else 80),
            )
            if method == "CONNECT":
                writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                await writer.drain()
                response_started = True
                pumps.append(asyncio.create_task(self._copy(reader, upstream)))
            else:
                headers = []
                for line in lines[1:]:
                    if not line:
                        continue
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    if key == "transfer-encoding" or (key == "content-length" and value.strip() != "0"):
                        raise ValueError("Request bodies are not supported")
                    if key not in ("host", "connection", "proxy-connection", "proxy-authorization"):
                        headers.append(line)
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                request = [f"{method} {path} HTTP/1.1", f"Host: {parsed.netloc}", "Connection: close", *headers, "", ""]
                upstream.write("\r\n".join(request).encode("iso-8859-1"))
                await upstream.drain()
                response_started = True
            pumps.append(asyncio.create_task(self._copy(upstream_reader, writer)))
            await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
        except (ValueError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            if not response_started:
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                with contextlib.suppress(OSError):
                    await writer.drain()
        finally:
            for pump in pumps:
                pump.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            for stream in (upstream, writer):
                if stream:
                    stream.close()
                    with contextlib.suppress(OSError, asyncio.CancelledError):
                        await stream.wait_closed()
            self.tasks.discard(task)


_proxy = None


async def get_media_proxy():
    global _proxy
    if _proxy is None:
        from config import ALLOW_PRIVATE_STREAM_URLS
        _proxy = MediaProxy(allow_private=ALLOW_PRIVATE_STREAM_URLS)
    return await _proxy.start()


async def close_media_proxy():
    global _proxy
    if _proxy:
        await _proxy.close()
        _proxy = None


async def media_options(source, ffmpeg_parameters=""):
    """Options for every player/probe, including seek and retry calls."""
    if not str(source).startswith(("http://", "https://")):
        if urlsplit(str(source)).scheme:
            raise ValueError("Unsupported media source protocol")
        return {"ffmpeg_parameters": f"-protocol_whitelist file,pipe {ffmpeg_parameters}".strip()}
    proxy = await get_media_proxy()
    # Exclude file/data/concat and other protocols from remote nested inputs.
    return {
        "ffmpeg_parameters": f"-http_proxy {proxy} -protocol_whitelist http,https,tcp,tls,crypto {ffmpeg_parameters}".strip(),
        "ytdlp_parameters": f"--proxy {proxy}",
    }
