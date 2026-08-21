"""
plugins/info.py
/ping, /stats, /ac, /np (nowplaying), /lang
"""

import asyncio
import datetime
import logging
import os
import time
from random import choice

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType

from config import OWNER_ID, ggg, StartTime
from tools import (
    state, clients, SUDO, assistants, calls, assistant_info,
    get_admin_ids, get_readable_time, convert_bytes,
    get_assistant, set_assistant, change_assistant,
    get_call_client, get_assistant_count,
)
from utils.emoji import EmojiTag
from utils.message import Messages
from utils.lang import get_str, get_lang, LANGUAGES, lang_list_text
from database import user_sessions, collection

logger = logging.getLogger(__name__)


# ── /ping ──────────────────────────────────────────────────────────────────────
@Client.on_message(filters.command("ping"))
async def pingme(client, message):
    uptime = await get_readable_time(int(time.time() - StartTime))
    start = datetime.datetime.now()
    owner = await client.get_users(OWNER_ID)

    ping_frames = [
        "█▒▒▒▒▒▒▒▒▒ 10%", "███▒▒▒▒▒▒▒ 30%", "█████▒▒▒▒▒ 50%",
        "███████▒▒▒ 70%", "█████████▒ 90%", "██████████ 100%",
    ]
    loading = ["🕐","🕑","🕒","🕓","🕔","🕕","🕖","🕗","🕘","🕙","🕚","🕛"]

    msg = await message.reply_text(Messages.PINGING, link_preview_options=None)
    for frame in ping_frames:
        await msg.edit(f"```\n{frame}\n```{choice(loading)}")
        await asyncio.sleep(0.3)

    end = datetime.datetime.now()
    ms = (end - start).microseconds / 1000
    status = f"EXCELLENT {EmojiTag.SUCCESS}" if ms < 100 else (f"GOOD {EmojiTag.WARNING}" if ms < 200 else f"MODERATE {EmojiTag.ERROR}")
    quotes = [
        f"Blazing fast! {EmojiTag.BOLT}",
        f"Speed demon! {EmojiTag.FIRE}",
        f"Lightning quick! {EmojiTag.BOLT}",
        f"Sonic boom! {EmojiTag.ROCKET}",
    ]

    response = (
        f"╭──────────────────\n"
        f"│   <b>PONG!</b> {EmojiTag.PING}\n"
        f"├──────────────────\n"
        f"│ {EmojiTag.BOLT} <b>Speed:</b> <code>{ms:.2f}ms</code>\n"
        f"│ {EmojiTag.STATS} <b>Status:</b> {status}\n"
        f"│ {EmojiTag.LOADING} <b>Uptime:</b> <code>{uptime}</code>\n"
        f"│ {EmojiTag.CROWN} <b>Owner:</b> {owner.mention()}\n"
        f"│ {EmojiTag.HEADPHONES} <b>Assistants:</b> <code>{len(assistants)} Online</code>\n"
        f"╰──────────────────"
    )
    await msg.edit(response + f"\n<b>{choice(quotes)}</b>")


# ── /ac (active calls) ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("ac"))
async def active_chats_info(client, message):
    uid = message.from_user.id if message.from_user else None
    is_auth = (
        uid in get_admin_ids(f"{ggg}/admin.txt")
        or str(OWNER_ID) == str(uid)
        or (uid and uid in SUDO)
    )
    if not is_auth:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    all_active = set()
    for ast_idx, cp in calls.items():
        if cp:
            try:
                c_list = await cp.calls
                all_active.update(c_list)
            except Exception:
                pass

    if not all_active and state.active:
        all_active.update(state.active)

    if all_active:
        async def _fetch_title(cid):
            try:
                chat = await client.get_chat(cid)
                ast_num = state.get_chat_assistant(cid) or 1
                return f"• {chat.title} <i>(Ast {ast_num})</i>"
            except Exception:
                return f"• [ID: {cid}]"

        titles = await asyncio.gather(*[_fetch_title(cid) for cid in all_active])
        titles_str = "\n".join(titles)
        reply_text = (
            f"<b>{EmojiTag.HEADPHONES} ᴀᴄᴛɪᴠᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟs ({len(all_active)}):</b>\n"
            f"<blockquote expandable>{titles_str}</blockquote>\n"
            f"<b>‣ ᴛᴏᴛᴀʟ ᴀssɪsᴛᴀɴᴛs:</b> <code>{len(assistants)}</code>"
        )
    else:
        reply_text = f"<b>{EmojiTag.HEADPHONES} ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs:</b>\n<blockquote>{EmojiTag.INFO} No active group calls</blockquote>"

    await message.reply_text(reply_text, link_preview_options=None)


