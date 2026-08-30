"""utils/rich_ui.py — Bot API 10.2 Rich Message helpers (Kurigram >= 2.2.25).

Shared, reusable builders + safe senders for native Telegram Rich Blocks.

Why this module exists
----------------------
Bot API 10.2 introduces server-side parsed *rich messages*: HTML supporting
``<h1>``-``<h6>``, ``<table>``, ``<details>``/``<summary>``, ``<mark>``,
``<sub>``/``<sup>`` on top of the classic inline tags. That HTML is only
understood when it travels inside ``InputRichMessage(html=...)`` — the
client-side parser used for ordinary ``text=``/``caption=`` arguments silently
drops those tags. So every rich block must go through the helpers below.

Hard rules encoded here (learned from the API surface):
  * ``Message.edit_text()`` does **not** accept ``rich_message``. Use
    ``Client.edit_message_text(chat_id=..., message_id=..., rich_message=...)``
    or ``CallbackQuery.edit_message_text(rich_message=...)``.
  * Captions can never be rich (``edit_message_caption`` / ``send_photo`` have
    no ``rich_message`` parameter).
  * ``send_rich_message_draft()`` is a ~30 s ephemeral preview. It **must** be
    followed by a real ``send_rich_message()`` or the output is lost.
  * Ephemeral delivery (``receiver_user_id=``) only works in groups /
    supergroups; in private chats we transparently fall back to a normal send.
  * ``InputRichMessage`` with neither ``html`` nor ``markdown`` raises.

Every sender degrades gracefully: if the server rejects the rich HTML (or the
running Kurigram build predates 10.2) the helper falls back to the plain-text
path so no handler can regress.
"""

from __future__ import annotations

import html as _html
import logging
import re

from pyrogram.enums import ParseMode
from pyrogram.types import InputRichMessage, ReplyParameters

logger = logging.getLogger("pyrogram")

__all__ = [
    "RICH_AVAILABLE",
    "rich_esc",
    "rich_heading",
    "rich_note",
    "rich_table",
    "rich_button",
    "rich_details",
    "rich_kv_table",
    "rich_code",
    "rich_to_plain",
    "rich_caption",
    "rich_send",
    "rich_send_blocks",
    "rich_reply",
    "rich_edit",
    "rich_answer",
    "ephemeral_edit",
    "ephemeral_delete",
    "RichDraft",
]

# ── capability probe ─────────────────────────────────────────────────────────
try:  # pragma: no cover - depends on installed Kurigram build
    from pyrogram import Client as _Client

    RICH_AVAILABLE = hasattr(_Client, "send_rich_message")
except Exception:  # pragma: no cover
    RICH_AVAILABLE = False


# ── block-level tags that only exist inside InputRichMessage ─────────────────
_RICH_ONLY_TAGS = (
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "details", "summary", "mark", "sub", "sup",
    "tg-button", "button",
)
_BLOCK_BREAK_RE = re.compile(
    r"</(?:h[1-6]|tr|details|summary|blockquote|table|pre)>", re.I
)
_CELL_BREAK_RE = re.compile(r"</(?:th|td)>", re.I)
# Accepts both the current ``<tg-emoji emoji-id="...">`` spelling (the only one
# Telegram's rich compiler honours) and the legacy ``<emoji id="...">`` form that
# may still live in user-authored text stored in the database.
_EMOJI_TAG_RE = re.compile(
    r'<(?:tg-)?emoji\s+(?:emoji-)?id="[^"]*"\s*>(.*?)</(?:tg-)?emoji>', re.I | re.S
)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_RICH_TAGS_RE = re.compile(
    r"</?(?:h[1-6]|table|thead|tbody|tr|th|td|details|summary|mark|sub|sup|tg-button|button|img)\b", re.I
)


