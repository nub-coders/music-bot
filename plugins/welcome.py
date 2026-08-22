"""plugins/welcome.py — /setwelcome and /resetwelcome."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command("setwelcome") & filters.private)
async def set_welcome_handler(client, message):
    sender_id = message.from_user.id
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    try:
        if not sender_id == OWNER_ID:
           return await rich_reply(message, rich_note(Messages.BOT_OWNER_ONLY), ephemeral=True, client=client)

        replied_msg = message.reply_to_message
        if not replied_msg:
            # Private-chat command: ephemeral delivery is group-only, so this
            # stays a normal (rich) reply.
            usage_text = (
                rich_heading(f"{EmojiTag.INFO} sᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ", 1)
                + rich_note("<b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ sᴇᴛ ɪᴛ ᴀs ᴛʜᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ.</b>")
                + rich_table(
                    ["ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀ", "ʀᴇᴘʟᴀᴄᴇᴅ ᴡɪᴛʜ"],
                    [
                        (rich_code("{name}"), "ᴜsᴇʀ's ɴᴀᴍᴇ"),
                        (rich_code("{id}"), "ᴜsᴇʀ's ɪᴅ"),
                        (rich_code("{botname}"), "ʙᴏᴛ's ᴜsᴇʀɴᴀᴍᴇ"),
                    ],
                )
                + rich_details(
                    f"{EmojiTag.HELP} sᴜᴘᴘᴏʀᴛᴇᴅ ᴛʏᴘᴇs &amp; ʟɪᴍɪᴛs",
                    rich_table(
                        ["ᴛʏᴘᴇ", "ʟɪᴍɪᴛ"],
                        [
                            ("Text message", rich_code("4096 chars")),
                            ("Photo / video / gif / sticker", rich_code("5 MB")),
                            ("Media with caption", rich_code("5 MB")),
                        ],
                    ),
                )
            )
            return await rich_reply(message, usage_text, client=client)

        updates = []

        # Handle text if present
        if replied_msg.text or replied_msg.caption:
            welcome_text = (replied_msg.text or replied_msg.caption).strip()
            if len(welcome_text) > 4096:
                return await rich_reply(message, rich_note(Messages.WELCOME_TOO_LONG), ephemeral=True, client=client)

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
                error_msg = (
                    rich_heading(f"{EmojiTag.ERROR} ɪɴᴠᴀʟɪᴅ ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀs", 1)
                    + rich_table(
                        ["꩖ᴏᴜɴᴅ", "sᴛᴀᴛᴜs"],
                        [(rich_code(p), f"{EmojiTag.ERROR} not allowed") for p in invalid_placeholders],
                    )
                    + rich_details(
                        f"{EmojiTag.INFO} ᴀʟʟᴏᴡᴇᴅ ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀs &amp; ᴇxᴀᴍᴘʟᴇs",
                        rich_table(
                            ["ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀ", "ᴇxᴀᴍᴘʟᴇ"],
                            [
                                (rich_code("{name}"), rich_code("Welcome {name}!")),
                                (rich_code("{id}"), rich_code("Your ID: {id}")),
                                (rich_code("{botname}"), rich_code("Welcome to {botname}!")),
                            ],
                        ),
                    )
                )
                return await rich_reply(message, error_msg, ephemeral=True, client=client)

            set_user_data(client.me.id, "WELCOME", processed_text)
            updates.append("welcome message")

        # Handle media if present
        if replied_msg.media:
            m_d = None
            try:
                # Check if media type is allowed
                if not (replied_msg.photo or replied_msg.video or
                       replied_msg.sticker or replied_msg.animation):
                    return await rich_reply(message, rich_note(Messages.ONLY_MEDIA_ALLOWED), ephemeral=True, client=client)

                # Check file size (5MB = 5 * 1024 * 1024 bytes)
                file_size = getattr(replied_msg, 'file_size', 0)
                if file_size > 5242880:  # 5MB in bytes
                    return await rich_reply(message, rich_note(Messages.MEDIA_SIZE_EXCEED), ephemeral=True, client=client)

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
                logger.error(f"[setwelcome] Media processing failed: {e}")
                if m_d and os.path.exists(m_d):
                    os.remove(m_d)
                return await rich_reply(message, rich_note(Messages.ERROR_MEDIA_PROCESS), ephemeral=True, client=client)

        if not updates:
            return await rich_reply(message, rich_note(Messages.NOTHING_TO_UPDATE), ephemeral=True, client=client)

        # Send confirmation and preview
        await rich_reply(
            message,
            rich_heading(f"{EmojiTag.SUCCESS} ᴜᴘᴅᴀᴛᴇᴅ", 2)
            + rich_table(["ᴜᴘᴅᴀᴛᴇᴅ"], [(rich_esc(u),) for u in updates])
            + rich_note(f"{EmojiTag.INFO} <b>ᴘʀᴇᴠɪᴇᴡ ʙᴇʟᴏᴡ</b>"),
            client=client,
        )

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
                        photo_id = getattr(photos[0], "big_file_id", getattr(photos[0], "file_id", None))
                        if photo_id:
                            logo = await client.download_media(photo_id, logo_path_jpg)
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
        logger.info(f"Error for user {message.from_user.id}: {str(e)}")
        return await rich_reply(
            message,
            rich_note(f"{EmojiTag.ERROR} <b>Error:</b> {rich_code(e)}"),
            ephemeral=True,
            client=client,
        )


@Client.on_message(filters.command(["resetwelcome", "rwelcome"]))
async def resetwelcome(client: Client, message: Message):
    sender_id = message.from_user.id
    if not sender_id == OWNER_ID:
        return await rich_reply(message, rich_note(Messages.BOT_OWNER_ONLY), ephemeral=True, client=client)

    set_user_data(client.me.id, "WELCOME", None)
    set_user_data(client.me.id, "LOGO", None)
    await rich_reply(message, rich_note(Messages.WELCOME_RESET), ephemeral=True, client=client)
