

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

# All config read from config.py (single source of truth)
from config import YT_API_TOKEN as API_TOKEN, NUB_YT_API_BASE_URL as BASE_URL, YOUTUBE_API_KEYS as _YOUTUBE_API_KEYS_RAW

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DETAILS_URL = "https://www.googleapis.com/youtube/v3/videos"

YOUTUBE_API_KEYS = [k.strip() for k in _YOUTUBE_API_KEYS_RAW.split(",") if k.strip()]

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
    if cookies and os.path.exists(cookies):
        cmd.insert(1, "--cookies")
        cmd.insert(2, cookies)
    else:
        cmd.insert(1, "--cookies-from-browser")
        cmd.insert(2, "firefox")
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
    logger.info(f"[AUDIO] No cache, extracting fresh stream...")
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
    logger.info(f"[VIDEO] No cache, extracting fresh stream...")
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
async def get_video_info(query: str, max_results: int = 1, mode: str = "audio") -> Tuple[str, str, str, str, str, str, str, str, str]:
    """Get video info using nubcoder API, falling back to local search."""
    # Primary: use the nubcoder /info API endpoint
    if API_TOKEN and BASE_URL:
        try:
            logger.debug(f"[youtube.get_video_info] Using nubcoder /info API for '{query}' (mode={mode})")
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{BASE_URL}/info",
                    params={"q": query, "token": API_TOKEN, "mode": mode},
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stream_url") and data.get("title"):
                    logger.info(f"[youtube.get_video_info] nubcoder API success: title='{data.get('title')}'")
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
        except Exception as e:
            logger.warning(f"[youtube.get_video_info] nubcoder API failed: {e}, falling back")

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
    Get video details using API first, then yt_dlp fallback

    Args:
        video_id (str): Video ID to fetch details for

    Returns:
        dict: Video details or error message
    """
    
    # First try API if token is available
    if API_TOKEN:
        try:
            logger.debug(f"[youtube.get_video_details] Using API for video_id='{video_id}'")
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
                logger.warning("[youtube.get_video_details] API returned no usable data, falling back to yt-dlp")
        except Exception as e:
            logger.error(f"[youtube.get_video_details] API error: {e}")

    # Fallback to yt-dlp
    try:
        logger.debug(f"[youtube.get_video_details] Using yt-dlp fallback for video_id='{video_id}'")
        ydl_opts = {
            # Only gather metadata, no downloads
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "cookiesfrombrowser": ("firefox",),

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
