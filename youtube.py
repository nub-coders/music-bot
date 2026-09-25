

import os
import re
import logging
import asyncio
import httpx
import random
import hashlib
import json
import time
import yt_dlp
from urllib.parse import urlparse, parse_qs
from typing import List, Tuple, Dict


_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

# Separate caches for permanent search mappings and expiring stream URLs
_SEARCH_CACHE: dict = {}  # query -> video_id (long-lived)
_STREAM_CACHE: dict = {}  # (mode, url) -> (stream_url, expire_timestamp)
_MAX_SEARCH_CACHE_SIZE = 5000
_MAX_STREAM_CACHE_SIZE = 3000

# Unified dict for backward compatibility with callers/tests accessing _MEM_CACHE
_MEM_CACHE: dict = {}
_MAX_MEM_CACHE_SIZE = 5000


def _mem_cache_get(key):
    """Retrieve from in-memory cache with namespace separation and TTL enforcement."""
    if isinstance(key, tuple) and len(key) == 2:
        kind, val = key
        if kind == "search":
            if val in _SEARCH_CACHE:
                return _SEARCH_CACHE[val]
            return _MEM_CACHE.get(key)
        elif kind in ("audio", "video"):
            entry = _STREAM_CACHE.get((kind, val))
            if entry:
                stream_url, expire = entry
                if expire and time.time() < expire - 15:
                    return stream_url
                else:
                    _STREAM_CACHE.pop((kind, val), None)
                    _MEM_CACHE.pop(key, None)
                    return None
            cached = _MEM_CACHE.get(key)
            if cached:
                expire = _extract_expire(cached)
                if expire and time.time() < expire - 15:
                    return cached
                _MEM_CACHE.pop(key, None)
                return None
    return _MEM_CACHE.get(key)


def _mem_cache_set(key, value):
    """Set in-memory cache with separate namespaces, TTL tracking, and size bounds."""
    if isinstance(key, tuple) and len(key) == 2:
        kind, val = key
        if kind == "search":
            if len(_SEARCH_CACHE) >= _MAX_SEARCH_CACHE_SIZE:
                for k in list(_SEARCH_CACHE.keys())[:100]:
                    _SEARCH_CACHE.pop(k, None)
            _SEARCH_CACHE[val] = value
        elif kind in ("audio", "video"):
            expire = _extract_expire(value)
            if not expire:
                # No expire= in the URL means we cannot know when it dies.
                # Storing it anyway put a (value, None) entry in _STREAM_CACHE
                # that _mem_cache_get always treats as expired -- a permanent
                # miss that additionally evicted the _MEM_CACHE fallback on
                # every lookup. Skip it, exactly as _write_cache does on disk.
                logger.warning(f"[MEM CACHE SKIP] No expire found in {kind} stream URL for {str(val)[:80]}")
                return
            if len(_STREAM_CACHE) >= _MAX_STREAM_CACHE_SIZE:
                now = time.time()
                expired = [k for k, v in _STREAM_CACHE.items() if v[1] and now >= v[1] - 15]
                for k in expired:
                    _STREAM_CACHE.pop(k, None)
                if len(_STREAM_CACHE) >= _MAX_STREAM_CACHE_SIZE:
                    for k in list(_STREAM_CACHE.keys())[:100]:
                        _STREAM_CACHE.pop(k, None)
            _STREAM_CACHE[(kind, val)] = (value, expire)

    if len(_MEM_CACHE) >= _MAX_MEM_CACHE_SIZE:
        keys_to_remove = list(_MEM_CACHE.keys())[:100]
        for k in keys_to_remove:
            _MEM_CACHE.pop(k, None)
    _MEM_CACHE[key] = value

logger = logging.getLogger(__name__)

# Single long-lived HTTP client shared by every network resolver (InnerTube,
# ytube API, YouTube Data API). httpx pools connections per-host, so the
# search+player pair InnerTube fires on each /play reuses one warm TCP+TLS
# connection instead of paying a fresh DNS/TCP/TLS handshake per request.
# Measured: ~3s -> ~0.7s p50, and the multi-second tail collapses.
# Lazily created on first use so it binds to the running event loop.
_http_client: "httpx.AsyncClient | None" = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        use_h2 = False
        try:
            import h2  # noqa: F401
            use_h2 = True
        except ImportError:
            logger.warning("[youtube] h2 package not installed; HTTP/2 disabled for httpx client")

        verify: bool | str = True
        try:
            import certifi
            ca_path = certifi.where()
            if os.path.exists(ca_path):
                verify = ca_path
        except Exception as e:
            logger.debug(f"[youtube.get_http_client] certifi CA bundle unavailable, falling back to default verification: {e}")

        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            http2=use_h2,
            verify=verify,
            limits=httpx.Limits(max_keepalive_connections=20, keepalive_expiry=90),
        )
    return _http_client


async def close_http_client():
    """Gracefully close the global httpx client on shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# All config read from config.py (single source of truth)
from config import (
    YT_API_TOKEN as API_TOKEN,
    NUB_YT_API_BASE_URL as BASE_URL,
    YOUTUBE_API_KEYS as _YOUTUBE_API_KEYS_RAW,
    YT_COOKIES_FILE,
    COOKIES_FROM_BROWSER,
    COOKIES_BOOTSTRAP_URL,
    COOKIES_REFRESH_HOURS,
    MAX_FILE_SIZE_BYTES,
    ALLOW_PRIVATE_STREAM_URLS,
)
from url_guard import check_url as check_stream_url

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DETAILS_URL = "https://www.googleapis.com/youtube/v3/videos"

YOUTUBE_API_KEYS = [k.strip() for k in _YOUTUBE_API_KEYS_RAW.split(",") if k.strip()]

def is_direct_stream_url(url: str) -> bool:
    """Return True if url is a direct HTTP/HTTPS stream link (not a standard YouTube watch/playlist page or Spotify link)."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False
    if re.search(r"spotify\.com", url, re.I):
        return False
    if re.search(r"(youtube\.com/(watch|playlist|shorts|embed)|youtu\.be/)", url, re.I):
        return False
    return True


def get_random_key():
    if not YOUTUBE_API_KEYS:
        raise RuntimeError("YouTube API key not configured")
    return random.choice(YOUTUBE_API_KEYS)

def parse_dur(duration: str) -> str:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return "N/A"
    hours, minutes, seconds = match.groups(default="0")
    h = int(hours)
    m = int(minutes)
    s = int(seconds)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def format_ind(n):
    try:
        n = float(n)
    except (ValueError, TypeError):
        return "0"
    if n >= 10**7:
        return f"{n / 10**7:.1f} Crore"
    if n >= 10**5:
        return f"{n / 10**5:.1f} Lakh"
    if n >= 10**3:
        return f"{n / 10**3:.1f}K"
    return str(int(n))

def extract_artist(title: str, channel: str):
    if "-" in title:
        name = title.split("-", 1)[0].strip()
        if name:
            return name
    return channel or "Unknown Artist"

def process_video(item, details):
    try:
        video_id = item["id"]["videoId"]
        snippet = item.get("snippet", {})
        title = snippet.get("title", "")
        channel = snippet.get("channelTitle", "")
        thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
        url = f"https://www.youtube.com/watch?v={video_id}"
        duration = details.get("contentDetails", {}).get("duration", "N/A")
        views = details.get("statistics", {}).get("viewCount", "0")
        artist = extract_artist(title, channel)
        return {
            "title": title,
            "url": url,
            "video_id": video_id,
            "video_url": url,
            "artist_name": artist,
            "channel_name": channel,
            "views": format_ind(views),
            "duration": parse_dur(duration),
            "thumbnail": thumbnail,
        }
    except Exception:
        return None

