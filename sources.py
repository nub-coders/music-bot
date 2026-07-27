"""Source resolution seam.

Turns a raw /play argument into a list of `(query, title)` pairs that the
existing YouTube pipeline (youtube.handle_youtube) can resolve one-by-one.

Today only two cases exist:
  * a YouTube *playlist* URL  -> expand (flat, one network call) into its
    per-video URLs, with titles for free;
  * anything else (search text or a single video URL) -> pass through as a
    single element, title unknown until it resolves at play time.

This is the seam where non-YouTube providers plug in later: add a branch that
recognises the foreign URL (e.g. Spotify) and maps it to a list of
"artist - title" search strings — same return contract, no caller changes.
"""
import asyncio
import logging
import os
import re

import yt_dlp

from config import YT_COOKIES_FILE

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
        vid = e.get("id")
        if vid:
            out.append((f"https://www.youtube.com/watch?v={vid}", e.get("title")))
    return out


async def resolve_sources(argument: str):
    """Return a list of (query, title) to enqueue. Never empty: on any failure
    or non-playlist input, falls back to a single passthrough element."""
    if is_youtube_playlist(argument):
        try:
            items = await asyncio.to_thread(_extract_playlist_sync, argument)
            if items:
                logger.info(f"[sources] Expanded playlist into {len(items)} track(s)")
                return items
            logger.warning(f"[sources] Playlist expansion returned nothing: {argument[:80]}")
        except Exception as e:
            logger.error(f"[sources] Playlist expansion failed, treating as single query: {e}")
    return [(argument, None)]
