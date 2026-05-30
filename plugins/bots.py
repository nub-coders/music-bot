
import asyncio
import base64
import datetime
import logging
import os
import random
import re
import requests
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

from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall
from pytgcalls.types import AudioQuality, MediaStream, VideoQuality

from config import *
from tools import *
from youtube import handle_youtube, extract_video_id, format_duration
from tools import trim_title, join_call
from utils.message import Messages
from utils.lang import get_str, get_lang, set_lang, LANGUAGES, lang_list_text
from utils.button import Buttons
from utils.emoji import Emoji
from database import find_one, push_to_array, pull_from_array, set_fields, collection, user_sessions, db_task
from thumbnails import get_thumb

async def end(client, update):
    """Handle stream end event"""
    chat_id = update.chat_id
    logger.info(f"Stream ended in chat {chat_id}")
    await dend(clients['bot'], type('obj', (object,), {'chat': type('obj', (object,), {'id': chat_id})})(), chat_id)

async def hd_stream_closed_kicked(client, update):
    """Handle voice chat closed or kicked events"""
    chat_id = update.chat_id
    logger.info(f"Voice chat closed or kicked in chat {chat_id}")
    await remove_active_chat(clients['bot'], chat_id)
    if chat_id in playing:
        playing[chat_id].clear()
    if chat_id in queues:
        queues[chat_id].clear()

# Clients will be passed as parameter instead of imported
# Get the logger
logger = logging.getLogger("pyrogram")
session = clients["session"]
call_py = clients["call_py"]

_admin_member_cache: dict[tuple[int, int], tuple[str, float]] = {}


def _chat_type_value(chat_type):
    return getattr(chat_type, "value", chat_type)


def _chat_type_from_cache(chat_type_value):
    if not chat_type_value:
        return None
    try:
        return enums.ChatType(chat_type_value)
    except Exception:
        return chat_type_value


def _is_admin_member_status(status):
    status_value = _chat_type_value(status)
    return status_value in (
        ChatMemberStatus.OWNER.value,
        ChatMemberStatus.ADMINISTRATOR.value,
    )






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

                # --- Fast in-memory checks first (no network I/O) ---
                is_admin = user_id in get_admin_ids(f"{ggg}/admin.txt")
                is_owner = str(OWNER_ID) == str(user_id)
                is_sudo = user_id in SUDO

                is_auth_user = False
                chat_key = str(chat_id)
                if chat_key in AUTH:
                    is_auth_user = user_id in AUTH[chat_key]

                if not isinstance(update, CallbackQuery):
                    if command and str(command).endswith('del'):
                        is_auth_user = False

                is_authorized = is_admin or is_owner or is_sudo or is_auth_user

                # --- Song-owner skip check (in-memory, no I/O) ---
                is_song_owner_skip = False
                if command in ("skip", "cskip"):
                    _cid = update.message.chat.id if isinstance(update, CallbackQuery) else update.chat.id
                    song = playing.get(_cid)
                    if song and hasattr(song.get("by"), "id") and song["by"].id == user_id:
                        is_song_owner_skip = True

                # --- Short-circuit: skip network call if already authorized ---
                if is_authorized or is_song_owner_skip:
                    logger.info(f"User {user_id} authorized for {func.__name__} (fast-path)")
                    return await func(client, update)

                # --- Fallback: check Telegram group admin status (1 network call) ---
                cache_key = (chat_id, user_id)
                now = time.time()
                cached_member = _admin_member_cache.get(cache_key)
                if cached_member and cached_member[1] > now:
                    is_chat_admin = _is_admin_member_status(cached_member[0])
                else:
                    chat_member = await client.get_chat_member(chat_id, user_id)
                    status_value = _chat_type_value(chat_member.status)
                    _admin_member_cache[cache_key] = (status_value, now + 60)
                    is_chat_admin = _is_admin_member_status(status_value)

                if not is_chat_admin:
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



# Define the main bot client (app)
create_custom_filter = filters.create(lambda _, __, message: any(m.is_self for m in (message.new_chat_members if message.new_chat_members else [])))

# Auth handler

from PIL import Image, ImageDraw, ImageFont
# Add /queue command to show up to 20 items in queue as a photo with brown background
@Client.on_message(filters.command("queue"))
async def queue_command(client, message):
    chat_id = message.chat.id
    queue_list = queues.get(chat_id, [])
    items = queue_list[:20]
    if not items:
        return await message.reply(Messages.QUEUE_EMPTY, link_preview_options=None)

    # Build styled queue text
    text_lines = ["🎵 | ǫᴜᴇᴜᴇ (ᴍᴀx 20)\n"]
    for idx, item in enumerate(items, 1):
        title = item.get("title", "Unknown")
        duration = item.get("duration", "-")
        text_lines.append(f"{idx}. {title}  [{duration}]")
    text = "\n".join(text_lines)

    # Create dark gradient-style image
    width, height = 900, 650
    img = Image.new("RGB", (width, height), (15, 15, 30))  # deep dark indigo
    draw = ImageDraw.Draw(img)
    # Draw a subtle accent bar on the left
    for x in range(8):
        opacity = max(0, 255 - x * 30)
        draw.rectangle([(x, 0), (x, height)], fill=(138, 43, 226))
    # Font
    try:
        font_title = ImageFont.truetype("Poppins-Bold.ttf", 36)
        font_body  = ImageFont.truetype("Poppins-Regular.ttf", 28)
    except:
        font_title = ImageFont.load_default()
        font_body  = font_title
    # Title
    draw.text((30, 30), text_lines[0].strip(), fill=(200, 150, 255), font=font_title)
    # Body items
    y = 90
    for line in text_lines[1:]:
        draw.text((30, y), line, fill=(230, 230, 255), font=font_body)
        y += 40

    # Save to bytes
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    styled_caption = (
        "<u><b>🎵 | ᴄᴜʀʀᴇɴᴛ ǫᴜᴇᴜᴇ</b></u>\n"
        f"<blockquote expandable>\n"
        + "\n".join(
            f"<b>{idx}.</b> {item.get('title','Unknown')}  <code>[{item.get('duration','-')}]</code>"
            for idx, item in enumerate(items, 1)
        )
        + "\n</blockquote>"
    )
    await message.reply_photo(photo=buf, caption=styled_caption)



# Local helpers matching the (client, chat_id) pattern used throughout bots.py
# is_active_chat / add_active_chat use the set 'active' imported from tools via *
async def is_active_chat(client, chat_id):  # noqa: F811
    return chat_id in active

async def add_active_chat(client, chat_id):  # noqa: F811
    active.add(chat_id)



async def remove_active_chat(client, chat_id):
    active.discard(chat_id)
    chat_dir = f"{ggg}/user_{client.me.id}/{chat_id}"
    os.makedirs(chat_dir, exist_ok=True)
    clear_directory(chat_dir)



@Client.on_message(filters.command("tagall") & filters.group)
@admin_only()
async def mentionall(client, message):
    await message.delete()
    chat_id = message.chat.id
    direp = message.reply_to_message
    args = get_arg(message)

    # If no message or reply provided, use random message from TAGALL
    if not direp and not args:
        import random
        from tools import TAGALL
        args = random.choice(TAGALL)

    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if not chat_id in spam_chats:
            break
        usrnum += 1
        usrtxt += f"{usr.user.mention()}, "
        if usrnum == 5:
            if args:
                txt = f"<blockquote>{args}\n\n{usrtxt}</blockquote>"
                await client.send_message(chat_id, txt, link_preview_options=None)
            elif direp:
                await direp.reply(f"<blockquote>{usrtxt}</blockquote>", link_preview_options=None)
            await asyncio.sleep(5)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except:
        pass


@Client.on_message(filters.command(["seek", "seekback"]))
@admin_only()
async def seek_handler_func(client, message):
    try:
        await message.delete()
    except:
        pass
    # Check if user is banned using global variable
    if message.from_user.id in BLOCK:
        return

    try:
        # Get seek value from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await client.send_message(
                message.chat.id,
                Messages.SEEK_NO_ARGS, 
            link_preview_options=None)
            return

        try:
            seek_value = int(command_parts[1])
            if seek_value < 0:
                await client.send_message(
                    message.chat.id,
                    Messages.SEEK_NEGATIVE, 
                link_preview_options=None)
                return
        except ValueError:
            await client.send_message(
                message.chat.id,
                Messages.SEEK_INVALID, 
            link_preview_options=None)
            return

        # Check if there's a song playing
        if message.chat.id in playing and playing[message.chat.id]:
            current_song = playing[message.chat.id]
            duration_str = str(current_song['duration'])

            # Convert HH:MM:SS to total seconds
            duration_seconds = sum(
                int(x) * 60 ** i
                for i, x in enumerate(reversed(duration_str.split(":")))
            )

            # Get call client from main.py

            # Check if bot is actually streaming by fetching elapsed time
            if message.chat.id not in played:
                await client.send_message(
                    message.chat.id,
                    "Assistant is not streaming anything!", 
                link_preview_options=None)
                return

            played_in_seconds = int(time.time() - played[message.chat.id])

            # Check seek boundaries based on command
            command = command_parts[0].lower()
            if command == "/seek":
                # Check if seeking forward would exceed remaining duration
                remaining_duration = duration_seconds - played_in_seconds
                if seek_value > remaining_duration:
                    await client.send_message(
                        message.chat.id,
                        Messages.SEEK_BEYOND_REMAINING, 
                    link_preview_options=None)
                    return
                total_seek = seek_value + played_in_seconds
            else:  # seekback
                # Check if seeking back would exceed played duration
                if seek_value > played_in_seconds:
                    await client.send_message(
                        message.chat.id,
                        Messages.SEEK_BEYOND_PLAYED, 
                    link_preview_options=None)
                    return
                total_seek = played_in_seconds - seek_value

            # Set audio flags based on mode
            mode = current_song['mode']
            audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None

            # Seek to specified position
            to_seek = format_duration(total_seek)
            yt_link = current_song['yt_link']
            
            # Get stream URL (async-safe, thread-pooled)
            stream_url = await get_stream_url(yt_link)
            if not stream_url:
                stream_url = yt_link  # Fallback to original link
            
            await call_py.play(
                message.chat.id,
                MediaStream(
                    stream_url,
                    AudioQuality.STUDIO,
                VideoQuality.HD_720p,
                    video_flags=audio_flags,
                    ffmpeg_parameters=f"-ss {to_seek} -to {duration_str}"
                ),
            )

            # Update played time based on command
            if command == "/seek":
                played[message.chat.id] -= seek_value
            else:  # seekback
                played[message.chat.id] += seek_value

            await client.send_message(
                message.chat.id,
                f"Seeked to {to_seek}!\n\nʙʏ: {message.from_user.mention()}", 
            link_preview_options=None)
        else:
            await client.send_message(
                message.chat.id,
                "Assistant is not streaming anything!", 
            link_preview_options=None)
    except Exception as e:
        await client.send_message(
            message.chat.id,
            f"{Messages.ERROR_OCCURRED} {str(e)}", 
        link_preview_options=None)


@Client.on_message(filters.command("cancel") & filters.group)
@admin_only()
async def cancel_spam(client, message):
    if not message.chat.id in spam_chats:
        return await message.reply(Messages.NO_TAGALL, link_preview_options=None)
    else:
        try:
            spam_chats.remove(message.chat.id)
        except:
            pass
        return await message.reply(Messages.DISMISS_MENTION, link_preview_options=None)

@Client.on_message(filters.command("del") & filters.group)
@admin_only()
async def delete_message_handler(client, message):
    # Check if the message is a reply
    if message.reply_to_message:
        try:
            # Delete the replied message
            await message.reply_to_message.delete()
            # Optionally, delete the command message as well
            await message.delete()
        except MessageDeleteForbidden:
              pass
        except Exception as e:
            await message.reply(Messages.ERROR_DEL_MSG.format(str(e)), link_preview_options=None)
    else:
        await message.reply(Messages.REPLY_TO_DEL, link_preview_options=None)


