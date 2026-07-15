"""
utils/lang.py — Per-chat multilingual string loader for NUB Music Bot.

Usage:
    from utils.lang import get_str, get_lang, set_lang, LANGUAGES

    # Get a translated string for a chat
    txt = await get_str(chat_id, "PLAY")

    # In a command handler
    lang = await get_lang(chat_id)        # → "en"
    await set_lang(chat_id, "es")         # store in DB

Supported languages (no Hindi):
    en · ar · es · fr · ru · de
"""

import json
import logging
import os
from typing import Dict

from database import user_sessions, db_task

logger = logging.getLogger(__name__)

# ── Load all JSON files from /lang/ ────────────────────────────────────────────
_LANG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lang")

# dict[code → dict[key → str]]
_STRINGS: Dict[str, dict] = {}

def _load_languages() -> None:
    for fname in sorted(os.listdir(_LANG_DIR)):
        if not fname.endswith(".json"):
            continue
        code = fname[:-5]          # strip .json
        path = os.path.join(_LANG_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            _STRINGS[code] = data
            logger.debug(f"[lang] Loaded language: {code} ({data.get('_name', '?')})")
        except Exception as e:
            logger.warning(f"[lang] Failed to load {fname}: {e}")

_load_languages()

# ── Public helpers ──────────────────────────────────────────────────────────────

#: Available language metadata for bot commands
LANGUAGES: Dict[str, dict] = {
    code: {
        "name": data.get("_name", code),
        "flag": data.get("_flag", "🏳️"),
        "code": code,
    }
    for code, data in _STRINGS.items()
    if not code.startswith("_")
}

DEFAULT_LANG = "en"

# In-memory cache: chat_id → lang_code
_lang_cache: Dict[int, str] = {}


async def get_lang(chat_id: int) -> str:
    """Return the language code set for this chat (default: 'en')."""
    if chat_id in _lang_cache:
        return _lang_cache[chat_id]

    doc = await user_sessions.find_one({"_id": f"lang_{chat_id}"})
    code = (doc or {}).get("lang", DEFAULT_LANG)
    if code not in _STRINGS:
        code = DEFAULT_LANG
    _lang_cache[chat_id] = code
    return code


async def set_lang(chat_id: int, code: str) -> None:
    """Persist language choice for a chat."""
    _lang_cache[chat_id] = code
    db_task(
        user_sessions.update_one(
            {"_id": f"lang_{chat_id}"},
            {"$set": {"lang": code}},
            upsert=True,
        )
    )


def _get_string(code: str, key: str) -> str:
    """Return translated string; fall back to English if missing."""
    lang_data = _STRINGS.get(code, {})
    value = lang_data.get(key)
    if value is None:
        value = _STRINGS.get(DEFAULT_LANG, {}).get(key, key)
    return value


async def get_str(chat_id: int, key: str, **kwargs) -> str:
    """
    Return the translated string for `key` in the chat's language.
    Supports named format kwargs:

        await get_str(chat_id, "PLAY", mode="audio", title="Song", duration="3:20", by="@user")
    """
    code = await get_lang(chat_id)
    text = _get_string(code, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"[lang] Missing format key {e} for string '{key}' in lang '{code}'")
    return text


def lang_list_text() -> str:
    """Return a formatted list of all available languages for display."""
    lines = []
    for code, meta in sorted(LANGUAGES.items()):
        lines.append(f"  {meta['flag']} <code>{code}</code> — {meta['name']}")
    return "\n".join(lines)