def _has_rich_only_tags(html_text: str) -> bool:
    """Check if html_text contains Bot API 10.2+ rich tags that specifically require InputRichMessage."""
    if not html_text:
        return False
    return bool(_RICH_TAGS_RE.search(str(html_text)))



# ── builders ────────────────────────────────────────────────────────────────

def rich_esc(value) -> str:
    """HTML-escape untrusted text (titles, usernames, exception strings).

    Always run user/remote-supplied strings through this before interpolating
    them into rich HTML, otherwise a stray ``<`` breaks the whole block.
    """
    if value is None:
        return ""
    return _html.escape(str(value), quote=False)


def rich_img(src: str) -> str:
    """Embedded image tag (<img src="...">) for Rich Messages."""
    return f'<img src="{rich_esc(src)}" />' if src else ""


def rich_heading(text: str, level: int = 1) -> str:
    """``<h1>``-``<h6>`` page/section title. Text is passed through verbatim so
    callers may embed ``EmojiTag.*`` / ``<b>`` inside it."""
    level = max(1, min(6, int(level)))
    return f"<h{level}>{text}</h{level}>"


def rich_note(text: str, expandable: bool = False) -> str:
    """``<blockquote>`` note / tip / caveat."""
    attr = " expandable" if expandable else ""
    return f"<blockquote{attr}>{text}</blockquote>"


def rich_code(value) -> str:
    """``<code>`` wrapped, escaped — for commands, IDs and other literals."""
    return f"<code>{rich_esc(value)}</code>"


def rich_button(text: str, url: str = None, callback_data: str = None, style: str = None) -> str:
    """Native Rich Message inline button (<tg-button>) for Telegram Bot API 10.3+.

    Embeddable directly inside tables (<td>), paragraphs, lists, and blockquotes.
    Supports both URL buttons and Callback Data buttons, with optional styling (e.g. style="danger").
    """
    style_attr = f' style="{rich_esc(style)}"' if style else ''
    if callback_data:
        return f'<tg-button callback_data="{rich_esc(callback_data)}"{style_attr}>{text}</tg-button>'
    if url:
        return f'<tg-button url="{rich_esc(url)}"{style_attr}>{text}</tg-button>'
    return f'<tg-button{style_attr}>{text}</tg-button>'


def rich_table(headers, rows, border: int = 1) -> str:
    """Native Rich Block table.

    ``headers`` may be ``None``/empty for a header-less grid. Cells are emitted
    verbatim (so ``EmojiTag``/``<code>`` work) — escape untrusted values with
    :func:`rich_esc` yourself. ``None`` cells render as an empty string.
    """
    parts = [f'<table border="{int(border)}">']
    if headers:
        cells = "".join(f"<th>{'' if h is None else h}</th>" for h in headers)
        parts.append(f"<tr>{cells}</tr>")
    for row in rows or ():
        cells = "".join(f"<td>{'' if c is None else c}</td>" for c in row)
        parts.append(f"<tr>{cells}</tr>")
    parts.append("</table>")
    return "".join(parts)


def rich_kv_table(pairs, headers=None, border: int = 1) -> str:
    """Two-column key/value table from an iterable of ``(key, value)`` pairs.

    Keys are bolded, values are emitted verbatim. ``pairs`` entries whose value
    is ``None`` are skipped so callers can build optional rows inline.
    """
    rows = [
        (f"<b>{k}</b>", v)
        for k, v in (pairs or ())
        if v is not None
    ]
    return rich_table(headers, rows, border=border)


def rich_details(summary: str, body: str, open: bool = False) -> str:
    """Collapsible section — keeps long help/FAQ/debug output out of the way."""
    attr = " open" if open else ""
    return f"<details{attr}><summary>{summary}</summary>{body}</details>"


