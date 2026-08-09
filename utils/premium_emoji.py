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

The answer is stored in PREMIUM_EMOJI and enforced from the two places every
emoji is born, so no send site has to know about it:

    InlineKeyboardButton.__init__   every button, whenever it is built
    HTML.parse                      every message text and caption
                                    (Markdown.parse delegates to it)

    PREMIUM_EMOJI = True   buttons drop their unicode text emoji for the custom
                           icon; message glyphs upgrade to <emoji> tags
    PREMIUM_EMOJI = False  buttons never carry an icon id; <emoji> tags collapse
                           back to the plain glyph

On a NO verdict the constants are also rewritten in place, so anything that
reads them without going through a parser is already correct:

    EmojiTag.*   '<emoji id="123">🎵</emoji>'  ->  '🎵'
    Messages.*   the 112 templates already f-string-built at import
    Emoji.*      the custom-emoji document ids  ->  None
    Buttons.*    the markups already built at import

Nothing is probed again after startup.
"""

import re
import logging

from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.errors import PremiumAccountRequired
from pyrogram.errors.exceptions.forbidden_403 import (
    PremiumAccountRequired as PremiumAccountRequiredForbidden,
)
from pyrogram.parser.html import HTML
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.emoji import Emoji, EmojiTag

logger = logging.getLogger(__name__)

# The verdict. Set once by apply_premium_emoji(), read on every button build
# and every message parse. Starts True: an inconclusive probe keeps custom
# emoji on, which is the bot's long-standing behaviour.
PREMIUM_EMOJI = True

_patched = False

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


# Button-only fallback glyphs — plain shapes, not emoji. A custom-emoji entity
# may only cover an actual emoji, so message text never upgrades these.
_BUTTON_ONLY_GLYPHS = {"II", "‣‣I", "▷", "▢", "‣"}

# Longest match first, so "⚙️" (with the variation selector) beats "⚙".
_UPGRADE_RE = re.compile("|".join(
    re.escape(g)
    for g in sorted(set(_UNICODE_TO_EMOJI_ID) - _BUTTON_ONLY_GLYPHS, key=len, reverse=True)
))

# Spans the upgrade must leave alone: already-tagged emoji (would nest twice)
# and code/pre (Telegram rejects a custom-emoji entity inside them).
_NO_UPGRADE_RE = re.compile(
    r'(<emoji\b[^>]*>.*?</emoji>|<code\b[^>]*>.*?</code>|<pre\b[^>]*>.*?</pre>)',
    re.S,
)


def _upgrade_unicode_emoji(text):
    """'🎵' -> '<emoji id="...">🎵</emoji>' for every glyph we hold an id for."""
    if not isinstance(text, str) or not text:
        return text
    parts = _NO_UPGRADE_RE.split(text)
    for i in range(0, len(parts), 2):  # odd indices are the skipped spans
        parts[i] = _UPGRADE_RE.sub(
            lambda m: f'<emoji id="{_UNICODE_TO_EMOJI_ID[m.group(0)]}">{m.group(0)}</emoji>',
            parts[i],
        )
    return "".join(parts)


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


def _rebuild_markup(markup):
    """Markups built at import (Buttons.HELP_HOME, .BACK) were constructed
    before the patch existed, so their buttons never saw the verdict. Re-run
    them through the constructor. Never mutates the input markup."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    return InlineKeyboardMarkup([
        [
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
                icon_custom_emoji_id=btn.icon_custom_emoji_id,
                style=btn.style,
            )
            for btn in row
        ]
        for row in markup.inline_keyboard
    ])


def _install_patches():
    """Enforce PREMIUM_EMOJI at the two choke points, once. Both read the flag
    at call time, so the verdict can be baked after the patches are in."""
    global _patched
    if _patched:
        return
    _patched = True

    _original_init = InlineKeyboardButton.__init__

    def _patched_init(self, text, *args, **kwargs):
        icon_id = kwargs.get("icon_custom_emoji_id")
        is_positional = False
        if icon_id is None and len(args) >= 12:
            icon_id = args[11]
            is_positional = True

        if PREMIUM_EMOJI:
            text, icon_id = _detect_and_strip_button_emoji(text, icon_id)
        else:
            icon_id = None

        if is_positional:
            args = list(args)
            args[11] = icon_id
            args = tuple(args)
        else:
            kwargs["icon_custom_emoji_id"] = icon_id

        _original_init(self, text, *args, **kwargs)

    InlineKeyboardButton.__init__ = _patched_init

    _original_parse = HTML.parse

    async def _patched_parse(self, text):
        # ponytail: HTML.parse only — Markdown.parse ends by delegating here,
        # so both modes are covered. ParseMode.DISABLED bypasses it, and the
        # baked constants cover that case.
        text = _upgrade_unicode_emoji(text) if PREMIUM_EMOJI else strip_custom_emoji_text(text)
        return await _original_parse(self, text)

    HTML.parse = _patched_parse


