"""plugins/welcome.py — /setwelcome and /resetwelcome."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command("setwelcome") & filters.private)
async def set_welcome_handler(client, message):
    sender_id = message.from_user.id
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    try:
        if not sender_id == OWNER_ID:
           return await message.reply_text(Messages.BOT_OWNER_ONLY, link_preview_options=None)

        replied_msg = message.reply_to_message
        if not replied_msg:
            usage_text = (
                "Please reply to a message to set it as welcome message.\n\n"
                "You can set:\n"
                "• Text message\n"
                "• Media (photo/video/gif/sticker)\n"
                "• Media with caption\n\n"
                "Available placeholders:\n"
                "• {name} - User's name\n"
                "• {id} - User's ID\n"
                "• {botname} - Bot's username\n\n"
                "Size limits:\n"
                "• Text: Maximum 4096 characters\n"
                "• Media: Maximum 5MB\n\n"
                "Example usage:\n"
                "• 'Welcome {name}! Your ID is {id}'\n"
                "• Reply to a photo/video with caption 'Welcome to {botname}!'"
            )
            return await message.reply_text(usage_text, link_preview_options=None)

        updates = []

        # Handle text if present
        if replied_msg.text or replied_msg.caption:
            welcome_text = (replied_msg.text or replied_msg.caption).strip()
            if len(welcome_text) > 4096:
                return await message.reply_text(Messages.WELCOME_TOO_LONG, link_preview_options=None)

            entities = sorted(
                (replied_msg.entities or replied_msg.caption_entities or []),
                key=lambda x: (x.offset, -x.length)
            )

            ENTITY_TO_HTML = {
                MessageEntityType.BOLD: ('b', 'b'),
                MessageEntityType.ITALIC: ('i', 'i'),
                MessageEntityType.UNDERLINE: ('u', 'u'),
                MessageEntityType.STRIKETHROUGH: ('s', 's'),
                MessageEntityType.SPOILER: ('spoiler', 'spoiler'),
                MessageEntityType.CODE: ('code', 'code'),
                MessageEntityType.PRE: ('pre', 'pre'),
                MessageEntityType.BLOCKQUOTE: ('blockquote', 'blockquote')
            }

            def convert_to_html(text, msg_entities):
                tag_positions = []

                for entity in msg_entities:
                    if entity.type in ENTITY_TO_HTML:
                        start_tag, end_tag = ENTITY_TO_HTML[entity.type]

                        if entity.type == MessageEntityType.PRE and getattr(entity, 'language', None):
                            tag_positions.append((entity.offset, f'<pre language="{entity.language}">', True))
                        else:
                            tag_positions.append((entity.offset, f'<{start_tag}>', True))

                        tag_positions.append((entity.offset + entity.length, f'</{end_tag}>', False))

                tag_positions.sort(key=lambda x: (x[0], x[2]))

                result = []
                current_pos = 0

                for pos, tag, _ in tag_positions:
                    if pos > current_pos:
                        result.append(text[current_pos:pos])
                    result.append(tag)
                    current_pos = pos

                if current_pos < len(text):
                    result.append(text[current_pos:])

                return ''.join(result)

            processed_text = convert_to_html(welcome_text, entities)

            # Validate placeholders
            ALLOWED_PLACEHOLDERS = {"{name}", "{id}", "{botname}"}
            placeholder_regex = r'\{([^{}]+)\}'
            found_placeholders = set(re.findall(placeholder_regex, processed_text))

            invalid_placeholders = [f"{{{p}}}" for p in found_placeholders
                                  if f"{{{p}}}" not in ALLOWED_PLACEHOLDERS]

            if invalid_placeholders:
                error_msg = "❌ Invalid placeholders found:\n"
                error_msg += "\n".join(f"• {p}" for p in invalid_placeholders)
                error_msg += "\n\nAllowed placeholders:\n"
                error_msg += "\n".join(f"• {p}" for p in sorted(ALLOWED_PLACEHOLDERS))
                error_msg += "\n\nExample usage:\n"
                error_msg += "• Welcome {name}!\n"
                error_msg += "• Your ID: {id}\n"
                error_msg += "• Welcome to {botname}!"
                return await message.reply_text(error_msg, link_preview_options=None)

            set_user_data(client.me.id, "WELCOME", processed_text)
            updates.append("welcome message")

        # Handle media if present
        if replied_msg.media:
            m_d = None
            try:
                # Check if media type is allowed
                if not (replied_msg.photo or replied_msg.video or
                       replied_msg.sticker or replied_msg.animation):
                    return await message.reply_text(Messages.ONLY_MEDIA_ALLOWED, link_preview_options=None)

                # Check file size (5MB = 5 * 1024 * 1024 bytes)
                file_size = getattr(replied_msg, 'file_size', 0)
                if file_size > 5242880:  # 5MB in bytes
                    return await message.reply_text(Messages.MEDIA_SIZE_EXCEED, link_preview_options=None)

                # First try to save to user_dir
                logo_path_jpg = f"{user_dir}/logo.jpg"
                logo_path_mp4 = f"{user_dir}/logo.mp4"

                # Process media based on type
                if replied_msg.sticker:
                    m_d = await convert_to_image(replied_msg)
                else:
                    m_d = await replied_msg.download()

                if m_d:
                    # Save to appropriate path based on media type
                    if replied_msg.video:
                        target_path = logo_path_mp4
                    else:
                        target_path = logo_path_jpg

                    os.rename(m_d, target_path)
                    updates.append(f"logo (saved to {target_path})")

            except Exception as e:
                if m_d and os.path.exists(m_d):
                    os.remove(m_d)
                return await message.reply_text(Messages.ERROR_MEDIA_PROCESS.format(str(e)), link_preview_options=None)

        if not updates:
            return await message.reply_text(Messages.NOTHING_TO_UPDATE, link_preview_options=None)

        # Send confirmation and preview
        success_msg = f"✅ Updated {' and '.join(updates)}!"
        await client.send_message(message.chat.id, success_msg + "\n\nPreview:", link_preview_options=None)

        # Show preview
        try:
            # First check user_dir for existing logos
            logo_path_jpg = f"{user_dir}/logo.jpg"
            logo_path_mp4 = f"{user_dir}/logo.mp4"
            logo = None

            if os.path.exists(logo_path_mp4):
                logo = logo_path_mp4
            elif os.path.exists(logo_path_jpg):
                logo = logo_path_jpg
            else:
                # Fallback to old methods
                logo = await gvarstatus(sender_id, "LOGO")
                if not logo and client.me.photo:
                    photos = await client.get_profile_photos("me")
                    if photos:
                        logo = await client.download_media(photos[0].file_id, logo_path_jpg)
                if not logo:
                    logo = "music.jpg"

            alive_logo = logo
            if isinstance(logo, bytes):
                alive_logo = logo_path_jpg
                with open(alive_logo, "wb") as fimage:
                    fimage.write(base64.b64decode(logo))
                if 'video' in mime.from_file(alive_logo):
                    alive_logo = rename_file(alive_logo, logo_path_mp4)

            welcome_text = await gvarstatus(sender_id, "WELCOME") or f"""
