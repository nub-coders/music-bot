"""resolvers.py — Multi-platform link resolution & extraction pipeline.

Supports Apple Music, Amazon Music (Odesli API), JioSaavn, SoundCloud, and plain-text search fallback.
"""
import asyncio
import html
import re
import urllib.parse
from html.parser import HTMLParser
import aiohttp


# ── Custom Exceptions ─────────────────────────────────────────────────────────

class ResolverError(Exception):
    """Base exception for all resolution failures."""
    pass


class PlatformHTTPError(ResolverError):
    """Raised when an upstream platform returns an HTTP error status (e.g. 404, 429)."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


class EmptyPlaylistError(ResolverError):
    """Raised when a playlist or album returns no tracks."""
    pass


class MalformedURLError(ResolverError):
    """Raised when a URL is malformed or missing required path segments."""
    pass


class NetworkTimeoutError(ResolverError):
    """Raised when an upstream request times out."""
    pass


# ── Regex Patterns ────────────────────────────────────────────────────────────

APPLE_MUSIC_RE = re.compile(
    r"^https?://music\.apple\.com/([a-z]{2}/)?(album|playlist|song|artist)/([^/]+)(/([^/\?]+))?",
    re.IGNORECASE
)

AMAZON_MUSIC_RE = re.compile(
    r"^https?://music\.amazon\.[a-z\.]+/.*",
    re.IGNORECASE
)

SOUNDCLOUD_RE = re.compile(
    r"^https?://(www\.)?soundcloud\.com/[^/]+/.+",
    re.IGNORECASE
)

JIOSAAVN_RE = re.compile(
    r"^https?://(www\.)?(jiosaavn|saavn)\.com/.+",
    re.IGNORECASE
)


# ── Provider Detection & URL Validation ───────────────────────────────────────

def is_apple_music(url: str) -> bool:
    """True if input is a valid Apple Music URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(APPLE_MUSIC_RE.match(url.strip()))


def is_amazon_music(url: str) -> bool:
    """True if input is a valid Amazon Music URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(AMAZON_MUSIC_RE.match(url.strip()))


def is_soundcloud(url: str) -> bool:
    """True if input is a SoundCloud track or set URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(SOUNDCLOUD_RE.match(url.strip()))


