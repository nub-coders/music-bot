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
    MessageDeleteForbidden,
    ChatAdminRequired,
    ChatWriteForbidden,
    UserAlreadyParticipant,
    UserNotParticipant
)
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.enums import MessageEntityType
from pyrogram.raw.types import InputStickerSetShortName
from pyrogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputRichMessage,
    ReplyParameters
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
from utils.premium_emoji import position_tag, strip_custom_emoji_text
from utils.rich_ui import *  # noqa: F403  (rich_send/rich_reply/rich_edit/rich_table/... )
from database import push_to_array, pull_from_array, set_fields, collection, user_sessions, db_task, remove_chat_assistant as db_remove_chat_assistant, get_top_chats
from thumbnails import get_thumb
from PIL import Image
import imageio
import cv2
from mutagen import File
from mutagen import MutagenError
import magic

logger = logging.getLogger(__name__)

# Global cache for admin status: (chat_id, user_id) -> (status, expires_at)
_admin_member_cache = {}


async def _build_top_groups_table(client) -> str:
    """Build the Top 10 Groups table sorted by song play count."""
    top_chats = await get_top_chats(10)
    if not top_chats:
        return ""

    rows = []
    for rank, (cid, count) in enumerate(top_chats, 1):
        try:
            chat_obj = await client.get_chat(cid)
            title = getattr(chat_obj, "title", None) or getattr(chat_obj, "first_name", None) or f"Chat {cid}"
            name_str = rich_esc(title)
        except Exception:
            name_str = f"<i>[ID: {rich_code(cid)}]</i>"
        rows.append((f"<b>#{rank}</b>", name_str, rich_code(count)))

    if not rows:
        return ""

    return (
        rich_heading(f"{EmojiTag.CROWN} ᴛᴏᴘ 10 ɢʀᴏᴜᴘs (sᴏɴɢs ᴘʟᴀʏᴇᴅ)", 2)
        + rich_table(["#", "ɢʀᴏᴜᴘ", "ᴘʟᴀʏs"], rows)
    )


def clean_alert(text: str) -> str:
    """Strip custom premium emoji tags and HTML for plain-text callback_query.answer toasts/alerts."""
    if not text:
        return ""
    clean = strip_custom_emoji_text(str(text))
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
    cached = _admin_member_cache.get(cache_key)
    if cached:
        status_value, expires_at = cached
        if now < expires_at:
            return _is_admin_member_status(status_value)
    try:
        chat_member = await client.get_chat_member(chat_id, user_id)
        status_value = _chat_type_value(chat_member.status)
        _admin_member_cache[cache_key] = (status_value, now + 60)
        return _is_admin_member_status(status_value)
    except Exception as e:
        logger.debug(f"[is_authorized] Failed to get chat member for ({chat_id}, {user_id}): {e}")
        return False
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
                        try:
                            await rich_reply(
                                update,
                                rich_note(Messages.ADMIN_UNKNOWN_USER),
                                ephemeral=True,
                                client=client,
                            )
                        except Exception as notify_error:
                            logger.debug(f"[admin_only] ADMIN_UNKNOWN_USER notice failed for message {reply_id}: {notify_error}")
                    return

                # --- Song-owner skip: whoever queued the current track may skip
                # it, admin or not (in-memory, no I/O). ---
                if command in ("skip", "cskip"):
                    target_id = chat_id
                    if command == "cskip":
                        try:
                            linked = (await client.get_chat(chat_id)).linked_chat
                            if linked:
                                target_id = linked.id
                        except Exception:
                            pass
                    song = state.playing.get(target_id)
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
                        try:
                            await rich_reply(
                                update,
                                rich_heading(f"{EmojiTag.LOCK} Permission Denied", 3)
                                + rich_note(Messages.ADMIN_RESTRICTED_CMD),
                                ephemeral=True,
                                client=client,
                            )
                        except Exception as notify_error:
                            logger.debug(f"[admin_only] ADMIN_RESTRICTED_CMD notice failed for message {reply_id}: {notify_error}")
                    return

                logger.info(f"User {user_id} authorized for {func.__name__}")
                return await func(client, update)

            except Exception as e:
                logger.error(f"Error checking admin status: {e}")
                if isinstance(update, CallbackQuery):
                    await update.answer(Messages.AUTH_FAILED, show_alert=True)
                else:
                    try:
                        await rich_reply(
                            update,
                            rich_note(Messages.AUTH_FAILED),
                            ephemeral=True,
                            quote=False,
                            client=client,
                        )
                    except Exception as notify_error:
                        logger.debug(f"[admin_only] AUTH_FAILED notice failed: {notify_error}")
                return
        return wrapper
    return decorator