# ── /assistants / /userbot ────────────────────────────────────────────────────
@Client.on_message(filters.command(["assistants", "userbot", "userbots"]))
async def assistants_info_handler(client, message):
    uid = message.from_user.id if message.from_user else None
    is_auth = (
        uid in get_admin_ids(f"{ggg}/admin.txt")
        or str(OWNER_ID) == str(uid)
        or (uid and uid in SUDO)
    )
    if not is_auth:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    if not assistants:
        return await message.reply("<b>No active assistant accounts connected.</b>", link_preview_options=None)

    lines = [f"<b>{EmojiTag.CROWN} ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴀssɪsᴛᴀɴᴛs ({len(assistants)}):</b>\n"]
    for idx, ast in assistants.items():
        info = assistant_info.get(idx, {})
        name = info.get("name") or getattr(ast.me, "first_name", f"Assistant {idx}")
        username = f"@{info.get('username')}" if info.get("username") else f"ID: {info.get('id', 'N/A')}"
        active_count = len(state.assistant_active.get(idx, set()))
        lines.append(f"<b>{idx}.</b> <b>{name}</b> ({username})\n   └ 🎙 <b>Active Streams:</b> <code>{active_count}</code>")

    await message.reply("\n\n".join(lines), link_preview_options=None)


# ── /changeassistant / /assistant ─────────────────────────────────────────────
@Client.on_message(filters.command(["changeassistant", "changeast", "assistant"]))
async def change_assistant_handler(client, message):
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return await message.reply(Messages.GROUP_ONLY, link_preview_options=None)

    chat_id = message.chat.id
    current_num, userbot, call_py = await get_assistant(chat_id)
    cur_info = assistant_info.get(current_num, {})
    cur_name = cur_info.get("name") or (getattr(userbot.me, "first_name", f"Assistant {current_num}") if userbot else f"Assistant {current_num}")

    buttons = []
    row = []
    for idx in sorted(assistants.keys()):
        mark = "✓ " if idx == current_num else ""
        row.append(InlineKeyboardButton(f"{mark}Assistant {idx}", callback_data=f"change_ast_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    text = (
        f"<b>{EmojiTag.SETTINGS} ɢʀᴏᴜᴘ ᴀssɪsᴛᴀɴᴛ sᴇᴛᴛɪɴɢs</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴀssɪsᴛᴀɴᴛ:</b> <code>Assistant {current_num}</code> ({cur_name})\n"
        f"<i>Select an assistant below to assign to this group:</i>"
    )
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons), link_preview_options=None)


@Client.on_callback_query(filters.regex(r"^change_ast_(\d+)$"))
async def callback_change_assistant(client, callback_query):
    chat_id = callback_query.message.chat.id
    ast_idx = int(callback_query.matches[0].group(1))

    if ast_idx not in assistants:
        return await callback_query.answer("Assistant not found.", show_alert=True)

    await set_assistant(chat_id, ast_idx)
    target_ast = assistants[ast_idx]
    info = assistant_info.get(ast_idx, {})
    name = info.get("name") or getattr(target_ast.me, "first_name", f"Assistant {ast_idx}")

    buttons = []
    row = []
    for idx in sorted(assistants.keys()):
        mark = "✓ " if idx == ast_idx else ""
        row.append(InlineKeyboardButton(f"{mark}Assistant {idx}", callback_data=f"change_ast_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    text = (
        f"<b>{EmojiTag.SETTINGS} ɢʀᴏᴜᴘ ᴀssɪsᴛᴀɴᴛ sᴇᴛᴛɪɴɢs</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴀssɪsᴛᴀɴᴛ:</b> <code>Assistant {ast_idx}</code> ({name})\n"
        f"<i>Select an assistant below to assign to this group:</i>"
    )
    try:
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass
    await callback_query.answer(f"Switched group assistant to Assistant {ast_idx}!", show_alert=False)


# ── /leaveall (Owner / Sudo Only) ─────────────────────────────────────────────
@Client.on_message(filters.command("leaveall"))
async def leave_all_handler(client, message):
    uid = message.from_user.id if message.from_user else None
    if str(OWNER_ID) != str(uid) and (not uid or uid not in SUDO):
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    progress_msg = await message.reply("<b>Cleaning idle chats across all assistants...</b>", link_preview_options=None)
    total_left = 0

    for idx, ast in assistants.items():
        try:
            async for dialog in ast.get_dialogs():
                chat = dialog.chat
                chat_type = str(getattr(chat, "type", "")).lower()
                if "group" in chat_type or "supergroup" in chat_type:
                    if chat.id not in state.active:
                        try:
                            await ast.leave_chat(chat.id)
                            total_left += 1
                            await asyncio.sleep(1.0)
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"[leaveall] Assistant {idx} error: {e}")

    await progress_msg.edit_text(f"<b>Done! Left {total_left} inactive chats across all assistants.</b>")