def rich_to_plain(html_text: str) -> str:
    """Best-effort rich HTML -> readable plain text.

    Used for the automatic fallback path and for ``copy_text=`` button payloads
    (which must copy literal text, never markup).
    """
    if not html_text:
        return ""
    text = str(html_text)
    text = _EMOJI_TAG_RE.sub(r"\1", text)
    # Cell boundaries -> a sentinel so trailing separators can be trimmed.
    text = _CELL_BREAK_RE.sub("\x1f", text)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = _ANY_TAG_RE.sub("", text)
    text = _html.unescape(text)
    text = re.sub(r"\x1f+(?=\s*(?:\n|$))", "", text)
    text = text.replace("\x1f", " \u2022 ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def rich_caption(html_text: str) -> str:
    """Downgrade rich HTML for a **caption**.

    Photo/video captions have no ``rich_message`` parameter, so block tags would
    be silently stripped by Telegram's client-side parser. This keeps the tags
    captions *do* support (``b/i/u/s/code/pre/blockquote/emoji/a``) and flattens
    the rest, letting caption-bound UIs reuse the same builders as rich ones
    instead of maintaining a second copy of every layout.
    """
    return _plain_fallback(html_text)


_VERBATIM_BLOCK_RE = re.compile(
    r'(<(?:table|pre)\b[\s\S]*?</(?:table|pre)>)', re.I
)
_BR_CONVERT_RE = re.compile(
    r'(?<!<br/>)(?<!<br>)(?<!</p>)(?<!</h2>)(?<!</h1>)(?<!</h3>)(?<!</h4>)(?<!</h5>)(?<!</h6>)(?<!</blockquote>)(?<!</summary>)(?<!</details>)(?<!</table>)(?<!</pre>)(?<!</li>)(?<!</ul>)(?<!</ol>)(?<!<hr/>)(?<!<hr>)\n',
    re.I,
)


def _normalize_html(html_text: str) -> str:
    """Normalize HTML for Telegram API & InputRichMessage.
    Fixes unquoted attributes like href=tg://user?id=123 -> href="tg://user?id=123"
    which Kurigram's User.mention() generates and Telegram's HTML parser rejects.
    Upgrades unicode emoji (such as keycap digits in tables) to custom emoji tags if PREMIUM_EMOJI is enabled.
    Preserves line breaks so text in Rich Messages does not collapse into a single line.
    """
    if not html_text:
        return ""
    text = str(html_text).replace("\r\n", "\n")
    try:
        from utils.premium_emoji import PREMIUM_EMOJI, _upgrade_unicode_emoji, strip_custom_emoji_text
        text = _upgrade_unicode_emoji(text) if PREMIUM_EMOJI else strip_custom_emoji_text(text)
    except Exception as e:
        logger.debug(f"[_normalize_html] premium-emoji pass skipped: {e}")
    text = re.sub(r'href=([^\s">]+)', r'href="\1"', text)

    # Convert line breaks to <br/> outside table tags and pre tags to avoid line collapsing in rich HTML
    parts = _VERBATIM_BLOCK_RE.split(text)
    for i in range(0, len(parts), 2):
        if not parts[i]:
            continue
        if i > 0 and parts[i].startswith("\n"):
            leading_nl = ""
            content = parts[i]
            while content.startswith("\n"):
                leading_nl += "\n"
                content = content[1:]
            parts[i] = leading_nl + _BR_CONVERT_RE.sub("<br/>\n", content)
        else:
            parts[i] = _BR_CONVERT_RE.sub("<br/>\n", parts[i])
    return "".join(parts)


def _plain_fallback(html_text: str) -> str:
    """Plain text for a failed rich send, keeping the inline tags Telegram's
    normal HTML parser *does* understand (b/i/u/s/code/pre/blockquote/emoji)."""
    if not html_text:
        return ""
    text = _normalize_html(html_text)
    # Headings -> bold lines, table/detail structure -> newlines & bullets.
    text = re.sub(r"<h[1-6]>(.*?)</h[1-6]>", r"\n<b>\1</b>\n", text, flags=re.I | re.S)
    text = re.sub(r"<summary>(.*?)</summary>", r"<b>\1</b>\n", text, flags=re.I | re.S)
    text = re.sub(r"<mark>(.*?)</mark>", r"<b>\1</b>", text, flags=re.I | re.S)
    text = re.sub(r'<tg-button\s+url="([^"]*)">(.*?)</tg-button>', r'<a href="\1">\2</a>', text, flags=re.I | re.S)
    text = re.sub(r'<tg-button\s+callback_data="[^"]*">(.*?)</tg-button>', r'<b>\1</b>', text, flags=re.I | re.S)
    text = re.sub(r'<tg-button>(.*?)</tg-button>', r'<b>\1</b>', text, flags=re.I | re.S)
    text = re.sub(r"<button[^>]*>(.*?)</button>", r"<b>\1</b>", text, flags=re.I | re.S)
    text = _CELL_BREAK_RE.sub("  ", text)
    text = re.sub(r"</tr>", "\n", text, flags=re.I)
    text = re.sub(r"</table>", "\n", text, flags=re.I)
    text = re.sub(
        r"</?(?:%s)(?:\s[^>]*)?>" % "|".join(_RICH_ONLY_TAGS),
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"<br\s*/?>\n?", "\n", text, flags=re.I)
    text = re.sub(r"[ \t]{2,}", "  ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _input_rich(html_text: str) -> InputRichMessage:
    return InputRichMessage(html=_normalize_html(html_text))


def _is_group(chat_type) -> bool:
    value = getattr(chat_type, "value", chat_type)
    return value in ("group", "supergroup")


# ── senders ─────────────────────────────────────────────────────────────────

async def rich_send(
    client,
    chat_id,
    html_text: str,
    *,
    reply_markup=None,
    markup=None,
    receiver_user_id=None,
    callback_query_id=None,
    reply_to_message_id=None,
    reply_parameters=None,
    message_thread_id=None,
    disable_notification=None,
    protect_content=None,
    effect_id=None,
    **kwargs,
):
    """Send a rich message, falling back to ``send_message`` on any failure.

    ``receiver_user_id`` makes the message *ephemeral* (visible only to that
    user, groups/supergroups only). Never changes any callback data.
    """
    if reply_markup is None:
        reply_markup = markup

    if not html_text:
        return None

    if reply_parameters is None and reply_to_message_id:
        reply_parameters = ReplyParameters(message_id=reply_to_message_id)

    if RICH_AVAILABLE and (receiver_user_id or _has_rich_only_tags(html_text)):
        try:
            return await client.send_rich_message(
                chat_id=chat_id,
                rich_message=_input_rich(html_text),
                reply_markup=reply_markup,
                receiver_user_id=receiver_user_id,
                callback_query_id=callback_query_id,
                reply_parameters=reply_parameters,
                message_thread_id=message_thread_id,
                disable_notification=disable_notification,
                protect_content=protect_content,
                effect_id=effect_id,
            )
        except Exception as e:
            logger.debug(f"[rich_send] rich delivery failed, falling back: {e}")

    # ── standard HTML send ──
    try:
        return await client.send_message(
            chat_id=chat_id,
            text=_plain_fallback(html_text),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            reply_parameters=reply_parameters,
            message_thread_id=message_thread_id,
            disable_notification=disable_notification,
            protect_content=protect_content,
            effect_id=effect_id,
            link_preview_options=None,
        )
    except Exception as e:
        logger.debug(f"[rich_send] plain send failed: {e}")
        return None


async def rich_send_blocks(
    client,
    chat_id: int | str,
    blocks: list,
    *,
    reply_markup=None,
    reply_parameters=None,
    receiver_user_id=None,
    media_file=None,
):
    """Send a structured Rich Message using Bot API 10.3 Block entities (supporting RichTextButton callbacks and local file upload)."""
    try:
        from config import BOT_TOKEN
        token = getattr(client, "bot_token", None) or BOT_TOKEN
        if token:
            payload = {
                "chat_id": chat_id,
                "rich_message": {"blocks": blocks},
            }
            if receiver_user_id:
                payload["ephemeral_message_parameters"] = {"receiver_user_id": receiver_user_id}
            if reply_markup and hasattr(reply_markup, "inline_keyboard"):
                payload["reply_markup"] = {
                    "inline_keyboard": [
                        [
                            {
                                k: v
                                for k, v in {
                                    "text": getattr(btn, "text", ""),
                                    "callback_data": getattr(btn, "callback_data", None),
                                    "url": getattr(btn, "url", None),
                                    "icon_custom_emoji_id": str(getattr(btn, "icon_custom_emoji_id", "")) if getattr(btn, "icon_custom_emoji_id", None) else None,
                                    "style": getattr(btn.style, "value", str(btn.style)) if getattr(btn, "style", None) else None,
                                }.items()
                                if v is not None
                            }
                            for btn in row
                        ]
                        for row in reply_markup.inline_keyboard
                    ]
                }
            if reply_parameters and hasattr(reply_parameters, "message_id"):
                payload["reply_parameters"] = {"message_id": reply_parameters.message_id}

            import httpx
            import json
            import os
            from pyrogram import types, enums
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                has_local = bool(media_file and isinstance(media_file, str) and os.path.exists(media_file))
                if has_local:
                    form_data = {
                        "chat_id": str(chat_id),
                        "rich_message": json.dumps(payload["rich_message"]),
                    }
                    if "reply_markup" in payload:
                        form_data["reply_markup"] = json.dumps(payload["reply_markup"])
                    if "reply_parameters" in payload:
                        form_data["reply_parameters"] = json.dumps(payload["reply_parameters"])
                    if "ephemeral_message_parameters" in payload:
                        form_data["ephemeral_message_parameters"] = json.dumps(payload["ephemeral_message_parameters"])

                    with open(media_file, "rb") as f:
                        files = {"thumb": (os.path.basename(media_file), f.read(), "image/jpeg")}
                        resp = await http_client.post(
                            f"https://api.telegram.org/bot{token}/sendRichMessage",
                            data=form_data,
                            files=files,
                        )
                else:
                    resp = await http_client.post(
                        f"https://api.telegram.org/bot{token}/sendRichMessage",
                        json=payload,
                    )

                if resp.status_code != 200 and any(b.get("type") == "photo" for b in blocks if isinstance(b, dict)):
                    # If Telegram fails to download image URL (400), retry with text blocks
                    clean_blocks = [b for b in blocks if isinstance(b, dict) and b.get("type") != "photo"]
                    payload["rich_message"]["blocks"] = clean_blocks
                    resp = await http_client.post(
                        f"https://api.telegram.org/bot{token}/sendRichMessage",
                        json=payload,
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        msg_id = data["result"]["message_id"]
                        peer_id = chat_id if isinstance(chat_id, int) else 0
                        return types.Message(
                            id=msg_id,
                            chat=types.Chat(id=peer_id, type=enums.ChatType.SUPERGROUP, client=client),
                            reply_markup=reply_markup,
                            client=client,
                        )
                else:
                    logger.warning(f"[rich_send_blocks] Bot API {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.debug(f"[rich_send_blocks] direct Bot API block send failed: {e}")

    return None


async def rich_reply(
    message,
    html_text: str,
    *,
    reply_markup=None,
    markup=None,
    ephemeral: bool = False,
    quote: bool = True,
    client=None,
    **kwargs,
):
    """Reply to an update with rich formatting.

    ``message`` may be a :class:`Message` or a :class:`CallbackQuery`.
    ``ephemeral=True`` makes the reply visible only to the triggering user
    (groups/supergroups only, ignored in PM).
    """
    if reply_markup is None:
        reply_markup = markup

    if not html_text:
        return None

    # CallbackQuery -> extract inner message and sender.
    if hasattr(message, "data") and hasattr(message, "message"):
        app = client or getattr(message, "_client", None)
        cb_user = getattr(message, "from_user", None)
        inner_msg = getattr(message, "message", None)
        chat = getattr(inner_msg, "chat", None)
        if not chat:
            return None
        receiver_user_id = cb_user.id if (ephemeral and cb_user and _is_group(chat.type)) else None
        return await rich_send(
            app,
            chat.id,
            html_text,
            reply_markup=reply_markup,
            receiver_user_id=receiver_user_id,
            reply_to_message_id=getattr(inner_msg, "id", None) if quote else None,
            message_thread_id=getattr(inner_msg, "message_thread_id", None),
        )

    # Standard Message.
    chat = getattr(message, "chat", None)
    if not chat:
        return None
    app = client or getattr(message, "_client", None)
    from_user = getattr(message, "from_user", None)
    receiver_user_id = from_user.id if (ephemeral and from_user and _is_group(chat.type)) else None

    reply_parameters = None
    if quote and not receiver_user_id:
        ephemeral_id = getattr(message, "ephemeral_message_id", None)
        if ephemeral_id:
            reply_parameters = ReplyParameters(ephemeral_message_id=ephemeral_id)
        elif getattr(message, "id", 0):
            reply_parameters = ReplyParameters(message_id=message.id)

    return await rich_send(
        app,
        chat.id,
        html_text,
        reply_markup=reply_markup,
        receiver_user_id=receiver_user_id,
        reply_parameters=reply_parameters,
        message_thread_id=getattr(message, "message_thread_id", None),
    )


async def rich_edit(
    target,
    html_text: str,
    *,
    reply_markup=None,
    markup=None,
    chat_id=None,
    message_id=None,
    client=None,
    **kwargs,
):
    """Edit an existing message into rich HTML.

    ``target`` may be a :class:`CallbackQuery` (uses its own
    ``edit_message_text``), a :class:`Message` (routed through
    ``Client.edit_message_text`` because ``Message.edit_text`` has no
    ``rich_message`` parameter), or a :class:`Client` together with explicit
    ``chat_id`` / ``message_id``.
    """
    if reply_markup is None:
        reply_markup = markup
    if not html_text:
        return None

    # CallbackQuery
    if hasattr(target, "data") and hasattr(target, "message"):
        app = client or getattr(target, "_client", None)
        msg = getattr(target, "message", None)
        if msg and hasattr(msg, "chat") and hasattr(msg, "id"):
            chat_id = msg.chat.id
            message_id = msg.id
        if app is not None and chat_id and message_id:
            return await _rich_edit_via_client(
                app, chat_id, message_id, html_text, reply_markup
            )
        try:
            return await target.edit_message_text(
                _plain_fallback(html_text), parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
        except Exception as e:
            logger.debug(f"[rich_edit] cq plain edit failed: {e}")
            return None

    # Message instance.
    if hasattr(target, "chat") and hasattr(target, "id"):
        app = client or getattr(target, "_client", None)
        chat_id = target.chat.id
        message_id = target.id
        if app is not None:
            return await _rich_edit_via_client(
                app, chat_id, message_id, html_text, reply_markup
            )
        try:
            return await target.edit_text(
                _plain_fallback(html_text),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                link_preview_options=None,
            )
        except Exception as e:
            logger.debug(f"[rich_edit] message plain edit failed: {e}")
            return None

    # Bare Client + ids.
    return await _rich_edit_via_client(
        target, chat_id, message_id, html_text, reply_markup
    )


async def _rich_edit_via_client(app, chat_id, message_id, html_text, reply_markup):
    if chat_id is None or not message_id:
        logger.debug("[rich_edit] missing chat_id/message_id")
        return None

    plain_text = _plain_fallback(html_text)

    if RICH_AVAILABLE and _has_rich_only_tags(html_text):
        try:
            from pyrogram import raw, utils, types
            peer = await app.resolve_peer(chat_id)
            input_rich = _input_rich(html_text).write()
            parsed = await utils.parse_text_entities(app, plain_text, ParseMode.HTML, None)
            r = await app.invoke(
                raw.functions.messages.EditMessage(
                    peer=peer,
                    id=message_id,
                    message=parsed["message"],
                    entities=parsed["entities"],
                    rich_message=input_rich,
                    reply_markup=await reply_markup.write(app) if reply_markup else None,
                )
            )
            for i in r.updates:
                if isinstance(i, (raw.types.UpdateEditMessage, raw.types.UpdateEditChannelMessage)):
                    return await types.Message._parse(
                        app, i.message, {i.id: i for i in r.users}, {i.id: i for i in r.chats}
                    )
        except Exception as e:
            logger.debug(f"[rich_edit] raw rich edit failed, falling back: {e}")

    try:
        return await app.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=plain_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            link_preview_options=None,
        )
    except Exception as e:
        logger.debug(f"[rich_edit] plain edit failed: {e}")
        return None


async def rich_answer(
    callback_query,
    html_text: str,
    *,
    reply_markup=None,
    client=None,
):
    """Ephemeral rich response to a button press.

    Only the pressing user sees it (groups/supergroups); in private chats it
    falls back to a normal message so nothing is swallowed. Button behaviour and
    callback data are untouched — this replaces noisy *public* confirmations.
    """
    if not html_text:
        return None

    app = client or getattr(callback_query, "_client", None)
    message = getattr(callback_query, "message", None)
    chat = getattr(message, "chat", None)
    user = getattr(callback_query, "from_user", None)
    if app is None or chat is None:
        return None

    receiver_user_id = user.id if (user and _is_group(getattr(chat, "type", None))) else None
    return await rich_send(
        app,
        chat.id,
        html_text,
        reply_markup=reply_markup,
        receiver_user_id=receiver_user_id,
        callback_query_id=getattr(callback_query, "id", None) if receiver_user_id else None,
        message_thread_id=getattr(message, "message_thread_id", None),
    )


# ── ephemeral message maintenance ───────────────────────────────────────────

def _ephemeral_receiver(message):
    """``(chat_id, receiver_user_id, ephemeral_message_id)`` or ``None``."""
    eph_id = getattr(message, "ephemeral_message_id", None)
    if not eph_id:
        return None
    chat = getattr(message, "chat", None)
    receiver = getattr(message, "receiver_user", None) or getattr(message, "from_user", None)
    receiver_id = getattr(receiver, "id", None)
    if chat is None or not receiver_id:
        return None
    return chat.id, receiver_id, eph_id


async def ephemeral_edit(message, html_text: str, *, reply_markup=None, client=None):
    """Edit an ephemeral message via ``edit_ephemeral_message_text``.

    Ordinary ``edit_message_text`` cannot address an ephemeral message (its
    ``id`` is 0), so this uses the dedicated Bot API 10.2 method. That method
    takes plain ``text=`` only, so the HTML is flattened with
    :func:`rich_caption`. Non-ephemeral messages fall through to
    :func:`rich_edit` so callers don't have to branch.
    """
    if not html_text:
        return None
    target = _ephemeral_receiver(message)
    if target is None:
        return await rich_edit(message, html_text, reply_markup=reply_markup, client=client)

    app = client or getattr(message, "_client", None)
    if app is None:
        return None
    chat_id, receiver_id, eph_id = target
    try:
        return await app.edit_ephemeral_message_text(
            chat_id=chat_id,
            receiver_user_id=receiver_id,
            ephemeral_message_id=eph_id,
            text=rich_caption(html_text),
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.debug(f"[ephemeral_edit] failed: {e}")
        return None


async def ephemeral_delete(message, *, client=None) -> bool:
    """Delete an ephemeral message via ``delete_ephemeral_message``.

    Falls back to ``Message.delete()`` for ordinary messages. Returns ``False``
    instead of raising so cleanup paths stay quiet.
    """
    if message is None:
        return False
    target = _ephemeral_receiver(message)
    app = client or getattr(message, "_client", None)
    if target is None:
        try:
            await message.delete()
            return True
        except Exception as e:
            logger.debug(f"[ephemeral_delete] plain delete failed: {e}")
            return False

    if app is None:
        return False
    chat_id, receiver_id, eph_id = target
    try:
        await app.delete_ephemeral_message(
            chat_id=chat_id,
            receiver_user_id=receiver_id,
            ephemeral_message_id=eph_id,
        )
        return True
    except Exception as e:
        logger.debug(f"[ephemeral_delete] failed: {e}")
        return False


# ── streaming drafts ────────────────────────────────────────────────────────

class RichDraft:
    """Streaming progress via ``send_rich_message_draft`` + a final real send.

    A draft is a ~30 s ephemeral preview the client animates in place; it is
    **not** persisted. Always call :meth:`finish` (the async context manager
    does it for you via the last pushed HTML) so the result survives.

    Usage::

        async with RichDraft(client, chat_id) as draft:
            await draft.update(rich_heading("Searching…"))
            ...
            await draft.finish(final_html, reply_markup=kb)

    If :meth:`finish` is never called explicitly, ``__aexit__`` finalises with
    the most recent ``update()`` payload, so no progress output is ever lost.
    On any draft failure the object silently downgrades to "final send only",
    keeping handlers working on pre-10.2 builds.
    """

    __slots__ = (
        "client", "chat_id", "message_thread_id", "draft_id",
        "_last_html", "_finished", "_result", "_drafts_ok",
    )

    def __init__(self, client, chat_id, *, message_thread_id=None, draft_id=None):
        self.client = client
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.draft_id = draft_id or self._new_id(client)
        self._last_html = None
        self._finished = False
        self._result = None
        self._drafts_ok = RICH_AVAILABLE and hasattr(client, "send_rich_message_draft")

    @staticmethod
    def _new_id(client):
        try:
            value = client.rnd_id()
        except Exception:
            import random

            value = random.getrandbits(63)
        return value or 1

    async def update(self, html_text: str) -> bool:
        """Push a progress frame. Cheap and best-effort — never raises."""
        if not html_text:
            return False
        self._last_html = html_text
        if not self._drafts_ok:
            return False
        try:
            await self.client.send_rich_message_draft(
                chat_id=self.chat_id,
                draft_id=self.draft_id,
                rich_message=_input_rich(html_text),
                message_thread_id=self.message_thread_id,
            )
            return True
        except Exception as e:
            logger.debug(f"[RichDraft] draft update failed, disabling drafts: {e}")
            self._drafts_ok = False
            return False

    async def finish(self, html_text: str = None, *, reply_markup=None, **kwargs):
        """Persist the final message (this is what the user keeps)."""
        self._finished = True
        final_html = html_text or self._last_html
        if not final_html:
            return None
        self._result = await rich_send(
            self.client,
            self.chat_id,
            final_html,
            reply_markup=reply_markup,
            message_thread_id=self.message_thread_id,
            **kwargs,
        )
        return self._result

    @property
    def result(self):
        """The persisted :class:`Message` from :meth:`finish`, if any."""
        return self._result

    def discard(self) -> None:
        """Finalise without persisting anything.

        For operations whose real output is a *different* artefact (a sticker, a
        photo, an uploaded file): the draft was only a progress indicator, and
        it expires on its own. Suppresses the auto-``finish()`` in
        ``__aexit__`` so no stray progress message is left behind.
        """
        self._finished = True
        self._last_html = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if not self._finished and exc_type is None:
            await self.finish()
        return False
