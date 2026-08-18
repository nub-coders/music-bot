"""plugins/_common.py — shared base for every plugin module.

NOT auto-loaded by Pyrogram (underscore prefix). Every plugin file does:
    from plugins._common import *
which re-exports the full namespace (pyrogram, tools, config, helpers).
"""

# ── imports (union of everything bots.py pulled in) ──
import asyncio
import base64
import datetime
import logging
import os
import random
import re
import time
from functools import wraps
from pyrogram import Client, filters, enums
from pyrogram.enums import ChatType, ChatMemberStatus, ButtonStyle
from pyrogram.errors import (
    StickersetInvalid,
    YouBlockedUser,
    FloodWait,
    InviteHashExpired,
    ChannelPrivate,
    UserBlocked,
    PeerIdInvalid,
    MessageDeleteForbidden
)
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.enums import MessageEntityType
from pyrogram.raw.types import InputStickerSetShortName
from pyrogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from pytgcalls.exceptions import NotInCallError
from pytgcalls.types import AudioQuality, MediaStream, VideoQuality
from config import *
from tools import *
from youtube import handle_youtube, extract_video_id, format_duration, get_video_details, format_number, time_to_seconds
from tools import trim_title, join_call
from utils.message import Messages
from utils.lang import get_str, get_lang, set_lang, LANGUAGES, lang_list_text
from utils.button import Buttons
from utils.emoji import Emoji, EmojiTag, keycaps
from utils.premium_emoji import position_tag
from database import push_to_array, pull_from_array, set_fields, collection, user_sessions, db_task
from thumbnails import get_thumb
from PIL import Image
import imageio
import cv2
from mutagen import File
from mutagen import MutagenError
import magic

logger = logging.getLogger("pyrogram")


def clean_alert(text: str) -> str:
    """Strip custom premium emoji tags and HTML for plain-text callback_query.answer toasts/alerts."""
    if not text:
        return ""
    clean = re.sub(r'<emoji id="[^"]*">(.*?)</emoji>', r'\1', str(text))
    clean = re.sub(r'<[^>]+>', '', clean)
    return clean.strip()


# Patch CallbackQuery.answer to automatically sanitize all button alert messages
if not getattr(CallbackQuery, "_clean_answer_patched", False):
    _orig_cb_answer = CallbackQuery.answer

    async def _safe_cb_answer(self, text: str = None, show_alert: bool = None, url: str = None, cache_time: int = 0):
        if text:
            text = clean_alert(text)
        return await _orig_cb_answer(self, text=text, show_alert=show_alert, url=url, cache_time=cache_time)

    CallbackQuery.answer = _safe_cb_answer
    CallbackQuery._clean_answer_patched = True


# ── module-level state ──
session = clients.get("session")
call_py = clients.get("call_py")
_admin_member_cache: dict[tuple[int, int], tuple[str, float]] = {}
create_custom_filter = filters.create(lambda _, __, message: any(m.is_self for m in (message.new_chat_members if message.new_chat_members else [])))
mime = magic.Magic(mime=True)

# ── shared helpers ──

def _chat_type_value(chat_type):
    return getattr(chat_type, "value", chat_type)
def _is_admin_member_status(status):
    status_value = _chat_type_value(status)
    return status_value in (
        ChatMemberStatus.OWNER.value,
        ChatMemberStatus.ADMINISTRATOR.value,
    )
async def is_authorized(client, chat_id, user_id, allow_auth_users=True):
    """May this user drive transport controls in this chat?

    Owner / sudo / bot-admin / chat-AUTH user / Telegram chat admin. The shared
    answer behind @admin_only() and any handler that needs the same call plus an
    exemption of its own. In-memory checks first; the cached get_chat_member
    round-trip only happens when none of them matched.
    """
    if user_id in get_admin_ids(f"{ggg}/admin.txt"):
        return True
    if str(OWNER_ID) == str(user_id) or user_id in SUDO:
        return True
    if allow_auth_users and user_id in AUTH.get(str(chat_id), []):
        return True

    cache_key = (chat_id, user_id)
    now = time.time()
    cached_member = _admin_member_cache.get(cache_key)
    if cached_member and cached_member[1] > now:
        return _is_admin_member_status(cached_member[0])
    chat_member = await client.get_chat_member(chat_id, user_id)
    status_value = _chat_type_value(chat_member.status)
    _admin_member_cache[cache_key] = (status_value, now + 60)
    return _is_admin_member_status(status_value)