🌟 𝖂𝖊𝖑𝖈𝖔𝖒𝖊, {name}! 🌟

🎶 Your **musical journey** begins with {botname}!

✨ Enjoy _crystal-clear_ audio and a vast library of sounds.

🚀 Get ready for an *unparalleled* musical adventure!
"""
            if alive_logo.endswith(".mp4"):
                await client.send_video(
                    message.chat.id,
                    alive_logo,
                    caption=welcome_text,
                )
            else:
                await client.send_photo(
                    message.chat.id,
                    alive_logo,
                    caption=welcome_text,
                )

        except Exception as e:
            logger.info(f"Error showing preview: {str(e)}")
            welcome_text = await gvarstatus(sender_id, "WELCOME")
            if welcome_text:
                await client.send_message(
                    message.chat.id,
                    welcome_text,
                link_preview_options=None)
    except Exception as e:
        error_msg = f"❌ Error: `{str(e)}`"
        logger.info(f"Error for user {message.from_user.id}: {str(e)}")
        return await message.reply_text(error_msg, link_preview_options=None)


@Client.on_message(filters.command(["resetwelcome", "rwelcome"]))
async def resetwelcome(client: Client, message: Message):
    sender_id = message.from_user.id
    if not sender_id == OWNER_ID:
        return await message.reply_text(Messages.BOT_OWNER_ONLY, link_preview_options=None)

    set_user_data(client.me.id, "WELCOME", None)
    set_user_data(client.me.id, "LOGO", None)
    await message.reply_text(Messages.WELCOME_RESET, link_preview_options=None)
