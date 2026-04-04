"""
Async MongoDB database handler for nub-music-bot
"""
import asyncio
import inspect
import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

from config import MONGODB_URI as MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# Collections
user_sessions = db["user_sessions"]
collection = db["collection"]


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

async def update_one(collection, filter, update, upsert=False):
    return await collection.update_one(filter, update, upsert=upsert)

async def find_one(collection, filter):
    return await collection.find_one(filter)

async def push_to_array(collection, filter, field, value, upsert=False):
    return await collection.update_one(filter, {"$push": {field: value}}, upsert=upsert)

async def pull_from_array(collection, filter, field, value, upsert=False):
    return await collection.update_one(filter, {"$pull": {field: value}}, upsert=upsert)

async def set_fields(collection, filter, fields, upsert=False):
    return await collection.update_one(filter, {"$set": fields}, upsert=upsert)

# Add more helpers as needed
