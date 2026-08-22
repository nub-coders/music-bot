"""plugins/lang_commands.py — /setlang and /lang."""

from plugins._common import *  # noqa: F401,F403


def _lang_rows(current: str | None = None):
    """Rows for the available-languages table; marks the active code."""
    return [
        (
            f"{meta['flag']} {rich_code(code)}",
            rich_esc(meta["name"]),
            EmojiTag.SUCCESS if code == current else "",
        )
        for code, meta in sorted(LANGUAGES.items())
    ]


def _lang_table(current: str | None = None) -> str:
    """Native table of selectable languages — replaces the plain bullet list.

    Rendered into the ``{list}`` slot of the localized ``LANG_USAGE`` /
    ``LANG_INVALID`` strings, so translations keep working untouched.
    """
    return rich_table(["ᴄᴏᴅᴇ", "ʟᴀɴɢᴜᴀɢᴇ", ""], _lang_rows(current))


@Client.on_message(filters.command(["setlang", "language"]) & filters.group)
@admin_only()
async def setlang_handler(client, message):
    """Set the language for this chat. Usage: /setlang <code>"""
    args = message.text.split()
    chat_id = message.chat.id

    if len(args) < 2:
        # Show usage + available languages
        text = (await get_str(chat_id, "LANG_USAGE")).format(
            list=_lang_table(await get_lang(chat_id))
        )
        return await rich_reply(message, text, ephemeral=True, client=client)

    code = args[1].lower().strip()

    if code not in LANGUAGES:
        text = (await get_str(chat_id, "LANG_INVALID")).format(
            list=_lang_table(await get_lang(chat_id))
        )
        return await rich_reply(message, text, ephemeral=True, client=client)

    current = await get_lang(chat_id)
    if current == code:
        text = (await get_str(chat_id, "LANG_ALREADY")).format(
            lang=LANGUAGES[code]["name"]
        )
        return await rich_reply(message, rich_note(text), ephemeral=True, client=client)

    await set_lang(chat_id, code)
    text = (await get_str(chat_id, "LANG_SET")).format(
        lang=LANGUAGES[code]["name"],
        flag=LANGUAGES[code]["flag"],
    )
    await rich_reply(message, rich_note(text), ephemeral=True, client=client)


@Client.on_message(filters.command("lang"))
async def lang_info_handler(client, message):
    """Show the current language and all available options."""
    chat_id = message.chat.id
    code = await get_lang(chat_id)
    meta = LANGUAGES.get(code, {"name": code, "flag": "🏳️"})
    text = (
        rich_heading(f"{EmojiTag.GLOBE} ʟᴀɴɢᴜᴀɢᴇ sᴇᴛᴛɪɴɢs", 1)
        + rich_kv_table([
            (f"{EmojiTag.SUCCESS} ᴄᴜʀʀᴇɴᴛ", f"{meta['flag']} {rich_code(code)} — {rich_esc(meta['name'])}"),
        ])
        + rich_details(
            f"{EmojiTag.GLOBE} ᴀᴠᴀɪʟᴀʙʟᴇ ʟᴀɴɢᴜᴀɢᴇs ({len(LANGUAGES)})",
            _lang_table(code),
        )
        + rich_note(f"{EmojiTag.INFO} <i>ᴜsᴇ</i> {rich_code('/setlang <code>')} <i>ᴛᴏ ᴄʜᴀɴɢᴇ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</i>")
    )
    await rich_reply(message, text, client=client)