def admin_only():
    def decorator(func):
        @wraps(func)
        async def wrapper(client, update):
            try:
                logger.debug(f"Admin check initiated for {func.__name__}")

                # Handle both callback query and regular message
                if isinstance(update, CallbackQuery):
                    chat_id = update.message.chat.id
                    reply_id = update.message.id
                    user_id = update.from_user.id if update.from_user else None
                    command = update.data
                else:
                    chat_id = update.chat.id
                    reply_id = update.id
                    user_id = update.from_user.id if update.from_user else None
                    command = update.command[0].lower()

                if not user_id:
                    linked_chat = await client.get_chat(chat_id)
                    if linked_chat.linked_chat and update.sender_chat.id == linked_chat.linked_chat.id:
                        return await func(client, update)
                    if isinstance(update, CallbackQuery):
                        await update.answer(Messages.ADMIN_UNKNOWN_USER, show_alert=True)
                    else:
                        await update.reply(Messages.ADMIN_UNKNOWN_USER, reply_to_message_id=reply_id, link_preview_options=None)
                    return

                # --- Song-owner skip: whoever queued the current track may skip
                # it, admin or not (in-memory, no I/O). ---
                if command in ("skip", "cskip"):
                    song = state.playing.get(chat_id)
                    if song and getattr(song.get("by"), "id", None) == user_id:
                        logger.info(f"User {user_id} authorized for {func.__name__} (song owner)")
                        return await func(client, update)

                # AUTH-listed users are trusted for everything except /*del.
                allow_auth_users = isinstance(update, CallbackQuery) or not (
                    command and str(command).endswith('del')
                )
                if not await is_authorized(client, chat_id, user_id, allow_auth_users):
                    logger.warning(f"User {user_id} not authorized for command {command}")
                    if isinstance(update, CallbackQuery):
                        await update.answer(Messages.ADMIN_RESTRICTED_ACTION, show_alert=True)
                    else:
                        await update.reply(Messages.ADMIN_RESTRICTED_CMD, reply_to_message_id=reply_id, link_preview_options=None)
                    return

                logger.info(f"User {user_id} authorized for {func.__name__}")
                return await func(client, update)

            except Exception as e:
                logger.error(f"Error checking admin status: {e}")
                if isinstance(update, CallbackQuery):
                    await update.answer(Messages.AUTH_FAILED, show_alert=True)
                else:
                    await update.reply(Messages.AUTH_FAILED, link_preview_options=None)
                return
        return wrapper
    return decorator
async def is_active_chat(client, chat_id):  # noqa: F811
    return chat_id in state.active
async def add_active_chat(client, chat_id):  # noqa: F811
    state.active.add(chat_id)
async def remove_active_chat(client, chat_id):
    state.active.discard(chat_id)
    chat_dir = f"{ggg}/user_{client.me.id}/{chat_id}"
    os.makedirs(chat_dir, exist_ok=True)
    clear_directory(chat_dir)
async def get_user_data(user_id, key):
    user_data = await user_sessions.find_one({"bot_id": user_id})
    if user_data and key in user_data:
        return user_data[key]
    return None
def set_user_data(user_id, key, value):
    db_task(user_sessions.update_one({"bot_id": user_id}, {"$set": {key: value}}, upsert=True))
async def gvarstatus(user_id, key):
    return await get_user_data(user_id, key)
def rename_file(old_name, new_name):
    try:
        # Rename the file
        os.rename(old_name, new_name)

        # Get the absolute path of the renamed file
        new_file_path = os.path.abspath(new_name)
        logger.info(f'File renamed from {old_name} to {new_name}')
        return new_file_path  # Return the new file location
    except FileNotFoundError:
        logger.info(f'The file {old_name} does not exist.')
    except FileExistsError:
        logger.info(f'The file {new_name} already exists.')
    except Exception as e:
        logger.info(f'An error occurred: {e}')
async def get_chat_type(client, chat_id):
  try:
    chat = await client.get_chat(chat_id)
    return chat.type
  except FloodWait as e:
        logger.info(f"Rate limited! Sleeping for {e.value} seconds.")
        await asyncio.sleep(e.value)
  except Exception as e:
    logger.info(f"Error getting chat type for {chat_id}: {e}")
    return None
async def get_cached_chat_type(client, bot_id, chat_id, chat_type_cache):
    chat_id_key = str(chat_id)
    chat_type_value = chat_type_cache.get(chat_id_key)
    if chat_type_value:
        try:
            cached_chat_type = enums.ChatType(chat_type_value)
        except Exception:
            cached_chat_type = chat_type_value
        return cached_chat_type

    chat_type = await get_chat_type(client, chat_id)
    if chat_type:
        chat_type_value = _chat_type_value(chat_type)
        chat_type_cache[chat_id_key] = chat_type_value
        db_task(collection.update_one(
            {"bot_id": bot_id},
            {"$set": {f"chat_type_cache.{chat_id_key}": chat_type_value}},
            upsert=True,
        ))
    return chat_type
