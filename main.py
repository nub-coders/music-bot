import asyncio
import os
import logging

from pyrogram import idle
from pytgcalls import PyTgCalls, filters as call_filters
from pytgcalls.types import ChatUpdate, Device
from pyrogram import Client
from pyrogram.errors.exceptions import (
    SessionRevoked, UserDeactivatedBan, AuthKeyInvalid,
    AuthKeyUnregistered, AuthTokenExpired, AuthKeyDuplicated,
    AccessTokenExpired, UserDeactivated,
)

from tools import *
from config import *
from youtube import check_and_update_ytdlp, export_browser_cookies, refresh_cookies_loop
from database import user_sessions as async_user_sessions, collection as async_collection, ensure_indexes
from utils.premium_emoji import setup_premium_emoji

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


async def _assistant_autoleave_loop(check_interval_seconds: int = 3600):
    """Periodically scan groups and make assistants leave idle chats to stay under Telegram's 500-group limit."""
    if not AUTO_LEAVING_ASSISTANT:
        return
    await asyncio.sleep(90)  # grace period on startup
    while True:
        try:
            now = time.time()
            # Allowlist: never leave authorized chats, logger group, or active calls
            exempt_chat_ids = set()
            if LOGGER_ID:
                try:
                    exempt_chat_ids.add(int(LOGGER_ID))
                except (ValueError, TypeError):
                    pass
            for auth_cid in AUTH.keys():
                try:
                    exempt_chat_ids.add(int(auth_cid))
                except (ValueError, TypeError):
                    pass

            for idx, ast in list(assistants.items()):
                active_in_ast = state.assistant_active.get(idx, set())
                try:
                    async for dialog in ast.get_dialogs():
                        chat = dialog.chat
                        chat_type_str = str(getattr(chat, "type", "")).lower()
                        if "group" in chat_type_str or "supergroup" in chat_type_str:
                            cid = chat.id
                            # If this chat has an active stream or is authorized / exempt, skip
                            if cid in state.active or cid in active_in_ast or cid in exempt_chat_ids or str(cid) in AUTH or cid in AUTH:
                                continue
                            # If last played was within ASSISTANT_LEAVE_TIME, skip.
                            # On startup, unrecorded chats use StartTime as baseline to prevent mass-leaves.
                            last_played_ts = state.played.get(cid, StartTime)
                            if (now - last_played_ts) < ASSISTANT_LEAVE_TIME:
                                continue
                            # Otherwise, leave idle chat to conserve group slots
                            chat_title = getattr(chat, "title", str(cid))
                            logger.info(f"[auto_leave] Assistant {idx} leaving idle chat '{chat_title}' ({cid}) (inactive for {int(now - last_played_ts)}s)...")
                            try:
                                await ast.leave_chat(cid)
                                logger.info(f"[auto_leave] Assistant {idx} successfully left idle chat '{chat_title}' ({cid})")
                                await asyncio.sleep(2.0)  # Rate limit safety spacing
                            except Exception as leave_err:
                                logger.warning(f"[auto_leave] Assistant {idx} failed to leave chat '{chat_title}' ({cid}): {leave_err}")
                except Exception as dialog_err:
                    logger.warning(f"[auto_leave] Error scanning dialogs for Assistant {idx}: {dialog_err}")
        except Exception as e:
            logger.warning(f"[auto_leave] Exception in auto-leave loop: {e}")
        await asyncio.sleep(check_interval_seconds)


async def main():
    logger.info("Starting bot initialization...")

    # Check and update yt-dlp if needed
    await check_and_update_ytdlp()

    # Optionally refresh the yt-dlp cookie file from a browser profile (no-op
    # unless COOKIES_FROM_BROWSER is set). Best effort — never blocks startup.
    await export_browser_cookies()

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

        # Collect configured assistant sessions
        sessions_to_init = STRING_SESSIONS if STRING_SESSIONS else ([STRING_SESSION] if STRING_SESSION else [])
        if not sessions_to_init:
            raise SystemExit("No assistant STRING_SESSION found. Provide at least one session string in .env.")

        # Initialize all assistant clients and PyTgCalls instances
        assistants.clear()
        calls.clear()
        assistant_info.clear()

        for idx, s_str in enumerate(sessions_to_init, start=1):
            ast_client = Client(
                f"assistant_{idx}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=s_str,
                in_memory=True,
                sleep_threshold=32,
                device_model="Desktop",
                system_version="Windows 10",
                app_version="3.4.3 x64",
                lang_code="en",
                lang_pack="tdesktop",
            )
            ast_call = PyTgCalls(ast_client)
            ast_call.add_handler(end, call_filters.stream_end(device=Device.MICROPHONE))
            ast_call.add_handler(
                hd_stream_closed_kicked,
                call_filters.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT) |
                call_filters.chat_update(ChatUpdate.Status.KICKED),
            )
            assistants[idx] = ast_client
            calls[idx] = ast_call

        clients["assistants"] = assistants
        clients["calls"] = calls
        clients["assistant_info"] = assistant_info
        clients["session"] = assistants[1]  # primary assistant fallback
        clients["call_py"] = calls[1]      # primary call fallback
        clients["bot"] = bot

        # Start all assistant clients and PyTgCalls instances concurrently
        for idx, ast in assistants.items():
            await ast.start()
            cp = calls[idx]
            await cp.start()
            me = ast.me
            name = f"{me.first_name} {me.last_name or ''}".strip()
            mention = me.mention() if hasattr(me, "mention") else f"@{me.username or me.id}"
            assistant_info[idx] = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "mention": mention,
                "name": name,
            }
            logger.info(f"Assistant {idx} authorized successfully! 🎉 Authorized as: {name} (@{me.username or me.id})")

        # Start the bot client
        await bot.start()
        await ensure_indexes()
        user_data = await async_user_sessions.find_one({"bot_id": bot.me.id})
        bot_data = await async_collection.find_one({"bot_id": bot.me.id})

        # Update global variables
        SUDO.clear()
        SUDO.extend(user_data.get("SUDOERS", []) if user_data else [])

        AUTH.clear()
        AUTH.update(user_data.get('auth_users', {}) if user_data else {})

        BLOCK.clear()
        BLOCK.extend(bot_data.get('busers', []) if bot_data else [])

        # Seed admin list from INITIAL_ADMIN_IDS on first start, then load from DB.
        ADMIN.clear()
        db_admins = bot_data.get("admins", []) if bot_data else []
        seed = [a for a in INITIAL_ADMIN_IDS if a not in db_admins]
        if seed:
            await async_collection.update_one(
                {"bot_id": bot.me.id},
                {"$addToSet": {"admins": {"$each": seed}}},
                upsert=True,
            )
            db_admins = db_admins + seed
        ADMIN.extend(db_admins)
        client_name = f"{bot.me.first_name} {bot.me.last_name or ''}".strip()
        logger.info(f"Bot authorized successfully! 🎉 Authorized as: {client_name} with {len(assistants)} Assistant(s)")

        # Ask Telegram once whether this bot may send premium/custom emoji, then
        # bake the answer into the emoji constants. Everything built after this
        # line — messages, buttons — is already correct; nothing re-checks.
        await setup_premium_emoji(bot, LOGGER_ID, OWNER_ID)
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
    asyncio.create_task(refresh_cookies_loop())  # periodic cookie re-export (no-op unless enabled)
    if AUTO_LEAVING_ASSISTANT:
        asyncio.create_task(_assistant_autoleave_loop())  # periodic idle group cleanup
    await idle()

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())


