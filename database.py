"""
Async MongoDB database handler for nub-music-bot
"""
import asyncio
import inspect
import logging

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

from config import MONGODB_URI as MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# Collections
user_sessions = db["user_sessions"]
collection = db["collection"]
chat_assistants = db["chat_assistants"]
chat_playback = db["chat_playback"]


async def ensure_indexes():
    """Create the indexes for fields we actually query. Idempotent — safe to call every startup."""
    try:
        await user_sessions.create_index("bot_id")
        await user_sessions.create_index("user_id")
        await collection.create_index("bot_id")
        await chat_assistants.create_index("chat_id", unique=True)
        await chat_playback.create_index("chat_id", unique=True)
        logger.info("[db] Indexes ensured on user_sessions(bot_id, user_id), collection(bot_id), chat_assistants(chat_id), and chat_playback(chat_id)")
    except Exception as e:
        logger.warning(f"[db] Failed to ensure indexes: {e}")


async def set_last_played(chat_id: int, ts: int):
    """Persist the last time a chat started playback.

    state.played is in-memory only, so after a restart every chat looks "never
    played" and the auto-leave sweep cannot tell idle from unknown. Persisting it
    lets idle reclamation survive reboots.
    """
    try:
        await chat_playback.update_one(
            {"chat_id": int(chat_id)},
            {"$set": {"last_played": int(ts)}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[db] set_last_played error for {chat_id}: {e}")


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

