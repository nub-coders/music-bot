"""
plugins/font_cmd.py — /font command for converting text into Telegram bot font styles.
"""

from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery
from utils.font import apply_font, FONTS
from utils.emoji import EmojiTag
from utils.button import Buttons
from utils.message import Messages
from utils.rich_ui import (
    rich_code, rich_details, rich_heading, rich_note, rich_reply, rich_table,
)


@Client.on_message(filters.command(["font", "style"]))
async def font_command_handler(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        help_text = (
            rich_heading(f"{EmojiTag.KANG} ꩖ᴏɴᴛ sᴛʏʟᴇ ɢᴇɴᴇʀᴀᴛᴏʀ", 1)
            + rich_table(
                ["", ""],
                [
                    ("<b>ᴜsᴀɢᴇ</b>", rich_code("/font <text>")),
                    ("<b>ᴇxᴀᴍᴘʟᴇ</b>", rich_code("/font Hello World")),
                ],
            )
            + rich_details(
                f"{EmojiTag.STAR} ᴀᴠᴀɪʟᴀʙʟᴇ sᴛʏʟᴇs ({len(FONTS)})",
                rich_table(
                    ["sᴛʏʟᴇ", "ᴘʀᴇᴠɪᴇᴡ"],
                    [
                        (f"<b>{label}</b>", rich_code(func("Sample")))
                        for label, func in FONTS.values()
                    ],
                ),
            )
            + rich_note("<i>ᴄᴏɴᴠᴇʀᴛ ʏᴏᴜʀ ᴛᴇxᴛ ɪɴᴛᴏ ᴄʟᴇᴀɴ, ᴀᴇsᴛʜᴇᴛɪᴄ ʙᴏᴛ ꩖ᴏɴᴛ sᴛʏʟᴇs.</i>")
        )
        return await rich_reply(message, help_text, ephemeral=True, client=client)

    target_text = args[1]

    # NOTE: deliberately NOT a rich message. font_callback_handler below recovers
    # the original text by scraping `callback_query.message.text`, and rich
    # messages are sent with an empty `message` field (so `.text` is None) --
    # converting this would silently degrade every button to "Sample Text".
    # Generate samples for all 4 clean font styles
    styled_lines = [
        f"{EmojiTag.STAR} <b>꩖ᴏɴᴛ sᴛʏʟᴇs ꩖ᴏʀ:</b> <i>{target_text}</i>\n"
    ]
    for key, (label, func) in FONTS.items():
        converted = func(target_text)
        styled_lines.append(f"<b>‣ {label}:</b>\n<code>{converted}</code>\n")

    full_text = "\n".join(styled_lines)
    await message.reply_text(
        full_text,
        reply_markup=Buttons.font_markup(),
        reply_to_message_id=message.id
    )


@Client.on_callback_query(filters.regex("^font_"))
async def font_callback_handler(client: Client, callback_query: CallbackQuery):
    style_key = callback_query.data.split("_", 1)[1]
    if style_key not in FONTS:
        return await callback_query.answer(Messages.INVALID_FONT_SELECTION, show_alert=True)

    label, func = FONTS[style_key]
    # Extract original text from message if present
    msg_text = callback_query.message.text or ""
    lines = msg_text.splitlines()
    target_text = "Sample Text"
    for line in lines:
        if "ꜰᴏɴᴛ sᴛʏʟᴇs ꜰᴏʀ:" in line or "FOR:" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                target_text = parts[1].strip()
            break

    converted = func(target_text)
    await callback_query.answer(f"Selected {label}:\n{converted}", show_alert=True)