async def youtube_search(query: str, limit: int = 1):
    if is_direct_stream_url(query):
        return []
    if not YOUTUBE_API_KEYS:
        return []
    client = get_http_client()
    api_key = get_random_key()
    search_params = {
        "part": "snippet",
        "q": query,
        "maxResults": limit,
        "type": "video",
        "key": api_key,
    }
    search_api_url = f"{SEARCH_URL}?q={query}&type=video&part=snippet&maxResults={limit}"
    logger.info(f"[API CALL] YouTube Data API Search -> {search_api_url}")
    print(f"[API CALL] YouTube Data API Search -> {search_api_url}", flush=True)
    search_res = await client.get(SEARCH_URL, params=search_params)
    if search_res.status_code != 200:
        return []
    items = search_res.json().get("items", [])
    video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
    if not video_ids:
        return []
    api_key = get_random_key()
    details_params = {
        "part": "contentDetails,statistics",
        "id": ",".join(video_ids),
        "key": api_key,
    }
    details_api_url = f"{DETAILS_URL}?id={','.join(video_ids)}&part=contentDetails,statistics"
    logger.info(f"[API CALL] YouTube Data API Details -> {details_api_url}")
    print(f"[API CALL] YouTube Data API Details -> {details_api_url}", flush=True)
    detail_res = await client.get(DETAILS_URL, params=details_params)
    if detail_res.status_code != 200:
        return []
    detail_items = {v["id"]: v for v in detail_res.json().get("items", [])}
    results = []
    for item in items:
        video_id = item["id"].get("videoId")
        if not video_id:
            continue
        video_details = detail_items.get(video_id)
        if not video_details:
            continue
        video_info = process_video(item, video_details)
        if video_info:
            results.append(video_info)
    return results

def _key(url: str, prefix: str = "") -> str:
    return hashlib.md5((prefix + url).encode()).hexdigest()

def _cache_path(url: str, prefix: str = "") -> str:
    return os.path.join(_CACHE_DIR, _key(url, prefix) + ".json")

def _extract_expire(stream_url: str) -> int | None:
    try:
        q = parse_qs(urlparse(stream_url).query)
        expire = int(q.get("expire", [0])[0])
        return expire if expire > int(time.time()) else None
    except Exception:
        return None

# The disk cache sits on the /play hot path, so the blocking parts (stat, open,
# json, unlink) live in *_sync helpers and the coroutines below hand them to a
# worker thread. Previously every resolve did this filesystem work directly on the
# event loop, stalling playback in every other chat for the duration.

def _read_cache_sync(url: str, prefix: str = "") -> str | None:
    path = _cache_path(url, prefix)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        expire = data.get("expire", 0)
        if time.time() < expire - 15:
            logger.info(f"[CACHE HIT] {prefix}{url[:80]}... (expires in {int(expire - time.time())}s)")
            return data.get("url")
        logger.info(f"[CACHE EXPIRED] {prefix}{url[:80]}... removing")
        os.remove(path)
    except Exception as e:
        logger.debug(f"[CACHE READ] Discarding unreadable entry {os.path.basename(path)}: {type(e).__name__} - {e}")
        try:
            os.remove(path)
        except Exception as remove_error:
            logger.debug(f"[CACHE READ] Could not remove {os.path.basename(path)}: {remove_error}")
    return None


def _write_cache_sync(url: str, stream_url: str, prefix: str = ""):
    expire = _extract_expire(stream_url)
    if not expire:
        logger.warning(f"[CACHE SKIP] No expire found in stream URL for {url[:80]}")
        return
    try:
        # 0o600: the payload is a signed CDN URL, so anyone who can read this file
        # can stream the media until it expires. Under the default umask the file
        # would be group- and world-readable, which matters on a shared host. fchmod
        # as well as the open mode, because O_TRUNC reuses an existing file and
        # would keep whatever permissions it already had.
        fd = os.open(_cache_path(url, prefix), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"url": stream_url, "expire": expire}, f)
        logger.info(f"[CACHE WRITE] {prefix}{url[:80]}... (expires in {int(expire - time.time())}s)")
    except Exception as e:
        logger.error(f"[CACHE WRITE ERROR] {e}")


async def _read_cache(url: str, prefix: str = "") -> str | None:
    return await asyncio.to_thread(_read_cache_sync, url, prefix)


async def _write_cache(url: str, stream_url: str, prefix: str = ""):
    # Awaited rather than fire-and-forget: the thread hop costs far less than the
    # resolve that just happened, and it keeps a following read consistent with
    # the write. _write_cache_sync swallows and logs its own failures.
    await asyncio.to_thread(_write_cache_sync, url, stream_url, prefix)


def evict_stream_cache(url: str, mode: str = "audio"):
    """Evict stream cache for a given URL across memory and disk caches."""
    if not url:
        return
    _STREAM_CACHE.pop((mode, url), None)
    _MEM_CACHE.pop((mode, url), None)
    prefix = f"{mode}_"
    try:
        path = _cache_path(url, prefix)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"[CACHE EVICT] Evicted cache for {prefix}{url[:80]}")
    except Exception as e:
        logger.debug(f"[CACHE EVICT] Could not remove disk cache file: {e}")


async def _kill_process(process):
    """Kill and reap a yt-dlp child process.

    `asyncio.wait_for` only cancels our side of `communicate()`; the child keeps
    running and its pipes stay open, so a bot that times out regularly leaks one
    process and three fds per attempt for its whole lifetime.
    """
    if process is None or process.returncode is not None:
        return
    try:
        process.kill()
    except ProcessLookupError:
        return  # already exited between the check and the kill
    except Exception as e:
        logger.debug(f"[YT-DLP] kill() failed: {e}")
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except Exception:
        logger.warning(f"[YT-DLP] child pid={process.pid} did not exit after kill()")


async def _run_yt_dlp(url: str, format_selector: str, cookies: str | None):
    cmd = [
        "yt-dlp",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "-f", format_selector,
        "--no-playlist",
        "-g",
        url,
    ]
    cookies = cookies or YT_COOKIES_FILE
    if cookies and os.path.exists(cookies):
        cmd.insert(1, "--cookies")
        cmd.insert(2, cookies)
    # No cookies file → run without cookies. (Previously fell back to a Firefox
    # browser profile that isn't present in prod, causing a 40s stall per call.)
    sanitized_cmd = [c if (not cookies or c != cookies) else "[REDACTED]" for c in cmd]
    logger.debug(f"[YT-DLP] Running: {' '.join(sanitized_cmd)}")
    start = time.time()
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=40,
        )
    except asyncio.TimeoutError:
        logger.error(f"[YT-DLP] TIMEOUT after 40s for {url}")
        await _kill_process(process)
        return None
    except Exception as e:
        logger.error(f"[YT-DLP] Exception: {e}")
        await _kill_process(process)
        return None
    elapsed = round(time.time() - start, 2)
    if process.returncode == 0 and stdout:
        stream_url = stdout.decode().strip().split("\n")[0]
        logger.info(f"[YT-DLP] ✅ Success ({elapsed}s) — {stream_url}")
        print(f"[DIRECT URL] yt-dlp extracted stream URL: {stream_url}", flush=True)
        return stream_url
    stderr_text = stderr.decode().strip() if stderr else "no stderr"
    logger.error(f"[YT-DLP] ❌ Failed (exit={process.returncode}, {elapsed}s) — {url}")
    logger.error(f"[YT-DLP] stderr: {stderr_text[-500:]}")
    return None

