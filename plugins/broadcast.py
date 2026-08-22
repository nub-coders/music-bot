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
    forward = user_data.get('forward', False)

    await callback_query.message.delete()

    # Fetch bot data and broadcast payload
    bot_data = await collection.find_one({"bot_id": client.me.id})
    broadcast_data = broadcast_message.get(client.me.id)
    if not broadcast_data:
        return await callback_query.answer(Messages.NO_MSG_FOR_BROADCAST, show_alert=True)
    message_to_broadcast = broadcast_data[0] if isinstance(broadcast_data, list) else broadcast_data

    # Bot Broadcast
    if bot_data and bot:
        chat_id_for_progress = callback_query.message.chat.id
        users = bot_data.get('users', [])
        u, g, a_chat = 0, 0, 0
        last_edit_time = time.time()

        async with RichDraft(client, chat_id_for_progress) as draft:
            await draft.update(rich_note(Messages.START_BOT_BROADCAST))

            for chat_id in users:
                try:
                    cid = int(chat_id)
                    is_private = cid > 0
                    is_group = cid < 0

                    if is_private and not private:
                        continue
                    if is_group and not group:
                        continue

                    sent_message = await message_to_broadcast.forward(cid) if forward else await message_to_broadcast.copy(cid)
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
                            await draft.update(
                                rich_heading(f"{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ꜰʀᴏᴍ ʙᴏᴛ", 2)
                                + rich_kv_table([
                                    (f"{EmojiTag.USER} Private Chats", rich_code(u)),
                                    (f"{EmojiTag.USERS} Groups", rich_code(g)),
                                    (f"{EmojiTag.SHIELD} Pinned", rich_code(a_chat)),
                                ])
                            )
                            last_edit_time = time.time()
                        except Exception:
                            pass

                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    try:
                        sent_message = await message_to_broadcast.forward(cid) if forward else await message_to_broadcast.copy(cid)
                        if cid > 0:
                            u += 1
                        else:
                            g += 1
                    except Exception as e:
                        logger.info(f"Error broadcasting to {chat_id}: {e}")
                except Exception as e:
                    logger.info(f"Error broadcasting to {chat_id}: {e}")

            await draft.finish(
                rich_heading(f"{EmojiTag.SUCCESS} ʙᴏᴛ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ", 1)
                + rich_table(
                    ["Result", "Count"],
                    [
                        (f"{EmojiTag.USER} Private Chats", rich_code(u)),
                        (f"{EmojiTag.USERS} Groups", rich_code(g)),
                        (f"{EmojiTag.SHIELD} Pinned in Groups", rich_code(a_chat)),
                        (f"{EmojiTag.STATS} Total Delivered", rich_code(u + g)),
                    ],
                )
            )

    bot_username = client.me.username

    # Assistant Broadcast
    if userbot and session:
        chat_id_for_progress = callback_query.message.chat.id
        uu, ug = 0, 0
        last_edit_time = time.time()
        async with RichDraft(client, chat_id_for_progress) as draft:
            await draft.update(rich_note(Messages.START_ASSISTANT_BROADCAST))
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
                copied_message = await message_to_broadcast.forward(session.me.id) if forward else await message_to_broadcast.copy(session.me.id)
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
                        if forward:
                            await msg.forward(chat_id)
                        else:
                            await msg.copy(chat_id)
                        if is_private:
                            uu += 1
                        else:
                            ug += 1

                        # Debounce progress edits
                        if (uu + ug) % 20 == 0 or time.time() - last_edit_time > 3:
                            try:
                                await draft.update(
                                    rich_heading(f"{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴠɪᴀ ᴀssɪsᴛᴀɴᴛ", 2)
                                    + rich_kv_table([
                                        (f"{EmojiTag.USER} Private Chats", rich_code(uu)),
                                        (f"{EmojiTag.USERS} Groups", rich_code(ug)),
                                    ])
                                )
                                last_edit_time = time.time()
                            except Exception:
                                pass
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        try:
                            if forward:
                                await msg.forward(chat_id)
                            else:
                                await msg.copy(chat_id)
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
                await rich_send(client, chat_id_for_progress, rich_note(Messages.ERROR_OCCURRED))

            # Finalize assistant broadcast summary
            await draft.finish(
                rich_heading(f"{EmojiTag.SUCCESS} ᴀssɪsᴛᴀɴᴛ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ", 1)
                + rich_table(
                    ["Result", "Count"],
                    [
                        (f"{EmojiTag.USER} Private Chats", rich_code(uu)),
                        (f"{EmojiTag.USERS} Groups", rich_code(ug)),
                        (f"{EmojiTag.STATS} Total Delivered", rich_code(uu + ug)),
                    ],
                )
            )