async def is_active_chat(client, chat_id):  # noqa: F811
    return chat_id in state.active
async def add_active_chat(client, chat_id):  # noqa: F811
    state.active.add(chat_id)
async def remove_active_chat(client, chat_id):
    await state.deactivate(chat_id)
    db_task(db_remove_chat_assistant(chat_id))
    bot_id = getattr(client.me, "id", None) if client and getattr(client, "me", None) else "default"
    chat_dir = f"{ggg}/user_{bot_id}/{chat_id}"
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
async def _build_stats_content(client, bot_id, period: str = "24h"):
    """Build stats content for a given period.

    Args:
        client: Pyrogram client
        bot_id: Bot's user ID
        period: One of "24h", "week", "overall"
    """
    now = datetime.datetime.now()
    if period == "24h":
        time_threshold = now - datetime.timedelta(hours=24)
        period_label = "24h"
    elif period == "week":
        time_threshold = now - datetime.timedelta(weeks=1)
        period_label = "Week"
    else:  # overall
        time_threshold = None
        period_label = "Overall"

    user_data = await collection.find_one({"bot_id": bot_id})
    if not user_data:
        return rich_note(Messages.NO_OPERATIONAL_DATA)

    dates = user_data.get('dates', [])
    if time_threshold:
        play_count = len([d for d in dates if d >= time_threshold])
    else:
        play_count = len(dates)

    users = user_data.get('users', [])
    total_users = len(users)

    top_groups_table = await _build_top_groups_table(client)

    # For overall stats, we still limit detailed breakdown for large bots
    if total_users > 500 and period == "overall":
        return (
            rich_heading(f"{EmojiTag.STATS} Bot Statistics ({period_label})", 1)
            + rich_table(
                ["Metric", "Count"],
                [
                    (f"{EmojiTag.USER} Stored Users", rich_code(total_users)),
                    (f"{EmojiTag.MUSIC_NOTE} Songs Played ({period_label})", rich_code(play_count)),
                    (f"{EmojiTag.INFO} Detailed stats", rich_code("Skipped to avoid timeout")),
                ],
            )
            + top_groups_table
            + rich_note(
                f"{EmojiTag.BOLT} <b>Processed in:</b> {rich_code('0s')}\n"
                f"{EmojiTag.INFO} Per-chat breakdown skipped: too many stored "
                f"users to enumerate without timing out.\n"
                f"<b>{EmojiTag.MUSIC_NOTE} @{client.me.username} Performance Summary</b>"
            )
        )

    # Count chat types
    u = g = sg = c = a_chat = 0
    chat_type_cache = dict(user_data.get('chat_type_cache', {}))

    for i, chat_id in enumerate(users):
        try:
            chat_type = await get_cached_chat_type(client, bot_id, chat_id, chat_type_cache)

            if chat_type == enums.ChatType.PRIVATE:
                u += 1
            elif chat_type == enums.ChatType.GROUP:
                g += 1
            elif chat_type == enums.ChatType.SUPERGROUP:
                sg += 1
                try:
                    user_status = await client.get_chat_member(chat_id, bot_id)
                    if user_status.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
                        a_chat += 1
                except Exception as e:
                    logger.info(f"Admin check error: {e}")
            elif chat_type == enums.ChatType.CHANNEL:
                c += 1
        except Exception as e:
            logger.info(f"Error processing chat {chat_id}: {e}")

    return (
        rich_heading(f"{EmojiTag.STATS} Bot Statistics ({period_label})", 1)
        + rich_table(
            ["Metric", "Count"],
            [
                (f"{EmojiTag.USER} Private Chats", rich_code(u)),
                (f"{EmojiTag.USERS} Groups", rich_code(g)),
                (f"{EmojiTag.USERS} Super Groups", rich_code(sg)),
                (f"{EmojiTag.BROADCAST} Channels", rich_code(c)),
                (f"{EmojiTag.SHIELD} Admin Privileges", rich_code(a_chat)),
                (f"{EmojiTag.MUSIC_NOTE} Songs Played ({period_label})", rich_code(play_count)),
            ],
        )
        + top_groups_table
        + rich_note(
            f"<b>{EmojiTag.MUSIC_NOTE} @{client.me.username} Performance Summary</b>"
        )
    )


