"""plugins/broadcast.py — Broadcast flow and stats commands."""

from plugins._common import *  # noqa: F401,F403


@Client.on_callback_query(filters.regex(r"^broadcast$"))
async def broadcast_callback_handler(client, callback_query):
    # Fetch user settings for the broadcast
    user_data = await user_sessions.find_one({"bot_id": client.me.id})
    if not user_data:
        user_data = {}
    group = user_data.get('group', True)
    private = user_data.get('private', True)
    ugroup = user_data.get('ugroup', False)
    uprivate = user_data.get('uprivate', False)
    bot = user_data.get('bot', True)
    userbot = user_data.get('userbot', False)
    pin = user_data.get('pin', False)

    await callback_query.message.delete()

    # Fetch bot data and broadcast payload
    bot_data = await collection.find_one({"bot_id": client.me.id})
    broadcast_data = broadcast_message.get(client.me.id)
    if not broadcast_data:
        return await callback_query.answer(Messages.NO_MSG_FOR_BROADCAST, show_alert=True)
    message_to_broadcast, forwarding = broadcast_data

    # Bot Broadcast
    if bot_data and bot:
        X = await callback_query.message.reply(Messages.START_BOT_BROADCAST, link_preview_options=None)
        users = bot_data.get('users', [])
        u, g, a_chat = 0, 0, 0
        last_edit_time = time.time()

        for chat_id in users:
            try:
                cid = int(chat_id)
                is_private = cid > 0
                is_group = cid < 0

                if is_private and not private:
                    continue
                if is_group and not group:
                    continue

                sent_message = await message_to_broadcast.copy(cid) if not forwarding else await message_to_broadcast.forward(cid)
                if is_private:
                    u += 1
                else:
                    g += 1
                    if pin:
                        try:
                            await sent_message.pin()
                            a_chat += 1
                        except Exception:
                            pass

                # Debounce progress edits to avoid rate-limiting
                if (u + g) % 20 == 0 or time.time() - last_edit_time > 3:
                    try:
                        await X.edit(
                            f"<b>{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ꜰʀᴏᴍ ʙᴏᴛ...</b>\n\n"
                            f"✦ {EmojiTag.USER} <b>Private Chats:</b> <code>{u}</code>\n"
                            f"✦ {EmojiTag.USERS} <b>Groups:</b> <code>{g}</code>\n"
                            f"✦ {EmojiTag.SHIELD} <b>Pinned:</b> <code>{a_chat}</code>"
                        )
                        last_edit_time = time.time()
                    except Exception:
                        pass

            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    sent_message = await message_to_broadcast.copy(cid) if not forwarding else await message_to_broadcast.forward(cid)
                    if cid > 0:
                        u += 1
                    else:
                        g += 1
                except Exception as e:
                    logger.info(f"Error broadcasting to {chat_id}: {e}")
            except Exception as e:
                logger.info(f"Error broadcasting to {chat_id}: {e}")

        await X.edit(
            f"<b>{EmojiTag.SUCCESS} ʙᴏᴛ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!</b>\n\n"
            f"✦ {EmojiTag.USER} <b>Private Chats:</b> <code>{u}</code>\n"
            f"✦ {EmojiTag.USERS} <b>Groups:</b> <code>{g}</code>\n"
            f"✦ {EmojiTag.SHIELD} <b>Pinned in Groups:</b> <code>{a_chat}</code>"
        )

    bot_username = client.me.username

    # Assistant Broadcast
    if userbot and session:
        XX = await callback_query.message.reply(Messages.START_ASSISTANT_BROADCAST, link_preview_options=None)
        uu, ug = 0, 0
        last_edit_time = time.time()
        try:
            # Ensure communication with the bot
            try:
                await session.get_chat(client.me.id)
            except PeerIdInvalid:
                await session.send_message(bot_username, "/start", link_preview_options=None)
            except UserBlocked:
                await session.unblock_user(bot_username)
            await asyncio.sleep(1)

            # Copy the message to session and fetch history
            copied_message = await message_to_broadcast.copy(session.me.id) if not forwarding else await message_to_broadcast.forward(session.me.id)
            await asyncio.sleep(2)

            msg = await compare_message(copied_message, client, session)
            if not msg:
                msg = copied_message

            # Broadcast to dialogs
            async for dialog in session.get_dialogs():
                chat_id = dialog.chat.id
                if str(chat_id) == str(-1001806816712):
                    continue

                is_private = int(chat_id) > 0 or dialog.chat.type == enums.ChatType.PRIVATE
                is_group = int(chat_id) < 0 or dialog.chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP)

                if is_private and not uprivate:
                    continue
                if is_group and not ugroup:
                    continue

                try:
                    if not forwarding:
                        await msg.copy(chat_id)
                    else:
                        await msg.forward(chat_id)
                    if is_private:
                        uu += 1
                    else:
                        ug += 1

                    # Debounce progress edits
                    if (uu + ug) % 20 == 0 or time.time() - last_edit_time > 3:
                        try:
                            await XX.edit(
                                f"<b>{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴠɪᴀ ᴀssɪsᴛᴀɴᴛ...</b>\n\n"
                                f"✦ {EmojiTag.USER} <b>Private Chats:</b> <code>{uu}</code>\n"
                                f"✦ {EmojiTag.USERS} <b>Groups:</b> <code>{ug}</code>"
                            )
                            last_edit_time = time.time()
                        except Exception:
                            pass
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    try:
                        if not forwarding:
                            await msg.copy(chat_id)
                        else:
                            await msg.forward(chat_id)
                        if is_private:
                            uu += 1
                        else:
                            ug += 1
                    except Exception as e:
                        logger.info(f"Error broadcasting to {chat_id}: {e}")
                except Exception as e:
                    logger.info(f"Error broadcasting to {chat_id}: {e}")

        except Exception as e:
            logger.info(f"Error with session broadcast: {e}")
            await XX.reply(Messages.ERROR_OCCURRED, link_preview_options=None)

        # Finalize assistant broadcast summary
        await XX.edit(
            f"<b>{EmojiTag.SUCCESS} ᴀssɪsᴛᴀɴᴛ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!</b>\n\n"
            f"✦ {EmojiTag.USER} <b>Private Chats:</b> <code>{uu}</code>\n"
            f"✦ {EmojiTag.USERS} <b>Groups:</b> <code>{ug}</code>"
        )