def strip_custom_emoji_text(text):
    """Collapses <emoji id="...">X</emoji> down to just X. Returns a new string."""
    if not isinstance(text, str):
        return text
    return _EMOJI_TAG_RE.sub(r"\1", text)


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
    Store the verdict and install the patches that enforce it. Called once, at
    startup. Iterates over list(vars(...)) because it reassigns while walking.
    """
    global PREMIUM_EMOJI
    PREMIUM_EMOJI = bool(available)
    _install_patches()

    if not PREMIUM_EMOJI:
        # EmojiTag.X -> plain glyph. Templates that f-string EmojiTag at call
        # time (plugins/info.py, plugins/font_cmd.py, ...) pick this up
        # automatically.
        for name, value in list(vars(EmojiTag).items()):
            if not name.startswith("_") and isinstance(value, str):
                setattr(EmojiTag, name, strip_custom_emoji_text(value))

        # Messages.X was f-string-built at import, before the probe could run,
        # so those 112 strings already captured the tags and need their own pass.
        from utils.message import Messages

        for name, value in list(vars(Messages).items()):
            if not name.startswith("_") and isinstance(value, str):
                setattr(Messages, name, strip_custom_emoji_text(value))

        # Emoji.X -> None so nothing can hand an id to a message entity either.
        for name, value in list(vars(Emoji).items()):
            if not name.startswith("_") and isinstance(value, int):
                setattr(Emoji, name, None)

    # Markups built at import captured the pre-verdict state, either way.
    from utils.button import Buttons

    for name, value in list(vars(Buttons).items()):
        if isinstance(value, InlineKeyboardMarkup):
            setattr(Buttons, name, _rebuild_markup(value))

    if PREMIUM_EMOJI:
        logger.info("Premium emoji available — messages and buttons will use custom emoji.")
    else:
        logger.warning("Premium emoji unavailable — messages baked to plain Unicode emoji.")
    return PREMIUM_EMOJI


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


if __name__ == "__main__":  # python -m utils.premium_emoji
    import asyncio

    from utils.button import Buttons

    NOTE = Emoji.MUSIC_NOTE
    parse = lambda t: asyncio.run(HTML(None).parse(t))  # noqa: E731

    apply_premium_emoji(True)
    assert PREMIUM_EMOJI is True
    b = InlineKeyboardButton("🎵 ᴘʟᴀʏʙᴀᴄᴋ", callback_data="x", icon_custom_emoji_id=NOTE)
    assert (b.text, b.icon_custom_emoji_id) == ("ᴘʟᴀʏʙᴀᴄᴋ", NOTE), b.text
    b = InlineKeyboardButton("▷", callback_data="x", icon_custom_emoji_id=Emoji.RESUME)
    assert (b.text, b.icon_custom_emoji_id) == ("▷", Emoji.RESUME)
    assert _upgrade_unicode_emoji("hi 🎵") == f'hi <emoji id="{NOTE}">🎵</emoji>'
    assert _upgrade_unicode_emoji(EmojiTag.MUSIC_NOTE) == EmojiTag.MUSIC_NOTE  # no double wrap
    assert _upgrade_unicode_emoji("<code>🎵</code>") == "<code>🎵</code>"      # entity would nest
    assert _upgrade_unicode_emoji("▷ II ‣") == "▷ II ‣"                        # not real emoji
    out = parse("hi 🎵")
    assert out["message"] == "hi 🎵"
    assert any(e.QUALNAME.endswith("MessageEntityCustomEmoji") for e in out["entities"])

    apply_premium_emoji(False)
    assert PREMIUM_EMOJI is False
    b = InlineKeyboardButton("🎵 ᴘʟᴀʏʙᴀᴄᴋ", callback_data="x", icon_custom_emoji_id=NOTE)
    assert (b.text, b.icon_custom_emoji_id) == ("🎵 ᴘʟᴀʏʙᴀᴄᴋ", None), b.text
    assert Emoji.MUSIC_NOTE is None and "<emoji" not in EmojiTag.MUSIC_NOTE
    out = parse(f'<emoji id="{NOTE}">🎵</emoji> hi')
    assert out["message"] == "🎵 hi" and not out["entities"], out
    assert Buttons.BACK.inline_keyboard[0][0].icon_custom_emoji_id is None

    print("ok")
