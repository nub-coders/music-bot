"""
Async MongoDB database handler for nub-music-bot
"""
import asyncio
import inspect
import logging
import time
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticCollection, AgnosticDatabase, AgnosticClient

# Pyrogram/Kurigram `load_plugins()` inspects `hasattr(attr, "handlers")` for every
# module-level global. Motor's dynamic `__getattr__` returns sub-collections for any
# attribute name, causing `hasattr` to return True and crash on `for handler in coll.handlers`.
for _cls in (AgnosticCollection, AgnosticDatabase, AgnosticClient):
    _orig = _cls.__getattr__

    def _make_safe(orig):
        def _safe_getattr(self, name):
            if name == "handlers" or name.startswith("_"):
                raise AttributeError(f"{self.__class__.__name__} has no attribute {name!r}")
            return orig(self, name)
        return _safe_getattr

    _cls.__getattr__ = _make_safe(_orig)

logger = logging.getLogger(__name__)

from config import MONGODB_URI as MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# Collections
user_sessions = db["user_sessions"]
collection = db["collection"]
chat_assistants = db["chat_assistants"]
chat_playback = db["chat_playback"]
user_playlists = db["user_playlists"]


async def ensure_indexes():
    """Create the indexes for fields we actually query. Idempotent — safe to call every startup."""
    try:
        await user_sessions.create_index("bot_id")
        await user_sessions.create_index("user_id")
        await collection.create_index("bot_id")
        await chat_assistants.create_index("chat_id", unique=True)
        await chat_playback.create_index("chat_id", unique=True)
        await user_playlists.create_index("user_id", unique=True)
        logger.info("[db] Indexes ensured on user_sessions(bot_id, user_id), collection(bot_id), chat_assistants(chat_id), chat_playback(chat_id), and user_playlists(user_id)")
    except Exception as e:
        logger.warning(f"[db] Failed to ensure indexes: {e}")


