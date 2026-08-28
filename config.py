import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

# ── SSL CA Certificates Setup ──────────────────────────────────────────────────
# Ensure SSL CA certificates are properly configured for httpx, requests, urllib,
# yt-dlp, etc., preventing FileNotFoundError on HTTPS connections in minimal environments.
try:
    import certifi
    ca_bundle = certifi.where()
    for env_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        val = os.getenv(env_var)
        if not val or not os.path.exists(val):
            os.environ[env_var] = ca_bundle
except Exception as e:
    # Runs before main.py configures logging, so this is only visible when a
    # handler is already attached; the fallback (system CA store) is harmless.
    logging.getLogger(__name__).debug(f"[config] certifi CA bundle setup skipped: {e}")

# ── Telegram (non-sensitive — safe as defaults) ───────────────────────────────
API_ID      = os.getenv("API_ID", "2040")
API_HASH    = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")
GROUP       = os.getenv("GROUP", "nub_coder_s")

# OWNER_ID grants unrestricted sudo (/reboot, /broadcast, auth bypass), so it
# must never fall back to a baked-in identity: any deployment that forgot to set
# it would hand full control of the bot to whoever owns that hardcoded account.
#
# It is OPTIONAL. Leave it unset (or 0) to run an ownerless bot: no user holds
# owner rights, the "creator" button is omitted from /start, and owner-only
# commands are reachable only via SUDO / admin.txt. Every `user_id == OWNER_ID`
# check fails closed for 0, since no real Telegram account has ID 0. Negative
# values are still rejected -- they are group/channel IDs, not users, so they
# indicate a genuine misconfiguration rather than a deliberate opt-out.
_owner_raw = os.getenv("OWNER_ID", "").strip()
if not _owner_raw:
    OWNER_ID = 0
else:
    try:
        OWNER_ID = int(_owner_raw)
    except ValueError:
        raise SystemExit("OWNER_ID must be a numeric Telegram user ID (or empty for an ownerless bot).")
    if OWNER_ID < 0:
        raise SystemExit(f"OWNER_ID={OWNER_ID} is not a valid user ID (negative IDs are chats). Leave it empty to run without an owner.")

# True when a real owner is configured. Prefer this over truth-testing OWNER_ID
# at call sites that must not contact Telegram for a nonexistent account.
HAS_OWNER = OWNER_ID > 0


def is_bot_owner(user_id) -> bool:
    """Is this caller the configured bot owner? The single place that answers it.

    Around twenty handlers used to inline this comparison, each written slightly
    differently (`user.id != OWNER_ID`, `str(OWNER_ID) == str(uid)`, `not sender_id
    == OWNER_ID`), so there was no one place to reason about the two edge cases:

    * HAS_OWNER -- in ownerless mode OWNER_ID is 0, and a bare comparison promotes
      any caller whose id is 0 or otherwise falsy.
    * A missing id -- anonymous group admins and channel senders have no user id,
      so callers can pass `message.from_user.id if message.from_user else None`
      and get False rather than an accidental match.

    Named `is_bot_owner` rather than `is_owner` because several handlers already
    use `is_owner` as a local flag, and a star-imported function of that name
    would be shadowed into an UnboundLocalError.
    """
    if not HAS_OWNER or not user_id:
        return False
    return str(OWNER_ID) == str(user_id)

# ── Sensitive — must be set via environment, no defaults ────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN", "")
STRING_SESSION  = os.getenv("STRING_SESSION", os.getenv("STRING_SESSION1", ""))
STRING_SESSION1 = os.getenv("STRING_SESSION1", STRING_SESSION)
STRING_SESSION2 = os.getenv("STRING_SESSION2", "")
STRING_SESSION3 = os.getenv("STRING_SESSION3", "")
STRING_SESSION4 = os.getenv("STRING_SESSION4", "")
STRING_SESSION5 = os.getenv("STRING_SESSION5", "")

# Collect all non-empty assistant session strings (supports 1 to 5 assistants)
STRING_SESSIONS = [
    s for s in [STRING_SESSION1, STRING_SESSION2, STRING_SESSION3, STRING_SESSION4, STRING_SESSION5] if s
]

# Auto-leave idle chats for assistant accounts to stay under Telegram's 500-group limit
AUTO_LEAVING_ASSISTANT = os.getenv("AUTO_LEAVING_ASSISTANT", "True").lower() in ("true", "1", "yes")
try:
    ASSISTANT_LEAVE_TIME = int(os.getenv("ASSISTANT_LEAVE_TIME", "5400"))  # default: 90 minutes (seconds)
except ValueError:
    ASSISTANT_LEAVE_TIME = 5400

# Blast radius controls for the auto-leave sweep. A bug in the idle heuristic is
# unrecoverable (re-joining hundreds of groups needs fresh invite links), so cap
# how many chats one sweep may leave and allow a log-only rehearsal first.
try:
    ASSISTANT_MAX_LEAVES_PER_SWEEP = int(os.getenv("ASSISTANT_MAX_LEAVES_PER_SWEEP", "10"))