# ── /np / /nowplaying ──────────────────────────────────────────────────────────
@Client.on_message(filters.command(["np", "nowplaying"]))
async def now_playing(client, message):
    chat_id = message.chat.id
    song = state.playing.get(chat_id)

    if not song:
        txt = await get_str(chat_id, "NO_STREAM")
        return await message.reply(txt, link_preview_options=None)

    title = song.get("title", "Unknown")
    duration = song.get("duration", "N/A")
    mode = song.get("mode", "audio")
    by = song.get("by")
    yt_link = song.get("yt_link", "")

    # Elapsed
    start_ts = state.played.get(chat_id)
    elapsed = ""
    if start_ts:
        elapsed_s = int(time.time() - start_ts)
        elapsed = f"{elapsed_s // 60:02d}:{elapsed_s % 60:02d}"

    # Progress bar
    progress_text = ""
    if elapsed and duration and duration != "N/A":
        try:
            dur_parts = duration.split(":")
            total_s = sum(int(x) * 60 ** i for i, x in enumerate(reversed(dur_parts)))
            elapsed_s_val = int(time.time() - start_ts)
            pct = min(elapsed_s_val / max(total_s, 1), 1.0)
            filled = int(pct * 10)
            bar = "▓" * filled + "░" * (10 - filled)
            progress_text = f"\n<code>{elapsed} {bar} {duration}</code>"
        except Exception:
            pass

    mention = by.mention() if by and hasattr(by, "mention") else str(by or "Unknown")
    mode_label = "🎵 Audio" if mode == "audio" else "🎬 Video"
    title_link = f'<a href="{yt_link}">{title}</a>' if yt_link else f"<b>{title}</b>"

    queued_count = len(state.queues.get(chat_id, []))
    queue_info = f"\n<b>ǫᴜᴇᴜᴇ:</b> {queued_count} track(s) up next" if queued_count else ""

    text = (
        f"<u><b>{EmojiTag.NOW_PLAYING} | ɴᴏᴡ ᴘʟᴀʏɪɴɢ</b></u>\n\n"
        f"<b>ᴛʀᴀᴄᴋ:</b> {title_link}\n"
        f"<b>ᴍᴏᴅᴇ:</b> {mode_label}\n"
        f"<b>ʀᴇQᴜᴇsᴛᴇᴅ ʙʏ:</b> {mention}"
        f"{progress_text}"
        f"{queue_info}"
    )
    await message.reply(text, link_preview_options=None)


# ── /lang ──────────────────────────────────────────────────────────────────────
@Client.on_message(filters.command("lang"))
async def lang_info_handler(client, message):
    chat_id = message.chat.id
    code = await get_lang(chat_id)
    meta = LANGUAGES.get(code, {"name": code, "flag": "🏳️"})
    text = (
        f"<u><b>{EmojiTag.GLOBE} | ʟᴀɴɢᴜᴀɢᴇ sᴇᴛᴛɪɴɢs</b></u>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ:</b> {meta['flag']} <code>{code}</code> — {meta['name']}\n\n"
        f"<b>ᴀᴠᴀɪʟᴀʙʟᴇ ʟᴀɴɢᴜᴀɢᴇs:</b>\n{lang_list_text()}\n\n"
        f"<i>ᴜsᴇ <code>/setlang &lt;code&gt;</code> ᴛᴏ ᴄʜᴀɴɢᴇ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</i>"
    )
    await message.reply(text, link_preview_options=None)

