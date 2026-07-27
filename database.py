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


async def ensure_indexes():
    """Create the indexes for fields we actually query. Idempotent — safe to call every startup."""
    try:
        await user_sessions.create_index("bot_id")
        await user_sessions.create_index("user_id")
        await collection.create_index("bot_id")
        logger.info("[db] Indexes ensured on user_sessions(bot_id, user_id) and collection(bot_id)")
    except Exception as e:
        logger.warning(f"[db] Failed to ensure indexes: {e}")


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

# Add more helpers as needed
