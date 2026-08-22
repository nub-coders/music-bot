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

from pyrogram.types import InputRichMessage, ReplyParameters

logger = logging.getLogger("pyrogram")

__all__ = [
    "RICH_AVAILABLE",
    "rich_esc",
    "rich_heading",
    "rich_note",
    "rich_table",
    "rich_details",
    "rich_kv_table",
    "rich_code",
    "rich_to_plain",
    "rich_caption",
    "rich_send",
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


# ── builders ────────────────────────────────────────────────────────────────

def rich_esc(value) -> str:
    """HTML-escape untrusted text (titles, usernames, exception strings).

    Always run user/remote-supplied strings through this before interpolating
    them into rich HTML, otherwise a stray ``<`` breaks the whole block.
    """
    if value is None:
        return ""
    return _html.escape(str(value), quote=False)


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


def _plain_fallback(html_text: str) -> str:
    """Plain text for a failed rich send, keeping the inline tags Telegram's
    normal HTML parser *does* understand (b/i/u/s/code/pre/blockquote/emoji)."""
    if not html_text:
        return ""
    text = str(html_text)
    # Headings -> bold lines, table/detail structure -> newlines & bullets.
    text = re.sub(r"<h[1-6]>(.*?)</h[1-6]>", r"<b>\1</b>\n", text, flags=re.I | re.S)
    text = re.sub(r"<summary>(.*?)</summary>", r"<b>\1</b>\n", text, flags=re.I | re.S)
    text = re.sub(r"<mark>(.*?)</mark>", r"<b>\1</b>", text, flags=re.I | re.S)
    text = _CELL_BREAK_RE.sub("  ", text)
    text = re.sub(r"</tr>", "\n", text, flags=re.I)
    text = re.sub(
        r"</?(?:%s)(?:\s[^>]*)?>" % "|".join(_RICH_ONLY_TAGS),
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"[ \t]{2,}", "  ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _input_rich(html_text: str) -> InputRichMessage:
    return InputRichMessage(html=html_text)


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
    receiver_user_id=None,
    callback_query_id=None,
    reply_to_message_id=None,
    reply_parameters=None,
    message_thread_id=None,
    disable_notification=None,
    protect_content=None,
    effect_id=None,
):
    """Send a rich message, falling back to ``send_message`` on any failure.

    ``receiver_user_id`` makes the message *ephemeral* (visible only to that
    user, groups/supergroups only). Never changes any callback data.
    """
    if not html_text:
        return None

    if reply_parameters is None and reply_to_message_id:
        reply_parameters = ReplyParameters(message_id=reply_to_message_id)

    if RICH_AVAILABLE:
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

    # ── plain-text fallback ──
    try:
        return await client.send_message(
            chat_id,
            _plain_fallback(html_text),
            reply_markup=reply_markup,
            reply_parameters=reply_parameters,
            message_thread_id=message_thread_id,
            disable_notification=disable_notification,
            protect_content=protect_content,
            link_preview_options=None,
        )
    except Exception as e:
        logger.error(f"[rich_send] plain fallback failed for {chat_id}: {e}")
        return None


async def rich_reply(
    message,
    html_text: str,
    *,
    ephemeral: bool = False,
    quote: bool = True,
    reply_markup=None,
    client=None,
):
    """Reply to ``message`` with rich HTML.

    ``ephemeral=True`` delivers privately to the sender in groups/supergroups;
    in private chats (where ephemeral is unsupported) it degrades to a normal
    reply so the user still sees the response.
    """
    if not html_text:
        return None

    app = client or getattr(message, "_client", None)
    if app is None:
        logger.debug("[rich_reply] no client bound to message; using message.reply")
        return await message.reply(
            _plain_fallback(html_text),
            reply_markup=reply_markup,
            link_preview_options=None,
        )

    chat = getattr(message, "chat", None)
    from_user = getattr(message, "from_user", None)
    receiver_user_id = None
    if ephemeral and from_user and _is_group(getattr(chat, "type", None)):
        receiver_user_id = from_user.id

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
    chat_id=None,
    message_id=None,
    client=None,
):
    """Edit an existing message into rich HTML.

    ``target`` may be a :class:`CallbackQuery` (uses its own
    ``edit_message_text``), a :class:`Message` (routed through
    ``Client.edit_message_text`` because ``Message.edit_text`` has no
    ``rich_message`` parameter), or a :class:`Client` together with explicit
    ``chat_id`` / ``message_id``.
    """
    if not html_text:
        return None

    # CallbackQuery — has a rich-aware edit_message_text of its own.
    if hasattr(target, "edit_message_text") and hasattr(target, "data"):
        if RICH_AVAILABLE:
            try:
                return await target.edit_message_text(
                    rich_message=_input_rich(html_text),
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.debug(f"[rich_edit] cq rich edit failed, falling back: {e}")
        try:
            return await target.edit_message_text(
                _plain_fallback(html_text), reply_markup=reply_markup
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
    if RICH_AVAILABLE:
        try:
            return await app.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                rich_message=_input_rich(html_text),
                reply_markup=reply_markup,
            )
        except Exception as e:
            logger.debug(f"[rich_edit] rich edit failed, falling back: {e}")
    try:
        return await app.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_plain_fallback(html_text),
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
