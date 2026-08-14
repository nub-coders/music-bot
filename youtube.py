

import os
import re
import sys
import logging
import asyncio
import httpx
import random
import hashlib
import json
import time
import subprocess
import requests
import yt_dlp
from urllib.parse import urlparse, parse_qs
from typing import List, Tuple, Dict


_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_MEM_CACHE = {}
_MAX_MEM_CACHE_SIZE = 500

def _mem_cache_set(key, value):
    """Set in memory cache with size bounds (FIFO eviction)."""
    if len(_MEM_CACHE) >= _MAX_MEM_CACHE_SIZE:
        keys_to_remove = list(_MEM_CACHE.keys())[:100]
        for k in keys_to_remove:
            _MEM_CACHE.pop(k, None)
    _MEM_CACHE[key] = value

logger = logging.getLogger(__name__)

# Single long-lived HTTP client shared by every network resolver (InnerTube,
# nubcoder API, YouTube Data API). httpx pools connections per-host, so the
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
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            http2=use_h2,
            limits=httpx.Limits(max_keepalive_connections=20, keepalive_expiry=90),
        )
    return _http_client


# All config read from config.py (single source of truth)
from config import YT_API_TOKEN as API_TOKEN, NUB_YT_API_BASE_URL as BASE_URL, YOUTUBE_API_KEYS as _YOUTUBE_API_KEYS_RAW, YT_COOKIES_FILE, COOKIES_FROM_BROWSER, COOKIES_BOOTSTRAP_URL, COOKIES_REFRESH_HOURS

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
    async with httpx.AsyncClient(timeout=10) as client:
        api_key = get_random_key()
        search_params = {
            "part": "snippet",
            "q": query,
            "maxResults": limit,
            "type": "video",
            "key": api_key,
        }
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

def _read_cache(url: str, prefix: str = "") -> str | None:
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
    except Exception:
        try:
            os.remove(path)
        except Exception:
            pass
    return None

def _write_cache(url: str, stream_url: str, prefix: str = ""):
    expire = _extract_expire(stream_url)
    if not expire:
        logger.warning(f"[CACHE SKIP] No expire found in stream URL for {url[:80]}")
        return
    try:
        with open(_cache_path(url, prefix), "w") as f:
            json.dump({"url": stream_url, "expire": expire}, f)
        logger.info(f"[CACHE WRITE] {prefix}{url[:80]}... (expires in {int(expire - time.time())}s)")
    except Exception as e:
        logger.error(f"[CACHE WRITE ERROR] {e}")

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
    logger.info(f"[YT-DLP] Running: {' '.join(cmd)}")
    start = time.time()
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
        return None
    except Exception as e:
        logger.error(f"[YT-DLP] Exception: {e}")
        return None
    elapsed = round(time.time() - start, 2)
    if process.returncode == 0 and stdout:
        stream_url = stdout.decode().strip().split("\n")[0]
        logger.info(f"[YT-DLP] ✅ Success ({elapsed}s) — {stream_url[:100]}...")
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
            vid = _MEM_CACHE.get(("search", argument))
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


        title = details.get("title", "N/A")
        duration_sec = int(details.get("lengthSeconds", 0))
        # format_duration handles minute/hour rollover; parse_dur(f"PT{n}S") does
        # not, and would render 213s as "0:213" instead of "03:33".
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
    cached = _MEM_CACHE.get(("audio", url))
    if cached:
        expire = _extract_expire(cached)
        if expire and time.time() < expire - 15:
            logger.info(f"[AUDIO] MEM_CACHE hit for {url[:80]}")
            return cached
    cached = _read_cache(url, prefix="audio_")
    if cached:
        _mem_cache_set(("audio", url), cached)
        return cached
    logger.info("[AUDIO] No cache, extracting fresh stream...")

    # Fast Path: Innertube direct resolution
    innertube_data = await resolve_innertube(url, mode="audio")
    if innertube_data and innertube_data.get("stream_url"):
        stream = innertube_data["stream_url"]
        logger.info(f"[AUDIO] ✅ Innertube success — {stream[:100]}...")
        _mem_cache_set(("audio", url), stream)
        _write_cache(url, stream, prefix="audio_")
        return stream

    logger.warning("[AUDIO] Innertube extraction returned None, falling back to yt-dlp...")
    stream = await _run_yt_dlp(
        url,
        "bestaudio[ext=m4a]/bestaudio/best",
        cookies,
    )
    if stream:
        _mem_cache_set(("audio", url), stream)
        _write_cache(url, stream, prefix="audio_")
    else:
        logger.warning(f"[AUDIO] Extraction returned None for {url}")
    return stream