# Innertube API Configuration
INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
INNERTUBE_CLIENT_ANDROID = {
    "clientName": "ANDROID",
    "clientVersion": "20.10.38",
    "androidSdkVersion": 30,
    "hl": "en",
    "gl": "US",
}
INNERTUBE_HEADERS_ANDROID = {
    "Content-Type": "application/json",
    "X-Youtube-Client-Name": "3",
    "User-Agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 11) gzip",
}

INNERTUBE_CLIENT_VR = {
    "clientName": "ANDROID_VR",
    "clientVersion": "1.65.10",
    "deviceMake": "Oculus",
    "deviceModel": "Quest 3",
    "androidSdkVersion": 32,
    "osName": "Android",
    "osVersion": "12L",
    "hl": "en",
    "gl": "US",
}
INNERTUBE_HEADERS_VR = {
    "Content-Type": "application/json",
    "X-Youtube-Client-Name": "28",
    "User-Agent": "com.google.android.apps.youtube.vr.oculus/1.65.10 (Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip",
}

INNERTUBE_CLIENT_REMIX = {
    "clientName": "WEB_REMIX",
    "clientVersion": "1.20240101.01.00",
    "hl": "en",
    "gl": "US",
}
INNERTUBE_HEADERS_REMIX = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://music.youtube.com/",
}



def _innertube_extract_vid(url_or_query: str) -> str | None:
    if not url_or_query:
        return None
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/|/live/)([A-Za-z0-9_-]{11})", url_or_query)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_query.strip()):
        return url_or_query.strip()
    return None