async def get_status(client, user_data=None):
    """Broadcast summary with target counts and currently chosen options."""
    bot_id = client.me.id
    target_data = await collection.find_one({"bot_id": bot_id})
    users = target_data.get('users', []) if target_data else []

    u = sum(1 for cid in users if int(cid) > 0)
    g = sum(1 for cid in users if int(cid) < 0)
    total = len(users)

    if user_data is None:
        user_data = await user_sessions.find_one({"bot_id": bot_id}) or {}

    group = user_data.get('group', True)
    private = user_data.get('private', True)
    ugroup = user_data.get('ugroup', False)
    uprivate = user_data.get('uprivate', False)
    bot = user_data.get('bot', True)
    userbot = user_data.get('userbot', False)
    pin = user_data.get('pin', False)
    forward = user_data.get('forward', False)

    bot_status = f"{EmojiTag.TICK} <b>ʏᴇs</b>" if bot else f"{EmojiTag.UNTICK} <b>ɴᴏ</b>"
    userbot_status = f"{EmojiTag.TICK} <b>ʏᴇs</b>" if userbot else f"{EmojiTag.UNTICK} <b>ɴᴏ</b>"
    sender_name_status = f"{EmojiTag.TICK} <b>ᴛʀᴜᴇ</b>" if forward else f"{EmojiTag.UNTICK} <b>ꜰᴀʟsᴇ</b>"

    bot_group_str = f"{EmojiTag.TICK} Yes" if group else f"{EmojiTag.UNTICK} No"
    bot_private_str = f"{EmojiTag.TICK} Yes" if private else f"{EmojiTag.UNTICK} No"
    bot_pin_str = f"{EmojiTag.TICK} Yes" if pin else f"{EmojiTag.UNTICK} No"

    ubot_group_str = f"{EmojiTag.TICK} Yes" if ugroup else f"{EmojiTag.UNTICK} No"
    ubot_private_str = f"{EmojiTag.TICK} Yes" if uprivate else f"{EmojiTag.UNTICK} No"

    mess = (
        rich_heading(f"{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛ sᴇᴛᴛɪɴɢs", 1)
        + rich_heading(f"{EmojiTag.STATS} ᴛᴀʀɢᴇᴛs", 2)
        + rich_table(
            ["Target", "Count"],
            [
                (f"{EmojiTag.USER} Private Chats", rich_code(u)),
                (f"{EmojiTag.USERS} Groups", rich_code(g)),
                (f"{EmojiTag.STATS} Total Targets", rich_code(total)),
            ],
        )
        + rich_heading(f"{EmojiTag.SETTINGS} ᴄʜᴏsᴇɴ ᴏᴘᴛɪᴏɴs", 2)
        # Sub-options that used to hang off a "└" line are now their own rows,
        # scoped by the Source column.
        + rich_table(
            ["Source", "Setting", "State"],
            [
                ("—", "Sender Name", sender_name_status),
                (f"{EmojiTag.CHAT} Bot", "Enabled", bot_status),
                (f"{EmojiTag.CHAT} Bot", "Groups", bot_group_str),
                (f"{EmojiTag.CHAT} Bot", "Private", bot_private_str),
                (f"{EmojiTag.CHAT} Bot", "Pin", bot_pin_str),
                (f"{EmojiTag.USER} Assistant", "Enabled", userbot_status),
                (f"{EmojiTag.USER} Assistant", "Groups", ubot_group_str),
                (f"{EmojiTag.USER} Assistant", "Private", ubot_private_str),
            ],
        )
        + rich_details(
            "What do these settings do?",
            rich_table(
                ["Setting", "Effect"],
                [
                    ("Sender Name", "Forward the message so the original author stays visible, instead of sending a clean copy."),
                    ("From Bot", "Deliver from the bot account to every chat it knows."),
                    ("From Assistant", "Deliver from the assistant account to its own dialogs."),
                    ("Groups / Private", "Restrict delivery to that chat kind for the chosen source."),
                    ("Pin", "Pin the broadcast in groups after sending (bot only)."),
                ],
            ),
        )
        + rich_note("<b>ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ʙʀᴏᴀᴅᴄᴀsᴛ ᴏᴘᴛɪᴏɴs ʙᴇʟᴏᴡ ⬇️</b>")
    )
    broadcasts[bot_id] = mess
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

    user_data = await user_sessions.find_one({"bot_id": sender_id}) or {}
    setting_to_toggle = callback_query.data.split("_", 1)[1]

    defaults = {
        'group': True,
        'private': True,
        'ugroup': False,
        'uprivate': False,
        'bot': True,
        'userbot': False,
        'pin': False,
        'forward': False,
    }
    current_value = user_data.get(setting_to_toggle, defaults.get(setting_to_toggle, False))
    new_value = not current_value

    await user_sessions.update_one(
        {"bot_id": sender_id},
        {"$set": {setting_to_toggle: new_value}},
        upsert=True
    )
    user_data[setting_to_toggle] = new_value
    await callback_query.answer()
    await broadcast_command_handler(client, callback_query, user_data=user_data)


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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    await status(client, message)