@Client.on_message(filters.command("auth") & filters.group)
@admin_only()
async def auth_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id

    chat_id = message.chat.id

    # Use global AUTH variable and ensure chat exists
    if str(chat_id) not in AUTH:
        AUTH[str(chat_id)] = []

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if replied user is admin (use cache)
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.OWNER_AUTH_ALL, link_preview_options=None)

            # Check if user can be authorized
            if (replied_user_id != message.chat.id and
                not replied_message.from_user.is_self and
                not OWNER_ID == replied_user_id):

                # Check if user is already authorized in this chat using global AUTH
                if replied_user_id not in AUTH[str(chat_id)]:
                    AUTH[str(chat_id)].append(replied_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(user_sessions.update_one(
                        {"bot_id": client.me.id},
                        {"$set": {'auth_users': AUTH}},
                        upsert=True
                    ))
                    await message.reply(Messages.USER_AUTH.format(replied_user_id), link_preview_options=None)
                else:
                    await message.reply(Messages.USER_ALREADY_AUTH.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.CANT_AUTH_SELF, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_auth = int(command_parts[1])
                # Check if user is already authorized in this chat using global AUTH
                if user_id_to_auth not in AUTH[str(chat_id)]:
                    AUTH[str(chat_id)].append(user_id_to_auth)
                    # Update database to maintain persistence (low priority)
                    db_task(user_sessions.update_one(
                        {"bot_id": client.me.id},
                        {"$set": {'auth_users': AUTH}},
                        upsert=True
                    ))
                    await message.reply(Messages.USER_AUTH.format(user_id_to_auth), link_preview_options=None)
                else:
                    await message.reply(Messages.USER_ALREADY_AUTH.format(user_id_to_auth), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)

@Client.on_message(filters.command("unauth") & filters.group)
@admin_only()
async def unauth_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    chat_id = message.chat.id

    # Ensure chat exists in global AUTH
    if str(chat_id) not in AUTH:
        AUTH[str(chat_id)] = []

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if replied user is admin (use cache)
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.CANT_REMOVE_AUTH_OWNER, link_preview_options=None)

            # Check if user can be unauthorized using global AUTH
            if replied_user_id in AUTH[str(chat_id)]:
                AUTH[str(chat_id)].remove(replied_user_id)
                # Update database to maintain persistence (low priority)
                db_task(user_sessions.update_one(
                    {"bot_id": client.me.id},
                    {"$set": {'auth_users': AUTH}},
                    upsert=True
                ))
                await message.reply(Messages.USER_REMOVED_AUTH.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.USER_NOT_AUTH.format(replied_user_id), link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_unauth = int(command_parts[1])
                # Check if user is authorized in this chat using global AUTH
                if user_id_to_unauth in AUTH[str(chat_id)]:
                    AUTH[str(chat_id)].remove(user_id_to_unauth)
                    # Update database to maintain persistence (low priority)
                    db_task(user_sessions.update_one(
                        {"bot_id": client.me.id},
                        {"$set": {'auth_users': AUTH}},
                        upsert=True
                    ))
                    await message.reply(Messages.USER_REMOVED_AUTH.format(user_id_to_unauth), link_preview_options=None)
                else:
                    await message.reply(Messages.USER_NOT_AUTH.format(user_id_to_unauth), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)

@Client.on_message(filters.command("block"))
async def block_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    admin_ids = get_admin_ids(admin_file)
    is_admin = user_id in admin_ids

    # Check permissions using global SUDO variable
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in SUDO
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    # Check if the message is a reply
    if message.reply_to_message:
        replied_message = message.reply_to_message
        # If the replied message is from a user (and not from the bot itself)
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id
            admin_file = f"{ggg}/admin.txt"
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.OWNER_BLOCK_RESTRICT, link_preview_options=None)
            # Check if the replied user is the same as the current chat (group) id
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self and not OWNER_ID == replied_user_id:
                if replied_user_id not in BLOCK:
                    BLOCK.append(replied_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$push": {'busers': replied_user_id}},
                                        upsert=True))
                    await message.reply(Messages.USER_BLOCKED.format(replied_user_id), link_preview_options=None)
                else:
                   return await message.reply(Messages.USER_ALREADY_BLOCKED.format(replied_user_id), link_preview_options=None)

            else:
                await message.reply(Messages.CANT_BLOCK_SELF, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_block = int(command_parts[1])
                # Block the user with the provided user ID using global BLOCK
                if user_id_to_block not in BLOCK:
                    BLOCK.append(user_id_to_block)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$push": {'busers': user_id_to_block}},
                                        upsert=True
                                    ))
                    await message.reply(Messages.USER_BLOCKED.format(user_id_to_block), link_preview_options=None)
                else:
                   return await message.reply(Messages.USER_ALREADY_BLOCKED.format(user_id_to_block), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)

@Client.on_message(filters.command("reboot") & filters.private)
async def reboot_handler(client: Client, message: Message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    is_admin = user_id in get_admin_ids(admin_file)

    # Authorization check using global SUDO variable
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in SUDO
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    # Authorized: Reboot process
    await message.reply(Messages.REBOOTING, link_preview_options=None)
    os.system(f"kill -9 {os.getpid()}")  # Hard kill (optional after client.stop())


# ─── Language commands ─────────────────────────────────────────────────────────

@Client.on_message(filters.command(["setlang", "language"]) & filters.group)
@admin_only()
async def setlang_handler(client, message):
    """Set the language for this chat. Usage: /setlang <code>"""
    args = message.text.split()
    chat_id = message.chat.id

    if len(args) < 2:
        # Show usage + available languages
        text = (await get_str(chat_id, "LANG_USAGE")).format(
            list=lang_list_text()
        )
        return await message.reply(text, link_preview_options=None)

    code = args[1].lower().strip()

    if code not in LANGUAGES:
        text = (await get_str(chat_id, "LANG_INVALID")).format(
            list=lang_list_text()
        )
        return await message.reply(text, link_preview_options=None)

    current = await get_lang(chat_id)
    if current == code:
        text = (await get_str(chat_id, "LANG_ALREADY")).format(
            lang=LANGUAGES[code]["name"]
        )
        return await message.reply(text, link_preview_options=None)

    await set_lang(chat_id, code)
    text = (await get_str(chat_id, "LANG_SET")).format(
        lang=LANGUAGES[code]["name"],
        flag=LANGUAGES[code]["flag"],
    )
    await message.reply(text, link_preview_options=None)


@Client.on_message(filters.command("lang"))
async def lang_info_handler(client, message):
    """Show the current language and all available options."""
    chat_id = message.chat.id
    code = await get_lang(chat_id)
    meta = LANGUAGES.get(code, {"name": code, "flag": "🏳️"})
    text = (
        f"<u><b>🌐 | ʟᴀɴɢᴜᴀɢᴇ sᴇᴛᴛɪɴɢs</b></u>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ:</b> {meta['flag']} <code>{code}</code> — {meta['name']}\n\n"
        f"<b>ᴀᴠᴀɪʟᴀʙʟᴇ ʟᴀɴɢᴜᴀɢᴇs:</b>\n{lang_list_text()}\n\n"
        f"<i>ᴜsᴇ <code>/setlang &lt;code&gt;</code> ᴛᴏ ᴄʜᴀɴɢᴇ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</i>"
    )
    await message.reply(text, link_preview_options=None)


# ───────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("unblock"))
async def unblock_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    is_admin = user_id in get_admin_ids(admin_file)

    # Check permissions using global SUDO variable
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in SUDO
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    if message.reply_to_message:
        replied_message = message.reply_to_message
        replied_user_id = replied_message.from_user.id

        # Check if user is in blocklist using global BLOCK
        if replied_user_id in BLOCK:
            BLOCK.remove(replied_user_id)
            # Update database to maintain persistence (low priority)
            db_task(collection.update_one({"bot_id": client.me.id},
                                {"$pull": {'busers': replied_user_id}},
                                upsert=True))
            await message.reply(Messages.REMOVED_FROM_BLOCKLIST.format(replied_user_id), link_preview_options=None)
        else:
            return await message.reply(Messages.NOT_IN_BLOCKLIST.format(replied_user_id), link_preview_options=None)

    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if user is in blocklist using global BLOCK
                if target_user_id in BLOCK:
                    BLOCK.remove(target_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$pull": {'busers': target_user_id}},
                                        upsert=True))
                    await message.reply(Messages.REMOVED_FROM_BLOCKLIST.format(target_user_id), link_preview_options=None)
                else:
                    return await message.reply(Messages.NOT_IN_BLOCKLIST.format(target_user_id), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("sudolist"))