async def _post_innertube_async(endpoint: str, payload: dict, client: dict = INNERTUBE_CLIENT_ANDROID, headers: dict = INNERTUBE_HEADERS_ANDROID) -> dict:
    url = f"https://youtubei.googleapis.com/youtubei/v1/{endpoint}?key={INNERTUBE_KEY}"
    logger.info(f"[API CALL] Innertube {endpoint} -> {url}")
    print(f"[API CALL] Innertube {endpoint} -> {url}", flush=True)
    body = {"context": {"client": client}, **payload}
    http = get_http_client()
    resp = await http.post(url, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()


def _first_video_id(node) -> tuple[str, str | None] | None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower().endswith("videorenderer") and isinstance(v, dict) and v.get("videoId"):
                title = None
                t_node = v.get("title")
                if isinstance(t_node, dict):
                    title = t_node.get("simpleText") or "".join(r.get("text", "") for r in t_node.get("runs", []))
                return v["videoId"], title
        for v in node.values():
            res = _first_video_id(v)
            if res:
                return res
    elif isinstance(node, list):
        for item in node:
            res = _first_video_id(item)
            if res:
                return res
    return None


def _pick_best_format(formats: list, *keys) -> dict | None:
    def rank(f):
        return tuple(("mp4" in (f.get("mimeType") or "")) if k == "mp4" else (f.get(k) or 0) for k in keys)

    valid = [f for f in formats if f.get("url")]
    return sorted(valid, key=rank)[-1] if valid else None


def pick_innertube_streams(streaming_data: dict) -> dict:
    """
    Pick strictly from progressive Muxed streams (audio + video combined, e.g. formats array).
    """
    if not streaming_data:
        return {"stream": None}

    formats = streaming_data.get("formats") or []
    muxed = _pick_best_format(formats, "height", "bitrate")

    return {
        "stream": (muxed or {}).get("url"),
    }


async def resolve_innertube(argument: str, mode: str = "audio") -> dict | None:
    """
    Resolve YouTube stream and metadata using direct Innertube player/search endpoints.
    Innertube ONLY provides Muxed Streams (audio + video progressive formats).
    """
    try:
        vid = _innertube_extract_vid(argument)
        if not vid:
            # query -> video_id is stable, so cache it (no expiry): a replay of
            # the same search skips the search round-trip and only re-fetches a
            # fresh (unexpired) stream URL via the player call below.
            vid = _mem_cache_get(("search", argument))
            if not vid:
                search_resp = await _post_innertube_async("search", {"query": argument})
                hit = _first_video_id(search_resp)
                if not hit:
                    logger.warning(f"[Innertube] Search gave no results for: {argument}")
                    return None
                vid = hit[0]
                _mem_cache_set(("search", argument), vid)

        player_data = None
        try:
            player_data = await _post_innertube_async("player", {"videoId": vid}, INNERTUBE_CLIENT_ANDROID, INNERTUBE_HEADERS_ANDROID)
        except Exception as e:
            logger.warning(f"[Innertube] ANDROID client failed for {vid}: {e}")

        ps = (player_data or {}).get("playabilityStatus") or {}
        if ps.get("status") != "OK":
            try:
                visitor = ((player_data or {}).get("responseContext") or {}).get("visitorData")
                vr_client = {**INNERTUBE_CLIENT_VR}
                if visitor:
                    vr_client["visitorData"] = visitor
                player_data = await _post_innertube_async("player", {"videoId": vid}, vr_client, INNERTUBE_HEADERS_VR)
                ps = (player_data or {}).get("playabilityStatus") or {}
            except Exception as e:
                logger.warning(f"[Innertube] ANDROID_VR client failed for {vid}: {e}")

        if ps.get("status") != "OK":
            logger.warning(f"[Innertube] Video {vid} playability status: {ps.get('status')} - {ps.get('reason')}")
            return None

        details = player_data.get("videoDetails") or {}
        sd = player_data.get("streamingData") or {}
        picked = pick_innertube_streams(sd)

        stream_url = picked.get("stream")
        if not stream_url:
            logger.warning(f"[Innertube] No muxed stream URL found for {vid}")
            return None

        logger.info(f"[DIRECT URL] Innertube resolved stream URL: {stream_url}")
        print(f"[DIRECT URL] Innertube resolved stream URL: {stream_url}", flush=True)


        title = details.get("title", "N/A")
        duration_sec = int(details.get("lengthSeconds", 0))
        # format_duration handles minute/hour rollover; parse_dur(f"PT{n}S") does
        # not, and would render 213s as "0:213" instead of "03:33".
        if details.get("isLive") or details.get("isLiveContent") or (not duration_sec and details.get("isLive") is not False):
            duration_formatted = "Live Stream"
        else:
            duration_formatted = format_duration(duration_sec) if duration_sec else "N/A"
        youtube_link = f"https://www.youtube.com/watch?v={vid}"
        thumbs = (details.get("thumbnail") or {}).get("thumbnails") or []
        thumbnail_url = thumbs[-1].get("url") if thumbs else "N/A"
        channel_name = details.get("author", "N/A")
        views = format_ind(details.get("viewCount", "0"))

        return {
            "title": title,
            "video_id": vid,
            "duration": duration_formatted,
            "duration_sec": duration_sec,
            "youtube_link": youtube_link,
            "channel_name": channel_name,
            "views": views,
            "stream_url": stream_url,
            "thumbnail": thumbnail_url,
            "picked_streams": picked,
        }
    except Exception as e:
        logger.error(f"[Innertube] Resolution exception for '{argument}': {e}")
        return None


async def get_stream(url: str, cookies: str | None = None) -> str | None:
    logger.info(f"[AUDIO] get_stream called: {url}")
    cached = _mem_cache_get(("audio", url))
    if cached:
        logger.info(f"[AUDIO] MEM_CACHE hit for {url[:80]}")
        return cached
    cached = await _read_cache(url, prefix="audio_")
    if cached:
        _mem_cache_set(("audio", url), cached)
        return cached
    logger.info("[AUDIO] No cache, extracting fresh stream...")

    # Fast Path 1: ytube API (/info) if configured and breaker is closed
    if API_TOKEN and BASE_URL and not _api_breaker_open():
        try:
            api_url = f"{BASE_URL}/info?q={url}"
            logger.info(f"[API CALL] ytube audio API -> {api_url}")
            print(f"[API CALL] ytube audio API -> {api_url}", flush=True)
            resp = await get_http_client().get(
                f"{BASE_URL}/info",
                params={"q": url},
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stream_url"):
                    stream = data["stream_url"]
                    logger.info(f"[AUDIO] ✅ ytube API success — {stream}")
                    print(f"[DIRECT URL] Audio stream URL (ytube API): {stream}", flush=True)
                    _api_record_success()
                    _mem_cache_set(("audio", url), stream)
                    await _write_cache(url, stream, prefix="audio_")
                    return stream
            _api_record_failure()
        except Exception as e:
            logger.warning(f"[AUDIO] ytube API extraction failed: {e}")
            _api_record_failure()

    # Fast Path 2: Innertube direct resolution
    innertube_data = await resolve_innertube(url, mode="audio")
    if innertube_data and innertube_data.get("stream_url"):
        stream = innertube_data["stream_url"]
        logger.info(f"[AUDIO] ✅ Innertube success — {stream}")
        print(f"[DIRECT URL] Audio stream URL (Innertube): {stream}", flush=True)
        _mem_cache_set(("audio", url), stream)
        await _write_cache(url, stream, prefix="audio_")
        return stream

    logger.warning("[AUDIO] Innertube & API extraction returned None, falling back to yt-dlp...")
    stream = await _run_yt_dlp(
        url,
        "bestaudio[ext=m4a]/bestaudio/best",
        cookies,
    )
    if stream:
        logger.info(f"[DIRECT URL] Audio stream URL (yt-dlp): {stream}")
        print(f"[DIRECT URL] Audio stream URL (yt-dlp): {stream}", flush=True)
        _mem_cache_set(("audio", url), stream)
        await _write_cache(url, stream, prefix="audio_")
    else:
        logger.warning(f"[AUDIO] Extraction returned None for {url}")
    return stream

async def get_video_stream(url: str, cookies: str | None = None) -> str | None:
    logger.info(f"[VIDEO] get_video_stream called: {url}")
    cached = _mem_cache_get(("video", url))
    if cached:
        logger.info(f"[VIDEO] MEM_CACHE hit for {url[:80]}")
        return cached
    cached = await _read_cache(url, prefix="video_")
    if cached:
        _mem_cache_set(("video", url), cached)
        return cached
    logger.info("[VIDEO] No cache, extracting fresh stream...")

    # Fast Path 1: ytube API (/info) if configured and breaker is closed
    if API_TOKEN and BASE_URL and not _api_breaker_open():
        try:
            api_url = f"{BASE_URL}/info?q={url}&mode=video"
            logger.info(f"[API CALL] ytube video API -> {api_url}")
            print(f"[API CALL] ytube video API -> {api_url}", flush=True)
            resp = await get_http_client().get(
                f"{BASE_URL}/info",
                params={"q": url, "mode": "video"},
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stream_url"):
                    stream = data["stream_url"]
                    logger.info(f"[VIDEO] ✅ ytube API video success — {stream}")
                    print(f"[DIRECT URL] Video stream URL (ytube API): {stream}", flush=True)
                    _api_record_success()
                    _mem_cache_set(("video", url), stream)
                    await _write_cache(url, stream, prefix="video_")
                    return stream
            _api_record_failure()
        except Exception as e:
            logger.warning(f"[VIDEO] ytube API video extraction failed: {e}")
            _api_record_failure()

    # Fast Path 2: Innertube direct resolution (muxed / video stream)
    innertube_data = await resolve_innertube(url, mode="video")
    if innertube_data and innertube_data.get("stream_url"):
        stream = innertube_data["stream_url"]
        logger.info(f"[VIDEO] ✅ Innertube success — {stream}")
        print(f"[DIRECT URL] Video stream URL (Innertube): {stream}", flush=True)
        _mem_cache_set(("video", url), stream)
        await _write_cache(url, stream, prefix="video_")
        return stream

    logger.warning("[VIDEO] Innertube & API extraction returned None, falling back to yt-dlp...")
    stream = await _run_yt_dlp(
        url,
        "best[ext=mp4][protocol=https]",
        cookies,
    )
    if stream:
        logger.info(f"[DIRECT URL] Video stream URL (yt-dlp): {stream}")
        print(f"[DIRECT URL] Video stream URL (yt-dlp): {stream}", flush=True)
        _mem_cache_set(("video", url), stream)
        await _write_cache(url, stream, prefix="video_")
    else:
        logger.warning(f"[VIDEO] Extraction returned None for {url}")
    return stream


# New: Get video info using local search and stream extraction
# Circuit breaker for the external ytube resolution API: after N consecutive
# failures/timeouts, skip it for a cooldown window instead of paying the ~15s
# timeout on every single call. Resets on the first success.
_API_FAIL_THRESHOLD = 3
_API_COOLDOWN_S = 60
_api_fail_count = 0
_api_cooldown_until = 0.0


def _api_breaker_open() -> bool:
    return time.time() < _api_cooldown_until


def _api_record_success():
    global _api_fail_count, _api_cooldown_until
    _api_fail_count = 0
    _api_cooldown_until = 0.0


def _api_record_failure():
    global _api_fail_count, _api_cooldown_until
    _api_fail_count += 1
    if _api_fail_count >= _API_FAIL_THRESHOLD:
        _api_cooldown_until = time.time() + _API_COOLDOWN_S
        logger.warning(
            f"[youtube] ytube API circuit breaker OPEN for {_API_COOLDOWN_S}s "
            f"after {_api_fail_count} consecutive failures"
        )


async def get_video_info(query: str, max_results: int = 1, mode: str = "audio") -> Tuple[str, str, str, str, str, str, str, str, str]:
    """Get video info using ytube API, Innertube resolution, or local search fallback."""
    # Direct stream URL handling (bypasses ytube API completely)
    if is_direct_stream_url(query):
        logger.info(f"[DIRECT URL] Direct stream URL requested: {query}")
        print(f"[DIRECT URL] Direct stream URL requested: {query}", flush=True)
        details = await get_video_details(query)
        if details and "error" not in details:
            return (
                details.get("title", "Direct Stream"),
                query,
                details.get("duration", "N/A"),
                query,
                details.get("channel_name", "Direct Stream"),
                "N/A",
                details.get("stream_url", query),
                details.get("thumbnail", "N/A"),
                "direct",
            )
        return (None,) * 9

    # Primary: ytube /info API endpoint (api > innertube > ytdlp)
    if API_TOKEN and BASE_URL and not _api_breaker_open():
        try:
            api_url = f"{BASE_URL}/info?q={query}"
            if mode == "video":
                api_url += "&mode=video"
            logger.info(f"[API CALL] ytube /info API -> {api_url}")
            print(f"[API CALL] ytube /info API -> {api_url}", flush=True)
            params = {"q": query}
            if mode == "video":
                params["mode"] = "video"
            resp = await get_http_client().get(
                f"{BASE_URL}/info",
                params=params,
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stream_url") and data.get("title"):
                    stream_url = data.get("stream_url")
                    logger.info(f"[DIRECT URL] ytube API stream URL: {stream_url}")
                    print(f"[DIRECT URL] ytube API stream URL: {stream_url}", flush=True)
                    _api_record_success()
                    return (
                        data.get('title', 'N/A'),
                        data.get('video_id', 'N/A'),
                        data.get('duration', '0'),
                        data.get('youtube_link', 'N/A'),
                        data.get('channel_name', 'N/A'),
                        data.get('views', '0'),
                        stream_url,
                        data.get('thumbnail', 'N/A'),
                        'ytube',
                    )
            logger.warning(f"[youtube.get_video_info] ytube API returned status {resp.status_code}, falling back to Innertube")
            _api_record_failure()
        except Exception as e:
            logger.warning(f"[youtube.get_video_info] ytube API failed: {e}, falling back to Innertube")
            _api_record_failure()

    # Secondary: Fast Innertube direct resolution
    try:
        logger.info(f"[API CALL] Resolving via Innertube for query: '{query}' (mode={mode})")
        print(f"[API CALL] Resolving via Innertube for query: '{query}' (mode={mode})", flush=True)
        innertube_res = await resolve_innertube(query, mode=mode)
        if innertube_res and innertube_res.get("stream_url"):
            logger.info(f"[youtube.get_video_info] Innertube direct success: title='{innertube_res.get('title')}'")
            return (
                innertube_res.get('title', 'N/A'),
                innertube_res.get('video_id', 'N/A'),
                innertube_res.get('duration', '0'),
                innertube_res.get('youtube_link', 'N/A'),
                innertube_res.get('channel_name', 'N/A'),
                innertube_res.get('views', '0'),
                innertube_res.get('stream_url', 'N/A'),
                innertube_res.get('thumbnail', 'N/A'),
                'innertube',
            )
    except Exception as e:
        logger.warning(f"[youtube.get_video_info] Innertube direct resolution failed: {e}")

    # Fallback: local YouTube Data API search + stream extraction
    try:
        logger.debug(f"[youtube.get_video_info] Falling back to local search for '{query}' (max_results={max_results}, mode={mode})")
        results = await youtube_search(query, limit=max_results)
        if not results:
            return (None,) * 9
        video = results[0]
        video_id = video['url'].split('v=')[-1]
        stream_url = await get_stream(video['url']) if mode == "audio" else await get_video_stream(video['url'])
        return (
            video.get('title', 'N/A'),
            video_id,
            video.get('duration', '0'),
            video.get('url', 'N/A'),
            video.get('channel_name', 'N/A'),
            video.get('views', '0'),
            stream_url or 'N/A',
            video.get('thumbnail', 'N/A'),
            'local',
        )
    except Exception as e:
        logger.error(f"[youtube.get_video_info] Exception: {e}")
        return (None,) * 9



def extract_video_id(url):
    """
    Extract 11-character YouTube video ID from various forms of YouTube URLs.

    Args:
        url (str): YouTube video URL

    Returns:
        str: 11-character Video ID or None if not found
    """
    if not url or not isinstance(url, str):
        return None
    try:
        logger.debug(f"[youtube.extract_video_id] Extracting video id from url='{url}'")
        patterns = [
            r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})',
            r'(?:watch\?v=)([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                logger.debug(f"[youtube.extract_video_id] Matched pattern '{pattern}', video_id='{video_id}'")
                return video_id

        logger.debug("[youtube.extract_video_id] No match found")
        return None

    except Exception as e:
        logger.error(f"[youtube.extract_video_id] Error: {e}")
        return None


def format_number(num):
    """Format number to international system (K, M, B). Accepts only digits."""
    if num is None:
        logger.debug("[youtube.format_number] Input is None")
        return "N/A"

    # If input is a string, check if it's digits only
    if isinstance(num, str):
        num = num.replace(',', '')
        if not num.isdigit():
            logger.debug(f"[youtube.format_number] Non-digit string input: {num}")
            return "N/A"
        num = int(num)

    # If not int/float after conversion, reject
    if not isinstance(num, (int, float)):
        logger.debug(f"[youtube.format_number] Invalid type: {type(num).__name__}")
        return "N/A"

    if num < 1000:
        return str(num)

    magnitude = 0
    original_num = num
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0

    # Add precision based on magnitude
    if magnitude > 0:
        num = round(num, 1)
        if isinstance(num, float) and num.is_integer():
            num = int(num)

    formatted = f"{num:g}{'KMB'[magnitude-1]}"
    logger.debug(f"[youtube.format_number] Formatted {original_num} -> {formatted}")
    return formatted

def format_duration(seconds):
    """Formats duration from seconds to HH:MM:SS or MM:SS"""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        logger.debug(f"[youtube.format_duration] Invalid seconds input: {seconds}")
        return "N/A"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        formatted = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        formatted = f"{minutes:02d}:{secs:02d}"

    return formatted

def time_to_seconds(time):
    stringt = str(time)
    try:
        seconds = sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))
        logger.debug(f"[youtube.time_to_seconds] Converted '{time}' -> {seconds}s")
        return seconds
    except Exception as e:
        logger.warning(f"[youtube.time_to_seconds] Failed to convert '{time}': {e}")
        return 0

async def _export_cookies():
    """Re-export the browser cookie jar into YT_COOKIES_FILE. yt-dlp writes the
    Netscape file to --cookies after running, so pairing it with
    --cookies-from-browser persists the browser session to a file. The bootstrap
    URL makes yt-dlp exit cleanly and validates the cookies against a real
    request.

    COOKIES_FROM_BROWSER may name several browsers (comma/space-separated); each
    is tried in order and the first to produce a valid file wins.

    Best effort: never raises, and bounded by a timeout so a missing or locked
    browser profile can't hang startup (the reason the old per-call browser
    fallback was removed). Runtime yt-dlp calls already gate on the file
    existing, so a failed export just means "no cookies", not a crash.
    """
    browsers = [b for b in re.split(r"[,\s]+", COOKIES_FROM_BROWSER or "") if b]
    if not browsers or not YT_COOKIES_FILE:
        return
    errors = []
    for browser in browsers:
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", browser,
            "--cookies", YT_COOKIES_FILE,
            "--skip-download",
            COOKIES_BOOTSTRAP_URL,
        ]
        logger.info(f"[cookies] Exporting {YT_COOKIES_FILE} from {browser}...")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                errors.append(f"{browser}: timed out")
                continue
        except FileNotFoundError:
            logger.error("[cookies] yt-dlp not found; skipping cookie export")
            return
        except Exception as e:
            errors.append(f"{browser}: {e}")
            continue

        if os.path.exists(YT_COOKIES_FILE) and os.path.getsize(YT_COOKIES_FILE) > 0:
            logger.info(f"[cookies] ✅ Cookie file ready from {browser} "
                        f"({os.path.getsize(YT_COOKIES_FILE)} bytes)")
            return
        tail = (stderr.decode(errors="replace").strip().splitlines() or ["no stderr"])[-1]
        errors.append(f"{browser}: {tail}")

    logger.warning(f"[cookies] ❌ No cookie file produced from any of {browsers} "
                   f"(profiles not present/locked?) — {'; '.join(errors)}")