async def get_video_stream(url: str, cookies: str | None = None) -> str | None:
    logger.info(f"[VIDEO] get_video_stream called: {url}")
    cached = _MEM_CACHE.get(("video", url))
    if cached:
        expire = _extract_expire(cached)
        if expire and time.time() < expire - 15:
            logger.info(f"[VIDEO] MEM_CACHE hit for {url[:80]}")
            return cached
    cached = _read_cache(url, prefix="video_")
    if cached:
        _mem_cache_set(("video", url), cached)
        return cached
    logger.info("[VIDEO] No cache, extracting fresh stream...")

    # Fast Path: Innertube direct resolution (muxed / video stream)
    innertube_data = await resolve_innertube(url, mode="video")
    if innertube_data and innertube_data.get("stream_url"):
        stream = innertube_data["stream_url"]
        logger.info(f"[VIDEO] ✅ Innertube success — {stream[:100]}...")
        _mem_cache_set(("video", url), stream)
        _write_cache(url, stream, prefix="video_")
        return stream

    logger.warning("[VIDEO] Innertube extraction returned None, falling back to yt-dlp...")
    stream = await _run_yt_dlp(
        url,
        "best[ext=mp4][protocol=https]",
        cookies,
    )
    if stream:
        _mem_cache_set(("video", url), stream)
        _write_cache(url, stream, prefix="video_")
    else:
        logger.warning(f"[VIDEO] Extraction returned None for {url}")
    return stream


# New: Get video info using local search and stream extraction
# Circuit breaker for the external nubcoder resolution API: after N consecutive
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
            f"[youtube] nubcoder API circuit breaker OPEN for {_API_COOLDOWN_S}s "
            f"after {_api_fail_count} consecutive failures"
        )