except ValueError:
    ASSISTANT_MAX_LEAVES_PER_SWEEP = 10
# Set ASSISTANT_LEAVE_DRY_RUN=True to log every would-be leave without leaving.
ASSISTANT_LEAVE_DRY_RUN = os.getenv("ASSISTANT_LEAVE_DRY_RUN", "False").lower() in ("true", "1", "yes")

try:
    MONGODB_URI = os.environ["MONGODB_URI"]  # fail fast on startup if unset — never bake in a cluster
except KeyError:
    raise SystemExit("MONGODB_URI is not set. Set it via environment (or .env for local dev) — no default cluster is baked in.")

# Optional: comma-separated user IDs seeded into the DB admin list on first startup.
INITIAL_ADMIN_IDS = [
    int(x) for x in os.getenv("INITIAL_ADMIN_IDS", "").replace(",", " ").split() if x.strip()
]

# ── Optional ──────────────────────────────────────────────────────────────────────
LOGGER_ID = os.getenv("LOGGER_ID", None)
DB_NAME   = os.getenv("DB_NAME", "musicbot")

# ── YouTube API ───────────────────────────────────────────────────────────────────
# Comma-separated list of YouTube Data API v3 keys.
# Get from https://console.cloud.google.com  (10K req/day free per key)
# Leave blank → yt-dlp only (no view counts / channel info from Data API)
YOUTUBE_API_KEYS = os.getenv("YOUTUBE_API_KEYS", "")

# External ytube proxy API (optional)
YTUBE_API_TOKEN   = os.getenv("YTUBE_API_TOKEN") or os.getenv("YT_API_TOKEN", None)
YT_API_TOKEN      = YTUBE_API_TOKEN
YTUBE_API_BASE_URL = os.getenv("YTUBE_API_BASE_URL") or os.getenv("NUB_YT_API_BASE_URL", "https://api.nubcoders.com")
NUB_YT_API_BASE_URL = YTUBE_API_BASE_URL

# Optional path to a Netscape-format cookies.txt for yt-dlp (age-restricted / region-locked
# videos). Export one from your browser and mount it into the container, then set this env var.
# Left unset → yt-dlp runs without cookies (the normal path; no silent browser-profile fallback).
YT_COOKIES_FILE = os.getenv("YT_COOKIES_FILE", None)

# Optionally export cookies from a locally-installed browser profile into
# YT_COOKIES_FILE once at startup (youtube.export_browser_cookies). Set to a
# browser name yt-dlp understands: firefox, chrome, chromium, edge, brave,
# opera, vivaldi, safari, whale. May list several (comma/space-separated) —
# each is tried in order until one yields a valid cookie file. Unset → no
# export. When set but YT_COOKIES_FILE is not, cookies are written to
# ./cookies.txt.
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER", None)
if COOKIES_FROM_BROWSER and not YT_COOKIES_FILE:
    YT_COOKIES_FILE = os.path.join(os.getcwd(), "cookies.txt")
# URL hit during the export so yt-dlp exits cleanly and the cookies are
# validated against a real request. And how often to re-export — YouTube rotates
# tokens mid-session, so a once-at-startup file goes stale. 0 disables refresh.
COOKIES_BOOTSTRAP_URL = os.getenv("COOKIES_BOOTSTRAP_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw")
try:
    COOKIES_REFRESH_HOURS = float(os.getenv("COOKIES_REFRESH_HOURS", "6"))
except ValueError:
    COOKIES_REFRESH_HOURS = 6.0

# Spotify Web API (optional). When both are set, Spotify track/album/playlist
# links are resolved to "artist - title" searches and played via YouTube.
# Client Credentials flow — no user login, no redirect. Unset → Spotify links
# fall back to a plain search. Keep the secret out of git (env only).
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", None)
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", None)

# ── Media File Limits ─────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB limit (2,147,483,648 bytes)

# ── Direct stream URL safety (SSRF) ───────────────────────────────────────────────
# /play accepts arbitrary http(s) URLs from any group member, which are then
# fetched by yt-dlp and by the bot's HTTP client. By default those URLs must
# resolve to globally-routable addresses, so nobody can make the bot read
# 169.254.169.254 (cloud metadata), a loopback admin port, or the host's LAN.
#
# Set ALLOW_PRIVATE_STREAM_URLS=True only when the bot is deliberately pointed at
# a private media server (Jellyfin/Plex on a LAN). It re-opens the metadata and
# loopback surface to everyone who can type /play, so keep it off in public bots.
ALLOW_PRIVATE_STREAM_URLS = os.getenv("ALLOW_PRIVATE_STREAM_URLS", "False").lower() in ("true", "1", "yes")

# ── Working directory / startup ───────────────────────────────────────────────────
ggg       = os.getcwd()
StartTime = time.time()