async def export_browser_cookies():
    """Export browser cookies into YT_COOKIES_FILE once, at startup. No-op unless
    COOKIES_FROM_BROWSER is set."""
    if not COOKIES_FROM_BROWSER or not YT_COOKIES_FILE:
        return
    await _export_cookies()


async def refresh_cookies_loop():
    """Re-export cookies every COOKIES_REFRESH_HOURS — YouTube rotates tokens
    mid-session, so the file goes stale. No-op unless enabled."""
    if not COOKIES_FROM_BROWSER or not YT_COOKIES_FILE or COOKIES_REFRESH_HOURS <= 0:
        return
    logger.info(f"[cookies] Refresh every {COOKIES_REFRESH_HOURS}h")
    while True:
        await asyncio.sleep(COOKIES_REFRESH_HOURS * 3600)
        await _export_cookies()


def log_ytdlp_version():
    """Log the installed yt-dlp version. Purely informational.

    This deliberately does NOT check PyPI or upgrade anything. The bot used to
    run `pip install -U yt-dlp` at every startup, which mutated its own
    dependencies at runtime, made the deployed version unreproducible, and
    blocked the event loop for up to ~130s on a slow network. yt-dlp is now
    whatever the image/venv was built with -- bump it by rebuilding, not by
    restarting the bot.
    """
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            installed = version("yt-dlp")
        except PackageNotFoundError:
            logger.warning("[youtube] yt-dlp is not installed; playback will fail until it is")
            return None
        logger.info(f"[youtube] yt-dlp version {installed}")
        return installed
    except Exception as e:
        logger.warning(f"[youtube] Could not determine yt-dlp version: {e}")
        return None


