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
except Exception:
    pass

# ── Telegram (non-sensitive — safe as defaults) ───────────────────────────────
API_ID      = os.getenv("API_ID", "2040")
API_HASH    = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")
GROUP       = os.getenv("GROUP", "nub_coder_s")

# OWNER_ID grants unrestricted sudo (/reboot, /broadcast, auth bypass), so it
# must never fall back to a baked-in identity: any deployment that forgot to set
# it would hand full control of the bot to whoever owns that hardcoded account.
# 0 / negative are rejected too -- they are not valid user IDs, and silently
# accepting the placeholder leaves the real owner locked out of every owner-only
# command while get_users(0) fails at startup.
try:
    OWNER_ID = int(os.environ["OWNER_ID"])
except KeyError:
    raise SystemExit("OWNER_ID is not set. Set it via environment (or .env for local dev) — no default owner is baked in.")
except ValueError:
    raise SystemExit("OWNER_ID must be a numeric Telegram user ID.")
if OWNER_ID <= 0:
    raise SystemExit(f"OWNER_ID={OWNER_ID} is not a valid Telegram user ID. Set it to your own numeric user ID (get it from @userinfobot).")

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

# ── Working directory / startup ───────────────────────────────────────────────────
ggg       = os.getcwd()
StartTime = time.time()