async def show_sudo_list(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    is_admin = user_id in get_admin_ids(admin_file)

    # Check permissions
    is_authorized = is_admin or str(OWNER_ID) == str(user_id)

    if not is_authorized:
        return await message.reply(Messages.PAID_OWNER_CMD, link_preview_options=None)
    try:
        # Get all users who have SUDOERS field
        users_data = await find_one(user_sessions, {"bot_id": client.me.id})
        sudo_users = users_data.get("SUDOERS", []) if users_data else []

        if not sudo_users:
            return await message.reply(Messages.NO_SUDO_USERS, link_preview_options=None)

        # Build the sudo list message
        sudo_list = ["**🔱 SUDO USERS LIST:**\n"]
        number = 1

        for user_id in sudo_users:
                try:
                    # Try to get user info from Telegram
                    user_info = await client.get_users(user_id)
                    user_mention = f"@{user_info.username}" if user_info.username else user_info.first_name
                    sudo_list.append(f"**{number}➤** {user_mention} [`{user_id}`]")
                except Exception:
                    # If can't get user info, just show the ID
                    sudo_list.append(f"**{number}➤** Unknown User [`{user_id}`]")
                number += 1

        # Add count at the bottom
        sudo_list.append(f"\n**Total SUDO Users:** `{number-1}`")

        # Send the message
        await message.reply("\n".join(sudo_list), link_preview_options=None)

    except Exception as e:
        await message.reply(Messages.ERR_FETCH_SUDO.format(str(e)), link_preview_options=None)


@Client.on_message(filters.command("addsudo"))
async def add_to_sudo(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    admin_ids = get_admin_ids(admin_file)
    is_admin = user_id in admin_ids

    is_authorized = is_admin or str(OWNER_ID) == str(user_id)

    if not is_authorized:
        return await message.reply(Messages.OWNER_CMD, link_preview_options=None)

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is already admin
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.ALREADY_OWNER, link_preview_options=None)

            # Check if trying to add self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = await find_one(user_sessions, {"bot_id": client.me.id})
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if replied_user_id not in sudoers:
                    asyncio.create_task(push_to_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", replied_user_id, upsert=True))
                    await message.reply(Messages.USER_ADDED_SUDO.format(replied_user_id), link_preview_options=None)
                    SUDO.append(replied_user_id)
                else:
                    await message.reply(Messages.USER_ALREADY_SUDO.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.CANT_SUDO_SELF, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is already admin
                if target_user_id in get_admin_ids(admin_file):
                    return await message.reply(Messages.ALREADY_OWNER, link_preview_options=None)

                # Get current sudo users
                users_data = await find_one(user_sessions, {"bot_id": client.me.id})
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if target_user_id not in sudoers:
                    asyncio.create_task(push_to_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", target_user_id, upsert=True))
                    await message.reply(Messages.USER_ADDED_SUDO.format(target_user_id), link_preview_options=None)
                    SUDO.append(target_user_id)
                else:
                    await message.reply(Messages.USER_ALREADY_SUDO.format(target_user_id), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)

@Client.on_message(filters.command("rmsudo"))
async def remove_from_sudo(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    admin_ids = get_admin_ids(admin_file)
    is_admin = user_id in admin_ids

    is_authorized = is_admin or (user_id == OWNER_ID)

    if not is_authorized:
        return await message.reply(Messages.OWNER_CMD, link_preview_options=None)

    # Handle reply to message
    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is an admin
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.CANT_REMOVE_OWNER_SUDO, link_preview_options=None)

            # Check if trying to remove self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = await find_one(user_sessions, {"bot_id": client.me.id})
                if not users_data:
                    return await message.reply(Messages.USER_NOT_IN_DB.format(replied_user_id), link_preview_options=None)
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if replied_user_id in sudoers:
                    asyncio.create_task(pull_from_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", replied_user_id))
                    await message.reply(Messages.USER_REMOVED_SUDO.format(replied_user_id), link_preview_options=None)
                    SUDO.remove(replied_user_id)
                else:
                    await message.reply(Messages.USER_NOT_IN_SUDO.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.CANT_REMOVE_SELF_SUDO, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is an admin
                if target_user_id in get_admin_ids(admin_file):
                    return await message.reply(Messages.CANT_REMOVE_OWNER_SUDO, link_preview_options=None)

                # Get current sudo users
                users_data = await find_one(user_sessions, {"bot_id": client.me.id})
                if not users_data:
                    return await message.reply(Messages.USER_NOT_IN_DB.format(target_user_id), link_preview_options=None)
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if target_user_id in sudoers:
                    asyncio.create_task(pull_from_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", target_user_id))
                    await message.reply(Messages.USER_REMOVED_SUDO.format(target_user_id), link_preview_options=None)
                    SUDO.remove(target_user_id)
                else:
                    await message.reply(Messages.USER_NOT_IN_SUDO.format(target_user_id), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)






from pyrogram.types import Chat
from pyrogram.errors import ChatAdminRequired

async def get_chat_member_count(client, chat_id):
    try:
        return await client.get_chat_members_count(chat_id)
    except Exception:
        return "Unknown"

async def send_log_message(client, log_group_id, message, is_private):
    try:
        if is_private:
            user = message.from_user
            log_text = (
                "📥 **New User Started Bot**\n\n"
                f"**User Details:**\n"
                f"• Name: {user.first_name}\n"
                f"• Username: @{user.username if user.username else 'None'}\n"
                f"• User ID: `{user.id}`\n"
                f"• Is Premium: {'Yes' if user.is_premium else 'No'}\n"
                f"• DC ID: {user.dc_id if user.dc_id else 'Unknown'}\n"
                f"• Language: {user.language_code if user.language_code else 'Unknown'}\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            chat = message.chat
            members_count = await get_chat_member_count(client, chat.id)
            try:
                invite_link = await client.export_chat_invite_link(chat.id)
            except Exception:
                invite_link = "Don't have invite right"
            log_text = (
                "📥 **Bot Added to New Group**\n\n"
                f"**Group Details:**\n"
                f"• Name: {chat.title}\n"
                f"• Chat ID: `{chat.id}`\n"
                f"• Type: {chat.type}\n"
                f"• Members: {members_count}\n"
                f"• Username: @{chat.username if chat.username else invite_link}\n"
                f"• Added By: {message.from_user.mention if message.from_user else 'Unknown'}\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        await asyncio.sleep(2)
        await client.send_message(
            chat_id=int(log_group_id),
            text=log_text,
            link_preview_options=None
        )
    except Exception as e:
        logger.info(f"Error sending log message: {str(e)}")



@Client.on_message(filters.command("start") | (filters.group & create_custom_filter))
async def user_client_start_handler(client, message):
    user_id = message.chat.id
    user_data = await find_one(collection, {"bot_id": client.me.id})
    is_private = message.chat.type == enums.ChatType.PRIVATE
    should_log = False
    if user_data:
        users = user_data.get('users', {})
        if not user_id in users:
            asyncio.create_task(push_to_array(collection, {"bot_id": client.me.id}, 'users', user_id, upsert=True))
            should_log = True
    else:
        asyncio.create_task(set_fields(collection, {"bot_id": client.me.id}, {'users': [user_id]}, upsert=True))
        should_log = True
    if should_log:
        log_group = LOGGER_ID

        if log_group:
          try:
            await send_log_message(
                client=client,
                log_group_id=log_group,
                message=message,
                is_private=is_private
            )
          except Exception as e:
             logger.info(e)

    # Process video ID if provided in start command
    command_args = message.text.split() if message.text else "hh".split()
    if len(command_args) > 1 and '_' in command_args[1]:
        try:
            loading = await message.reply(Messages.GETTING_STREAM_INFO, link_preview_options=None)
            # Split the argument using underscore and get the video ID
            _, video_id = command_args[1].split('_', 1)

            # Get video details
            video_info = await get_video_details(video_id)

            if isinstance(video_info, dict):
                # Format numbers
                views = format_number(video_info['view_count'])

                # Create formatted message
                logger.info(video_info['thumbnail'])
                await loading.delete()
                caption = (
                    f"📝 **Title:** {video_info['title']}\n\n"
                    f"⏱ **Duration:** {video_info['duration']}\n"
                    f"👁 **Views:** {views}\n"
                    f"📺 **Channel:** {video_info['channel_name']}\n"
                )

                # Create inline keyboard with YouTube button
                keyboard = Buttons.force_play_markup(video_info['video_url'])

                # Send thumbnail as photo with caption and keyboard
                try:
                    return await message.reply_photo(
                        photo=video_info['thumbnail'],
                        caption=caption,
                        reply_markup=keyboard,
                        reply_to_message_id=message.id
                    )
                except Exception as e:
                    return await message.reply_text(
                        f"❌ Failed to send photo: {str(e)}\n\n{caption}",
                        reply_markup=keyboard,
                        reply_to_message_id=message.id, 
                    link_preview_options=None)
            else:
                return await message.reply_text(
                    f"❌ Error: {video_info}",
                    reply_to_message_id=message.id, 
                link_preview_options=None)

        except Exception as e:
            return await message.reply_text(
                f"❌ Error processing video ID: {str(e)}",
                reply_to_message_id=message.id, 
            link_preview_options=None)

    # Handle logging

    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    editing = await message.reply(Messages.LOADING, link_preview_options=None)
    owner = await client.get_users(OWNER_ID)
    ow_id = owner.id if owner.username else None

    buttons_markup = Buttons.start_markup(client.me.username, ow_id, OWNER_ID, GROUP)
    import psutil
    from random import choice
    uptime = await get_readable_time((time.time() - StartTime))
    start = datetime.datetime.now()



    # Get system resources
    try:
        cpu_cores = psutil.cpu_count() or "N/A"
        ram = psutil.virtual_memory()
        ram_total = f"{ram.total / (1024**3):.2f} GB"
        disk = psutil.disk_usage('/')
        disk_total = f"{disk.total / (1024**3):.2f} GB"
    except Exception as e:
        cpu_cores = "N/A"
        ram_total = "N/A"
        disk_total = "N/A"
    try:
       photu = None
       async for photo in client.get_chat_photos(client.me.id):
           photu = photo.file_id

       # First try to get logo from user_dir
       logo_path_jpg = f"{user_dir}/logo.jpg"
       logo_path_mp4 = f"{user_dir}/logo.mp4"
       logo = None

       if os.path.exists(logo_path_mp4):
           logo = logo_path_mp4
       elif os.path.exists(logo_path_jpg):
           logo = logo_path_jpg
       else:
           logo = await gvarstatus(client.me.id, "LOGO") or (await client.download_media(client.me.photo.big_file_id, logo_path_jpg) if client.me.photo else "music.jpg")

       alive_logo = logo
       if type(logo) is bytes:
           alive_logo = logo_path_jpg
           with open(alive_logo, "wb") as fimage:
               fimage.write(base64.b64decode(logo))
           if 'video' in mime.from_file(alive_logo):
               alive_logo = rename_file(alive_logo, logo_path_mp4)




       greet_message = await gvarstatus(client.me.id, "WELCOME") or (
           "👋 <b>ʜᴇʏ {name}!</b>\n\n"
           "🎵 <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {botname}</b>\n\n"
           "<i>ᴀ ᴍᴜsɪᴄ ʙᴏᴛ ᴡɪᴛʜ ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ & ʜɪɢʜ-ǫᴜᴀʟɪᴛʏ sᴛʀᴇᴀᴍɪɴɢ.</i>\n\n"
           "<b><i>ᴜsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ.</i></b>"
       )

       send = client.send_video if alive_logo.endswith(".mp4") else client.send_photo
       await editing.delete()
       await send(
                user_id ,
                alive_logo,
                caption=await format_welcome_message(client, greet_message, user_id, message.from_user.mention() if message.chat.type == enums.ChatType.PRIVATE else (message.chat.title or ""))
,reply_markup=buttons_markup
            )
    except Exception as e:
      logger.info(e)

# Create an instance of the Update class
async def format_welcome_message(client, text, chat_id, user_or_chat_name):
    """Helper function to format welcome message with real data"""
    try:
        # Ensure user_or_chat_name is a string, even if None is passed
        user_or_chat_name = str(user_or_chat_name) if user_or_chat_name is not None else ""
        formatted_text = text
        formatted_text = formatted_text.replace("{name}", user_or_chat_name)
        formatted_text = formatted_text.replace("{id}", str(chat_id))
        formatted_text = formatted_text.replace("{botname}", client.me.mention())
        return formatted_text
    except Exception as e:
        logging.error(f"Error formatting welcome message: {str(e)}")
        return text  # Return original text if formatting fails


@Client.on_callback_query(filters.regex(r"commands_(.*)"))
async def commands_handler(client, callback_query):
    data = callback_query.data.split("_", 1)[1]          # Extract page name
    user_id = callback_query.from_user.id
    admin_file = f"{ggg}/admin.txt"

    # --- Permission check (owner / admin / sudo) ---
    admin_ids = get_admin_ids(f"{ggg}/admin.txt")
    is_admin = user_id in admin_ids or str(OWNER_ID) == str(user_id)
    owner = await client.get_users(OWNER_ID)
    ow_id = owner.id if owner.username else None

    # ---------- Command pages (text blocks) ----------
    playback_commands = (
        "<u><b>🎵 | ᴘʟᴀʏʙᴀᴄᴋ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /play  /vplay        — ǫᴜᴇᴜᴇ ʏᴏᴜᴛᴜʙᴇ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ\n"
        "‣ /queue               — sʜᴏᴡ ᴄᴜʀʀᴇɴᴛ ǫᴜᴇᴜᴇ (ᴜᴘ ᴛᴏ 20)\n"
        "‣ /playforce /vplayforce — ꜰᴏʀᴄᴇ ᴘʟᴀʏ (sᴋɪᴘ ᴄᴜʀʀᴇɴᴛ)\n"
        "‣ /cplay /cvplay       — ᴘʟᴀʏ ɪɴ ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ\n"
        "‣ /pause               — ᴘᴀᴜsᴇ sᴛʀᴇᴀᴍ\n"
        "‣ /resume              — ʀᴇsᴜᴍᴇ sᴛʀᴇᴀᴍ\n"
        "‣ /skip  /cskip        — ɴᴇxᴛ ᴛʀᴀᴄᴋ\n"
        "‣ /end  /cend          — sᴛᴏᴘ & ᴄʟᴇᴀʀ ǫᴜᴇᴜᴇ\n"
        "‣ /seek &lt;sec&gt;    — ᴊᴜᴍᴘ ꜰᴏʀᴡᴀʀᴅ\n"
        "‣ /seekback &lt;sec&gt; — ᴊᴜᴍᴘ ʙᴀᴄᴋᴡᴀʀᴅ\n"
        "‣ /loop &lt;1-20&gt;   — ʀᴇᴘᴇᴀᴛ ᴄᴜʀʀᴇɴᴛ sᴏɴɢ\n"
        "</blockquote>"
    )

    auth_commands = (
        "<u><b>🔐 | ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /auth &lt;reply|id&gt;   — ᴀʟʟᴏᴡ ᴜsᴇʀ ᴛᴏ ᴜsᴇ ᴘʟᴀʏᴇʀ\n"
        "‣ /unauth &lt;reply|id&gt; — ʀᴇᴍᴏᴠᴇ ᴛʜᴀᴛ ᴘᴇʀᴍɪssɪᴏɴ\n"
        "‣ /authlist              — ʟɪsᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs\n"
        "</blockquote>"
    )

    blocklist_commands = (
        "<u><b>🚫 | ʙʟᴏᴄᴋʟɪsᴛ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /block &lt;reply|id&gt;   — ʙʟᴏᴄᴋ ᴜsᴇʀ ꜰʀᴏᴍ ʙᴏᴛ\n"
        "‣ /unblock &lt;reply|id&gt; — ᴜɴʙʟᴏᴄᴋ ᴜsᴇʀ\n"
        "‣ /blocklist              — ᴠɪᴇᴡ ʙʟᴏᴄᴋᴇᴅ ʟɪsᴛ\n"
        "</blockquote>"
    )

    sudo_commands = (
        "<u><b>🔑 | sᴜᴅᴏ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /addsudo &lt;reply|id&gt; — ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ\n"
        "‣ /rmsudo &lt;reply|id&gt;  — ʀᴇᴍᴏᴠᴇ sᴜᴅᴏ ᴜsᴇʀ\n"
        "‣ /sudolist               — ʟɪsᴛ sᴜᴅᴏ ᴜsᴇʀs\n"
        "</blockquote>"
    )

    broadcast_commands = (
        "<u><b>📢 | ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /broadcast  — ᴄᴏᴘʏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴅɪᴀʟᴏɢs\n"
        "‣ /fbroadcast — ꜰᴏʀᴡᴀʀᴅ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴅɪᴀʟᴏɢs\n"
        "</blockquote>"
    )

    tools_commands = (
        "<u><b>🛠️ | ᴛᴏᴏʟs ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /del    — ᴅᴇʟᴇᴛᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ\n"
        "‣ /tagall — ᴍᴇɴᴛɪᴏɴ ᴀʟʟ ᴍᴇᴍʙᴇʀs\n"
        "‣ /cancel — ᴀʙᴏʀᴛ ʀᴜɴɴɪɴɢ ᴛᴀɢᴀʟʟ\n"
        "‣ /powers — sʜᴏᴡ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs\n"
        "</blockquote>"
    )

    kang_commands = (
        "<u><b>🎨 | sᴛɪᴄᴋᴇʀ & ᴍᴇᴍᴇ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /kang         — ᴄʟᴏɴᴇ sᴛɪᴄᴋᴇʀ/ᴘʜᴏᴛᴏ ᴛᴏ ʏᴏᴜʀ ᴘᴀᴄᴋ\n"
        "‣ /mmf &lt;text&gt; — ᴡʀɪᴛᴇ ᴛᴇxᴛ ᴏɴ ɪᴍᴀɢᴇ/sᴛɪᴄᴋᴇʀ\n"
        "</blockquote>"
    )

    status_commands = (
        "<u><b>📊 | sᴛᴀᴛᴜs & ɪɴꜰᴏ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /ping  — ʟᴀᴛᴇɴᴄʏ & ᴜᴘᴛɪᴍᴇ\n"
        "‣ /stats — ʙᴏᴛ ᴜsᴀɢᴇ sᴛᴀᴛs\n"
        "‣ /ac    — ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs\n"
        "‣ /about — ᴜsᴇʀ / ɢʀᴏᴜᴘ / ᴄʜᴀɴɴᴇʟ ɪɴꜰᴏ\n"
        "</blockquote>"
    )

    owner_commands = (
        "<u><b>⚙️ | ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /reboot       — ʀᴇsᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        "‣ /setwelcome   — sᴇᴛ ᴄᴜsᴛᴏᴍ /start ᴍᴇssᴀɢᴇ\n"
        "‣ /resetwelcome — ʀᴇsᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ & ʟᴏɢᴏ\n"
        "</blockquote>"
    )

    category_pages = {
        "playback": playback_commands,
        "auth": auth_commands,
        "blocklist": blocklist_commands,
        "sudo": sudo_commands,
        "broadcast": broadcast_commands,
        "tools": tools_commands,
        "kang": kang_commands,
        "status": status_commands,
    }

    # ---------- Navigation buttons ----------
    # --- Category Buttons replaced by Buttons.HELP_HOME ---


    back_markup = Buttons.BACK


    # ---------- Routing ----------
    if data == "all":
        await callback_query.answer()
        await callback_query.message.edit_caption(
            caption="<u><b>📜 | sᴇʟᴇᴄᴛ ᴀ ᴄᴏᴍᴍᴀɴᴅ ᴄᴀᴛᴇɢᴏʀʏ</b></u>",
            reply_markup=Buttons.HELP_HOME,
        )
    elif data in category_pages:
        await callback_query.answer()
        await callback_query.message.edit_caption(
            caption=category_pages[data],
            reply_markup=back_markup,
        )
    elif data == "owner":
        await callback_query.answer()
        await callback_query.message.edit_caption(caption=owner_commands, reply_markup=back_markup)
    elif data == "back":
            await callback_query.answer()
            name = callback_query.from_user.mention()
            botname = client.me.mention()
            greet_message = await gvarstatus(client.me.id, "WELCOME") or (
                "👋 <b>ʜᴇʏ {name}!</b>\n\n"
                "🎵 <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {botname}</b>\n\n"
                "<i>ᴀ ᴍᴜsɪᴄ ʙᴏᴛ ᴡɪᴛʜ ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ & ʜɪɢʜ-ǫᴜᴀʟɪᴛʏ sᴛʀᴇᴀᴍɪɴɢ.</i>\n\n"
                "<b><i>ᴜsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ.</i></b>"
            )
            greet_message = await format_welcome_message(client, greet_message, user_id, callback_query.from_user.mention())
            buttons_markup = Buttons.start_markup(client.me.username, ow_id, OWNER_ID, GROUP)
            await callback_query.message.edit_caption(
                caption=greet_message,
                reply_markup=buttons_markup,
            )



@Client.on_message(filters.command("blocklist"))
async def blocklist_handler(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    users_data = await find_one(user_sessions, {"bot_id": client.me.id})
    sudoers = users_data.get("SUDOERS", []) if users_data else []

    is_admin = False
    if os.path.exists(admin_file):
        admin_ids = get_admin_ids(admin_file)
        is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in sudoers
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    # Check for admin or owner


    # Fetch blocklist from the database
    user_data = await find_one(collection, {"bot_id": client.me.id})
    if not user_data:
        return await message.reply(Messages.NO_BLOCKLIST, link_preview_options=None)

    blocked_users = user_data.get('busers', [])
    if not blocked_users:
        return await message.reply(Messages.NO_USERS_BLOCKED, link_preview_options=None)

    blocklist_text = "Blocked Users:\n" + "\n".join([f"- `{user_id}`" for user_id in blocked_users])
    await message.reply_text(blocklist_text, link_preview_options=None)


from pytgcalls import filters as call_filters

def currently_playing(client, message):
    try:
        if len(queues[message.chat.id]) <=1:
           return False
        return True
    except KeyError:
        True



# Import join_call function from tools.py

async def dend(client, update, channel_id= None):
    # Enhanced input validation
    try:
        chat_id = int(channel_id or update.chat.id)
        logger.debug(f"Dend processing - Validated chat_id: {chat_id} (type: {type(chat_id)})")
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Invalid chat_id: {e}. channel_id: {channel_id}, update.chat.id: {getattr(update.chat, 'id', 'N/A')}")
        return
    try:
        chat_id = int(channel_id or update.chat.id)  # Ensure integer chat_id
        if chat_id in queues and queues[chat_id]:
            next_song = queues[chat_id].pop(0)
            playing[chat_id] = next_song
            await join_call(
                next_song['message'],
                next_song['title'],
                next_song['yt_link'],
                next_song['chat'],
                next_song['by'],
                next_song['duration'],
                next_song['mode'],
                next_song['thumb'],
                next_song.get('stream_url'),
                yt_task=next_song.get('_yt_task'),
            )
        else:
            logger.info(f"Song queue for chat {chat_id} is empty.")
            await client.leave_call(chat_id)
            await remove_active_chat(client, chat_id)
            if chat_id in playing:
                playing[chat_id].clear()
    except Exception as e:
        logger.error(f"Error in dend function: {e}")


from PIL import Image
import imageio
import cv2
from pyrogram.raw.types import DocumentAttributeVideo, DocumentAttributeAudio


def generate_thumbnail(video_path, thumb_path):
    try:
        reader = imageio.get_reader(video_path)
        frame = reader.get_data(0)
        image = Image.fromarray(frame)
        image.thumbnail((320, 320))
        image.save(thumb_path, "JPEG")
        return thumb_path
    except Exception as e:
        # Fallback to black thumbnail
        Image.new('RGB', (320, 320), (0, 0, 0)).save(thumb_path, "JPEG")
        return thumb_path
# Play handler function




# Modified media download with progress
async def download_media_with_progress(client, msg, media_msg, type_of):
    start_time = time.time()
    filename = getattr(media_msg, 'file_name', 'file')
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}/{msg.chat.id}"
    os.makedirs(user_dir, exist_ok=True)
    try:
        file_path = await client.download_media(media_msg,file_name=f"{user_dir}/",
            progress=progress_bar,
            progress_args=(client, msg, type_of, filename, start_time))
        return file_path
    except Exception as e:
        print(f"Download error: {e}")
        return None


# Modified progress bar with error handling
async def progress_bar(current, total, client, msg, type_of, filename, start_time):
    if total == 0:
        return

    try:
            progress_percent = current * 100 / total
            progress_message = f"{type_of} {filename}: {progress_percent:.2f}%\n"

            # Progress bar calculation
            progress_bar_length = 20
            num_ticks = int(progress_percent / (100 / progress_bar_length))
            progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

            # Speed calculation
            elapsed_time = time.time() - start_time
            speed = current / (elapsed_time * 1024 * 1024) if elapsed_time > 0 else 0

            # Time remaining calculation
            time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

            # Format message
            progress_message += (
                f"Speed: {speed:.2f} MB/s\n"
                f"Time left: {time_left:.2f}s\n"
                f"Size: {current/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n"
                f"[{progress_bar_text}]"
            )

            # Edit message with exponential backoff
            try:
              if random.choices([True, False], weights=[1, 20])[0]:
                await msg.edit(progress_message)
            except Exception as e:
                print(f"Progress update error: {e}")

    except Exception as e:
        print(f"Progress bar error: {e}")


import os
import cv2
from mutagen import File
from mutagen import MutagenError

def with_opencv(filename):
    # List of common audio file extensions
    audio_extensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.mp4', '.wma']
    file_ext = os.path.splitext(filename)[1].lower()

    # Handle audio files with mutagen
    if file_ext in audio_extensions:
        try:
            audio = File(filename)
            if audio is not None and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                duration = audio.info.length
                return int(duration)
            else:
                return 0
        except MutagenError:
            return 0
    # Handle video files with OpenCV
    else:
        video = cv2.VideoCapture(filename)
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps else 0
        video.release()
        return int(duration)
# Example usage
# duration = get_media_duration('path/to/your/media/file.ogg')
@Client.on_message(filters.command(["play", "vplay", "playforce", "vplayforce", "cplay", "cvplay", "cplayforce", "cvplayforce"]))
async def play_handler_func(client, message):
    # ── Speed tracking: start the clock the moment we enter this handler ──
    _query = message.text.split(" ", 1)[1].strip() if len(message.text.split(" ", 1)) > 1 else "<media reply>"
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    by = message.from_user
    try:
        await message.delete()
    except:
        pass

    # Check if user is banned using global BLOCK variable
    if message.from_user.id in BLOCK:
        return

    command = message.command[0].lower()
    mode = "video" if command.startswith("v") or command.startswith("cv") else "audio"
    force_play = command.endswith("force")
    channel_mode = command.startswith("c")

    # Check if the command is sent in a group
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply(Messages.GROUP_ONLY, link_preview_options=None)
        return

    # Get the bot username and retrieve the session client ID from connector
    youtube_link = None
    input_text = message.text.split(" ", 1)

    # Determine if we need channel mode
    chat = message.chat
    target_chat_id = message.chat.id
    # For channel commands, check for linked channel
    if channel_mode:
        linked_chat = (await client.get_chat(message.chat.id)).linked_chat
        if not linked_chat:
            await message.reply(Messages.NO_LINKED_CHANNEL, link_preview_options=None)
            return
        target_chat_id = linked_chat.id

    # Check queue for the target chat
    current_queue = len(queues.get(target_chat_id, [])) if queues else 0

    massage = await message.reply(Messages.BOLT, link_preview_options=None)
    # Set target chat as active based on channel mode or not
    is_active = await is_active_chat(client, target_chat_id)
    await add_active_chat(client, target_chat_id)

    youtube_link = None
    media_info = {}
    track_id = None
    _yt_task = None
    
    # Initialize title with a safe default to prevent unbound variable issues
    title = trim_title("Unknown Media")

    # Check if replied to media message
    if message.reply_to_message and message.reply_to_message.media:
        media_msg = message.reply_to_message
        media_type = None
        duration = 0
        thumbnail = None

        # Video handling
        if media_msg.video:
            media = media_msg.video
            media_type = "video"
            title = trim_title(media.file_name or "Telegram Video")
            duration = media.duration
            if media.thumbs:
                thumbnail = await client.download_media(media.thumbs[0].file_id)

        # Audio handling
        elif media_msg.audio:
            media = media_msg.audio
            media_type = "audio"
            title = trim_title(media.title or "Telegram Audio")
            duration = media.duration
            if media.thumbs:
                thumbnail = await client.download_media(media.thumbs[0].file_id)

        # Voice message handling
        elif media_msg.voice:
            media = media_msg.voice
            media_type = "voice"
            title = trim_title("Voice Message")
            duration = media.duration

        # Video note handling
        elif media_msg.video_note:
            media = media_msg.video_note
            media_type = "video_note"
            title = trim_title("Video Note")
            duration = media.duration
            if media.thumbs:
                thumbnail = await client.download_media(media.thumbs[0].file_id)
        elif media_msg.document:
            doc = media_msg.document
            media = media_msg.document
    # In Pyrogram, check the mime_type directly
            if doc.mime_type:
                if doc.mime_type.startswith("video/"):
                    media_type = "video"
                    title = trim_title(doc.file_name or "Telegram Video")
                    duration = getattr(doc, 'duration', 0)  # duration might not always be available
            elif doc.mime_type.startswith("audio/"):
                     media_type = "audio"
                     title = trim_title(doc.file_name or "Telegram Audio")
                     duration = getattr(doc, 'duration', 0)


            if media_type and doc.thumbs:
                thumbnail = await client.download_media(doc.thumbs[0].file_id,f"{user_dir}/")
        else:
            await massage.edit(Messages.UNSUPPORTED_MEDIA)
            return await remove_active_chat(client, target_chat_id)
        if not media_type:
            await massage.edit(Messages.UNSUPPORTED_MEDIA)
            return await remove_active_chat(client, target_chat_id)
        # For media messages
        youtube_link = await download_media_with_progress(
            client,
            massage,
            message.reply_to_message,
            "Media"
        )
        stream_url = None

        # Generate thumbnail if missing
        if not thumbnail and media_type in ["video", "video_note"]:
            try:
                thumbnail = await asyncio.to_thread(generate_thumbnail, youtube_link, f'{user_dir}/thumb.png')
            except Exception as e:
                print(e)
                thumbnail = None
        # Format duration
        if not duration or duration <=0:
            duration = await asyncio.to_thread(with_opencv, youtube_link)
        duration = format_duration(int(duration))
        media_info = {
            'title': title,
            'duration': duration,
            'thumbnail': thumbnail,
            'file_id': media.file_id,
            'media_type': media_type,
            'url': youtube_link
        }
    elif len(input_text) == 2:
        search_query = input_text[1]
        import uuid as _uuid
        track_id = str(_uuid.uuid4())

        # Placeholder values — join_call will wait for the task to resolve
        title = trim_title(search_query[:25])
        duration = None
        youtube_link = None
        thumbnail = None
        channel_name = None
        views = None
        video_id = None
        stream_url = None

        _yt_task = asyncio.create_task(handle_youtube(search_query))
        _yt_task.add_done_callback(
            lambda t: t.exception() if not t.cancelled() else None
        )
    else:
        try:
            await massage.edit(f"{Messages.NO_QUERY_GIVEN}\n`/play query`")
            return await remove_active_chat(client, target_chat_id)
        except:
            return

    # Start thumbnail generation in the background so the voice join is not blocked.
    # join_call will await the task only after streaming is already live.
    if media_info:
        thumb = asyncio.create_task(
            get_thumb(
                media_info['title'],
                media_info['duration'],
                media_info['thumbnail'],
                None,
                None,
                None,
            )
        )
    else:
        # join_call will create the thumb task once yt_task resolves
        thumb = None
    if thumb:
        thumb.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
    bot_username = client.me.username

    # Retrieve the session client from the clients dictionary

    # Join the group (same for both regular and channel mode)
    if message.chat.username:
        # Public group
        try:
            try:
                joined_chat = await session.get_chat(message.chat.username)
            except:
                joined_chat = await session.join_chat(message.chat.username)
        except (InviteHashExpired, ChannelPrivate):
            await massage.edit(f"Assistant is banned in this chat.\n\nPlease unban {session.me.username or session.me.id}")
            return await remove_active_chat(client, target_chat_id)
        except Exception as e:
            await massage.edit(f"Failed to join the group. Error: {e}")
            return await remove_active_chat(client, target_chat_id)
    else:
        # Private group — try to get/join without relying on privileges check.
        # Pyrogram often returns privileges=None for admins even when permissions
        # ARE granted, so we never pre-reject. We try directly and let Telegram's
        # API raise an error if something is actually missing.
        bot_member = await client.get_chat_member(message.chat.id, client.me.id)
        is_admin_or_owner = bot_member.status in (
            ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
        )

        # Step 1: Maybe the session is already a member — no join needed.
        try:
            joined_chat = await session.get_chat(message.chat.id)
            logger.info(f"[play] Session already in private group {message.chat.id}")
        except Exception:
            # Step 2: Not a member yet. Try to export invite link and join.
            if not is_admin_or_owner:
                await massage.edit(Messages.NEED_INVITE_PERMISSION)
                return await remove_active_chat(client, target_chat_id)
            try:
                invite_link = await client.export_chat_invite_link(message.chat.id)
                joined_chat = await session.join_chat(invite_link)
                logger.info(f"[play] Session joined private group {message.chat.id} via invite link")
            except (InviteHashExpired, ChannelPrivate):
                await massage.edit(
                    f"Assistant is banned in this chat.\n\nPlease unban "
                    f"{session.me.mention()}\nuser id: {session.me.id}"
                )
                return await remove_active_chat(client, target_chat_id)
            except Exception as e:
                # If Telegram rejects due to missing invite permission, tell the user
                err_str = str(e).lower()
                if "chat_admin_required" in err_str or "invite" in err_str or "forbidden" in err_str:
                    await massage.edit(Messages.NEED_INVITE_PERMISSION)
                else:
                    await massage.edit(f"Failed to join the group. Error: {e}")
                return await remove_active_chat(client, target_chat_id)


    # Set the target chat based on whether it's channel mode or not
    target_chat = None
    linked_chat = None
    if channel_mode:
        # For channel mode, use the linked chat
        linked_chat = (await session.get_chat(message.chat.id)).linked_chat
        if not linked_chat:
            await massage.edit(Messages.LINKED_CHANNEL_ERROR)
            return await remove_active_chat(client, target_chat_id)
        target_chat = linked_chat
    else:
        # For regular mode, use the joined chat
        target_chat = joined_chat

    await put_queue(
        massage,
        trim_title(title),
        client,
        youtube_link,
        target_chat,
        by,
        duration,
        mode,
        thumb,
        force_play,
        stream_url,
        track_id=track_id,
        yt_task=_yt_task,
    )
    if is_active and not force_play:
                position = len(queues.get(message.chat.id)) if queues.get(target_chat.id) else 1
                keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▷", callback_data=f"{'c' if channel_mode else ''}resume", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton("II", callback_data=f"{'c' if channel_mode else ''}pause", style=ButtonStyle.DEFAULT),
                InlineKeyboardButton("‣‣I", callback_data=f"{'c' if channel_mode else ''}skip", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("▢", callback_data=f"{'c' if channel_mode else ''}end", style=ButtonStyle.DANGER),
            ],
        [
            InlineKeyboardButton(
                text="✖ Close",
                callback_data="close",
                style=ButtonStyle.DANGER
            )
        ],
        ])
                await client.send_message(message.chat.id, Messages.QUEUE[int(11)].format(mode, f"[{trim_title(title)}](https://t.me/{client.me.username}?start=vidid_{extract_video_id(youtube_link)})" if not os.path.exists(youtube_link) else trim_title(title), duration, position), reply_markup=keyboard,link_preview_options=None)
                try:
                   await message.delete()
                except:
                   pass


    else:
      await dend(client, massage, target_chat.id if channel_mode else None)
    await message.delete()



from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# YouTube functions removed - using imports from youtube.py module



async def put_queue(
    message,
    title,
    client,
    yt_link,
    chat,
    by,
    duration,
    audio_flags,
    thumb,
    forceplay=False,
    stream_url=None,
    track_id=None,
    yt_task=None,
):
    try:
        duration_in_seconds = (time_to_seconds(duration) - 3) if duration else 0
    except Exception:
        duration_in_seconds = 0
    put = {
        "message": message,
        "title": trim_title(title),
        "duration": duration,
        "mode": audio_flags,
        "yt_link": yt_link,
        "chat": chat,
        "by": by,
        "session": client,
        "thumb": thumb,
        "stream_url": stream_url,
        "_track_id": track_id,
        "_yt_task": yt_task,
    }
    if forceplay:
        check = queues.get(chat.id)
        if check:
            queues[chat.id].insert(0, put)
        else:
            queues[chat.id] = []
            queues[chat.id].append(put)
    else:
        check = queues.get(chat.id)

        if not check:
           queues[chat.id] = []
        queues[chat.id].append(put)

def set_gvar(user_id, key, value):
    set_user_data(user_id, key, value)

async def get_user_data(user_id, key):
    user_data = await user_sessions.find_one({"bot_id": user_id})
    if user_data and key in user_data:
        return user_data[key]
    return None

def set_user_data(user_id, key, value):
    db_task(user_sessions.update_one({"bot_id": user_id}, {"$set": {key: value}}, upsert=True))

async def gvarstatus(user_id, key):
    return await get_user_data(user_id, key)

def unset_user_data(user_id, key):
    db_task(user_sessions.update_one({"bot_id": user_id}, {"$unset": {key: ''}}, upsert=True))


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
import magic

mime = magic.Magic(mime=True)


import psutil
import os
StartTime = time.time()
async def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += time_list.pop() + ", "

    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time








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
    cached_chat_type = _chat_type_from_cache(chat_type_cache.get(chat_id_key))
    if cached_chat_type:
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
    Man = await message.reply_text(Messages.COLLECTING_STATS, link_preview_options=None)
    start = datetime.datetime.now()
    u = g = sg = c = a_chat = play_count = 0
    user_data = await find_one(collection, {"bot_id": client.me.id})

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
            await Man.edit_text(
                f"<b>📊 Comprehensive Bot Statistics</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"⏱ <b>Processed in:</b> <code>0s</code>\n\n"
                f"✦ <b>Stored Users:</b> <code>{total_users}</code>\n"
                f"✦ <b>Detailed stats:</b> <code>Skipped to avoid timeout</code>\n"
                f"✦ <b>Songs Played (24h):</b> <code>{play_count}</code>\n\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🎶 @{client.me.username} Performance Summary</b>"
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
<b>🔍 Collecting Stats ({min(i+1, total_users)}/{total_users})</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
✦ <b>Private:</b> <code>{u}</code>
✦ <b>Groups:</b> <code>{g}</code>
✦ <b>Super Groups:</b> <code>{sg}</code>
✦ <b>Channels:</b> <code>{c}</code>
✦ <b>Admin Positions:</b> <code>{a_chat}</code>
✦ <b>Songs Played (24h):</b> <code>{play_count}</code>
"""
                    await Man.edit_text(progress_msg)

            except Exception as e:
                logger.info(f"Error processing chat {chat_id}: {e}")

        end = datetime.datetime.now()
        ms = (end - start).seconds

        final_stats = f"""
<b>📊 Comprehensive Bot Statistics</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
⏱ <b>Processed in:</b> <code>{ms}s</code>

✦ <b>Private Chats:</b> <code>{u}</code>
✦ <b>Groups:</b> <code>{g}</code>
✦ <b>Super Groups:</b> <code>{sg}</code>
✦ <b>Channels:</b> <code>{c}</code>
✦ <b>Admin Privileges:</b> <code>{a_chat}</code>
✦ <b>Songs Played (24h):</b> <code>{play_count}</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>🎶 @{client.me.username} Performance Summary</b>
"""
        await Man.edit_text(final_stats)

    else:
        await Man.edit_text(Messages.NO_OPERATIONAL_DATA)


@Client.on_callback_query(filters.regex("^(end|cend)$"))
@admin_only()
async def button_end_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_END_SESSION, show_alert=True)
        return

    try:
        bot_username = client.me.username

        # Determine the chat_id based on whether "cend" is used
        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cend"
            else callback_query.message.chat.id
        )

        is_active = await is_active_chat(client, chat_id)
        if is_active:
            # Clear the song queue and end the session
            await remove_active_chat(client, chat_id)
            queues.pop(chat_id, None)
            try:
                await call_py.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")
            
            await callback_query.message.reply(
                f"QUEUE CLEARED\nStreaming stopped\nRequested by: {callback_query.from_user.mention()}", 
            link_preview_options=None)
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")
            
            playing.pop(chat_id, None)
            
            await callback_query.answer(Messages.STREAM_ENDED, show_alert=False)
        else:
            await remove_active_chat(client, chat_id)
            try:
                await call_py.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")
            
            await callback_query.message.reply(
                Messages.NO_STREAM, 
            link_preview_options=None)
            playing.pop(chat_id, None)
            
            await callback_query.answer(Messages.NO_ACTIVE_STREAM, show_alert=False)
    except NotInCallError:
        await remove_active_chat(client, chat_id)
        playing.pop(chat_id, None)
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in end button handler: {e}")
        await callback_query.answer(f"Error: {str(e)[:100]}", show_alert=True)


@Client.on_message(filters.command("end"))
@admin_only()
async def end_handler_func(client, message):
  try:
         await message.delete()
  except:
         pass
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   bot_username = client.me.username
   is_active = await is_active_chat(client, message.chat.id)
   if is_active:
       await remove_active_chat(client, message.chat.id)
       queues.pop(message.chat.id, None)
       await client.send_message(message.chat.id,
f"QUEUE CLEARED\nStreaming stopped\nRequested by: {message.from_user.mention()}", 
            link_preview_options=None)
       await call_py.leave_call(message.chat.id)
       playing.pop(message.chat.id, None)
   else:
     await client.send_message(message.chat.id, Messages.NO_STREAM, 
link_preview_options=None)
     await remove_active_chat(client, message.chat.id)
     await call_py.leave_call(message.chat.id)
     playing.pop(message.chat.id, None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM, 
link_preview_options=None)
     playing.pop(message.chat.id, None)



from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton




@Client.on_callback_query(filters.regex(r"^(skip|cskip)$"))
@admin_only()
async def button_skip_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_SKIP, show_alert=True)
        return

    try:
        bot_username = client.me.username

        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cskip"
            else callback_query.message.chat.id
        )

        if chat_id in queues and len(queues[chat_id]) > 0:
            # There's a next song in queue
            next_song = queues[chat_id].pop(0)
            await callback_query.message.reply(Messages.SKIPPING.format(callback_query.from_user.mention()), link_preview_options=None)
            
            try:
                await clients['call_py'].pause(chat_id)
            except Exception as e:
                logger.warning(f"Could not pause before skip: {e}")
            
            await join_call(
                next_song['message'],
                next_song['title'], 
                next_song['yt_link'], 
                next_song['chat'], 
                next_song['by'], 
                next_song['duration'], 
                next_song['mode'], 
                next_song['thumb'], 
                next_song.get('stream_url'),
                yt_task=next_song.get('_yt_task'),
            )
            await callback_query.answer(Messages.SKIPPED_SUCCESS, show_alert=False)
        else:
            # No more songs in queue
            try:
                await clients['call_py'].leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")
            
            await remove_active_chat(client, chat_id)
            
            if chat_id in playing:
                playing[chat_id].clear()
            
            await callback_query.message.reply(Messages.SKIPPED_EMPTY.format(callback_query.from_user.mention()), link_preview_options=None)
            
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")
            
            await callback_query.answer(Messages.QUEUE_EMPTY_STREAM_ENDED, show_alert=False)
            
    except NotInCallError:
        await remove_active_chat(client, chat_id)
        if chat_id in playing:
            playing[chat_id].clear()
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in skip button handler: {e}")
        await callback_query.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)

@Client.on_message(filters.command("loop"))
@admin_only()
async def loop_handler_func(client, message):
    try:
        await message.delete()
    except:
        pass
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if message.from_user.id in BLOCK:
        return

    try:
        # Get loop count from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await client.send_message(
                message.chat.id,
                Messages.LOOP_NO_ARGS, 
            link_preview_options=None)
            return

        try:
            loop_count = int(command_parts[1])
            if loop_count <= 0 or loop_count > 20:
                await client.send_message(
                    message.chat.id,
                    Messages.LOOP_OUT_OF_BOUNDS, 
                link_preview_options=None)
                return
        except ValueError:
            await client.send_message(
                message.chat.id,
                Messages.LOOP_INVALID, 
            link_preview_options=None)
            return

        # Check if there's a song playing
        if message.chat.id in playing and playing[message.chat.id]:
            current_song = playing[message.chat.id]

            # Initialize queue for this chat if it doesn't exist
            if message.chat.id not in queues:
                queues[message.chat.id] = []

            # Add the current song to queue multiple times
            for _ in range(loop_count):
                queues[message.chat.id].insert(0, current_song)

            await client.send_message(
                message.chat.id,
                f"Current song will be repeated {loop_count} times!\n\nʙʏ: {message.from_user.mention()}", 
            link_preview_options=None)
        else:
            await client.send_message(
                message.chat.id,
                "Assistant is not streaming anything!", 
            link_preview_options=None)

    except Exception as e:
        await client.send_message(
            message.chat.id,
            f"❌ An error occurred: {str(e)}", 
        link_preview_options=None)

@Client.on_message(filters.command("skip"))
@admin_only()
async def skip_handler_func(client, message):
  try:
         await message.delete()
  except:
         pass
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   bot_username = client.me.username
   if message.chat.id in queues:
    if len(queues[message.chat.id]) >0:
       next = queues[message.chat.id].pop(0)
       await client.send_message(message.chat.id, Messages.SKIPPING.format(message.from_user.mention()), link_preview_options=None)
       playing[message.chat.id] = next
       try:
          await call_py.pause(message.chat.id)
       except:
          pass
       await join_call(next['message'], next['title'], next['yt_link'], next['chat'], next['by'], next['duration'], next['mode'], next['thumb'], next.get('stream_url'), yt_task=next.get('_yt_task'))
    else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(client, message.chat.id)
       await client.send_message(message.chat.id, Messages.SKIPPED_EMPTY.format(message.from_user.mention()), link_preview_options=None)
       playing[message.chat.id].clear()
   else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(client, message.chat.id)
       await client.send_message(message.chat.id,
              Messages.SKIPPED_EMPTY.format(message.from_user.mention()), link_preview_options=None)
       playing[message.chat.id].clear()
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM, 
link_preview_options=None)
     playing[message.chat.id].clear()



@Client.on_callback_query(filters.regex("^(resume|cresume)$"))
@admin_only()
async def button_resume_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_RESUME, show_alert=True)
        return

    try:
        bot_username = client.me.username

        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cresume"
            else callback_query.message.chat.id
        )

        if await is_active_chat(client, chat_id):
            await call_py.resume(chat_id)
            await callback_query.message.reply(
                f"Song resumed. Use the Pause button to pause again.\n\nʙʏ: {callback_query.from_user.mention()}", 
            link_preview_options=None)
        else:
            await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING)
    except NotInCallError:
        await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)


@Client.on_callback_query(filters.regex("^(pause|cpause)$"))
@admin_only()
async def button_pause_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_PAUSE, show_alert=True)
        return

    try:
        bot_username = client.me.username
        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cpause"
            else callback_query.message.chat.id
        )

        if await is_active_chat(client, chat_id):
            await call_py.pause(chat_id)
            await callback_query.message.reply(
                f"Song paused. Use the Resume button to continue.\n\nʙʏ: {callback_query.from_user.mention()}", 
            link_preview_options=None)
        else:
            await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING)
    except NotInCallError:
        await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)

@Client.on_message(filters.command("resume"))
@admin_only()
async def resume_handler_func(client, message):
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   bot_username = client.me.username
   if  await is_active_chat(client, message.chat.id):
       await call_py.resume(message.chat.id)
       await client.send_message(message.chat.id, Messages.RESUMED.format(message.from_user.mention()), link_preview_options=None)
   else: await client.send_message(message.chat.id, Messages.NO_STREAM, link_preview_options=None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM, link_preview_options=None)


@Client.on_message(filters.command("pause"))
@admin_only()
async def pause_handler_func(client, message):
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   bot_username = client.me.username
   if  await is_active_chat(client, message.chat.id):
       await call_py.pause(message.chat.id)
       await client.send_message(message.chat.id, Messages.PAUSED.format(message.from_user.mention()), 
link_preview_options=None)
   else:
       await client.send_message(message.chat.id,  Messages.NO_STREAM, link_preview_options=None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM, link_preview_options=None)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_callback_query(filters.regex("broadcast"))
async def broadcast_callback_handler(client, callback_query):
    # Fetch user data for the callback query
    user_data = await user_sessions.find_one({"bot_id": client.me.id})
    if not user_data:
        return await callback_query.answer(Messages.USER_DATA_NOT_FOUND, show_alert=True)
    group = user_data.get('group')
    private = user_data.get('private')
    ugroup = user_data.get('ugroup')
    uprivate = user_data.get('uprivate')
    bot = user_data.get('bot')
    userbot = user_data.get('userbot')
    pin = user_data.get('pin')
    await callback_query.message.delete()
    # Fetch bot data
    bot_data = await find_one(collection, {"bot_id": client.me.id})
    message_to_broadcast, forwarding = broadcast_message.get(client.me.id)
    if bot_data and bot:
        X = await callback_query.message.reply(Messages.START_BOT_BROADCAST, link_preview_options=None)
        users = bot_data.get('users', [])
        progress_msg = ""
        u, g, sg, a_chat = 0, 0, 0, 0

        # Use asyncio.gather for efficient parallel processing
        chat_types = await asyncio.gather(
            *[get_chat_type(client, chat_id) for chat_id in users]
        )

        # Prepare message for broadcast
        if not message_to_broadcast:
            return await callback_query.answer(Messages.NO_MSG_FOR_BROADCAST, show_alert=True)

        for i, chat_type in enumerate(chat_types):
            if not chat_type:
                continue  # Skip if chat type could not be fetched

            # Handle the chat based on its type and flags
            try:
                if chat_type == enums.ChatType.PRIVATE and private:
                    await message_to_broadcast.copy(users[i])  if not forwarding else await message_to_broadcast.forward(users[i])
                    u+=1

                elif chat_type in (enums.ChatType.SUPERGROUP, enums.ChatType.GROUP) and group:
                    # Handle supergroup-specific actions
                    sent_message = await message_to_broadcast.copy(users[i]) if not forwarding else await message_to_broadcast.forward(users[i])
                    if chat_type == enums.ChatType.SUPERGROUP:
                        sg+=1
                    else:
                        g+=1
                    if pin:
                      try:
                        user_s = await client.get_chat_member(users[i], client.me.id)
                        if user_s.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
                            await sent_message.pin()
                            a_chat += 1
                      except FloodWait as e:
                              await asyncio.sleep(e.value)
                      except Exception as e:
                        logger.info(f"Error getting chat member status for {users[i]}: {e}")
                else:
                       continue

                # Update progress for each broadcast action (optional)
                progress_msg = f"Broadcasting to {u} private, {g} groups, {sg} supergroups, and {a_chat} pinned messages"
                await X.edit(progress_msg)
            except Exception as e:
                logger.info(f"Error in broadcasting to {users[i]}: {e}")
        await X.edit(f"Broadcasted to {u} private, {g} groups, {sg} supergroups, and {a_chat} pinned messages from bot")
    bot_username = client.me.username


    if userbot and session:
        XX = await callback_query.message.reply(Messages.START_ASSISTANT_BROADCAST, link_preview_options=None)
        uu, ug, usg, ua_chat = 0, 0, 0, 0
        try:
            # Ensure communication with the bot
            try:
                await session.get_chat(client.me.id)
            except PeerIdInvalid:
                await session.send_message(bot_username, "/start", link_preview_options=None)
            except UserBlocked:
                await session.unblock_user(bot_username)
            await asyncio.sleep(1)

            # Copy the message to session and fetch history
            copied_message = await message_to_broadcast.copy(session.me.id) if not forwarding else await message_to_broadcast.forward(session.me.id)
            await asyncio.sleep(2)

            msg = await compare_message(copied_message, client, session)
            if not msg:
             raise Exception("broadcast msg not found")
            # Broadcast to all dialogs
            async for dialog in session.get_dialogs():
                chat_id = dialog.chat.id
                chat_type = dialog.chat.type
                if str(chat_id) == str(-1001806816712):
                      continue
                try:
                    if chat_type == enums.ChatType.PRIVATE and uprivate:
                        await msg.copy(chat_id)
                        uu += 1

                    elif chat_type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP) and ugroup:
                        sent_message = await msg.copy(chat_id)  if not forwarding else await message_to_broadcast.forward(users[i])
                        if chat_type == enums.ChatType.SUPERGROUP:
                            usg += 1
                        else:
                            ug += 1

                    else:
                       continue
                    # Update progress
                    progress_text = (
                        f"Broadcasting via assistant...\n\n"
                        f"Private Chats: {uu}\n"
                        f"Groups: {ug}\n"
                        f"Supergroups: {usg}\n"
                    )
                    await XX.edit(progress_text)
                except FloodWait as e:
                               await asyncio.sleep(e.value)
                except Exception as e:
                    logger.info(f"Error broadcasting to {chat_id}: {e}")

        except Exception as e:
            logger.info(f"Error with session broadcast: {e}")
            await XX.reply(f"An error occurred during userbot broadcasting.{e}", link_preview_options=None)

    # Finalize broadcast summary
        await XX.edit(
        f"Broadcast completed!\n\n"
        f"Private Chats: {uu}\n"
        f"Groups: {ug}\n"
        f"Supergroups: {usg}\n"
    )



async def get_status(client):
  bot_username = client.me.username

  start = datetime.datetime.now()
  u = g = sg = a_chat =  0 # Initialize counters
  user_data = await find_one(collection, {"bot_id": client.me.id})
  mess=""

  if user_data:
    users = user_data.get('users', [])
    progress_msg = ""

    if len(users) > 500:
        mess += (
            f"<b>BOT STATS:</b>\n"
            f"<blockquote><b>`Stored users = {len(users)}`</b>\n"
            f"<b>`Detailed stats skipped to avoid timeout`</b></blockquote>"
        )
        mess += (f"\n\n<blockquote><b>CHOOSE THE OPTIONS BELOW⬇️⬇️ FOR BRODCASTING</b></blockquote>")
        broadcasts[client.me.id] = mess
        return mess

    chat_type_cache = dict(user_data.get('chat_type_cache', {}))

    for i, chat_id in enumerate(users):
        chat_type = await get_cached_chat_type(client, client.me.id, chat_id, chat_type_cache)
        if chat_type is None:
            continue # Skip if chat type could not be fetched

        if chat_type == enums.ChatType.PRIVATE:
            u += 1
        elif chat_type == enums.ChatType.GROUP:
            g += 1
        elif chat_type == enums.ChatType.SUPERGROUP:
            sg += 1
            try:
                user_s = await client.get_chat_member(users[i], int(client.me.id))
                if user_s.status in (
                    enums.ChatMemberStatus.OWNER,
                    enums.ChatMemberStatus.ADMINISTRATOR,
                ):
                    a_chat += 1
            except Exception as e:
                logger.info(f"Error getting chat member status for {users[i]}: {e}")
    mess += (
        f"""<b>BOT STATS:</b>
<blockquote><b>`Private chats = {u}</b>`
<b>`Groups = {g}`
<b>`Super Groups = {sg}`<b>
<b>`Admin in Chats = {a_chat}`</b></blockquote>""")

    uu = ug = usg  = ua_chat =0
    async for dialog in session.get_dialogs():
        try:
            if dialog.chat.type == enums.ChatType.PRIVATE:
                uu += 1
            elif dialog.chat.type == enums.ChatType.GROUP:
                ug += 1
            elif dialog.chat.type == enums.ChatType.SUPERGROUP:
                usg += 1
                user_s = await dialog.chat.get_member(int(session.me.id))
                if user_s.status in (
                    enums.ChatMemberStatus.OWNER,
                    enums.ChatMemberStatus.ADMINISTRATOR,
                ):
                    ua_chat += 1
        except:
            pass

    mess += (
        f"""\n\n<b>ASSISTANT STATS:</b>
<blockquote><b>`Private Messages = {uu}`
<b>`Groups = {ug}`
<b>`Super Groups = {usg}`<b>
<b>`Admin in Chats = {ua_chat}`</b></blockquote>"""
    )
    mess += (f"\n\n<blockquote><b>CHOOSE THE OPTIONS BELOW⬇️⬇️ FOR BRODCASTING</b></blockquote>")
    broadcasts[client.me.id] = mess
    return mess
  else:
    return

async def compare_message(mess, client, session):
    async for msg in session.get_chat_history(chat_id=client.me.id, limit=2):
        # Compare text messages
        if mess.text and msg.text == mess.text:
            return msg

        # Compare media messages
        elif mess.media and msg.media:
            try:
                # Get the media type (photo, video, etc.)
                mess_media_type = mess.media.value
                msg_media_type = msg.media.value

                # Check if both messages have the same media type
                if mess_media_type == msg_media_type:
                    # Get file unique IDs for comparison
                    mess_file_id = getattr(mess, mess_media_type).file_unique_id
                    msg_file_id = getattr(msg, msg_media_type).file_unique_id

                    # Compare file IDs
                    if mess_file_id and msg_file_id and mess_file_id == msg_file_id:
                        return msg
            except AttributeError:
                # Skip if media attributes are not accessible
                continue

    # Return None if no matching message is found
    return None

@Client.on_callback_query(filters.regex(r"toggle_(.*)"))
async def toggle_setting(client, callback_query):
    sender_id = client.me.id

    user_data = await user_sessions.find_one({"bot_id": sender_id})
    if not user_data:
        return await callback_query.answer(Messages.USER_DATA_NOT_FOUND, show_alert=True)
    setting_to_toggle = callback_query.data.split("_", 1)[1]
    current_value = user_data.get(setting_to_toggle)
    new_value = not current_value
    db_task(user_sessions.update_one(
        {"bot_id": sender_id},
        {"$set": {setting_to_toggle: new_value}}
    ))
    await broadcast_command_handler(client, callback_query)


@Client.on_message(filters.command("stats"))
async def status_command_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"

    # Get user data and permissions
    users_data = await find_one(user_sessions, {"bot_id": client.me.id})
    sudoers = users_data.get("SUDOERS", []) if users_data else []

    is_admin = False
    if os.path.exists(admin_file):
        admin_ids = get_admin_ids(admin_file)
        is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in sudoers
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    await status(client, message)



@Client.on_message(filters.command(["broadcast", "fbroadcast"]) & filters.private)
async def broadcast_command_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    users_data = await find_one(user_sessions, {"bot_id": client.me.id})
    sudoers = users_data.get("SUDOERS", []) if users_data else []

    is_admin = False
    if os.path.exists(admin_file):
        admin_ids = get_admin_ids(admin_file)
        is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in sudoers
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    sender_id = client.me.id
    user_data = await user_sessions.find_one({"bot_id": sender_id})
    if not user_data:
        return await message.reply(Messages.USER_DATA_NOT_FOUND, link_preview_options=None)
    if not isinstance(message, CallbackQuery):
      if not message.reply_to_message:
        return await message.reply(Messages.REPLY_TO_BROADCAST, link_preview_options=None)
      broadcast_message[client.me.id] = [message.reply_to_message]
      broadcast_message[client.me.id].append(True if message.command[0].lower().startswith("f") else None)
    group = user_data.get('group')
    private = user_data.get('private')
    ugroup = user_data.get('ugroup')
    uprivate = user_data.get('uprivate')
    bot = user_data.get('bot')
    userbot = user_data.get('userbot')
    pin = user_data.get('pin')
    for_bot =[
            InlineKeyboardButton(f"Gʀᴏᴜᴘ {'✅' if group else '❌'}", callback_data="toggle_group"),
            InlineKeyboardButton(f"Pʀɪᴠᴀᴛᴇ {'✅' if private else '❌'}", callback_data="toggle_private"),
            InlineKeyboardButton(f"📌Pɪɴ {'✅' if pin else '❌'}", callback_data="toggle_pin"),]

    for_userbot = [
            InlineKeyboardButton(f"Gʀᴏᴜᴘ {'✅' if ugroup else '❌'}", callback_data="toggle_ugroup"),
            InlineKeyboardButton(f"Pʀɪᴠᴀᴛᴇ {'✅' if uprivate else '❌'}", callback_data="toggle_uprivate"),]
    buttons = [
            [InlineKeyboardButton(f"Fʀᴏᴍ ʙᴏᴛ {'⬇️' if bot else '❌'}", callback_data="toggle_bot"),], for_bot if bot else [],
        [
            InlineKeyboardButton(f"Fʀᴏᴍ ᴜꜱᴇʀʙᴏᴛ {'⬇️' if userbot else '❌'}", callback_data="toggle_userbot"),], for_userbot if userbot else [],
    ]


    buttons.append([InlineKeyboardButton("BROADCAST🚀🚀", callback_data="broadcast")])
    if isinstance(message, CallbackQuery):  # If it's a button click (CallbackQuery)
        if not client.me.id in broadcasts:
           await get_status(client)
        await message.edit_message_text(
            broadcasts[client.me.id],
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:  # If it's a normal command message
        mess = await message.reply(Messages.GETTING_CHATS, link_preview_options=None)
        await get_status(client)
        if broadcasts[client.me.id]:
           await mess.edit(
            broadcasts[client.me.id],
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        else:
           await message.reply(Messages.NO_DATA_FOUND, link_preview_options=None)



@Client.on_message(filters.command("powers") & filters.group)
@admin_only()
async def handle_power_command(client, message):
    try:
        # Get bot's permissions in the group
        bot_member = await client.get_chat_member(
            chat_id=message.chat.id,
            user_id=client.me.id if not message.reply_to_message else message.reply_to_message.from_user.id
        )

        # Get chat info
        chat = await client.get_chat(message.chat.id)

        # Create permission status message
        power_message = (
            f"🤖 **{'Bot' if not message.reply_to_message else message.reply_to_message.from_user.mention()} Permissions in {chat.title}**\n\n"
            "📋 **Basic Powers:**\n"
        )

        # Basic permissions
        permissions = {
            "can_delete_messages": "Delete Messages",
            "can_restrict_members": "Restrict Members",
            "can_promote_members": "Promote Members",
            "can_change_info": "Change Group Info",
            "can_invite_users": "Invite Users",
            "can_pin_messages": "Pin Messages",
            "can_manage_video_chats": "Manage Video Chats",
            "can_manage_chat": "Manage Chat",
            "can_manage_topics": "Manage Topics"
        }

        # Add permission statuses
        for perm, display_name in permissions.items():
            status = getattr(bot_member.privileges, perm, False)
            emoji = "✅" if status else "❌"
            power_message += f"{emoji} {display_name}\n"

        # Add administrative status
        power_message += "\n📊 **Status:**\n"
        if bot_member.status == enums.ChatMemberStatus.ADMINISTRATOR:
            power_message += "✨ Bot is an **Administrator**"
        elif bot_member.status == enums.ChatMemberStatus.MEMBER:
            power_message += "👤 Bot is a **Regular Member**"
        else:
            power_message += "❓ Bot Status: " + str(bot_member.status).title()

        # Add anonymous admin status if applicable
        if hasattr(bot_member.privileges, "is_anonymous"):
            anon_status = "✅" if bot_member.privileges.is_anonymous else "❌"
            power_message += f"\n{anon_status} Anonymous Admin"

        # Add custom title if exists
        if hasattr(bot_member, "custom_title") and bot_member.custom_title:
            power_message += f"\n👑 Custom Title: **{bot_member.custom_title}**"

        # Create inline buttons for refresh and support
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_power_{message.chat.id}", style=ButtonStyle.PRIMARY),
            ]
        ])

        await message.reply(
            power_message,
            #reply_markup=buttons
        link_preview_options=None)

    except Exception as e:
        logger.error(f"Power check error: {e}")
        await message.reply(Messages.ERROR_PERMISSIONS, link_preview_options=None)




from pyrogram import Client, enums, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("about"))
async def info_command(client: Client, message: Message):
    chat = message.chat
    replied = message.reply_to_message

    # Setup user directory
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    photo_path = f"{user_dir}/logo.jpg"

    def create_copy_markup(text: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Copy Info", copy_text=text, style=ButtonStyle.PRIMARY)
        ]])

    # Handle second argument if provided
    target_user = None
    sender_id = message.from_user.id
    if not sender_id == OWNER_ID:
        return await message.reply_text(Messages.BOT_OWNER_ONLY, link_preview_options=None)

    if len(message.command) >= 2:
        user_input = message.command[1]
        try:
            # Try to get user by ID first
            if user_input.isdigit():
                target_user = await client.get_users(int(user_input))
            else:
                # If not ID, try username (with or without @ symbol)
                username = user_input.strip('@')
                target_user = await client.get_users(username)
        except Exception:
            await message.reply(Messages.ERROR_USER_NOT_FOUND, link_preview_options=None)
            return

    if target_user:
        # Handle user specified by argument
        user = target_user
        response = (
            "👤 **User Info**\n"
            f"🆔 **ID**: `{user.id}`\n"
            f"📛 **Name**: {user.first_name}"
        )
        if user.last_name:
            response += f" {user.last_name}\n"
        else:
            response += "\n"

        if user.username:
            response += f"🌐 **Username**: @{user.username}\n"

        # Add restriction, scam, and fake flags
        if user.is_restricted:
            response += "⚠️ **Account Restricted**: Yes\n"
            if user.restriction_reason:
                response += f"📝 **Restriction Reason**: {user.restriction_reason}\n"
        if user.is_scam:
            response += "🚫 **Scam Account**: Yes\n"
        if user.is_fake:
            response += "🎭 **Impersonator**: Yes\n"

        # Add status and join date for group queries
        if chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            try:
                member = await client.get_chat_member(chat.id, user.id)
                status_map = {
                    enums.ChatMemberStatus.OWNER: "👑 Owner",
                    enums.ChatMemberStatus.ADMINISTRATOR: "🔧 Admin",
                    enums.ChatMemberStatus.MEMBER: "👤 Member"
                }
                response += f"🎚 **Status**: {status_map.get(member.status, 'Unknown')}\n"

                if member.joined_date:
                    join_date = member.joined_date.strftime("%Y-%m-%d %H:%M:%S UTC")
                    response += f"📅 **Joined**: {join_date}\n"
                else:
                    response += "📅 **Joined**: Unknown\n"
            except Exception:
                response += "🎚 **Status**: ❌ Not in group\n"

        # Handle profile photo
        if user.photo:
            try:
                await client.download_media(user.photo.big_file_id, photo_path)
                await message.reply_photo(
                    photo_path,
                    caption=response,
                    reply_markup=create_copy_markup(response)
                )
            except Exception:
                await message.reply(
                    response,
                    reply_markup=create_copy_markup(response), 
                link_preview_options=None)
        else:
            await message.reply(
                response,
                reply_markup=create_copy_markup(response), 
            link_preview_options=None)
        return

    # Rest of the original code for replied messages and chat info remains the same
    if replied:
        if replied.sender_chat:
            sender_chat = replied.sender_chat
            if sender_chat.id == chat.id:
                response = (
                    "👤 **Anonymous Group Admin**\n"
                    f"🏷 **Title**: {sender_chat.title}\n"
                    f"🆔 **Chat ID**: `{sender_chat.id}`"
                )
            else:
                response = (
                    "📢 **Channel Info**\n"
                    f"🏷 **Title**: {sender_chat.title}\n"
                    f"🆔 **ID**: `{sender_chat.id}`\n"
                )
                if sender_chat.username:
                    response += f"🌐 **Username**: @{sender_chat.username}\n"
                if sender_chat.description:
                    response += f"📄 **Description**: {sender_chat.description[:300]}..."

            await message.reply(
                response,
                reply_markup=create_copy_markup(response), 
            link_preview_options=None)

        else:
            user = await client.get_users(replied.from_user.id)

            response = (
                "👤 **User Info**\n"
                f"🆔 **ID**: `{user.id}`\n"
                f"📛 **Name**: {user.first_name}"
            )
            if user.last_name:
                response += f" {user.last_name}\n"
            else:
                response += "\n"

            if user.username:
                response += f"🌐 **Username**: @{user.username}\n"

            if user.is_restricted:
                response += "⚠️ **Account Restricted**: Yes\n"
                if user.restriction_reason:
                    response += f"📝 **Restriction Reason**: {user.restriction_reason}\n"
            if user.is_scam:
                response += "🚫 **Scam Account**: Yes\n"
            if user.is_fake:
                response += "🎭 **Impersonator**: Yes\n"

            if chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
                try:
                    member = await client.get_chat_member(chat.id, user.id)
                    status_map = {
                        enums.ChatMemberStatus.OWNER: "👑 Owner",
                        enums.ChatMemberStatus.ADMINISTRATOR: "🔧 Admin",
                        enums.ChatMemberStatus.MEMBER: "👤 Member"
                    }
                    response += f"🎚 **Status**: {status_map.get(member.status, 'Unknown')}\n"

                    if member.joined_date:
                        join_date = member.joined_date.strftime("%Y-%m-%d %H:%M:%S UTC")
                        response += f"📅 **Joined**: {join_date}\n"
                    else:
                        response += "📅 **Joined**: Unknown\n"
                except Exception:
                    response += "🎚 **Status**: ❌ Not in group\n"

            if user.photo:
                try:
                    await client.download_media(user.photo.big_file_id, photo_path)
                    await message.reply_photo(
                        photo_path,
                        caption=response,
                        reply_markup=create_copy_markup(response)
                    )
                except Exception:
                    await message.reply(
                        response,
                        reply_markup=create_copy_markup(response), 
                    link_preview_options=None)
            else:
                await message.reply(
                    response,
                    reply_markup=create_copy_markup(response), 
                link_preview_options=None)

    else:
        if chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            full_chat = await client.get_chat(chat.id)

            admin_count = 0
            async for member in client.get_chat_members(
                chat.id,
                filter=enums.ChatMembersFilter.ADMINISTRATORS
            ):
                admin_count += 1

            response = (
                "👥 **Group Info**\n"
                f"🏷 **Title**: {full_chat.title}\n"
                f"🆔 **ID**: `{full_chat.id}`\n"
            )

            if full_chat.username:
                response += f"🌐 **Username**: @{full_chat.username}\n"
            response += (
                f"👥 **Members**: {full_chat.members_count}\n"
                f"🔧 **Admins**: {admin_count}\n"
            )

            await message.reply(
                response,
                reply_markup=create_copy_markup(response), 
            link_preview_options=None)

        else:
            user = await client.get_users(chat.id)

            response = (
                "👤 **User Info**\n"
                f"🆔 **ID**: `{user.id}`\n"
                f"📛 **Name**: {user.first_name}"
            )
            if user.last_name:
                response += f" {user.last_name}\n"
            else:
                response += "\n"

            if user.username:
                response += f"🌐 **Username**: @{user.username}\n"

            if user.is_restricted:
                response += "⚠️ **Account Restricted**: Yes\n"
                if user.restriction_reason:
                    response += f"📝 **Restriction Reason**: {user.restriction_reason}\n"

            if user.is_scam:
                response += "🚫 **Scam Account**: Yes\n"

            if user.is_fake:
                response += "🎭 **Impersonator**: Yes\n"

            if user.photo:
                try:
                    await client.download_media(user.photo.big_file_id, photo_path)
                    await message.reply_photo(
                        photo_path,
                        caption=response,
                        reply_markup=create_copy_markup(response)
                    )
                except Exception:
                    await message.reply(
                        response,
                        reply_markup=create_copy_markup(response), 
                    link_preview_options=None)
            else:
                await message.reply(
                    response,
                    reply_markup=create_copy_markup(response), 
                link_preview_options=None)


@Client.on_callback_query(filters.regex("^close$"))
async def close_message(client, query):
    try:
        # Delete the original message
        await query.message.delete()
        # Send confirmation with mention and remove it after 5 seconds
        closed_msg = await client.send_message(
            query.message.chat.id,
            f"🗑 Message closed by {query.from_user.mention}", 
        link_preview_options=None)
        await asyncio.sleep(5)
        await closed_msg.delete()
    except Exception as e:
        print(f"Error closing message: {e}")




@Client.on_message(filters.command("kang"))
async def kang(client, message):
    bot_username = client.me.username
    client = clients['session']
    user = message.from_user
    if not user:
       return await message.reply_text(Messages.USE_COMMAND_AS_USER, link_preview_options=None)
    replied = message.reply_to_message
    Man = await message.reply_text(Messages.STICKER_LONG, link_preview_options=None)
    media_ = None
    emoji_ = None
    is_anim = False
    is_video = False
    resize = False
    ff_vid = False
    if replied and replied.media:
        if replied.photo:
            resize = True
        elif replied.document and "image" in replied.document.mime_type:
            resize = True
            replied.document.file_name
        elif replied.document and "tgsticker" in replied.document.mime_type:
            is_anim = True
            replied.document.file_name
        elif replied.document and "video" in replied.document.mime_type:
            resize = True
            is_video = True
            ff_vid = True
        elif replied.animation:
            resize = True
            is_video = True
            ff_vid = True
        elif replied.video:
            resize = True
            is_video = True
            ff_vid = True
        elif replied.sticker:
            if not replied.sticker.file_name:
                await Man.edit(Messages.STICKER_NO_NAME)
                return
            emoji_ = replied.sticker.emoji
            is_anim = replied.sticker.is_animated
            is_video = replied.sticker.is_video
            if not (
                replied.sticker.file_name.endswith(".tgs")
                or replied.sticker.file_name.endswith(".webm")
            ):
                resize = True
                ff_vid = True
        else:
            await Man.edit(Messages.UNSUPPORTED_FILE)
            return
        media_ = await client.download_media(replied, file_name=f"{ggg}/user_{client.me.id}/")
    else:
        await Man.edit(Messages.REPLY_TO_MEDIA)
        return
    if media_:
        args = get_arg(message)
        pack = 1
        if len(args) == 2:
            emoji_, pack = args
        elif len(args) == 1:
            if args[0].isnumeric():
                pack = int(args[0])
            else:
                emoji_ = args[0]

        if emoji_:
            def is_unicode_emoji(s: str) -> bool:
                if not s:
                    return False
                emoji_re = re.compile(
                    "["
                    "\U0001F300-\U0001F6FF"
                    "\U0001F700-\U0001F77F"
                    "\U0001F780-\U0001F7FF"
                    "\U0001F800-\U0001F8FF"
                    "\U0001F900-\U0001F9FF"
                    "\U0001FA00-\U0001FA6F"
                    "\U0001FA70-\U0001FAFF"
                    "\U00002702-\U000027B0"
                    "\U000024C2-\U0001F251"
                    "]+",
                    flags=re.UNICODE,
                )
                return bool(emoji_re.fullmatch(s) or emoji_re.search(s))

            valid = False
            # normalize
            e = str(emoji_).strip()

            # If user provided a named constant (e.g., PLAY, MUSIC_NOTE)
            if hasattr(Emoji, e):
                emoji_ = getattr(Emoji, e)
                valid = True

            # If it's purely numeric, treat as custom emoji id
            if not valid and e.isdigit():
                try:
                    emoji_ = int(e)
                    valid = True
                except Exception:
                    valid = False

            # If it's a unicode emoji (one or more glyphs), accept as-is
            if not valid and is_unicode_emoji(e):
                emoji_ = e
                valid = True

            # As a last resort, check if it matches any Emoji constant values
            if not valid:
                try:
                    for name in dir(Emoji):
                        if name.startswith("_"):
                            continue
                        val = getattr(Emoji, name)
                        if str(val) == e:
                            emoji_ = val
                            valid = True
                            break
                except Exception:
                    valid = False

            if not valid:
                emoji_ = None
        if not emoji_:
            emoji_ = "✨"

        u_name = user.username
        u_name = "@" + u_name if u_name else user.first_name or user.id
        packname = f"Sticker_u{user.id}_v{pack}"
        custom_packnick = f"{u_name} Sticker Pack"
        packnick = f"{custom_packnick} Vol.{pack}"
        cmd = "/newpack"
        if resize:
            media_ = await resize_media(media_, is_video, ff_vid)
        if is_anim:
            packname += "_animated"
            packnick += " (Animated)"
            cmd = "/newanimated"
        if is_video:
            packname += "_video"
            packnick += " (Video)"
            cmd = "/newvideo"
        exist = False
        while True:
            try:
                exist = await client.invoke(
                    GetStickerSet(
                        stickerset=InputStickerSetShortName(short_name=packname), hash=0
                    )
                )
            except StickersetInvalid:
                exist = False
                break
            limit = 50 if (is_video or is_anim) else 120
            if exist.set.count >= limit:
                pack += 1
                packname = f"a{user.id}_by_userge_{pack}"
                packnick = f"{custom_packnick} Vol.{pack}"
                if is_anim:
                    packname += f"_anim{pack}"
                    packnick += f" (Animated){pack}"
                if is_video:
                    packname += f"_video{pack}"
                    packnick += f" (Video){pack}"
                await Man.edit(
                    f"`Create a New Sticker Pack {pack} Because the Sticker Pack is Full`"
                )
                continue
            break
        if exist is not False:
            try:
                await client.send_message("stickers", "/addsticker", link_preview_options=None)
            except YouBlockedUser:
                await client.unblock_user("stickers")
                await client.send_message("stickers", "/addsticker", link_preview_options=None)
            except Exception as e:
                return await Man.edit(f"**ERROR:** `{e}`")
            await asyncio.sleep(2)
            await client.send_message("stickers", packname, link_preview_options=None)
            await asyncio.sleep(2)
            limit = "50" if is_anim else "120"
            while limit in await get_response(message, client):
                pack += 1
                packname = f"a{user.id}_by_{user.username}_{pack}"
                packnick = f"{custom_packnick} vol.{pack}"
                if is_anim:
                    packname += f"_anim"
                    packnick += " (Animated)"
                if is_video:
                    packname += "_video"
                    packnick += " (Video)"
                    await Man.edit(
                    f"`Creating a New Sticker Pack {pack} Because the Sticker Pack is Full`"
                )
                await client.send_message("stickers", packname, link_preview_options=None)
                await asyncio.sleep(2)
                if await get_response(message, client) == "Invalid pack selected.":
                    await client.send_message("stickers", cmd, link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_message("stickers", packnick, link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_document("stickers", media_)
                    await asyncio.sleep(2)
                    await client.send_message("Stickers", emoji_, link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_message("Stickers", "/publish", link_preview_options=None)
                    await asyncio.sleep(2)
                    if is_anim:
                        await client.send_message(
                            "Stickers", f"<{packnick}>", parse_mode=ParseMode.MARKDOWN, 
                        link_preview_options=None)
                        await asyncio.sleep(2)
                    await client.send_message("Stickers", "/skip", link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_message("Stickers", packname, link_preview_options=None)
                    await asyncio.sleep(2)
                    await Man.edit(
                        f"**Sticker Added Successfully!**\n 🔥 **[CLICK HERE](https://t.me/addstickers/{packname})** 🔥\n**To Use Stickers**"
                    )
            await client.send_document("stickers", media_)
            await asyncio.sleep(2)
            if (
                await get_response(message, client)
                == "Sorry, the file type is invalid."
            ):
                await Man.edit(
                    "**Failed to Add Sticker, Use @Stickers Bot to Add Your Sticker.**"
                )
                return
            await client.send_message("Stickers", emoji_, link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", "/done", link_preview_options=None)
        else:
            await Man.edit(Messages.CREATING_STICKER_PACK)
            try:
                await client.send_message("Stickers", cmd, link_preview_options=None)
            except YouBlockedUser:
                await client.unblock_user("stickers")
                await client.send_message("stickers", "/addsticker", link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", packnick, link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_document("stickers", media_)
            await asyncio.sleep(2)
            if (
                await get_response(message, client)
                == "Sorry, the file type is invalid."
            ):
                await Man.edit(
                    "**Failed to Add Sticker, Use @Stickers Bot to Add Your Sticker.**"
                )
                return
            await client.send_message("Stickers", emoji_, link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", "/publish", link_preview_options=None)
            await asyncio.sleep(2)
            if is_anim:
                await client.send_message("Stickers", f"<{packnick}>", link_preview_options=None)
                await asyncio.sleep(2)
            await client.send_message("Stickers", "/skip", link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", packname, link_preview_options=None)
            await asyncio.sleep(2)
        await Man.edit(
            f"**Sticker Added Successfully!**\n 🔥 **[CLICK HERE](https://t.me/addstickers/{packname})** 🔥\n**To Use Stickers**"
        )
        if os.path.exists(str(media_)):
            os.remove(media_)






async def get_response(message, client):
    return [x async for x in client.get_chat_history("Stickers", limit=1)][0].text


@Client.on_message(filters.command("mmf"))
async def memify(client, message):
    if not message.reply_to_message_id:
        await message.reply_text(Messages.REPLY_TO_PHOTO_OR_STICKER, link_preview_options=None)
        return
    reply_message = message.reply_to_message
    if not reply_message.media:
        await message.reply_text(Messages.REPLY_TO_PHOTO_OR_STICKER, link_preview_options=None)
        return
    file = await client.download_media(reply_message)
    Man = await message.reply_text(Messages.PROCESSING, link_preview_options=None)
    text = get_arg(message)
    if len(text) < 1:
        return await Man.edit(f"Please use `/mmf <text>`")
    meme = await add_text_img(file, text)
    await asyncio.gather(
        Man.delete(),
        client.send_sticker(
            message.chat.id,                                                                                          sticker=meme,
            reply_to_message_id=reply_message.id,                                                                 ),
    )
    os.remove(meme)
    await message.delete()


import subprocess
import os
from pyrogram import Client, filters



@Client.on_message(filters.command("setwelcome") & filters.private)
async def set_welcome_handler(client, message):
    sender_id = message.from_user.id
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    try:
        if not sender_id == OWNER_ID:
           return await message.reply_text(Messages.BOT_OWNER_ONLY, link_preview_options=None)

        replied_msg = message.reply_to_message
        if not replied_msg:
            usage_text = (
                "Please reply to a message to set it as welcome message.\n\n"
                "You can set:\n"
                "• Text message\n"
                "• Media (photo/video/gif/sticker)\n"
                "• Media with caption\n\n"
                "Available placeholders:\n"
                "• {name} - User's name\n"
                "• {id} - User's ID\n"
                "• {botname} - Bot's username\n\n"
                "Size limits:\n"
                "• Text: Maximum 4096 characters\n"
                "• Media: Maximum 5MB\n\n"
                "Example usage:\n"
                "• 'Welcome {name}! Your ID is {id}'\n"
                "• Reply to a photo/video with caption 'Welcome to {botname}!'"
            )
            return await message.reply_text(usage_text, link_preview_options=None)

        updates = []

        # Handle text if present
        if replied_msg.text or replied_msg.caption:
            welcome_text = (replied_msg.text or replied_msg.caption).strip()
            if len(welcome_text) > 4096:
                return await message.reply_text(Messages.WELCOME_TOO_LONG, link_preview_options=None)

            entities = sorted(
                (replied_msg.entities or replied_msg.caption_entities or []),
                key=lambda x: (x.offset, -x.length)
            )

            ENTITY_TO_HTML = {
                MessageEntityType.BOLD: ('b', 'b'),
                MessageEntityType.ITALIC: ('i', 'i'),
                MessageEntityType.UNDERLINE: ('u', 'u'),
                MessageEntityType.STRIKETHROUGH: ('s', 's'),
                MessageEntityType.SPOILER: ('spoiler', 'spoiler'),
                MessageEntityType.CODE: ('code', 'code'),
                MessageEntityType.PRE: ('pre', 'pre'),
                MessageEntityType.BLOCKQUOTE: ('blockquote', 'blockquote')
            }

            def convert_to_html(text, msg_entities):
                tag_positions = []

                for entity in msg_entities:
                    if entity.type in ENTITY_TO_HTML:
                        start_tag, end_tag = ENTITY_TO_HTML[entity.type]

                        if entity.type == MessageEntityType.PRE and getattr(entity, 'language', None):
                            tag_positions.append((entity.offset, f'<pre language="{entity.language}">', True))
                        else:
                            tag_positions.append((entity.offset, f'<{start_tag}>', True))

                        tag_positions.append((entity.offset + entity.length, f'</{end_tag}>', False))

                tag_positions.sort(key=lambda x: (x[0], x[2]))

                result = []
                current_pos = 0

                for pos, tag, _ in tag_positions:
                    if pos > current_pos:
                        result.append(text[current_pos:pos])
                    result.append(tag)
                    current_pos = pos

                if current_pos < len(text):
                    result.append(text[current_pos:])

                return ''.join(result)

            processed_text = convert_to_html(welcome_text, entities)

            # Validate placeholders
            ALLOWED_PLACEHOLDERS = {"{name}", "{id}", "{botname}"}
            placeholder_regex = r'\{([^{}]+)\}'
            found_placeholders = set(re.findall(placeholder_regex, processed_text))

            invalid_placeholders = [f"{{{p}}}" for p in found_placeholders
                                  if f"{{{p}}}" not in ALLOWED_PLACEHOLDERS]

            if invalid_placeholders:
                error_msg = "❌ Invalid placeholders found:\n"
                error_msg += "\n".join(f"• {p}" for p in invalid_placeholders)
                error_msg += "\n\nAllowed placeholders:\n"
                error_msg += "\n".join(f"• {p}" for p in sorted(ALLOWED_PLACEHOLDERS))
                error_msg += "\n\nExample usage:\n"
                error_msg += "• Welcome {name}!\n"
                error_msg += "• Your ID: {id}\n"
                error_msg += "• Welcome to {botname}!"
                return await message.reply_text(error_msg, link_preview_options=None)

            set_gvar(client.me.id, "WELCOME", processed_text)
            updates.append("welcome message")

        # Handle media if present
        if replied_msg.media:
            m_d = None
            try:
                # Check if media type is allowed
                if not (replied_msg.photo or replied_msg.video or
                       replied_msg.sticker or replied_msg.animation):
                    return await message.reply_text(Messages.ONLY_MEDIA_ALLOWED, link_preview_options=None)

                # Check file size (5MB = 5 * 1024 * 1024 bytes)
                file_size = getattr(replied_msg, 'file_size', 0)
                if file_size > 5242880:  # 5MB in bytes
                    return await message.reply_text(Messages.MEDIA_SIZE_EXCEED, link_preview_options=None)

                # First try to save to user_dir
                logo_path_jpg = f"{user_dir}/logo.jpg"
                logo_path_mp4 = f"{user_dir}/logo.mp4"

                # Process media based on type
                if replied_msg.sticker:
                    m_d = await convert_to_image(replied_msg)
                else:
                    m_d = await replied_msg.download()

                if m_d:
                    # Save to appropriate path based on media type
                    if replied_msg.video:
                        target_path = logo_path_mp4
                    else:
                        target_path = logo_path_jpg

                    os.rename(m_d, target_path)
                    updates.append(f"logo (saved to {target_path})")

            except Exception as e:
                if m_d and os.path.exists(m_d):
                    os.remove(m_d)
                return await message.reply_text(Messages.ERROR_MEDIA_PROCESS.format(str(e)), link_preview_options=None)

        if not updates:
            return await message.reply_text(Messages.NOTHING_TO_UPDATE, link_preview_options=None)

        # Send confirmation and preview
        success_msg = f"✅ Updated {' and '.join(updates)}!"
        await client.send_message(message.chat.id, success_msg + "\n\nPreview:", link_preview_options=None)

        # Show preview
        try:
            # First check user_dir for existing logos
            logo_path_jpg = f"{user_dir}/logo.jpg"
            logo_path_mp4 = f"{user_dir}/logo.mp4"
            logo = None

            if os.path.exists(logo_path_mp4):
                logo = logo_path_mp4
            elif os.path.exists(logo_path_jpg):
                logo = logo_path_jpg
            else:
                # Fallback to old methods
                logo = await gvarstatus(sender_id, "LOGO")
                if not logo and client.me.photo:
                    photos = await client.get_profile_photos("me")
                    if photos:
                        logo = await client.download_media(photos[0].file_id, logo_path_jpg)
                if not logo:
                    logo = "music.jpg"

            alive_logo = logo
            if isinstance(logo, bytes):
                alive_logo = logo_path_jpg
                with open(alive_logo, "wb") as fimage:
                    fimage.write(base64.b64decode(logo))
                if 'video' in mime.from_file(alive_logo):
                    alive_logo = rename_file(alive_logo, logo_path_mp4)

            welcome_text = await gvarstatus(sender_id, "WELCOME") or f"""
🌟 𝖂𝖊𝖑𝖈𝖔𝖒𝖊, {name}! 🌟

🎶 Your **musical journey** begins with {botname}!

✨ Enjoy _crystal-clear_ audio and a vast library of sounds.

🚀 Get ready for an *unparalleled* musical adventure!
"""
            if alive_logo.endswith(".mp4"):
                await client.send_video(
                    message.chat.id,
                    alive_logo,
                    caption=welcome_text,
                )
            else:
                await client.send_photo(
                    message.chat.id,
                    alive_logo,
                    caption=welcome_text,
                )

        except Exception as e:
            logger.info(f"Error showing preview: {str(e)}")
            welcome_text = await gvarstatus(sender_id, "WELCOME")
            if welcome_text:
                await client.send_message(
                    message.chat.id,
                    welcome_text,
                link_preview_options=None)
    except Exception as e:
        error_msg = f"❌ Error: `{str(e)}`"
        logger.info(f"Error for user {message.from_user.id}: {str(e)}")
        return await message.reply_text(error_msg, link_preview_options=None)

@Client.on_message(filters.command(["resetwelcome", "rwelcome"]))
async def resetwelcome(client: Client, message: Message):
    sender_id = message.from_user.id
    if not sender_id == OWNER_ID:
        return await message.reply_text(Messages.BOT_OWNER_ONLY, link_preview_options=None)

    set_gvar(client.me.id, "WELCOME", None)
    set_gvar(client.me.id, "LOGO", None)
    await message.reply_text(Messages.WELCOME_RESET, link_preview_options=None)