def extract_best_format(formats):
    """Pick the best format (progressive MP4 preferred) and return URL"""
    if not formats:
        logger.debug("[youtube.extract_best_format] No formats provided")
        return 'N/A'

    def has_av_and_http(f):
        return (
            f.get("acodec") != "none"
            and f.get("vcodec") != "none"
            and str(f.get("protocol", "")).startswith("http")
            and f.get("url")
        )

    # Prefer progressive MP4 (most universally playable)
    for f in formats:
        if has_av_and_http(f) and f.get("ext") == "mp4":
            logger.debug("[youtube.extract_best_format] Selected progressive MP4 format")
            return f.get("url", 'N/A')

    # Next: any HTTP progressive (audio+video)
    for f in formats:
        if has_av_and_http(f):
            logger.debug("[youtube.extract_best_format] Selected progressive AV format")
            return f.get("url", 'N/A')

    # Fallback: first available URL
    for f in formats:
        if f.get("url"):
            logger.debug("[youtube.extract_best_format] Selected fallback format with URL")
            return f.get("url", 'N/A')

    return 'N/A'


async def _get_remote_file_size(url: str) -> int | None:
    """Fetch file size from Content-Length / Content-Range HTTP headers for non-live stream URLs."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    # Defence in depth: callers are expected to have gated the URL already, but
    # this function is the one that actually issues the request.
    block_reason = await check_stream_url(url, allow_private=ALLOW_PRIVATE_STREAM_URLS)
    if block_reason:
        logger.warning(f"[youtube._get_remote_file_size] Refused size check: {block_reason}")
        return None
    try:
        http = get_http_client()
        resp = await http.head(url, follow_redirects=True, timeout=5.0)
        if resp.status_code == 200 and "content-length" in resp.headers:
            val = resp.headers["content-length"]
            if val.isdigit():
                return int(val)
        resp = await http.get(url, headers={"Range": "bytes=0-0"}, follow_redirects=True, timeout=5.0)
        cr = resp.headers.get("content-range", "")
        if "/" in cr:
            total = cr.split("/")[-1]
            if total.isdigit():
                return int(total)
        cl = resp.headers.get("content-length", "")
        if cl.isdigit() and resp.status_code == 200:
            return int(cl)
    except Exception as e:
        logger.debug(f"[youtube._get_remote_file_size] Size check for {url[:60]}: {e}")
    return None


# Extensions whose path alone identifies a playable media file or HLS/DASH
# manifest. ffmpeg can stream these even when yt-dlp failed to understand the
# page, so a failed probe on one of these is recoverable; anything else is not.
_DIRECT_MEDIA_EXTS = (
    ".mp3", ".m4a", ".aac", ".opus", ".ogg", ".oga", ".flac", ".wav", ".wma",
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts",
    ".m3u8", ".mpd",
)


def _looks_playable_direct_url(url: str) -> bool:
    """True when the URL path itself names a media file or a streaming manifest.

    Used to decide whether a failed yt-dlp probe may still be passed through to
    the player. An HTML page or JSON endpoint must NOT be passed through: doing
    so hands py-tgcalls an unplayable URL and the user hears silence with no
    error message.
    """
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    return path.endswith(_DIRECT_MEDIA_EXTS)


def _extract_direct_info_sync(url: str) -> dict | None:
    """Blocking yt-dlp probe of a direct stream URL. Always run in a thread.

    yt-dlp's extract_info does network I/O and can execute JS challenges, so
    calling it on the event loop stalls every voice chat and the Telegram
    heartbeat for its full duration.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "http_chunk_size": 10485760,
        "retries": 1,
        "socket_timeout": 15,
        **({"cookiefile": YT_COOKIES_FILE} if YT_COOKIES_FILE and os.path.exists(YT_COOKIES_FILE) else {}),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        return None
    if "entries" in info and info["entries"]:
        info = info["entries"][0]
    return info


# Wall-clock budget for the direct-URL probe above. The worker thread cannot be
# cancelled, but the event loop stops waiting on it.
DIRECT_PROBE_TIMEOUT = 30


