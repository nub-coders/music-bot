"""plugins/broadcast.py — Broadcast flow and stats commands."""

from plugins._common import *  # noqa: F401,F403
from rate_limiter import broadcast_semaphore, allow_broadcast, wait_broadcast_slot, broadcast_message_lock


@Client.on_callback_query(filters.regex(r"^broadcast$"))
async def broadcast_callback_handler(client, callback_query):
    # Prevent concurrent broadcasts globally
    sem = broadcast_semaphore()
    if sem.locked():
        return await callback_query.answer(
            "Another broadcast is in progress. Please wait.", show_alert=True
        )

    async with sem:
        # Rate limit check (non-blocking - reject if no tokens)
        if not await allow_broadcast():
            return await callback_query.answer(
                "Broadcast rate limit reached. Please wait a moment.", show_alert=True
            )

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
                    # Rate limit per-message sends
                    await wait_broadcast_slot(max_wait=1.0)

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
                                await sent_message.pin(both_sides=False)
                            except Exception:
                                pass

                        a_chat += 1

                        # Update progress every 3 seconds
                        if time.time() - last_edit_time > 3:
                            last_edit_time = time.time()
                            await draft.update(rich_note(
                                Messages.BROADCAST_PROGRESS.format(
                                    sent=u + g, users=u, groups=g, chats=a_chat
                                )
                            ))

                    except FloodWait as e:
                        # Respect Telegram's backoff
                        await asyncio.sleep(e.value)
                        # Retry once
                        try:
                            sent_message = await message_to_broadcast.forward(cid) if forward else await message_to_broadcast.copy(cid)
                            if is_private:
                                u += 1
                            else:
                                g += 1
                            a_chat += 1
                        except Exception:
                            pass
                    except Exception:
                        pass

                await draft.update(rich_note(
                    Messages.BROADCAST_COMPLETE.format(sent=u + g, users=u, groups=g)
                ))

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
                    # Rate limit per-message sends for assistant too
                    await wait_broadcast_slot(max_wait=1.0)

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

                        if time.time() - last_edit_time > 3:
                            last_edit_time = time.time()
                            await draft.update(rich_note(
                                Messages.ASSISTANT_BROADCAST_PROGRESS.format(
                                    sent=uu + ug, users=uu, groups=ug
                                )
                            ))

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
                        except Exception:
                            pass
                    except Exception:
                        pass

                await draft.update(rich_note(
                    Messages.ASSISTANT_BROADCAST_COMPLETE.format(sent=uu + ug, users=uu, groups=ug)
                ))

            except Exception as e:
                await draft.update(rich_note(f"Assistant broadcast failed: {e}"))


@Client.on_callback_query(filters.regex(r"^compare$"))
async def compare_message(mess, client, session):
    mess_file_id = None
    if mess.media:
        if hasattr(mess.media, 'photo') and mess.photo:
            mess_file_id = mess.photo.file_id
        elif hasattr(mess.media, 'video') and mess.video:
            mess_file_id = mess.video.file_id
        elif hasattr(mess.media, 'document') and mess.document:
            mess_file_id = mess.document.file_id
        elif hasattr(mess.media, 'audio') and mess.audio:
            mess_file_id = mess.audio.file_id
        elif hasattr(mess.media, 'voice') and mess.voice:
            mess_file_id = mess.voice.file_id
        elif hasattr(mess.media, 'animation') and mess.animation:
            mess_file_id = mess.animation.file_id
        elif hasattr(mess.media, 'sticker') and mess.sticker:
            mess_file_id = mess.sticker.file_id

    try:
        async for msg in session.get_chat_history(session.me.id, limit=20):
            msg_file_id = None
            if msg.media:
                if hasattr(msg.media, 'photo') and msg.photo:
                    msg_file_id = msg.photo.file_id
                elif hasattr(msg.media, 'video') and msg.video:
                    msg_file_id = msg.video.file_id
                elif hasattr(msg.media, 'document') and msg.document:
                    msg_file_id = msg.document.file_id
                elif hasattr(msg.media, 'audio') and msg.audio:
                    msg_file_id = msg.audio.file_id
                elif hasattr(msg.media, 'voice') and msg.voice:
                    msg_file_id = msg.voice.file_id
                elif hasattr(msg.media, 'animation') and msg.animation:
                    msg_file_id = msg.animation.file_id
                elif hasattr(msg.media, 'sticker') and msg.sticker:
                    msg_file_id = msg.sticker.file_id

            # Compare file IDs
            if mess_file_id and msg_file_id and mess_file_id == msg_file_id:
                return msg
    except AttributeError:
        # Skip if media attributes are not accessible
        pass

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
@admin_only()
async def status_command_handler(client, message):
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

        async with broadcast_message_lock():
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

    if isinstance(message, CallbackQuery):
        await message.message.delete()
    else:
        await message.delete()

    # Broadcast settings menu
    btns = []
    settings = [
        ("group", "👥 Groups", group),
        ("private", "👤 Private", private),
        ("ugroup", "👥 Userbot Groups", ugroup),
        ("uprivate", "👤 Userbot Private", uprivate),
        ("bot", "🤖 Bot Broadcast", bot),
        ("userbot", "👤 Userbot Broadcast", userbot),
        ("pin", "📌 Pin Messages", pin),
        ("forward", "↗️ Forward Mode", forward),
    ]

    for key, label, value in settings:
        status = "✅" if value else "❌"
        btns.append([InlineKeyboardButton(f"{status} {label}", callback_data=f"toggle_{key}")])

    btns.append([InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="close")])

    markup = InlineKeyboardMarkup(btns)

    await rich_send(
        client,
        message.chat.id,
        rich_note(Messages.BROADCAST_SETTINGS.format(
            group="✅" if group else "❌",
            private="✅" if private else "❌",
            ugroup="✅" if ugroup else "❌",
            uprivate="✅" if uprivate else "❌",
            bot="✅" if bot else "❌",
            userbot="✅" if userbot else "❌",
            pin="✅" if pin else "❌",
            forward="✅" if forward else "❌",
        )),
        markup=markup,
    )
