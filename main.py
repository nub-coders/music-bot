import asyncio
import os
import logging

from pyrogram import idle
from pytgcalls import filters as call_filters
from pyrogram import Client
from pyrogram.errors.exceptions import (
    SessionRevoked, UserDeactivatedBan, AuthKeyInvalid,
    AuthKeyUnregistered, AuthTokenExpired, AuthKeyDuplicated,
    AccessTokenExpired, UserDeactivated,
)

from tools import *
from config import *
from youtube import check_and_update_ytdlp
from database import user_sessions as async_user_sessions, collection as async_collection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.StreamHandler()],
)

import time

logger = logging.getLogger(__name__)

# Cache directory setup
cache_dir = f"{ggg}/cache"
os.makedirs(cache_dir, exist_ok=True)


async def _cache_cleanup_loop(max_age_hours: int = 6, interval_hours: int = 6):
    """Periodically delete stale files from cache/ directory."""
    max_age_s = max_age_hours * 3600
    interval_s = interval_hours * 3600
    while True:
        try:
            now = time.time()
            removed = 0
            for entry in os.scandir(cache_dir):
                if entry.is_file() and (now - entry.stat().st_mtime) > max_age_s:
                    os.remove(entry.path)
                    removed += 1
            if removed:
                logger.info(f"[cache_cleanup] Removed {removed} stale file(s) from cache/")
        except Exception as e:
            logger.warning(f"[cache_cleanup] Error: {e}")
        await asyncio.sleep(interval_s)


async def main():
    logger.info("Starting bot initialization...")
    
    # Check and update yt-dlp if needed
    await check_and_update_ytdlp()
    
    # Create and start the bot client
    try:
        bot = Client("bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins"),
            in_memory=True,
            sleep_threshold=32,
            device_model="Desktop",
            system_version="Windows 10",
            app_version="3.4.3 x64",
            lang_code="en",
            lang_pack="tdesktop"
        )
        
        # Initialize and store session client
        session = Client("session",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=STRING_SESSION,
            in_memory=True,
            #no_updates=True,
            sleep_threshold=32,
            device_model="Desktop",
            system_version="Windows 10",
            app_version="3.4.3 x64",
            lang_code="en",
            lang_pack="tdesktop"
        )
        
        call_py = PyTgCalls(session)
        call_py.add_handler(end, call_filters.stream_end())
        call_py.add_handler(hd_stream_closed_kicked,
            call_filters.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT) | 
            call_filters.chat_update(ChatUpdate.Status.KICKED)
        )
        
        
        clients["session"] = session
        clients["call_py"] = call_py
        clients["bot"] = bot
        
        # Initialize global variables from database
        await call_py.start()
        await bot.start() 
        user_data = await async_user_sessions.find_one({"bot_id": bot.me.id})
        bot_data = await async_collection.find_one({"bot_id": bot.me.id})
        
        # Update global variables
        SUDO.clear()
        SUDO.extend(user_data.get("SUDOERS", []) if user_data else [])
        
        AUTH.clear()
        AUTH.update(user_data.get('auth_users', {}) if user_data else {})
        
        BLOCK.clear()
        BLOCK.extend(bot_data.get('busers', []) if bot_data else [])
        client_name = f"{bot.me.first_name} {bot.me.last_name or ''}".strip()
        logger.info(f"Bot authorized successfully! 🎉 Authorized as: {client_name}")
        db_task(async_user_sessions.update_one(
            {"bot_id": bot.me.id},
            {"$setOnInsert": {"bot_id": bot.me.id}},
            upsert=True
        ))
    except Exception as e:
        logger.error(f"Failed to initialize bot client: {str(e)}")
        raise
    logger.info("Bot initialization completed successfully")
    asyncio.create_task(_cache_cleanup_loop())  # periodic cache janitor
    await idle()
# Run the main function
asyncio.run(main())
