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
from pyrogram.enums import ChatType, ButtonStyle

from config import OWNER_ID, ggg, StartTime
from tools import (
    state, clients, SUDO, assistants, calls, assistant_info,
    get_admin_ids, get_readable_time, convert_bytes,
    get_assistant, set_assistant, change_assistant,
    get_call_client, get_assistant_count,
)
from utils.emoji import Emoji, EmojiTag
from utils.message import Messages
from utils.lang import get_str, get_lang, LANGUAGES, lang_list_text
from utils.rich_ui import (
    RichDraft, rich_code, rich_details, rich_edit, rich_esc, rich_heading,
    rich_kv_table, rich_note, rich_reply, rich_table,
)
from database import user_sessions, collection

logger = logging.getLogger(__name__)


def _assistant_buttons(active_num):
    """Assistant picker keyboard. Callback data is unchanged (``change_ast_<idx>``);
    the selected entry is highlighted with SUCCESS, the rest stay neutral."""
    buttons = []
    row = []
    for idx in sorted(assistants.keys()):
        mark = "✓ " if idx == active_num else ""
        row.append(InlineKeyboardButton(
            f"{mark}Assistant {idx}",
            callback_data=f"change_ast_{idx}",
            style=ButtonStyle.SUCCESS if idx == active_num else ButtonStyle.DEFAULT,
            icon_custom_emoji_id=Emoji.TICK if idx == active_num else Emoji.HEADPHONES,
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return buttons


def _assistant_panel(active_num, active_name) -> str:
    """Shared assistant-settings card for the command and its callback."""
    return (
        rich_heading(f"{EmojiTag.SETTINGS} ɢʀᴏᴜᴘ ᴀssɪsᴛᴀɴᴛ sᴇᴛᴛɪɴɢs", 1)
        + rich_kv_table([
            (f"{EmojiTag.HEADPHONES} ᴀssɪsᴛᴀɴᴛ", rich_code(f"Assistant {active_num}")),
            (f"{EmojiTag.USER} ɴᴀᴍᴇ", rich_esc(active_name)),
            (f"{EmojiTag.STATS} ᴀᴠᴀɪʟᴀʙʟᴇ", rich_code(len(assistants))),
        ])
        + rich_note(f"{EmojiTag.INFO} <i>Select an assistant below to assign to this group.</i>")
    )


# ── /ping ──────────────────────────────────────────────────────────────────────
@Client.on_message(filters.command("ping"))
async def pingme(client, message):
    uptime = await get_readable_time(int(time.time() - StartTime))
    start = datetime.datetime.now()
    owner = await client.get_users(OWNER_ID) if OWNER_ID else None

    ping_frames = [
        "█▒▒▒▒▒▒▒▒▒ 10%", "███▒▒▒▒▒▒▒ 30%", "█████▒▒▒▒▒ 50%",
        "███████▒▒▒ 70%", "█████████▒ 90%", "██████████ 100%",
    ]
    loading = ["🕐","🕑","🕒","🕓","🕔","🕕","🕖","🕗","🕘","🕙","🕚","🕛"]

    msg = await rich_reply(message, rich_note(Messages.PINGING), client=client)
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

    owner_line = None if owner is None else rich_esc(owner.first_name)
    response = (
        rich_heading(f"{EmojiTag.PING} ᴘᴏɴɢ!", 1)
        + rich_kv_table([
            (f"{EmojiTag.BOLT} sᴘᴇᴇᴅ", rich_code(f"{ms:.2f}ms")),
            (f"{EmojiTag.STATS} sᴛᴀᴛᴜs", status),
            (f"{EmojiTag.LOADING} ᴜᴘᴛɪᴍᴇ", rich_code(uptime)),
            (f"{EmojiTag.CROWN} ᴏᴡɴᴇʀ", owner_line),
            (f"{EmojiTag.HEADPHONES} ᴀssɪsᴛᴀɴᴛs", rich_code(f"{len(assistants)} Online")),
        ])
        + rich_note(f"<b>{choice(quotes)}</b>")
    )
    await rich_edit(msg, response, client=client)


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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

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
                return (rich_esc(chat.title), rich_code(f"Ast {ast_num}"))
            except Exception:
                return (f"<i>[ID: {rich_code(cid)}]</i>", rich_code("?"))

        rows = await asyncio.gather(*[_fetch_title(cid) for cid in all_active])
        table = rich_table(["ᴄʜᴀᴛ", "ᴀssɪsᴛᴀɴᴛ"], rows)
        # Long lists get folded away so the chat isn't flooded.
        body = table if len(rows) <= 10 else rich_details(
            f"{EmojiTag.HEADPHONES} sʜᴏᴡ ᴀʟʟ {len(rows)} ᴄʜᴀᴛs", table
        )
        reply_text = (
            rich_heading(f"{EmojiTag.HEADPHONES} ᴀᴄᴛɪᴠᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟs ({len(all_active)})", 1)
            + body
            + rich_note(f"{EmojiTag.INFO} <b>ᴛᴏᴛᴀʟ ᴀssɪsᴛᴀɴᴛs:</b> {rich_code(len(assistants))}")
        )
    else:
        reply_text = (
            rich_heading(f"{EmojiTag.HEADPHONES} ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs", 1)
            + rich_note(f"{EmojiTag.INFO} No active group calls")
        )

    await rich_reply(message, reply_text, client=client)


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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    if not assistants:
        return await rich_reply(
            message,
            rich_note("<b>No active assistant accounts connected.</b>"),
            ephemeral=True,
            client=client,
        )

    rows = []
    for idx, ast in assistants.items():
        info = assistant_info.get(idx, {})
        name = info.get("name") or getattr(ast.me, "first_name", f"Assistant {idx}")
        username = f"@{info.get('username')}" if info.get("username") else f"ID: {info.get('id', 'N/A')}"
        active_count = len(state.assistant_active.get(idx, set()))
        rows.append((
            f"<b>{idx}</b>",
            rich_esc(name),
            rich_code(username),
            rich_code(active_count),
        ))

    await rich_reply(
        message,
        rich_heading(f"{EmojiTag.CROWN} ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴀssɪsᴛᴀɴᴛs ({len(assistants)})", 1)
        + rich_table(["#", "ɴᴀᴍᴇ", "ʜᴀɴᴅʟᴇ", f"{EmojiTag.MIC} sᴛʀᴇᴀᴍS"], rows),
        client=client,
    )


# ── /changeassistant / /assistant ─────────────────────────────────────────────
@Client.on_message(filters.command(["changeassistant", "changeast", "assistant"]))
async def change_assistant_handler(client, message):
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return await rich_reply(message, rich_note(Messages.GROUP_ONLY), ephemeral=True, client=client)

    chat_id = message.chat.id
    current_num, userbot, call_py = await get_assistant(chat_id)
    cur_info = assistant_info.get(current_num, {})
    cur_name = cur_info.get("name") or (getattr(userbot.me, "first_name", f"Assistant {current_num}") if userbot else f"Assistant {current_num}")

    await rich_reply(
        message,
        _assistant_panel(current_num, cur_name),
        reply_markup=InlineKeyboardMarkup(_assistant_buttons(current_num)),
        client=client,
    )


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

    try:
        await rich_edit(
            callback_query,
            _assistant_panel(ast_idx, name),
            reply_markup=InlineKeyboardMarkup(_assistant_buttons(ast_idx)),
        )
    except Exception:
        pass
    await callback_query.answer(f"Switched group assistant to Assistant {ast_idx}!", show_alert=False)


# ── /leaveall (Owner / Sudo Only) ─────────────────────────────────────────────
@Client.on_message(filters.command("leaveall"))
async def leave_all_handler(client, message):
    uid = message.from_user.id if message.from_user else None
    if str(OWNER_ID) != str(uid) and (not uid or uid not in SUDO):
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    total_left = 0
    failed = 0

    # Streaming draft: live progress while scanning, then one persisted report.
    async with RichDraft(client, message.chat.id) as draft:
        await draft.update(
            rich_heading(f"{EmojiTag.LOADING} ʟᴇᴀᴠɪɴɢ ɪᴅʟᴇ ᴄʜᴀᴛs", 1)
            + rich_note("<b>Cleaning idle chats across all assistants...</b>")
        )
        per_assistant = []

        for idx, ast in assistants.items():
            left_here = 0
            try:
                async for dialog in ast.get_dialogs():
                    chat = dialog.chat
                    chat_type = str(getattr(chat, "type", "")).lower()
                    if "group" in chat_type or "supergroup" in chat_type:
                        if chat.id not in state.active:
                            try:
                                await ast.leave_chat(chat.id)
                                total_left += 1
                                left_here += 1
                                await asyncio.sleep(1.0)
                            except Exception:
                                failed += 1
            except Exception as e:
                logger.warning(f"[leaveall] Assistant {idx} error: {e}")

            per_assistant.append((rich_code(f"Assistant {idx}"), rich_code(left_here)))
            # One frame per assistant -- no extra round-trips inside the inner loop.
            await draft.update(
                rich_heading(f"{EmojiTag.LOADING} ʟᴇᴀᴠɪɴɢ ɪᴅʟᴇ ᴄʜᴀᴛs", 1)
                + rich_kv_table([
                    (f"{EmojiTag.HEADPHONES} sᴄᴀɴɴᴇᴅ", rich_code(f"{len(per_assistant)}/{len(assistants)}")),
                    (f"{EmojiTag.SUCCESS} ʟᴇ꩖ᴛ", rich_code(total_left)),
                ])
            )

        await draft.finish(
            rich_heading(f"{EmojiTag.SUCCESS} ʟᴇᴀᴠᴇᴀʟʟ ᴄᴏᴍᴘʟᴇᴛᴇ", 1)
            + rich_kv_table([
                (f"{EmojiTag.SUCCESS} ᴄʜᴀᴛs ʟᴇ꩖ᴛ", rich_code(total_left)),
                (f"{EmojiTag.ERROR} ꩖ᴀɪʟᴇᴅ", rich_code(failed) if failed else None),
                (f"{EmojiTag.HEADPHONES} ᴀssɪsᴛᴀɴᴛs", rich_code(len(assistants))),
            ])
            + rich_details(
                f"{EmojiTag.STATS} ᴘᴇʀ-ᴀssɪsᴛᴀɴᴛ ʙʀᴇᴀᴋᴅᴏᴡɴ",
                rich_table(["ᴀssɪsᴛᴀɴᴛ", "ʟᴇ꩖ᴛ"], per_assistant),
            )
        )


# ── /np / /nowplaying ──────────────────────────────────────────────────────────
@Client.on_message(filters.command(["np", "nowplaying"]))
async def now_playing(client, message):
    chat_id = message.chat.id
    song = state.playing.get(chat_id)

    if not song:
        txt = await get_str(chat_id, "NO_STREAM")
        return await rich_reply(message, rich_note(txt), ephemeral=True, client=client)

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

    # Progress bar (kept as a monospace bar -- it reads better than a table cell)
    progress_text = None
    if elapsed and duration and duration != "N/A":
        try:
            dur_parts = duration.split(":")
            total_s = sum(int(x) * 60 ** i for i, x in enumerate(reversed(dur_parts)))
            elapsed_s_val = int(time.time() - start_ts)
            pct = min(elapsed_s_val / max(total_s, 1), 1.0)
            filled = int(pct * 10)
            bar = "▓" * filled + "░" * (10 - filled)
            progress_text = f"<code>{elapsed} {bar} {duration}</code>"
        except Exception:
            pass

    mention = by.mention() if by and hasattr(by, "mention") else str(by or "Unknown")
    mode_label = f"{EmojiTag.MUSIC_NOTE} Audio" if mode == "audio" else f"{EmojiTag.PLAY} Video"
    title_link = f'<a href="{yt_link}">{rich_esc(title)}</a>' if yt_link else f"<b>{rich_esc(title)}</b>"

    queued_count = len(state.queues.get(chat_id, []))

    # Public card -- everyone in the chat is listening to this.
    text = (
        rich_heading(f"{EmojiTag.NOW_PLAYING} ɴᴏᴡ ᴘʟᴀʏɪɴɢ", 1)
        + rich_kv_table([
            (f"{EmojiTag.MUSIC_NOTE} ᴛʀᴀᴄᴋ", title_link),
            (f"{EmojiTag.PLAY} ᴍᴏᴅᴇ", mode_label),
            (f"{EmojiTag.INFO} ᴅᴜʀᴀᴛɪᴏɴ", rich_code(duration)),
            (f"{EmojiTag.USER} ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ", mention),
            (f"{EmojiTag.LOADING} ᴘʀᴏɢʀᴇss", progress_text),
            (f"{EmojiTag.QUEUE_ICON} ǫᴜᴇᴜᴇ", f"{queued_count} track(s) up next" if queued_count else None),
        ])
    )
    await rich_reply(message, text, client=client)


# ── /lang ──────────────────────────────────────────────────────────────────────
@Client.on_message(filters.command("lang"))
async def lang_info_handler(client, message):
    chat_id = message.chat.id
    code = await get_lang(chat_id)
    meta = LANGUAGES.get(code, {"name": code, "flag": "🏳️"})
    rows = [
        (
            f"{m['flag']} {rich_code(c)}",
            rich_esc(m["name"]),
            f"{EmojiTag.SUCCESS}" if c == code else "",
        )
        for c, m in sorted(LANGUAGES.items())
    ]
    text = (
        rich_heading(f"{EmojiTag.GLOBE} ʟᴀɴɢᴜᴀɢᴇ sᴇᴛᴛɪɴɢs", 1)
        + rich_kv_table([
            (f"{EmojiTag.SUCCESS} ᴄᴜʀʀᴇɴᴛ", f"{meta['flag']} {rich_code(code)} — {rich_esc(meta['name'])}"),
        ])
        + rich_details(
            f"{EmojiTag.GLOBE} ᴀᴠᴀɪʟᴀʙʟᴇ ʟᴀɴɢᴜᴀɢᴇs ({len(LANGUAGES)})",
            rich_table(["ᴄᴏᴅᴇ", "ʟᴀɴɢᴜᴀɢᴇ", ""], rows),
        )
        + rich_note(f"{EmojiTag.INFO} <i>ᴜsᴇ</i> {rich_code('/setlang <code>')} <i>ᴛᴏ ᴄʜᴀɴɢᴇ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</i>")
    )
    await rich_reply(message, text, client=client)

