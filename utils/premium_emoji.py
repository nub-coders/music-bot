"""
utils/premium_emoji.py — decide ONCE whether this bot may send premium/custom
emoji, then build every message and button accordingly.

Custom emoji (InlineKeyboardButton.icon_custom_emoji_id, and <emoji id="...">
HTML tags in message text/captions) requires the bot owner to have an active
Telegram Premium subscription. Rather than discovering that per send, the bot
asks once at startup:

    setup_premium_emoji(bot, LOGGER_ID, OWNER_ID)

It posts one probe message carrying a custom emoji, checks whether Telegram
kept the entity, and deletes the probe either way — trying LOGGER_ID first,
then OWNER_ID, stopping at the first conclusive answer.

If the answer is NO, apply_premium_emoji() rewrites the emoji constants in
place so everything built afterwards is plain Unicode:

    EmojiTag.*   '<emoji id="123">🎵</emoji>'  ->  '🎵'
    Messages.*   the 112 templates already f-string-built at import
    Emoji.*      the custom-emoji document ids  ->  None
    Buttons.*    the markups already built at import

Nothing is checked again after this. Templates read EmojiTag/Emoji at call
time, so mutating the classes is what makes the ~180 send sites in plugins/
and tools.py correct without touching any of them.
"""

import re
import logging