async def get_status(client):
    """Instant broadcast summary generated directly from DB without Telegram network calls."""
    user_data = await collection.find_one({"bot_id": client.me.id})
    users = user_data.get('users', []) if user_data else []

    u = sum(1 for cid in users if int(cid) > 0)
    g = sum(1 for cid in users if int(cid) < 0)
    total = len(users)

    mess = (
        f"<b>{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛ sᴇᴛᴛɪɴɢs</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"✦ {EmojiTag.USER} <b>Private Chats:</b> <code>{u}</code>\n"
        f"✦ {EmojiTag.USERS} <b>Groups:</b> <code>{g}</code>\n"
        f"✦ {EmojiTag.STATS} <b>Total Targets:</b> <code>{total}</code>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<blockquote><b>ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ʙʀᴏᴀᴅᴄᴀsᴛ ᴏᴘᴛɪᴏɴs ʙᴇʟᴏᴡ ⬇️</b></blockquote>"
    )
    broadcasts[client.me.id] = mess
    return mess


async def compare_message(mess, client, session):
    async for msg in session.get_chat_history(chat_id=client.me.id, limit=2):
        # Compare text messages
        if mess.text and msg.text == mess.text:
            return msg

        # Compare media messages
        elif mess.media and msg.media:
            try:
                # Get the media type (photo, video, etc.)
                mess_media_type = mess.media.value
                msg_media_type = msg.media.value

                # Check if both messages have the same media type
                if mess_media_type == msg_media_type:
                    # Get file unique IDs for comparison
                    mess_file_id = getattr(mess, mess_media_type).file_unique_id
                    msg_file_id = getattr(msg, msg_media_type).file_unique_id

                    # Compare file IDs
                    if mess_file_id and msg_file_id and mess_file_id == msg_file_id:
                        return msg
            except AttributeError:
                # Skip if media attributes are not accessible
                continue

    # Return None if no matching message is found
    return None