async def get_video_info(query: str, max_results: int = 1, mode: str = "audio") -> Tuple[str, str, str, str, str, str, str, str, str]:
    """Get video info using nubcoder API, Innertube resolution, or local search fallback."""
    # Direct stream URL handling (bypasses nubcoder API completely)
    if is_direct_stream_url(query):
        logger.info(f"[youtube.get_video_info] Bypassing API for direct stream URL: '{query[:80]}...'")
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

    # Primary: Fast Innertube direct resolution
    try:
        logger.debug(f"[youtube.get_video_info] Trying direct Innertube resolution for '{query}' (mode={mode})")
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

    # Fallback: use the nubcoder /info API endpoint (skipped while the breaker is open)
    if API_TOKEN and BASE_URL and not _api_breaker_open():
        try:
            logger.debug(f"[youtube.get_video_info] Using nubcoder /info API for '{query}'")
            resp = await get_http_client().get(
                f"{BASE_URL}/info",
                params={"q": query},
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stream_url") and data.get("title"):
                    logger.info(f"[youtube.get_video_info] nubcoder API success: title='{data.get('title')}'")
                    _api_record_success()
                    return (
                        data.get('title', 'N/A'),
                        data.get('video_id', 'N/A'),
                        data.get('duration', '0'),
                        data.get('youtube_link', 'N/A'),
                        data.get('channel_name', 'N/A'),
                        data.get('views', '0'),
                        data.get('stream_url', 'N/A'),
                        data.get('thumbnail', 'N/A'),
                        'api',
                    )
            logger.warning(f"[youtube.get_video_info] nubcoder API returned status {resp.status_code}, falling back")
            _api_record_failure()
        except Exception as e:
            logger.warning(f"[youtube.get_video_info] nubcoder API failed: {e}, falling back")
            _api_record_failure()

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
    Extract YouTube video ID from various forms of YouTube URLs.

    Args:
        url (str): YouTube video URL

    Returns:
        str: Video ID or None if not found
    """
    try:
        logger.debug(f"[youtube.extract_video_id] Extracting video id from url='{url}'")
        # Patterns for different types of YouTube URLs
        patterns = [
            r'(?:v=|/v/|youtu\.be/|/embed/)([^&?/]+)',  # Standard, shortened and embed URLs
            r'(?:watch\?|/v/|youtu\.be/)([^&?/]+)',     # Watch URLs
            r'(?:youtube\.com/|youtu\.be/)([^&?/]+)'    # Channel URLs
        ]

        # Try each pattern
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
        return f"Error extracting video ID: {str(e)}"


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

def is_ytdlp_updated():
    """Check if yt-dlp is up to date"""
    try:
        # Get installed version using modern API
        try:
            from importlib.metadata import version, PackageNotFoundError
            installed_version = version('yt-dlp')
        except PackageNotFoundError:
            logger.warning("[youtube.is_ytdlp_updated] yt-dlp not installed via pip")
            return False

        # Get latest version from PyPI
        response = requests.get('https://pypi.org/pypi/yt-dlp/json', timeout=10)
        response.raise_for_status()  # better error handling
        latest_version = response.json()['info']['version']

        is_current = installed_version == latest_version
        logger.info(
            f"[youtube.is_ytdlp_updated] Installed={installed_version}, "
            f"Latest={latest_version}, UpToDate={is_current}"
        )
        return is_current

    except requests.RequestException as e:
        logger.error(f"[youtube.is_ytdlp_updated] PyPI request failed: {e}")
        return False
    except Exception as e:
        logger.error(f"[youtube.is_ytdlp_updated] Error: {e}")
        return False

def update_ytdlp():
    """Update yt-dlp to the latest version"""
    try:
        logger.info("[youtube.update_ytdlp] Updating yt-dlp")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-U", "yt-dlp"
        ], capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            logger.info("[youtube.update_ytdlp] Update successful")
            return True
        else:
            logger.error(f"[youtube.update_ytdlp] Update failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"[youtube.update_ytdlp] Error: {e}")
        return False

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


async def check_and_update_ytdlp():
    """Check and update yt-dlp if needed"""
    try:
        logger.debug("[youtube.check_and_update_ytdlp] Checking yt-dlp status")
        if not is_ytdlp_updated():
            logger.info("[youtube.check_and_update_ytdlp] yt-dlp is outdated, updating")
            update_ytdlp()
        else:
            logger.info("[youtube.check_and_update_ytdlp] yt-dlp is up to date")
    except Exception as e:
        logger.error(f"[youtube.check_and_update_ytdlp] Error: {e}")

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

async def get_video_details(video_id):
    """
    Get video details using direct stream resolution, API (for YouTube videos), or yt-dlp fallback.

    Args:
        video_id (str): Video ID or URL to fetch details for

    Returns:
        dict: Video details or error message
    """

    # Direct stream URL resolution (bypasses YouTube API and external nubcoder API)
    if is_direct_stream_url(video_id):
        logger.info(f"[youtube.get_video_details] Handling direct stream URL: '{video_id[:80]}...'")
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "http_chunk_size": 10485760,
                "retries": 1,
                **({"cookiefile": YT_COOKIES_FILE} if YT_COOKIES_FILE and os.path.exists(YT_COOKIES_FILE) else {}),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_id, download=False)
                if info:
                    if "entries" in info and info["entries"]:
                        info = info["entries"][0]
                    duration = "N/A"
                    if info.get("duration"):
                        duration = format_duration(int(info["duration"]))
                    thumbnail = "N/A"
                    if info.get("thumbnails"):
                        thumbnail = info["thumbnails"][-1].get("url", "N/A")
                    stream_url = extract_best_format(info.get("formats", [])) or info.get("url") or video_id
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
        except Exception as e:
            logger.warning(f"[youtube.get_video_details] Direct URL yt-dlp extraction notice: {e}")

        clean_filename = video_id.split("/")[-1].split("?")[0]
        title = clean_filename if clean_filename and len(clean_filename) < 50 else "Direct Stream"
        duration = "Live Stream" if ".m3u8" in video_id.lower() else "N/A"
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

    # Primary resolution chain: InnerTube -> nubcoder API -> YouTube Data API
    # search, in that priority (get_video_info owns the chain). Always attempted
    # first, unconditionally — InnerTube must stay the primary resolver even when
    # no nubcoder token is configured. yt-dlp below is the last-resort fallback,
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
        ydl_opts = {
            # Only gather metadata, no downloads
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
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
            # Extract initial info using ytsearch
            search_result = ydl.extract_info(f"ytsearch:{video_id}", download=False)

            if not search_result or 'entries' not in search_result or not search_result['entries']:
                logger.warning("[youtube.get_video_details] No entries found in yt-dlp search")
                return {'error': 'No video found for the given ID'}

            # Get the first entry from search results
            video_info = search_result['entries'][0]

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

            # Extract best format stream URL
            stream_url = extract_best_format(video_info.get('formats', []))

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
        logger.warning(f"[youtube.handle_youtube] Failed to get details: {details.get('error')}")
        return ("Error", "00:00", None, None, None, None, None, None)

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
        except Exception:
            pass

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
        vid = _MEM_CACHE.get(("search", argument))
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