async def set_last_played(chat_id: int, ts: int):
    """Persist the last time a chat started playback and increment its play count.

    state.played is in-memory only, so after a restart every chat looks "never
    played" and the auto-leave sweep cannot tell idle from unknown. Persisting it
    lets idle reclamation survive reboots.

    ``play_dates`` keeps the individual epochs (capped at the last 1000) so
    /stats can report a per-group play count for a chosen window; ``play_count``
    stays the authoritative all-time total, since it predates this array.
    """
    try:
        await chat_playback.update_one(
            {"chat_id": int(chat_id)},
            {
                "$set": {"last_played": int(ts)},
                "$inc": {"play_count": 1},
                "$push": {"play_dates": {"$each": [int(ts)], "$slice": -1000}},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[db] set_last_played error for {chat_id}: {e}")


async def get_chat_playback(chat_id: int) -> dict:
    """Return a chat's playback stats doc, or {} if it has never played."""
    try:
        doc = await chat_playback.find_one({"chat_id": int(chat_id)})
        return doc or {}
    except Exception as e:
        logger.warning(f"[db] get_chat_playback error for {chat_id}: {e}")
        return {}


async def get_all_last_played() -> dict:
    """Load every chat's last playback timestamp as {chat_id: ts} for warm start."""
    out = {}
    try:
        async for doc in chat_playback.find({}, {"chat_id": 1, "last_played": 1}):
            cid, ts = doc.get("chat_id"), doc.get("last_played")
            if cid is not None and ts is not None:
                out[int(cid)] = int(ts)
    except Exception as e:
        logger.warning(f"[db] get_all_last_played error: {e}")
    return out


async def get_top_chats(limit: int = 10) -> list:
    """Retrieve top chats sorted by play_count descending."""
    top_list = []
    try:
        cursor = chat_playback.find({}, {"chat_id": 1, "play_count": 1}).sort("play_count", -1).limit(limit)
        async for doc in cursor:
            cid = doc.get("chat_id")
            cnt = doc.get("play_count", 0)
            if cid is not None:
                top_list.append((int(cid), int(cnt)))
    except Exception as e:
        logger.warning(f"[db] get_top_chats error: {e}")
    return top_list



async def get_chat_assistant(chat_id: int) -> int | None:
    """Retrieve the assigned assistant index (1..5) for a chat from MongoDB."""
    try:
        doc = await chat_assistants.find_one({"chat_id": int(chat_id)})
        return int(doc["assistant_num"]) if doc and "assistant_num" in doc else None
    except Exception as e:
        logger.warning(f"[db] get_chat_assistant error for {chat_id}: {e}")
        return None


async def set_chat_assistant(chat_id: int, assistant_num: int):
    """Persist the assigned assistant index (1..5) for a chat in MongoDB."""
    try:
        await chat_assistants.update_one(
            {"chat_id": int(chat_id)},
            {"$set": {"assistant_num": int(assistant_num)}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[db] set_chat_assistant error for {chat_id} -> {assistant_num}: {e}")


async def remove_chat_assistant(chat_id: int):
    """Remove assistant assignment for a chat from MongoDB."""
    try:
        await chat_assistants.delete_one({"chat_id": int(chat_id)})
    except Exception as e:
        logger.warning(f"[db] remove_chat_assistant error for {chat_id}: {e}")


async def _bg_db_task(coro):
    """Fire-and-forget wrapper for low-priority MongoDB writes."""
    try:
        if inspect.iscoroutine(coro) or inspect.isawaitable(coro):
            await coro
        else:
            logger.warning(f"[bg_db] Received non-awaitable object: {type(coro).__name__}")
    except Exception as e:
        logger.warning(f"[bg_db] Low-priority DB write failed: {e}")


def db_task(coro):
    """Schedule a MongoDB write as a low-priority background task."""
    asyncio.create_task(_bg_db_task(coro))


async def push_to_array(collection, filter, field, value, upsert=False):
    return await collection.update_one(filter, {"$push": {field: value}}, upsert=upsert)

async def pull_from_array(collection, filter, field, value, upsert=False):
    return await collection.update_one(filter, {"$pull": {field: value}}, upsert=upsert)

async def set_fields(collection, filter, fields, upsert=False):
    return await collection.update_one(filter, {"$set": fields}, upsert=upsert)


# ── User Playlists ─────────────────────────────────────────────────────────────

async def get_user_playlists(user_id: int) -> list[dict]:
    """Retrieve all playlists for a user, returning a list of playlist dicts."""
    try:
        doc = await user_playlists.find_one({"user_id": int(user_id)})
        return (doc.get("playlists") or []) if doc else []
    except Exception as e:
        logger.warning(f"[db] get_user_playlists error for {user_id}: {e}")
        return []


async def get_playlist(user_id: int, playlist_id: str) -> dict | None:
    """Retrieve a specific playlist by its id for a user."""
    try:
        doc = await user_playlists.find_one({"user_id": int(user_id)})
        if not doc:
            return None
        for pl in doc.get("playlists", []):
            if pl.get("id") == str(playlist_id):
                return pl
    except Exception as e:
        logger.warning(f"[db] get_playlist error for user {user_id}, pl {playlist_id}: {e}")
    return None


async def get_playlist_by_name(user_id: int, name: str) -> dict | None:
    """Retrieve a specific playlist by its name (case-insensitive) for a user."""
    try:
        doc = await user_playlists.find_one({"user_id": int(user_id)})
        if not doc:
            return None
        target = str(name).strip().lower()
        for pl in doc.get("playlists", []):
            if str(pl.get("name", "")).strip().lower() == target:
                return pl
    except Exception as e:
        logger.warning(f"[db] get_playlist_by_name error for user {user_id}, name {name}: {e}")
    return None


async def create_playlist(user_id: int, name: str, max_playlists: int = 5) -> tuple[bool, str, dict | None]:
    """Create a new playlist for a user. Returns (success, message, playlist_dict)."""
    try:
        clean_name = str(name).strip()
        uid = int(user_id)
        doc = await user_playlists.find_one({"user_id": uid})
        existing = (doc.get("playlists") or []) if doc else []
        if len(existing) >= max_playlists:
            return False, "MAX_PLAYLISTS", None

        # Check if name already exists
        if any(pl.get("name", "").lower() == clean_name.lower() for pl in existing):
            return False, "NAME_EXISTS", None

        new_pl = {
            "id": uuid.uuid4().hex[:8],
            "name": clean_name,
            "tracks": [],
            "created_at": int(time.time()),
        }
        await user_playlists.update_one(
            {"user_id": uid},
            {"$push": {"playlists": new_pl}},
            upsert=True,
        )
        return True, "CREATED", new_pl
    except Exception as e:
        logger.warning(f"[db] create_playlist error for user {user_id}: {e}")
        return False, str(e), None


async def rename_playlist(user_id: int, playlist_id: str, new_name: str) -> tuple[bool, str]:
    """Rename a playlist for a user. Returns (success, message)."""
    try:
        clean_name = str(new_name).strip()
        uid = int(user_id)
        doc = await user_playlists.find_one({"user_id": uid})
        if not doc:
            return False, "NOT_FOUND"
        existing = doc.get("playlists", [])
        if any(pl.get("name", "").lower() == clean_name.lower() and pl.get("id") != str(playlist_id) for pl in existing):
            return False, "NAME_EXISTS"

        res = await user_playlists.update_one(
            {"user_id": uid, "playlists.id": str(playlist_id)},
            {"$set": {"playlists.$.name": clean_name}},
        )
        return (res.modified_count > 0), "RENAMED" if res.modified_count > 0 else "NOT_FOUND"
    except Exception as e:
        logger.warning(f"[db] rename_playlist error for user {user_id}, pl {playlist_id}: {e}")
        return False, str(e)


async def delete_playlist(user_id: int, playlist_id: str) -> bool:
    """Delete an entire playlist for a user."""
    try:
        uid = int(user_id)
        res = await user_playlists.update_one(
            {"user_id": uid},
            {"$pull": {"playlists": {"id": str(playlist_id)}}},
        )
        return res.modified_count > 0
    except Exception as e:
        logger.warning(f"[db] delete_playlist error for user {user_id}, pl {playlist_id}: {e}")
        return False


async def add_track_to_playlist(user_id: int, playlist_id: str, track: dict, max_tracks: int = 50) -> tuple[bool, str]:
    """Add a track dict to a user's playlist. Returns (success, message_code)."""
    try:
        uid = int(user_id)
        doc = await user_playlists.find_one({"user_id": uid})
        if not doc:
            return False, "NOT_FOUND"
        target_pl = None
        for pl in doc.get("playlists", []):
            if pl.get("id") == str(playlist_id):
                target_pl = pl
                break
        if not target_pl:
            return False, "NOT_FOUND"

        tracks = target_pl.get("tracks", [])
        if len(tracks) >= max_tracks:
            return False, "MAX_TRACKS"

        # Duplicate check by video_id or yt_link or title
        track_vid = track.get("video_id")
        track_link = track.get("yt_link")
        track_title = track.get("title")

        for existing_t in tracks:
            if track_vid and existing_t.get("video_id") and existing_t.get("video_id") == track_vid:
                return False, "ALREADY_EXISTS"
            if track_link and existing_t.get("yt_link") and existing_t.get("yt_link") == track_link:
                return False, "ALREADY_EXISTS"
            if track_title and existing_t.get("title") and existing_t.get("title").lower() == track_title.lower():
                return False, "ALREADY_EXISTS"

        track_entry = {
            "id": uuid.uuid4().hex[:8],
            "title": track.get("title", "Unknown Track"),
            "duration": track.get("duration", "N/A"),
            "yt_link": track.get("yt_link", ""),
            "video_id": track.get("video_id", ""),
            "mode": track.get("mode", "audio"),
        }

        res = await user_playlists.update_one(
            {"user_id": uid, "playlists.id": str(playlist_id)},
            {"$push": {"playlists.$.tracks": track_entry}},
        )
        return (res.modified_count > 0), "ADDED" if res.modified_count > 0 else "ERROR"
    except Exception as e:
        logger.warning(f"[db] add_track_to_playlist error: {e}")
        return False, str(e)


async def remove_track_from_playlist(user_id: int, playlist_id: str, track_index: int) -> bool:
    """Remove a track by 0-based index from a user's playlist."""
    try:
        uid = int(user_id)
        doc = await user_playlists.find_one({"user_id": uid})
        if not doc:
            return False
        for pl in doc.get("playlists", []):
            if pl.get("id") == str(playlist_id):
                tracks = pl.get("tracks", [])
                if 0 <= track_index < len(tracks):
                    tracks.pop(track_index)
                    await user_playlists.update_one(
                        {"user_id": uid, "playlists.id": str(playlist_id)},
                        {"$set": {"playlists.$.tracks": tracks}},
                    )
                    return True
        return False
    except Exception as e:
        logger.warning(f"[db] remove_track_from_playlist error: {e}")
        return False