async def status(client, message):
    """Handles the /status command with song statistics"""
    Nub = await message.reply_text(Messages.COLLECTING_STATS, link_preview_options=None)
    start = datetime.datetime.now()
    u = g = sg = c = a_chat = play_count = 0
    user_data = await collection.find_one({"bot_id": client.me.id})

    if user_data:
        # Clean old song entries and get count
        time_threshold = datetime.datetime.now() - datetime.timedelta(hours=24)
        db_task(collection.update_one(
            {"bot_id": client.me.id},
            {"$pull": {"dates": {"$lt": time_threshold}}}
        ))
        play_count = len([d for d in user_data.get('dates', []) if d >= time_threshold])

        users = user_data.get('users', [])
        total_users = len(users)

        if total_users > 500:
            await Nub.edit_text(
                f"<b>{EmojiTag.STATS} Comprehensive Bot Statistics</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"{EmojiTag.BOLT} <b>Processed in:</b> <code>0s</code>\n\n"
                f"✦ {EmojiTag.USER} <b>Stored Users:</b> <code>{total_users}</code>\n"
                f"✦ {EmojiTag.INFO} <b>Detailed stats:</b> <code>Skipped to avoid timeout</code>\n"
                f"✦ {EmojiTag.MUSIC_NOTE} <b>Songs Played (24h):</b> <code>{play_count}</code>\n\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>{EmojiTag.MUSIC_NOTE} @{client.me.username} Performance Summary</b>"
            )
            return

        chat_type_cache = dict(user_data.get('chat_type_cache', {}))

        # Process chats in batches for better performance
        for i, chat_id in enumerate(users):
            try:
                chat_type = await get_cached_chat_type(client, client.me.id, chat_id, chat_type_cache)

                if chat_type == enums.ChatType.PRIVATE:
                    u += 1
                elif chat_type == enums.ChatType.GROUP:
                    g += 1
                elif chat_type == enums.ChatType.SUPERGROUP:
                    sg += 1
                    try:
                        user_status = await client.get_chat_member(chat_id, client.me.id)
                        if user_status.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
                            a_chat += 1
                    except Exception as e:
                        logger.info(f"Admin check error: {e}")
                elif chat_type == enums.ChatType.CHANNEL:
                    c += 1

                # Update progress every 10 chats
                if i % 10 == 0 or i == total_users - 1:
                    progress_msg = f"""
<b>{EmojiTag.LOADING} Collecting Stats ({min(i+1, total_users)}/{total_users})</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
✦ {EmojiTag.USER} <b>Private:</b> <code>{u}</code>
✦ {EmojiTag.USERS} <b>Groups:</b> <code>{g}</code>
✦ {EmojiTag.USERS} <b>Super Groups:</b> <code>{sg}</code>
✦ {EmojiTag.BROADCAST} <b>Channels:</b> <code>{c}</code>
✦ {EmojiTag.SHIELD} <b>Admin Positions:</b> <code>{a_chat}</code>
✦ {EmojiTag.MUSIC_NOTE} <b>Songs Played (24h):</b> <code>{play_count}</code>
"""
                    await Nub.edit_text(progress_msg)

            except Exception as e:
                logger.info(f"Error processing chat {chat_id}: {e}")

        end = datetime.datetime.now()
        ms = (end - start).seconds

        final_stats = f"""
<b>{EmojiTag.STATS} Comprehensive Bot Statistics</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
{EmojiTag.BOLT} <b>Processed in:</b> <code>{ms}s</code>

✦ {EmojiTag.USER} <b>Private Chats:</b> <code>{u}</code>
✦ {EmojiTag.USERS} <b>Groups:</b> <code>{g}</code>
✦ {EmojiTag.USERS} <b>Super Groups:</b> <code>{sg}</code>
✦ {EmojiTag.BROADCAST} <b>Channels:</b> <code>{c}</code>
✦ {EmojiTag.SHIELD} <b>Admin Privileges:</b> <code>{a_chat}</code>
✦ {EmojiTag.MUSIC_NOTE} <b>Songs Played (24h):</b> <code>{play_count}</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>{EmojiTag.MUSIC_NOTE} @{client.me.username} Performance Summary</b>
"""
        await Nub.edit_text(final_stats)

    else:
        await Nub.edit_text(Messages.NO_OPERATIONAL_DATA)