def is_jiosaavn(url: str) -> bool:
    """True if input is a JioSaavn or Saavn URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(JIOSAAVN_RE.match(url.strip()))


def is_plain_text_query(query: str) -> bool:
    """True if input is not a URL (plain-text song search query)."""
    if not query or not isinstance(query, str):
        return False
    query = query.strip()
    return not query.startswith("http://") and not query.startswith("https://")


def detect_provider(query_or_url: str) -> str:
    """Detect the target platform for an incoming query or URL."""
    if not query_or_url or not isinstance(query_or_url, str):
        raise MalformedURLError("Input query or URL must be a non-empty string.")

    url = query_or_url.strip()
    if not url:
        raise MalformedURLError("Empty input provided.")

    if is_apple_music(url):
        return "apple_music"
    elif is_amazon_music(url):
        return "amazon_music"
    elif is_soundcloud(url):
        return "soundcloud"
    elif is_jiosaavn(url):
        return "jiosaavn"
    elif is_plain_text_query(url):
        return "text_search"
    elif url.startswith("http://") or url.startswith("https://"):
        return "generic_url"
    else:
        return "text_search"


# ── Apple Music Scraper & Parser ──────────────────────────────────────────────

def strip_apple_music_branding(title: str) -> str:
    """Strip Apple Music branding suffixes from page title or track metadata."""
    if not title:
        return ""
    cleaned = title.strip()
    # Remove " on Apple Music" suffix
    cleaned = re.sub(r"\s+on Apple Music$", "", cleaned, flags=re.IGNORECASE)
    # Replace " - Song by ..." or " - Album by ..." with " by ..."
    cleaned = re.sub(r"\s+-\s+(Song|Album|Playlist|Single|EP)\s+by\s+", " by ", cleaned, flags=re.IGNORECASE)
    # Strip residual trailing dashes or spaces
    return cleaned.strip(" -")


class AppleMusicHTMLParser(HTMLParser):
    """HTML Parser for Apple Music metadata and track listings."""
    def __init__(self):
        super().__init__()
        self.og_title = None
        self.og_description = None
        self.tracks = []
        self._in_song_name = False
        self._current_tag = None
        self._current_class = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_class = attr_dict.get("class", "")

        # Meta tags check
        if tag == "meta":
            prop = attr_dict.get("property") or attr_dict.get("name")
            content = attr_dict.get("content")
            if prop == "og:title" and content:
                self.og_title = content
            elif prop == "og:description" and content:
                self.og_description = content

        # Check for track containers (.songs-list-row__song-name)
        if "songs-list-row__song-name" in tag_class or "song-name" in tag_class:
            self._in_song_name = True

    def handle_endtag(self, tag):
        if self._in_song_name and tag in ("div", "span", "a", "p"):
            self._in_song_name = False

    def handle_data(self, data):
        if self._in_song_name:
            text = data.strip()
            if text:
                self.tracks.append(text)


def parse_apple_music_html(html_content: str) -> dict:
    """Parse HTML content from Apple Music to extract title, description, and tracks."""
    if not html_content or not html_content.strip():
        raise ResolverError("Empty Apple Music HTML content.")

    parser = AppleMusicHTMLParser()
    parser.feed(html_content)

    title = strip_apple_music_branding(parser.og_title or "")
    description = parser.og_description or ""

    # Fallback to regex if meta tags not found
    if not title:
        og_title_match = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_content, re.I)
        if og_title_match:
            title = strip_apple_music_branding(html_content_unescape(og_title_match.group(1)))

    if not description:
        og_desc_match = re.search(r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html_content, re.I)
        if og_desc_match:
            description = html_content_unescape(og_desc_match.group(1))

    # Regex fallback for song list rows if HTMLParser missed them
    tracks = parser.tracks
    if not tracks:
        row_matches = re.findall(r'class=["\'][^"\']*songs-list-row__song-name[^"\']*["\'][^>]*>(.*?)</', html_content, re.S)
        for m in row_matches:
            clean_m = re.sub(r'<[^>]+>', '', m).strip()
            if clean_m:
                tracks.append(html_content_unescape(clean_m))

    return {
        "title": title,
        "description": description,
        "tracks": tracks,
    }


def html_content_unescape(text: str) -> str:
    """Unescape HTML entities."""
    return html.unescape(text) if text else ""


async def resolve_apple_music(url: str, session: aiohttp.ClientSession = None) -> dict:
    """Fetch and parse Apple Music metadata."""
    if not is_apple_music(url):
        raise MalformedURLError("Invalid Apple Music URL format.")

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status in (404, 429):
                raise PlatformHTTPError(resp.status, f"Apple Music returned status {resp.status}")
            if resp.status != 200:
                raise PlatformHTTPError(resp.status, f"Apple Music request failed with status {resp.status}")
            html_text = await resp.text()
    except asyncio.TimeoutError:
        raise NetworkTimeoutError("Apple Music request timed out.")
    except aiohttp.ClientError as e:
        raise ResolverError(f"Network error fetching Apple Music: {e}")
    finally:
        if close_session:
            await session.close()

    parsed = parse_apple_music_html(html_text)

    # Determine type of Apple Music link: track vs playlist/album
    is_playlist_or_album = "/playlist/" in url or "/album/" in url
    if is_playlist_or_album and not parsed["tracks"]:
        # If single track album or og:title exists, treat as single track query fallback
        if not parsed["title"]:
            raise EmptyPlaylistError("Apple Music page contains no tracks or title.")

    return {
        "provider": "apple_music",
        "title": parsed["title"],
        "description": parsed["description"],
        "tracks": parsed["tracks"],
        "query": parsed["title"],
    }


# ── Amazon Music (Odesli / Songlink API) ──────────────────────────────────────

def parse_odesli_response(data: dict) -> dict:
    """Parse Odesli (song.link) API response for Amazon Music track resolution."""
    if not data or not isinstance(data, dict):
        raise ResolverError("Invalid Odesli API JSON response.")

    entity_id = data.get("entityUniqueId")
    entities = data.get("entitiesByUniqueId", {})
    entity = entities.get(entity_id, {}) if entity_id else {}

    title = entity.get("title") or ""
    artist_name = entity.get("artistName") or ""

    links_by_platform = data.get("linksByPlatform", {})
    youtube_info = links_by_platform.get("youtube") or {}
    youtube_url = youtube_info.get("url") if isinstance(youtube_info, dict) else None

    # Search query fallback when direct youtube URL is missing or empty
    search_query = f"{title} {artist_name}".strip() if (title or artist_name) else ""

    return {
        "entity_id": entity_id,
        "title": title,
        "artist": artist_name,
        "youtube_url": youtube_url,
        "search_query": search_query,
    }


async def resolve_amazon_music(url: str, session: aiohttp.ClientSession = None) -> dict:
    """Resolve Amazon Music URL using Odesli / Songlink API."""
    if not is_amazon_music(url):
        raise MalformedURLError("Invalid Amazon Music URL format.")

    encoded_url = urllib.parse.quote(url, safe="")
    odesli_api_url = f"https://api.song.link/v1-alpha.1/links?url={encoded_url}"

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(odesli_api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status in (404, 429):
                raise PlatformHTTPError(resp.status, f"Odesli API returned status {resp.status}")
            if resp.status != 200:
                raise PlatformHTTPError(resp.status, f"Odesli API request failed with status {resp.status}")
            json_data = await resp.json()
    except asyncio.TimeoutError:
        raise NetworkTimeoutError("Amazon Music (Odesli) request timed out.")
    except aiohttp.ClientError as e:
        raise ResolverError(f"Network error resolving Amazon Music: {e}")
    finally:
        if close_session:
            await session.close()

    parsed = parse_odesli_response(json_data)

    return {
        "provider": "amazon_music",
        "title": parsed["title"],
        "artist": parsed["artist"],
        "youtube_url": parsed["youtube_url"],
        "search_query": parsed["search_query"],
        "query": parsed["youtube_url"] or parsed["search_query"],
    }


# ── JioSaavn Scraper & Parser ─────────────────────────────────────────────────

def select_highest_bitrate_url(media_data) -> str | None:
    """Select the highest bitrate URL available from JioSaavn media data."""
    if not media_data:
        return None

    if isinstance(media_data, str):
        return media_data

    bitrate_map = {}

    # Case 1: List of dicts e.g. [{"quality": "320kbps", "link": "..."}, ...]
    if isinstance(media_data, list):
        for item in media_data:
            if isinstance(item, dict):
                quality = str(item.get("quality", "")).lower()
                link = item.get("link") or item.get("url")
                if link:
                    match = re.search(r"(\d+)", quality)
                    kbps = int(match.group(1)) if match else 0
                    bitrate_map[kbps] = link
    # Case 2: Dict of bitrates e.g. {"320kbps": "...", "160kbps": "..."}
    elif isinstance(media_data, dict):
        for key, value in media_data.items():
            if isinstance(value, str) and value:
                match = re.search(r"(\d+)", str(key))
                kbps = int(match.group(1)) if match else 0
                bitrate_map[kbps] = value

    if bitrate_map:
        highest_bitrate = max(bitrate_map.keys())
        return bitrate_map[highest_bitrate]

    return None


def parse_jiosaavn_json(data: dict) -> dict:
    """Parse JioSaavn API JSON response for track title, artists, duration, and stream URL."""
    if not data or not isinstance(data, dict):
        raise ResolverError("Invalid JioSaavn JSON response.")

    # Handle song title
    title = data.get("song") or data.get("title") or data.get("name") or ""
    title = html.unescape(title).strip()

    # Handle artists
    artist = data.get("singers") or data.get("primary_artists") or data.get("artist") or ""
    artist = html.unescape(artist).strip()

    # Handle duration
    duration = data.get("duration")
    try:
        duration = int(duration) if duration is not None else None
    except (ValueError, TypeError):
        duration = None

    # Handle download URL / stream URL
    media_data = data.get("download_url") or data.get("media_url") or data.get("media_preview_url")
    stream_url = select_highest_bitrate_url(media_data)

    return {
        "title": title,
        "artist": artist,
        "duration": duration,
        "stream_url": stream_url,
        "search_query": f"{title} {artist}".strip() if (title or artist) else "",
    }


async def resolve_jiosaavn(url: str, session: aiohttp.ClientSession = None) -> dict:
    """Resolve JioSaavn URL to metadata and audio stream link."""
    if not is_jiosaavn(url):
        raise MalformedURLError("Invalid JioSaavn URL format.")

    # API endpoint format for JioSaavn
    api_url = f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={urllib.parse.quote(url)}&type=song&_format=json&_marker=0"

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status in (404, 429):
                raise PlatformHTTPError(resp.status, f"JioSaavn API returned status {resp.status}")
            if resp.status != 200:
                raise PlatformHTTPError(resp.status, f"JioSaavn API request failed with status {resp.status}")
            json_data = await resp.json(content_type=None)
    except asyncio.TimeoutError:
        raise NetworkTimeoutError("JioSaavn request timed out.")
    except aiohttp.ClientError as e:
        raise ResolverError(f"Network error resolving JioSaavn: {e}")
    finally:
        if close_session:
            await session.close()

    parsed = parse_jiosaavn_json(json_data)

    return {
        "provider": "jiosaavn",
        "title": parsed["title"],
        "artist": parsed["artist"],
        "duration": parsed["duration"],
        "stream_url": parsed["stream_url"],
        "search_query": parsed["search_query"],
        "query": parsed["stream_url"] or parsed["search_query"],
    }


# ── SoundCloud Resolver ───────────────────────────────────────────────────────

def resolve_soundcloud(url: str) -> dict:
    """Validate SoundCloud URL and prepare direct extraction parameters."""
    if not is_soundcloud(url):
        raise MalformedURLError("Invalid SoundCloud URL format.")

    return {
        "provider": "soundcloud",
        "url": url,
        "bypass_search": True,
        "stream_url": url,
    }


# ── Master Dispatcher Function ────────────────────────────────────────────────

async def resolve_to_playable_stream(
    query_or_url: str,
    session: aiohttp.ClientSession = None,
    yt_dlp_extractor=None
) -> dict:
    """Master dispatcher: route input to platform handler or plain-text fallback.

    Returns a dict with resolved stream details:
      {
         "provider": str,
         "title": str | None,
         "artist": str | None,
         "stream_url": str | None,
         "search_query": str | None,
         "bypass_search": bool,
      }
    """
    if not query_or_url or not isinstance(query_or_url, str) or not query_or_url.strip():
        raise MalformedURLError("Input query or URL cannot be empty.")

    clean_input = query_or_url.strip()
    provider = detect_provider(clean_input)

    if provider == "apple_music":
        res = await resolve_apple_music(clean_input, session=session)
        # If Apple Music resolution returned tracks or title, generate query
        if res.get("tracks"):
            first_track = res["tracks"][0]
            query = f"{first_track} {res['title']}".strip()
        else:
            query = res["title"]
        return {
            "provider": "apple_music",
            "title": res["title"],
            "artist": None,
            "stream_url": None,
            "search_query": query,
            "tracks": res.get("tracks", []),
            "bypass_search": False,
        }

    elif provider == "amazon_music":
        res = await resolve_amazon_music(clean_input, session=session)
        if res.get("youtube_url"):
            stream_url = res["youtube_url"]
            if yt_dlp_extractor and callable(yt_dlp_extractor):
                extracted = await yt_dlp_extractor(stream_url)
                return extracted
            return {
                "provider": "amazon_music",
                "title": res["title"],
                "artist": res["artist"],
                "stream_url": stream_url,
                "search_query": res["search_query"],
                "bypass_search": True,
            }
        else:
            return {
                "provider": "amazon_music",
                "title": res["title"],
                "artist": res["artist"],
                "stream_url": None,
                "search_query": res["search_query"],
                "bypass_search": False,
            }

    elif provider == "jiosaavn":
        res = await resolve_jiosaavn(clean_input, session=session)
        if res.get("stream_url"):
            return {
                "provider": "jiosaavn",
                "title": res["title"],
                "artist": res["artist"],
                "duration": res["duration"],
                "stream_url": res["stream_url"],
                "search_query": res["search_query"],
                "bypass_search": True,
            }
        return {
            "provider": "jiosaavn",
            "title": res["title"],
            "artist": res["artist"],
            "duration": res["duration"],
            "stream_url": None,
            "search_query": res["search_query"],
            "bypass_search": False,
        }

    elif provider == "soundcloud":
        res = resolve_soundcloud(clean_input)
        if yt_dlp_extractor and callable(yt_dlp_extractor):
            extracted = await yt_dlp_extractor(clean_input)
            return extracted
        return {
            "provider": "soundcloud",
            "title": None,
            "artist": None,
            "stream_url": clean_input,
            "search_query": None,
            "bypass_search": True,
        }

    elif provider == "text_search":
        # Pure plain-text search query: bypass scraper passes completely
        if yt_dlp_extractor and callable(yt_dlp_extractor):
            extracted = await yt_dlp_extractor(clean_input)
            return extracted
        return {
            "provider": "text_search",
            "title": clean_input,
            "artist": None,
            "stream_url": None,
            "search_query": clean_input,
            "bypass_search": False,
        }

    else:
        # Generic URL fallback
        if yt_dlp_extractor and callable(yt_dlp_extractor):
            return await yt_dlp_extractor(clean_input)
        return {
            "provider": "generic_url",
            "title": clean_input,
            "artist": None,
            "stream_url": clean_input,
            "search_query": None,
            "bypass_search": True,
        }


# Alias for master dispatcher as requested
get_audio_stream = resolve_to_playable_stream