def _ytdlp_search_first_sync(query: str) -> dict | None:
    """Blocking yt-dlp `ytsearch:` metadata lookup. Always run in a thread.

    Last-resort fallback when the InnerTube -> ytube API -> Data API chain has
    yielded nothing. Same constraint as _extract_direct_info_sync: this does
    network I/O and may execute JS challenges, so it must never run on the loop.
    """
    ydl_opts = {
        # Only gather metadata, no downloads
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 15,
        **({"cookiefile": YT_COOKIES_FILE} if YT_COOKIES_FILE and os.path.exists(YT_COOKIES_FILE) else {}),

        # Performance optimizations
        "extract_flat": False,  # We need full info
        "writethumbnail": False,
        "writeinfojson": False,
        "writedescription": False,
        "writesubtitles": False,
        "writeautomaticsub": False,

        # Network optimizations
        "http_chunk_size": 10485760,  # 10MB chunks
        "retries": 1,  # Reduce retries for speed
        "fragment_retries": 1,

        # Skip unnecessary processing
        "skip_playlist_after_errors": 1,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_result = ydl.extract_info(f"ytsearch:{query}", download=False)
    entries = (search_result or {}).get("entries") or []
    return entries[0] if entries else None


# Searches go through a full extraction, so they get a longer budget than the
# direct-URL probe.
YTDLP_SEARCH_TIMEOUT = 60


async def get_video_details(video_id):
    """
    Get video details using direct stream resolution, API (for YouTube videos), or yt-dlp fallback.

    Args:
        video_id (str): Video ID or URL to fetch details for

    Returns:
        dict: Video details or error message
    """

    # Direct stream URL resolution (bypasses YouTube API and external ytube API)
    if is_direct_stream_url(video_id):
        logger.info(f"[DIRECT URL] Handling direct stream URL: {video_id}")
        print(f"[DIRECT URL] Handling direct stream URL: {video_id}", flush=True)

        # SSRF gate. Anyone in the group can pass a URL here, and everything
        # below fetches it -- so reject loopback / private / link-local targets
        # (cloud metadata, LAN services, admin ports) before the first request.
        block_reason = await check_stream_url(video_id, allow_private=ALLOW_PRIVATE_STREAM_URLS)
        if block_reason:
            logger.warning(f"[youtube.get_video_details] Refused direct URL: {block_reason} — {video_id[:120]}")
            return {"error": "That link points to a private or non-routable address, so it cannot be played."}

        is_live = (
            ".m3u8" in video_id.lower()
            or ".mpd" in video_id.lower()
            or "/live" in video_id.lower()
        )
        info = None
        probe_failed = False
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(_extract_direct_info_sync, video_id),
                timeout=DIRECT_PROBE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            probe_failed = True
            logger.warning(
                f"[youtube.get_video_details] Direct URL probe timed out after {DIRECT_PROBE_TIMEOUT}s: {video_id[:80]}"
            )
        except Exception as e:
            probe_failed = True
            logger.warning(f"[youtube.get_video_details] Direct URL yt-dlp extraction notice: {e}")

        if info:
            # extract_best_format signals failure with the *string* "N/A", which is
            # truthy -- so an `or` chain on its result silently swallows the
            # info["url"] fallback. Normalise it before falling back.
            best = extract_best_format(info.get("formats", []))
            if best == "N/A":
                best = None
            stream_url = best or info.get("url")
            if not stream_url:
                logger.warning(
                    f"[youtube.get_video_details] Probe returned metadata but no playable "
                    f"URL for {video_id[:80]}"
                )
                info = None

        if info:
            protocol = str(info.get("protocol", "")).lower()
            ext = str(info.get("ext", "")).lower()
            if (
                info.get("is_live") is True
                or info.get("live_status") == "is_live"
                or protocol in ("m3u8", "m3u8_native", "http_dash_segments")
                or ext in ("m3u8", "mpd")
            ):
                is_live = True

            duration = "Live Stream" if is_live else "N/A"
            if not is_live and info.get("duration"):
                try:
                    duration = format_duration(int(info["duration"]))
                except Exception:
                    duration = "N/A"

            # 2 GB limit check for non-live files
            if not is_live:
                filesize = info.get("filesize") or info.get("filesize_approx")
                if not filesize:
                    filesize = await _get_remote_file_size(video_id)
                if filesize and filesize > MAX_FILE_SIZE_BYTES:
                    size_mb = filesize / (1024 * 1024)
                    logger.warning(f"[youtube.get_video_details] Direct URL file size {size_mb:.1f}MB exceeds 2 GB limit")
                    return {"error": f"File size ({size_mb:.1f} MB) exceeds the 2 GB limit."}

            thumbnail = "N/A"
            if info.get("thumbnails"):
                thumbnail = info["thumbnails"][-1].get("url", "N/A")
            clean_filename = video_id.split("/")[-1].split("?")[0]
            title = info.get("title") or (clean_filename if clean_filename and len(clean_filename) < 50 else "Direct Stream")
            return {
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "view_count": "N/A",
                "channel_name": info.get("uploader") or "Direct Stream",
                "video_url": video_id,
                "platform": "Direct",
                "stream_url": stream_url,
                "video_id": video_id,
            }

        # The probe produced nothing. Passing the URL straight to the player is
        # only safe when the URL itself names media -- otherwise report the
        # failure instead of returning a success dict the caller cannot play.
        if not (is_live or _looks_playable_direct_url(video_id)):
            logger.error(
                f"[youtube.get_video_details] Direct URL is not a recognisable media stream "
                f"(probe_failed={probe_failed}): {video_id[:120]}"
            )
            return {"error": "Could not read that link as a media stream. Use a direct audio/video URL or an HLS/DASH manifest."}

        if not is_live:
            remote_size = await _get_remote_file_size(video_id)
            if remote_size and remote_size > MAX_FILE_SIZE_BYTES:
                size_mb = remote_size / (1024 * 1024)
                logger.warning(f"[youtube.get_video_details] Direct URL file size {size_mb:.1f}MB exceeds 2 GB limit")
                return {"error": f"File size ({size_mb:.1f} MB) exceeds the 2 GB limit."}

        clean_filename = video_id.split("/")[-1].split("?")[0]
        title = clean_filename if clean_filename and len(clean_filename) < 50 else "Direct Stream"
        duration = "Live Stream" if is_live else "N/A"
        return {
            "title": title,
            "thumbnail": "N/A",
            "duration": duration,
            "view_count": "N/A",
            "channel_name": "Direct Stream",
            "video_url": video_id,
            "platform": "Direct",
            "stream_url": video_id,
            "video_id": video_id,
        }

    # Primary resolution chain: InnerTube -> ytube API -> YouTube Data API
    # search, in that priority (get_video_info owns the chain). Always attempted
    # first, unconditionally — InnerTube must stay the primary resolver even when
    # no ytube token is configured. yt-dlp below is the last-resort fallback,
    # reached only when the whole chain yields nothing.
    try:
        logger.debug(f"[youtube.get_video_details] Resolving via get_video_info for video_id='{video_id}'")
        api_result = await get_video_info(video_id)

        if api_result and api_result[0] and api_result[0] != "N/A":
            title, video_id_result, duration, youtube_link, channel_name, views, stream_url, thumbnail, time_taken = api_result

            # Format duration if it's in seconds
            if isinstance(duration, int):
                duration = format_duration(duration)

            return {
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'view_count': views,
                'channel_name': channel_name,
                'video_url': youtube_link,
                'platform': 'YouTube',
                'stream_url': stream_url,
                'video_id': video_id_result
            }
        else:
            logger.warning("[youtube.get_video_details] Resolution chain returned no usable data, falling back to yt-dlp")
    except Exception as e:
        logger.error(f"[youtube.get_video_details] Resolution chain error: {e}")

    # Fallback to yt-dlp
    try:
        logger.debug(f"[youtube.get_video_details] Using yt-dlp fallback for video_id='{video_id}'")
        video_info = await asyncio.wait_for(
            asyncio.to_thread(_ytdlp_search_first_sync, video_id),
            timeout=YTDLP_SEARCH_TIMEOUT,
        )

        if not video_info:
            logger.warning("[youtube.get_video_details] No entries found in yt-dlp search")
            return {'error': 'No video found for the given ID'}

        # Create YouTube URL from video ID
        youtube_url = f"https://www.youtube.com/watch?v={video_info.get('id', video_id)}"

        # Process duration
        duration = 'N/A'
        if video_info.get('duration'):
            try:
                duration_seconds = int(video_info.get('duration'))
                duration = format_duration(duration_seconds)
            except (ValueError, TypeError):
                duration = 'N/A'

        # Get thumbnail URL
        thumbnail = 'N/A'
        if video_info.get('thumbnails'):
            thumbnail = video_info['thumbnails'][-1].get('url', 'N/A')

        # Extract best format stream URL. "N/A" is this helper's failure signal,
        # and a details dict carrying it is unplayable -- report the failure
        # rather than handing the caller a success it cannot stream.
        stream_url = extract_best_format(video_info.get('formats', []))
        if not stream_url or stream_url == 'N/A':
            logger.error(f"[youtube.get_video_details] yt-dlp returned no playable format for '{video_id}'")
            return {'error': 'No playable audio/video stream found for that track.'}
        logger.info(f"[DIRECT URL] yt-dlp resolved stream URL: {stream_url}")
        print(f"[DIRECT URL] yt-dlp resolved stream URL: {stream_url}", flush=True)

        # Prepare details dictionary
        details = {
            'title': video_info.get('title', 'N/A'),
            'thumbnail': thumbnail,
            'duration': duration,
            'view_count': video_info.get('view_count', 'N/A'),
            'channel_name': video_info.get('uploader', 'N/A'),
            'video_url': youtube_url,
            'platform': 'YouTube',
            'stream_url': stream_url,
            'video_id': video_info.get('id', video_id)
        }

        logger.info(f"[youtube.get_video_details] yt-dlp details extracted for id='{details.get('video_id')}'")
        return details

    except asyncio.TimeoutError:
        logger.error(f"[youtube.get_video_details] yt-dlp search timed out after {YTDLP_SEARCH_TIMEOUT}s for '{video_id}'")
        return {'error': 'Lookup timed out. Please try again.'}
    except (yt_dlp.utils.ExtractorError, yt_dlp.utils.DownloadError) as youtube_error:
        logger.error(f"[youtube.get_video_details] YouTube extraction failed: {youtube_error}")
        return {'error': f"YouTube extraction failed: {youtube_error}"}
    except Exception as e:
        logger.error(f"[youtube.get_video_details] Unexpected error: {e}")
        return {'error': f"Unexpected error: {str(e)}"}

async def handle_youtube(argument, track_id=None, chat_id=None, update_callback=None):
    """
    Main function to get YouTube video information.
    Prioritizes API calls, falls back to yt-dlp via get_video_details.

    Returns:
        tuple: (title, duration, youtube_link, thumbnail, channel_name, views, video_id, stream_url)
    """

    logger.debug(f"[youtube.handle_youtube] Handling argument='{argument}'")
    details = await get_video_details(argument)

    if 'error' in details:
        err_msg = str(details.get('error', 'Error'))
        logger.warning(f"[youtube.handle_youtube] Failed to get details: {err_msg}")
        return (err_msg, "00:00", None, None, None, None, None, None)

    # Convert dict result to tuple format
    result_tuple = (
        details.get('title', 'N/A'),
        details.get('duration', 'N/A'),
        details.get('video_url', 'N/A'),
        details.get('thumbnail', 'N/A'),
        details.get('channel_name', 'N/A'),
        details.get('view_count', 'N/A'),
        details.get('video_id', 'N/A'),
        details.get('stream_url', 'N/A')
    )

    logger.info(f"[youtube.handle_youtube] Success: title='{details.get('title', 'N/A')}', id='{details.get('video_id', 'N/A')}'")

    # If an update callback is provided, let it update the queued item by track_id
    if update_callback and track_id and chat_id:
        try:
            update_callback(track_id, chat_id, {
                'title': details.get('title', 'N/A'),
                'duration': details.get('duration', 'N/A'),
                'yt_link': details.get('video_url', 'N/A'),
                'stream_url': details.get('stream_url', 'N/A'),
                'thumbnail': details.get('thumbnail', 'N/A'),
            })
        except Exception as e:
            logger.debug(f"[youtube.handle_youtube] Queue update callback failed for track {track_id} in chat {chat_id} (video {details.get('video_id', 'N/A')}): {e}")

    return result_tuple


def _extract_ytm_tracks(data: dict) -> list[dict]:
    tracks = []
    seen = set()

    def find_renderers(node):
        if isinstance(node, dict):
            if "playlistPanelVideoRenderer" in node:
                r = node["playlistPanelVideoRenderer"]
                vid = r.get("videoId")
                title_node = r.get("title")
                title = ""
                if isinstance(title_node, dict):
                    title = title_node.get("simpleText") or "".join(x.get("text", "") for x in title_node.get("runs", []))

                byline_node = r.get("shortBylineText") or r.get("longBylineText")
                artist = ""
                if isinstance(byline_node, dict):
                    artist = byline_node.get("simpleText") or "".join(x.get("text", "") for x in byline_node.get("runs", []))

                dur_node = r.get("lengthText")
                dur = ""
                if isinstance(dur_node, dict):
                    dur = dur_node.get("simpleText") or "".join(x.get("text", "") for x in dur_node.get("runs", []))

                thumbs = (r.get("thumbnail") or {}).get("thumbnails", [])
                thumb = thumbs[-1]["url"] if thumbs else ""

                if vid and title and vid not in seen:
                    seen.add(vid)
                    tracks.append({
                        "video_id": vid,
                        "title": title,
                        "artist": artist,
                        "duration": dur or "N/A",
                        "thumbnail": thumb,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                    })
            elif "compactVideoRenderer" in node:
                r = node["compactVideoRenderer"]
                vid = r.get("videoId")
                title_node = r.get("title")
                title = ""
                if isinstance(title_node, dict):
                    title = title_node.get("simpleText") or "".join(x.get("text", "") for x in title_node.get("runs", []))
                byline_node = r.get("shortBylineText") or r.get("ownerText")
                artist = ""
                if isinstance(byline_node, dict):
                    artist = byline_node.get("simpleText") or "".join(x.get("text", "") for x in byline_node.get("runs", []))
                dur_node = r.get("lengthText")
                dur = ""
                if isinstance(dur_node, dict):
                    dur = dur_node.get("simpleText") or "".join(x.get("text", "") for x in dur_node.get("runs", []))
                thumbs = (r.get("thumbnail") or {}).get("thumbnails", [])
                thumb = thumbs[-1]["url"] if thumbs else ""
                if vid and title and vid not in seen:
                    seen.add(vid)
                    tracks.append({
                        "video_id": vid,
                        "title": title,
                        "artist": artist,
                        "duration": dur or "N/A",
                        "thumbnail": thumb,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                    })
            for v in node.values():
                find_renderers(v)
        elif isinstance(node, list):
            for item in node:
                find_renderers(item)

    find_renderers(data)
    return tracks


async def get_related_suggestions(argument: str, limit: int = 5, exclude_ids: set | list | None = None) -> list[dict]:
    """
    Fetch related music recommendations for a given video ID, URL, or song title.
    Uses YouTube Music Radio Mix (/next with RDAMVM) as primary source, falling back to YouTube search.
    Filters out recently played video IDs to prevent A -> B -> A recommendation loops.
    """
    if not argument:
        return []

    vid = _innertube_extract_vid(argument)
    if not vid:
        # If argument is a song title / query, find its video_id first
        vid = _mem_cache_get(("search", argument))
        if not vid:
            try:
                search_resp = await _post_innertube_async("search", {"query": argument})
                hit = _first_video_id(search_resp)
                if hit:
                    vid = hit[0]
                    _mem_cache_set(("search", argument), vid)
            except Exception as e:
                logger.warning(f"[Suggest] Initial search resolution failed for '{argument}': {e}")

    excluded = set(exclude_ids) if exclude_ids else set()
    if vid:
        excluded.add(vid)

    suggestions = []
    extracted = []
    if vid:
        try:
            http = get_http_client()
            url = f"https://music.youtube.com/youtubei/v1/next?key={INNERTUBE_KEY}"
            logger.info(f"[API CALL] YouTube Music Radio API -> {url} (videoId={vid})")
            print(f"[API CALL] YouTube Music Radio API -> {url} (videoId={vid})", flush=True)
            body = {
                "context": {"client": INNERTUBE_CLIENT_REMIX},
                "videoId": vid,
                "playlistId": f"RDAMVM{vid}",
                "isAutomix": True,
            }
            res = await http.post(url, json=body, headers=INNERTUBE_HEADERS_REMIX)
            if res.status_code == 200:
                extracted = _extract_ytm_tracks(res.json())
                # Filter out the seed video and any previously played / excluded videos
                suggestions = [t for t in extracted if t.get("video_id") and t.get("video_id") not in excluded]
                logger.info(f"[Suggest] Fetched {len(suggestions)} related tracks for video '{vid}' (excluded {len(excluded)} tracks)")
        except Exception as e:
            logger.warning(f"[Suggest] YouTube Music radio request failed for {vid}: {e}")

    # Fallback: if we got fewer than desired recommendations, use youtube_search
    if len(suggestions) < limit:
        try:
            query = argument if not vid else f"similar music to {vid}"
            search_items = await youtube_search(query, limit=limit * 3)
            for item in search_items:
                item_vid = item.get("video_id")
                if item_vid and item_vid not in excluded and not any(s.get("video_id") == item_vid for s in suggestions):
                    suggestions.append({
                        "video_id": item_vid,
                        "title": item.get("title", "N/A"),
                        "artist": item.get("channel_name", "N/A"),
                        "duration": item.get("duration", "N/A"),
                        "thumbnail": item.get("thumbnail", ""),
                        "url": item.get("video_url", f"https://www.youtube.com/watch?v={item_vid}"),
                    })
                    if len(suggestions) >= limit:
                        break
        except Exception as e:
            logger.warning(f"[Suggest] Fallback search failed: {e}")

    # Last-resort fallback: if strict exclusion resulted in 0 suggestions, relax exclusion to avoid dropping the call
    if not suggestions and extracted and vid:
        suggestions = [t for t in extracted if t.get("video_id") != vid]

    return suggestions[:limit]