async def status(client, message):
    """Handles the /status command with song statistics"""
    async with RichDraft(
        client,
        message.chat.id,
        message_thread_id=getattr(message, "message_thread_id", None),
    ) as draft:
        await draft.update(rich_note(Messages.COLLECTING_STATS))

        # Check if called from a group/supergroup: show group-specific stats & connected channel
        if message.chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            chat_id = message.chat.id
            linked_chat = None
            try:
                chat_obj = await client.get_chat(chat_id)
                linked_chat = getattr(chat_obj, "linked_chat", None)
            except Exception as e:
                logger.debug(f"[status] Failed to fetch chat info for {chat_id}: {e}")

            if linked_chat:
                chan_title = rich_esc(getattr(linked_chat, "title", "Connected Channel"))
                username = getattr(linked_chat, "username", None)
                if username:
                    channel_info = f"{chan_title} (<code>@{username}</code>)"
                else:
                    channel_info = f"{chan_title} (<code>ID: {linked_chat.id}</code>)"
            else:
                channel_info = "<i>Not Connected</i>"

            try:
                ast_num, ast_userbot, _ = await get_assistant(chat_id)
                ast_info = assistant_info.get(ast_num, {})
                ast_name = ast_info.get("name") or (
                    getattr(ast_userbot.me, "first_name", f"Assistant {ast_num}")
                    if ast_userbot
                    else f"Assistant {ast_num}"
                )
                assistant_text = f"Assistant {ast_num} ({rich_esc(ast_name)})"
            except Exception:
                assistant_text = "Assistant 1"

            target_id = (
                linked_chat.id
                if (linked_chat and chat_id not in state.playing and linked_chat.id in state.playing)
                else chat_id
            )
            song = state.playing.get(target_id)
            if song:
                song_title = song.get("title", "Unknown")
                mode = song.get("mode", "audio")
                mode_label = f"{EmojiTag.MUSIC_NOTE} Audio" if mode == "audio" else f"{EmojiTag.PLAY} Video"
                stream_status = f"<b>{rich_esc(song_title)}</b> ({mode_label})"
            else:
                stream_status = "<i>No Active Stream</i>"

            queue_len = len(state.queues.get(chat_id, []))
            queue_status = f"{queue_len} track(s)" if queue_len > 0 else "Empty"
            autoplay_status = "Enabled" if state.is_autoplay_enabled(chat_id) else "Disabled"

            lang_code = await get_lang(chat_id)
            lang_meta = LANGUAGES.get(lang_code, {"name": lang_code, "flag": "🏳️"})
            lang_text = f"{lang_meta['flag']} {lang_code.upper()} — {rich_esc(lang_meta['name'])}"

            members_count = None
            try:
                members_count = await client.get_chat_members_count(chat_id)
            except Exception:
                pass

            rows = [
                (f"{EmojiTag.USERS} ɢʀᴏᴜᴘ ɴᴀᴍᴇ", rich_esc(message.chat.title or "This Group")),
                (f"{EmojiTag.KEY} ɢʀᴏᴜᴘ ɪᴅ", rich_code(chat_id)),
                (f"{EmojiTag.INFO} ᴄʜᴀᴛ ᴛʏᴘᴇ", rich_code(message.chat.type.name.capitalize())),
            ]
            if members_count:
                rows.append((f"{EmojiTag.USER} ᴍᴇᴍʙᴇʀs", rich_code(members_count)))
            rows.extend([
                (f"{EmojiTag.BROADCAST} ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴄʜᴀɴɴᴇʟ", channel_info),
                (f"{EmojiTag.HEADPHONES} ᴀssɪsᴛᴀɴᴛ", assistant_text),
                (f"{EmojiTag.MUSIC_NOTE} sᴛʀᴇᴀᴍ sᴛᴀᴛᴜs", stream_status),
                (f"{EmojiTag.QUEUE_ICON} ǫᴜᴇᴜᴇ", rich_code(queue_status)),
                (f"{EmojiTag.SETTINGS} ᴀᴜᴛᴏᴘʟᴀʏ", rich_code(autoplay_status)),
                (f"{EmojiTag.GLOBE} ʟᴀɴɢᴜᴀɢᴇ", lang_text),
            ])

            top_groups_table = await _build_top_groups_table(client)

            await draft.finish(
                rich_heading(f"{EmojiTag.STATS} ɢʀᴏᴜᴘ sᴛᴀᴛɪsᴛɪᴄs", 1)
                + rich_kv_table(rows)
                + top_groups_table
                + rich_note(f"<b>{EmojiTag.MUSIC_NOTE} @{client.me.username} Group Performance Summary</b>")
            )
            return

        # Default to 24h for initial load
        user_data = await collection.find_one({"bot_id": client.me.id})
        if user_data:
            content = await _build_stats_content(client, client.me.id, "24h")
            await draft.finish(content + Buttons.stats_markup())
        else:
            await draft.finish(rich_note(Messages.NO_OPERATIONAL_DATA))