from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.errors import PremiumAccountRequired
from pyrogram.errors.exceptions.forbidden_403 import (
    PremiumAccountRequired as PremiumAccountRequiredForbidden,
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.emoji import Emoji, EmojiTag

logger = logging.getLogger(__name__)

# kurigram registers PREMIUM_ACCOUNT_REQUIRED under BOTH 400 and 403 as two
# unrelated classes, and pyrogram.errors exports only the 400 one — catching
# just that lets the 403 variant escape uncaught. Always except on the tuple.
PREMIUM_REQUIRED_ERRORS = (PremiumAccountRequired, PremiumAccountRequiredForbidden)

_EMOJI_TAG_RE = re.compile(r'<emoji id="\d+">(.*?)</emoji>')
_LEADING_EMOJI_RE = re.compile(r'^([\u2139]|[^\w\s\d])[\ufe0f\ufe0e]*\s+')

_UNICODE_TO_EMOJI_ID = {
    "🎵": Emoji.MUSIC_NOTE,
    "🎶": Emoji.MUSIC_NOTES,
    "🎧": Emoji.HEADPHONES,
    "🎤": Emoji.MIC,
    "📢": Emoji.BROADCAST,
    "🚀": Emoji.ROCKET,
    "▶️": Emoji.PLAY,
    "▷": Emoji.RESUME,
    "II": Emoji.PAUSE,
    "‣‣I": Emoji.SKIP,
    "▢": Emoji.STOP,
    "🔁": Emoji.LOOP,
    "⚡": Emoji.PING,
    "✅": Emoji.SUCCESS,
    "❌": Emoji.ERROR,
    "⚠️": Emoji.WARNING,
    "🚫": Emoji.STOP,
    "🔐": Emoji.LOCK,
    "🔒": Emoji.LOCK,
    "🔓": Emoji.UNLOCK,
    "🛡": Emoji.SHIELD,
    "👑": Emoji.CROWN,
    "💎": Emoji.DIAMOND,
    "⭐️": Emoji.STAR,
    "👤": Emoji.USER,
    "👥": Emoji.USERS,
    "🔑": Emoji.KEY,
    "🔥": Emoji.FIRE,
    "🌟": Emoji.SPARKLE_STAR,
    "◀️": Emoji.BACK,
    "✖": Emoji.CLOSE,
    "🏠": Emoji.HOME,
    "🔄": Emoji.LOOP,
    "🔗": Emoji.REPO,
    "➡️": Emoji.SKIP,
    "➕": Emoji.ADD,
    "📌": Emoji.PIN,
    "💬": Emoji.CHAT,
    "✉️": Emoji.SEND,
    "🌐": Emoji.GLOBE,
    "🛠️": Emoji.TOOLS,
    "🛠": Emoji.TOOLS,
    "🎨": Emoji.KANG,
    "⚙️": Emoji.SETTINGS,
    "⚙": Emoji.SETTINGS,
    "ℹ️": Emoji.HELP,
    "ℹ": Emoji.HELP,
    "📊": Emoji.STATS,
    "🎬": Emoji.ROCKET,
    "⬇️": Emoji.SKIP,
    "⬇": Emoji.SKIP,
    "‣": Emoji.PLAY,
    "🎞": Emoji.PLAY,
    "🔇": Emoji.PAUSE,
}


def _detect_and_strip_button_emoji(text, icon_id):
    if not isinstance(text, str) or not text:
        return text, icon_id

    # 1. Handle exact playback controls (keep text as fallback)
    if text == "▷":
        return "▷", Emoji.RESUME
    if text == "II":
        return "II", Emoji.PAUSE
    if text == "‣‣I":
        return "‣‣I", Emoji.SKIP
    if text == "▢":
        return "▢", Emoji.STOP

    # 2. Strip leading 📌 if present (e.g. "📌Pɪɴ ✅")
    if text.startswith("📌"):
        text = text[1:].strip()
        icon_id = Emoji.PIN

    # 3. Detect trailing toggle checkmarks/crosses (e.g. "Group ✅", "From bot ⬇️", "BROADCAST🚀🚀")
    for k, val in _UNICODE_TO_EMOJI_ID.items():
        if text.endswith(k) or (k in text and text.endswith(f" {k}")):
            clean_text = text.rsplit(k, 1)[0].strip()
            while clean_text.endswith(k):
                clean_text = clean_text[:-len(k)].strip()
            if clean_text:
                text = clean_text
                icon_id = val
                break

    # 4. If we already have an icon_id, strip any remaining leading emoji/space
    if icon_id:
        text = _LEADING_EMOJI_RE.sub("", text)
        return text, icon_id

    # 5. Otherwise, detect leading emoji (e.g. "🎵 Playback")
    match = _LEADING_EMOJI_RE.match(text)
    if match:
        emoji_char = match.group(1)
        for k, val in _UNICODE_TO_EMOJI_ID.items():
            if emoji_char == k or text.startswith(k):
                icon_id = val
                text = _LEADING_EMOJI_RE.sub("", text)
                break

    return text, icon_id


def strip_unicode_emoji_markup(markup):
    """Returns a NEW InlineKeyboardMarkup with leading unicode emoji removed
    from the text of every button that has an icon_custom_emoji_id set.
    Never mutates the input markup or its buttons."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    stripped_rows = []
    for row in markup.inline_keyboard:
        stripped_row = []
        for btn in row:
            text, icon_id = _detect_and_strip_button_emoji(btn.text, btn.icon_custom_emoji_id)
            stripped_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=btn.callback_data,
                    url=btn.url,
                    web_app=btn.web_app,
                    login_url=btn.login_url,
                    user_id=btn.user_id,
                    switch_inline_query=btn.switch_inline_query,
                    switch_inline_query_current_chat=btn.switch_inline_query_current_chat,
                    callback_game=btn.callback_game,
                    requires_password=btn.requires_password,
                    pay=btn.pay,
                    copy_text=btn.copy_text,
                    icon_custom_emoji_id=icon_id,
                    style=btn.style,
                )
            )
        stripped_rows.append(stripped_row)
    return InlineKeyboardMarkup(stripped_rows)


def _patch_button_init_for_premium():
    _original_init = InlineKeyboardButton.__init__

    def _patched_init(self, text, *args, **kwargs):
        icon_id = kwargs.get("icon_custom_emoji_id")
        is_positional = False
        if icon_id is None and len(args) >= 12:
            icon_id = args[11]
            is_positional = True

        text, icon_id = _detect_and_strip_button_emoji(text, icon_id)

        if is_positional:
            args = list(args)
            args[11] = icon_id
            args = tuple(args)
        else:
            kwargs["icon_custom_emoji_id"] = icon_id

        _original_init(self, text, *args, **kwargs)

    InlineKeyboardButton.__init__ = _patched_init


def strip_custom_emoji_text(text):
    """Collapses <emoji id="...">X</emoji> down to just X. Returns a new string."""
    if not isinstance(text, str):
        return text
    return _EMOJI_TAG_RE.sub(r"\1", text)


def strip_custom_emoji_markup(markup):
    """Returns a NEW InlineKeyboardMarkup with icon_custom_emoji_id removed
    from every button. Never mutates the input markup or its buttons."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    stripped_rows = []
    for row in markup.inline_keyboard:
        stripped_rows.append([
            InlineKeyboardButton(
                text=btn.text,
                callback_data=btn.callback_data,
                url=btn.url,
                web_app=btn.web_app,
                login_url=btn.login_url,
                user_id=btn.user_id,
                switch_inline_query=btn.switch_inline_query,
                switch_inline_query_current_chat=btn.switch_inline_query_current_chat,
                callback_game=btn.callback_game,
                requires_password=btn.requires_password,
                pay=btn.pay,
                copy_text=btn.copy_text,
                icon_custom_emoji_id=None,
                style=btn.style,
            )
            for btn in row
        ])
    return InlineKeyboardMarkup(stripped_rows)


def _as_chat_id(value):
    """Env vars arrive as strings; numeric chat ids must be int for pyrogram,
    usernames stay as-is."""
    text = str(value)
    return int(text) if text.lstrip("-").isdigit() else value


async def _probe_chat(client, chat_id):
    """Post one custom-emoji probe to chat_id, read it back, delete it either
    way. Returns True/False, or None when the probe itself could not run."""
    try:
        sent = await client.send_message(
            chat_id,
            EmojiTag.MUSIC_NOTE,
            parse_mode=ParseMode.HTML,
            disable_notification=True,
        )
    except PREMIUM_REQUIRED_ERRORS:
        return False
    except Exception as exc:
        logger.warning(f"Premium-emoji probe in {chat_id} could not run: {exc}")
        return None

    try:
        # Re-fetch rather than trusting the send result: Telegram may drop the
        # entity silently instead of erroring, which is the whole reason this
        # probe exists — a silent strip raises nothing to catch.
        fetched = await client.get_messages(chat_id, sent.id)
        ok = any(e.type == MessageEntityType.CUSTOM_EMOJI for e in (fetched.entities or []))
    except Exception as exc:
        logger.warning(f"Premium-emoji probe in {chat_id} could not be read back: {exc}")
        ok = None
    finally:
        try:
            await client.delete_messages(chat_id, sent.id)
        except Exception as exc:
            logger.warning(f"Could not delete premium-emoji probe message: {exc}")

    return ok


async def probe_premium_emoji(client, *chat_ids):
    """
    Tries each chat in the order given — LOGGER_ID first, then OWNER_ID — and
    stops at the first conclusive answer. Falsy entries are skipped. Returns
    True (can send premium emoji), False (cannot), or None (no chat could
    answer).
    """
    for chat_id in chat_ids:
        if not chat_id:
            continue
        result = await _probe_chat(client, _as_chat_id(chat_id))
        if result is not None:
            return result
    return None


def apply_premium_emoji(available):
    """
    Bake the verdict into the emoji constants. Called once, at startup.

    available=True is a no-op: the templates are authored with <emoji> tags
    already. available=False rewrites the four places custom emoji can hide.
    Iterates over list(vars(...)) because it reassigns while walking.
    """
    if available:
        logger.info("Premium emoji available — messages will use custom emoji.")
        # Monkey-patch InlineKeyboardButton.__init__ to strip leading emojis
        _patch_button_init_for_premium()

        # Strip leading unicode emoji from already built markups (e.g. Buttons.HELP_HOME, .BACK)
        from utils.button import Buttons
        for name, value in list(vars(Buttons).items()):
            if isinstance(value, InlineKeyboardMarkup):
                setattr(Buttons, name, strip_unicode_emoji_markup(value))
        return True

    # EmojiTag.X -> plain glyph. Templates that f-string EmojiTag at call time
    # (plugins/info.py, plugins/font_cmd.py, ...) pick this up automatically.
    for name, value in list(vars(EmojiTag).items()):
        if not name.startswith("_") and isinstance(value, str):
            setattr(EmojiTag, name, strip_custom_emoji_text(value))

    # Messages.X was f-string-built at import, before the probe could run, so
    # those 112 strings already captured the tags and need their own pass.
    from utils.message import Messages

    for name, value in list(vars(Messages).items()):
        if not name.startswith("_") and isinstance(value, str):
            setattr(Messages, name, strip_custom_emoji_text(value))

    # Emoji.X -> None so buttons built later carry no icon id at all.
    for name, value in list(vars(Emoji).items()):
        if not name.startswith("_") and isinstance(value, int):
            setattr(Emoji, name, None)

    # ...and the markups already built at import (Buttons.HELP_HOME, .BACK)
    # captured the real ids, so they need stripping too.
    from utils.button import Buttons

    for name, value in list(vars(Buttons).items()):
        if isinstance(value, InlineKeyboardMarkup):
            setattr(Buttons, name, strip_custom_emoji_markup(value))

    logger.warning("Premium emoji unavailable — messages baked to plain Unicode emoji.")
    return False


async def setup_premium_emoji(client, *chat_ids):
    """
    Probe once, then bake. The only entry point main.py needs.

    An inconclusive probe (no usable chat) keeps custom emoji on — that is the
    bot's long-standing behaviour, so an unset LOGGER_ID/OWNER_ID degrades
    nothing that worked before.
    """
    verdict = await probe_premium_emoji(client, *chat_ids)
    if verdict is None:
        logger.warning(
            "Premium-emoji probe inconclusive (no usable LOGGER_ID/OWNER_ID chat) — "
            "assuming custom emoji works. Set LOGGER_ID to a chat the bot can post "
            "in if emoji render wrong."
        )
    return apply_premium_emoji(verdict is not False)