@Client.on_message(filters.command(["broadcast", "fbroadcast"]) & filters.private)
async def broadcast_command_handler(client, message, user_data=None):
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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    sender_id = client.me.id
    if user_data is None:
        user_data = await user_sessions.find_one({"bot_id": sender_id})
        if not user_data:
            user_data = {}
            await user_sessions.update_one(
                {"bot_id": sender_id},
                {"$setOnInsert": {"bot_id": sender_id}},
                upsert=True
            )

    if not isinstance(message, CallbackQuery):
        if not message.reply_to_message:
            return await rich_reply(message, rich_note(Messages.REPLY_TO_BROADCAST), client=client)

        is_fbroadcast = bool(message.command and message.command[0].lower().startswith("f"))
        if is_fbroadcast and not user_data.get('forward'):
            user_data['forward'] = True
            await user_sessions.update_one(
                {"bot_id": sender_id},
                {"$set": {"forward": True}},
                upsert=True
            )

        broadcast_message[client.me.id] = [
            message.reply_to_message,
            user_data.get('forward', False)
        ]

    group = user_data.get('group', True)
    private = user_data.get('private', True)
    ugroup = user_data.get('ugroup', False)
    uprivate = user_data.get('uprivate', False)
    bot = user_data.get('bot', True)
    userbot = user_data.get('userbot', False)
    pin = user_data.get('pin', False)
    forward = user_data.get('forward', False)

    for_bot = [
        InlineKeyboardButton(
            "Group",
            callback_data="toggle_group",
            style=ButtonStyle.SUCCESS if group else ButtonStyle.DEFAULT,
            icon_custom_emoji_id=Emoji.TICK if group else Emoji.UNTICK,
        ),
        InlineKeyboardButton(
            "Private",
            callback_data="toggle_private",
            style=ButtonStyle.SUCCESS if private else ButtonStyle.DEFAULT,
            icon_custom_emoji_id=Emoji.TICK if private else Emoji.UNTICK,
        ),
        InlineKeyboardButton(
            "Pin",
            callback_data="toggle_pin",
            style=ButtonStyle.SUCCESS if pin else ButtonStyle.DEFAULT,
            icon_custom_emoji_id=Emoji.TICK if pin else Emoji.UNTICK,
        ),
    ]

    for_userbot = [
        InlineKeyboardButton(
            "Group",
            callback_data="toggle_ugroup",
            style=ButtonStyle.SUCCESS if ugroup else ButtonStyle.DEFAULT,
            icon_custom_emoji_id=Emoji.TICK if ugroup else Emoji.UNTICK,
        ),
        InlineKeyboardButton(
            "Private",
            callback_data="toggle_uprivate",
            style=ButtonStyle.SUCCESS if uprivate else ButtonStyle.DEFAULT,
            icon_custom_emoji_id=Emoji.TICK if uprivate else Emoji.UNTICK,
        ),
    ]

    buttons = [
        [
            InlineKeyboardButton(
                "Sender Name",
                callback_data="toggle_forward",
                style=ButtonStyle.SUCCESS if forward else ButtonStyle.DEFAULT,
                icon_custom_emoji_id=Emoji.TICK if forward else Emoji.UNTICK,
            )
        ],
        [
            InlineKeyboardButton(
                "From Bot",
                callback_data="toggle_bot",
                style=ButtonStyle.SUCCESS if bot else ButtonStyle.DEFAULT,
                icon_custom_emoji_id=Emoji.TICK if bot else Emoji.UNTICK,
            )
        ],
        for_bot if bot else [],
        [
            InlineKeyboardButton(
                "From Assistant",
                callback_data="toggle_userbot",
                style=ButtonStyle.SUCCESS if userbot else ButtonStyle.DEFAULT,
                icon_custom_emoji_id=Emoji.TICK if userbot else Emoji.UNTICK,
            )
        ],
        for_userbot if userbot else [],
        [InlineKeyboardButton("🚀 sᴛᴀʀᴛ ʙʀᴏᴀᴅᴄᴀsᴛ", callback_data="broadcast", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ROCKET)],
    ]

    # Filter out empty button rows
    buttons = [row for row in buttons if row]

    mess_text = await get_status(client, user_data=user_data)

    if isinstance(message, CallbackQuery):
        await rich_edit(
            message,
            mess_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await rich_reply(
            message,
            mess_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            client=client
        )
