"""plugins/lang_commands.py — /setlang and /lang."""

from plugins._common import *  # noqa: F401,F403


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
