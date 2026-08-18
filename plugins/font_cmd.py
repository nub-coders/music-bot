"""
plugins/font_cmd.py — /font command for converting text into Telegram bot font styles.
"""

from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery
from utils.font import apply_font, FONTS
from utils.emoji import EmojiTag
from utils.button import Buttons
from utils.message import Messages


@Client.on_message(filters.command(["font", "style"]))
async def font_command_handler(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        help_text = (
            f"{EmojiTag.KANG} <b>ꜰᴏɴᴛ sᴛʏʟᴇ ɢᴇɴᴇʀᴀᴛᴏʀ</b>\n\n"
            f"<b>‣ ᴜsᴀɢᴇ:</b> <code>/font <text></code>\n"
            f"<b>‣ ᴇxᴀᴍᴘʟᴇ:</b> <code>/font Hello World</code>\n\n"
            "<i>ᴄᴏɴᴠᴇʀᴛ ʏᴏᴜʀ ᴛᴇxᴛ ɪɴᴛᴏ ᴄʟᴇᴀɴ, ᴀᴇsᴛʜᴇᴛɪᴄ ʙᴏᴛ ꜰᴏɴᴛ sᴛʏʟᴇs.</i>"
        )
        return await message.reply_text(help_text, reply_to_message_id=message.id)

    target_text = args[1]

    # Generate samples for all 4 clean font styles
    styled_lines = [
        f"{EmojiTag.STAR} <b>ꜰᴏɴᴛ sᴛʏʟᴇs ꜰᴏʀ:</b> <i>{target_text}</i>\n"
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