@Client.on_callback_query(filters.regex(r"^toggle_(.*)$"))
async def toggle_setting(client, callback_query):
    sender_id = client.me.id

    user_data = await user_sessions.find_one({"bot_id": sender_id})
    if not user_data:
        user_data = {}
    setting_to_toggle = callback_query.data.split("_", 1)[1]
    current_value = user_data.get(setting_to_toggle, False)
    new_value = not current_value
    db_task(user_sessions.update_one(
        {"bot_id": sender_id},
        {"$set": {setting_to_toggle: new_value}},
        upsert=True
    ))
    await broadcast_command_handler(client, callback_query)


@Client.on_message(filters.command("stats"))
async def status_command_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"

    # Get user data and permissions
    users_data = await user_sessions.find_one({"bot_id": client.me.id})
    sudoers = users_data.get("SUDOERS", []) if users_data else []

    is_admin = False
    if os.path.exists(admin_file):
        admin_ids = get_admin_ids(admin_file)
        is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in sudoers
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    await status(client, message)


@Client.on_message(filters.command(["broadcast", "fbroadcast"]) & filters.private)
async def broadcast_command_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    users_data = await user_sessions.find_one({"bot_id": client.me.id})
    sudoers = users_data.get("SUDOERS", []) if users_data else []

    is_admin = False
    if os.path.exists(admin_file):
        admin_ids = get_admin_ids(admin_file)
        is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in sudoers
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    sender_id = client.me.id
    user_data = await user_sessions.find_one({"bot_id": sender_id})
    if not user_data:
        user_data = {}
        db_task(user_sessions.update_one(
            {"bot_id": sender_id},
            {"$setOnInsert": {"bot_id": sender_id}},
            upsert=True
        ))

    if not isinstance(message, CallbackQuery):
        if not message.reply_to_message:
            return await message.reply(Messages.REPLY_TO_BROADCAST, link_preview_options=None)
        broadcast_message[client.me.id] = [
            message.reply_to_message,
            True if message.command[0].lower().startswith("f") else None
        ]

    group = user_data.get('group', True)
    private = user_data.get('private', True)
    ugroup = user_data.get('ugroup', False)
    uprivate = user_data.get('uprivate', False)
    bot = user_data.get('bot', True)
    userbot = user_data.get('userbot', False)
    pin = user_data.get('pin', False)

    for_bot = [
        InlineKeyboardButton(f"Gʀᴏᴜᴘ {'✅' if group else '❌'}", callback_data="toggle_group"),
        InlineKeyboardButton(f"Pʀɪᴠᴀᴛᴇ {'✅' if private else '❌'}", callback_data="toggle_private"),
        InlineKeyboardButton(f"📌Pɪɴ {'✅' if pin else '❌'}", callback_data="toggle_pin"),
    ]

    for_userbot = [
        InlineKeyboardButton(f"Gʀᴏᴜᴘ {'✅' if ugroup else '❌'}", callback_data="toggle_ugroup"),
        InlineKeyboardButton(f"Pʀɪᴠᴀᴛᴇ {'✅' if uprivate else '❌'}", callback_data="toggle_uprivate"),
    ]

    buttons = [
        [InlineKeyboardButton(f"Fʀᴏᴍ ʙᴏᴛ {'⬇️' if bot else '❌'}", callback_data="toggle_bot")],
        for_bot if bot else [],
        [InlineKeyboardButton(f"Fʀᴏᴍ ᴜꜱᴇʀʙᴏᴛ {'⬇️' if userbot else '❌'}", callback_data="toggle_userbot")],
        for_userbot if userbot else [],
        [InlineKeyboardButton("BROADCAST🚀🚀", callback_data="broadcast")],
    ]

    # Filter out empty button rows
    buttons = [row for row in buttons if row]

    mess_text = await get_status(client)

    if isinstance(message, CallbackQuery):
        await message.edit_message_text(
            mess_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await message.reply(
            mess_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            link_preview_options=None
        )
