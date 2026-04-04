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
from pyrogram.types import Message

from config import OWNER_ID, ggg, StartTime
from tools import (
    queues, playing, played, active, clients, SUDO,
    get_admin_ids, get_readable_time, convert_bytes,
)
from utils.message import Messages
from utils.lang import get_str, get_lang, LANGUAGES, lang_list_text
from database import find_one, user_sessions, collection

logger = logging.getLogger(__name__)

# Reference to call_py (populated in main.py)
def _call_py():
    return clients.get("call_py")


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

    msg = await message.reply_text(Messages.PINGING, disable_web_page_preview=True)
    for frame in ping_frames:
        await msg.edit(f"```\n{frame}\n```{choice(loading)}")
        await asyncio.sleep(0.3)

    end = datetime.datetime.now()
    ms = (end - start).microseconds / 1000
    status = "EXCELLENT 🟢" if ms < 100 else ("GOOD 🟡" if ms < 200 else "MODERATE 🔴")
    quotes = ["Blazing fast! ⚡", "Speed demon! 🔥", "Lightning quick! ⚡", "Sonic boom! 💨"]

    response = (
        f"╭──────────────────\n"
        f"│   PONG! 🏓\n"
        f"├──────────────────\n"
        f"│ ⌚ Speed: {ms:.2f}ms\n"
        f"│ 📊 Status: {status}\n"
        f"│ ⏱️ Uptime: {uptime}\n"
        f"│ 👑 Owner: {owner.mention()}\n"
        f"╰──────────────────"
    )
    await msg.edit(response + f"\n<b>{choice(quotes)}</b>")


# ── /ac (active calls) ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("ac"))
async def active_chats_info(client, message):
    uid = message.from_user.id
    is_authorized = (
        uid in get_admin_ids(f"{ggg}/admin.txt")
        or str(OWNER_ID) == str(uid)
        or uid in SUDO
    )
    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, disable_web_page_preview=True)

    cp = _call_py()
    if cp is None:
        return await message.reply("❌ Call client not ready.", disable_web_page_preview=True)

    active_calls = await cp.calls
    if active_calls:
        titles = []
        for chat_id in active_calls:
            try:
                chat = await client.get_chat(chat_id)
                titles.append(f"• {chat.title}")
            except Exception:
                titles.append(f"• [ID: {chat_id}]")
        titles_str = "\n".join(titles)
        reply_text = (
            f"<b>Active group calls:</b>\n"
            f"<blockquote expandable>{titles_str}</blockquote>\n"
            f"<b>Total:</b> {len(active_calls)}"
        )
    else:
        reply_text = "<b>Active Voice Chats:</b>\n<blockquote>No active group calls</blockquote>"

    await message.reply_text(reply_text, disable_web_page_preview=True)


# ── /np / /nowplaying ──────────────────────────────────────────────────────────
@Client.on_message(filters.command(["np", "nowplaying"]))
async def now_playing(client, message):
    chat_id = message.chat.id
    song = playing.get(chat_id)

    if not song:
        txt = await get_str(chat_id, "NO_STREAM")
        return await message.reply(txt, disable_web_page_preview=True)

    title = song.get("title", "Unknown")
    duration = song.get("duration", "N/A")
    mode = song.get("mode", "audio")
    by = song.get("by")
    yt_link = song.get("yt_link", "")

    # Elapsed
    start_ts = played.get(chat_id)
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

    queued_count = len(queues.get(chat_id, []))
    queue_info = f"\n<b>ǫᴜᴇᴜᴇ:</b> {queued_count} track(s) up next" if queued_count else ""

    text = (
        f"<u><b>🎶 | ɴᴏᴡ ᴘʟᴀʏɪɴɢ</b></u>\n\n"
        f"<b>ᴛʀᴀᴄᴋ:</b> {title_link}\n"
        f"<b>ᴍᴏᴅᴇ:</b> {mode_label}\n"
        f"<b>ʀᴇQᴜᴇsᴛᴇᴅ ʙʏ:</b> {mention}"
        f"{progress_text}"
        f"{queue_info}"
    )
    await message.reply(text, disable_web_page_preview=True)


# ── /lang ──────────────────────────────────────────────────────────────────────
@Client.on_message(filters.command("lang"))
async def lang_info_handler(client, message):
    chat_id = message.chat.id
    code = await get_lang(chat_id)
    meta = LANGUAGES.get(code, {"name": code, "flag": "🏳️"})
    text = (
        f"<u><b>🌐 | ʟᴀɴɢᴜᴀɢᴇ sᴇᴛᴛɪɴɢs</b></u>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ:</b> {meta['flag']} <code>{code}</code> — {meta['name']}\n\n"
        f"<b>ᴀᴠᴀɪʟᴀʙʟᴇ ʟᴀɴɢᴜᴀɢᴇs:</b>\n{lang_list_text()}\n\n"
        f"<i>ᴜsᴇ <code>/setlang &lt;code&gt;</code> ᴛᴏ ᴄʜᴀɴɢᴇ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</i>"
    )
    await message.reply(text, disable_web_page_preview=True)
