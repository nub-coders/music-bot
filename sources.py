"""Source resolution seam.

Turns a raw /play argument into a list of `(query, title)` pairs that the
existing YouTube pipeline (youtube.handle_youtube) can resolve one-by-one.

Cases:
  * a Spotify track/album/playlist link -> resolve names via the Spotify Web
    API and map each to an "artist - title" search string;
  * a YouTube *playlist* URL -> expand (flat, one network call) into its
    per-video URLs, with titles for free;
  * anything else (search text or a single video URL) -> pass through as a
    single element, title unknown until it resolves at play time.

New providers plug in the same way: recognise the link, map it to a list of
search strings / URLs, return the same `(query, title)` contract — no caller
changes.
"""
import asyncio
import base64
import logging
import os
import re
import time

import httpx
import yt_dlp

from youtube import format_duration
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, YT_COOKIES_FILE

logger = logging.getLogger(__name__)

# ponytail: hard cap on how many tracks one playlist link may enqueue. A shared
# link to a 500-track playlist should not let one user flood the queue. Raise
# here (and only here) if a larger ceiling is ever wanted.
MAX_PLAYLIST_ITEMS = 50

_YT_DOMAIN = re.compile(r"^(https?://)?(www\.|music\.|m\.)?(youtube\.com|youtu\.be)/", re.I)


def is_youtube_playlist(url: str) -> bool:
    """True for a YouTube *playlist* link (has list=, and is not a plain
    watch?v=... single-video link that merely carries a playlist context)."""
    if not _YT_DOMAIN.match(url or ""):
        return False
    if "list=" not in url:
        return False
    # watch?v=VIDEO&list=... is a single video the user clicked *within* a
    # playlist — play just that video, don't dump the whole list.
    return "v=" not in url or "/playlist" in url


def _extract_playlist_sync(url: str):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,      # metadata only, no per-video network calls
        "playlistend": MAX_PLAYLIST_ITEMS,
        **({"cookiefile": YT_COOKIES_FILE} if YT_COOKIES_FILE and os.path.exists(YT_COOKIES_FILE) else {}),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = (info or {}).get("entries") or []
    out = []
    for e in entries[:MAX_PLAYLIST_ITEMS]:
        vid = e.get("id") or e.get("url")
        if vid:
            raw_url = vid if str(vid).startswith("http") else f"https://www.youtube.com/watch?v={vid}"
            dur = e.get("duration")
            dur_str = format_duration(dur) if dur else None
            out.append((raw_url, e.get("title"), dur_str))
    return out


async def resolve_sources(argument: str):
    """Return a list of (query, title, duration) to enqueue. Never empty: on any failure
    or non-playlist input, falls back to a single passthrough element."""
    if is_spotify(argument):
        try:
            items = await _resolve_spotify(argument)
            if items:
                logger.info(f"[sources] Resolved Spotify link into {len(items)} track(s)")
                return items
            logger.warning(f"[sources] Spotify resolution returned nothing: {argument[:80]}")
        except Exception as e:
            logger.error(f"[sources] Spotify resolution failed, treating as single query: {e}")
    if is_youtube_playlist(argument):
        try:
            items = await asyncio.to_thread(_extract_playlist_sync, argument)
            if items:
                logger.info(f"[sources] Expanded playlist into {len(items)} track(s)")
                return items
            logger.warning(f"[sources] Playlist expansion returned nothing: {argument[:80]}")
        except Exception as e:
            logger.error(f"[sources] Playlist expansion failed, treating as single query: {e}")
    return [(argument, None, None)]


# ── Spotify (Client Credentials flow — server-side metadata only) ───────────────
_SPOTIFY_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]+/)?(track|album|playlist)/([A-Za-z0-9]+)", re.I
)
# ponytail: single cached app token guarded by a lock; refreshed ~1 min before
# expiry. One process, one token — no per-request auth round-trip.
_token = {"value": None, "expires_at": 0.0}
_token_lock = asyncio.Lock()


def is_spotify(url: str) -> bool:
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET and _SPOTIFY_RE.search(url or ""))


async def _spotify_token(http: httpx.AsyncClient) -> str:
    async with _token_lock:
        if _token["value"] and time.time() < _token["expires_at"]:
            return _token["value"]
        auth = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        r = await http.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
        )
        r.raise_for_status()
        body = r.json()
        _token["value"] = body["access_token"]
        _token["expires_at"] = time.time() + body.get("expires_in", 3600) - 60
        return _token["value"]


def _track_query(track: dict):
    """A Spotify track object -> ("artist - title", "title") for YouTube search."""
    if not track:
        return None
    title = track.get("name")
    if not title:
        return None
    artists = ", ".join(a["name"] for a in track.get("artists", []) if a.get("name"))
    return (f"{artists} - {title}".strip(" -"), title)


async def _resolve_spotify(url: str):
    kind, sid = _SPOTIFY_RE.search(url).groups()
    kind = kind.lower()
    async with httpx.AsyncClient(timeout=15) as http:
        token = await _spotify_token(http)
        headers = {"Authorization": f"Bearer {token}"}

        if kind == "track":
            r = await http.get(f"https://api.spotify.com/v1/tracks/{sid}", headers=headers)
            r.raise_for_status()
            q = _track_query(r.json())
            return [q] if q else []

        # album / playlist: page through items, capped at MAX_PLAYLIST_ITEMS.
        if kind == "album":
            base = f"https://api.spotify.com/v1/albums/{sid}/tracks"
            def pick(item): return item                 # album items ARE tracks
        else:
            base = f"https://api.spotify.com/v1/playlists/{sid}/tracks"
            def pick(item): return (item or {}).get("track")  # playlist wraps them

        out, next_url, params = [], base, {"limit": 50}
        while next_url and len(out) < MAX_PLAYLIST_ITEMS:
            r = await http.get(next_url, headers=headers, params=params)
            r.raise_for_status()
            page = r.json()
            for item in page.get("items", []):
                q = _track_query(pick(item))
                if q:
                    out.append(q)
                    if len(out) >= MAX_PLAYLIST_ITEMS:
                        break
            next_url, params = page.get("next"), None  # `next` is a full URL
        return out
