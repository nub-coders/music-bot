"""plugins/broadcast.py — Broadcast flow and stats commands."""

from plugins._common import *  # noqa: F401,F403


@Client.on_callback_query(filters.regex("broadcast"))
async def broadcast_callback_handler(client, callback_query):
    # Fetch user data for the callback query
    user_data = await user_sessions.find_one({"bot_id": client.me.id})
    if not user_data:
        return await callback_query.answer(Messages.USER_DATA_NOT_FOUND, show_alert=True)
    group = user_data.get('group')
    private = user_data.get('private')
    ugroup = user_data.get('ugroup')
    uprivate = user_data.get('uprivate')
    bot = user_data.get('bot')
    userbot = user_data.get('userbot')
    pin = user_data.get('pin')
    await callback_query.message.delete()
    # Fetch bot data
    bot_data = await collection.find_one({"bot_id": client.me.id})
    message_to_broadcast, forwarding = broadcast_message.get(client.me.id)
    if bot_data and bot:
        X = await callback_query.message.reply(Messages.START_BOT_BROADCAST, link_preview_options=None)
        users = bot_data.get('users', [])
        progress_msg = ""
        u, g, sg, a_chat = 0, 0, 0, 0

        # Use asyncio.gather for efficient parallel processing
        chat_types = await asyncio.gather(
            *[get_chat_type(client, chat_id) for chat_id in users]
        )

        # Prepare message for broadcast
        if not message_to_broadcast:
            return await callback_query.answer(Messages.NO_MSG_FOR_BROADCAST, show_alert=True)

        for i, chat_type in enumerate(chat_types):
            if not chat_type:
                continue  # Skip if chat type could not be fetched

            # Handle the chat based on its type and flags
            try:
                if chat_type == enums.ChatType.PRIVATE and private:
                    await message_to_broadcast.copy(users[i])  if not forwarding else await message_to_broadcast.forward(users[i])
                    u+=1

                elif chat_type in (enums.ChatType.SUPERGROUP, enums.ChatType.GROUP) and group:
                    # Handle supergroup-specific actions
                    sent_message = await message_to_broadcast.copy(users[i]) if not forwarding else await message_to_broadcast.forward(users[i])
                    if chat_type == enums.ChatType.SUPERGROUP:
                        sg+=1
                    else:
                        g+=1
                    if pin:
                      try:
                        user_s = await client.get_chat_member(users[i], client.me.id)
                        if user_s.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
                            await sent_message.pin()
                            a_chat += 1
                      except FloodWait as e:
                              await asyncio.sleep(e.value)
                      except Exception as e:
                        logger.info(f"Error getting chat member status for {users[i]}: {e}")
                else:
                       continue

                # Update progress for each broadcast action (optional)
                progress_msg = f"Broadcasting to {u} private, {g} groups, {sg} supergroups, and {a_chat} pinned messages"
                await X.edit(progress_msg)
            except Exception as e:
                logger.info(f"Error in broadcasting to {users[i]}: {e}")
        await X.edit(f"Broadcasted to {u} private, {g} groups, {sg} supergroups, and {a_chat} pinned messages from bot")
    bot_username = client.me.username


    if userbot and session:
        XX = await callback_query.message.reply(Messages.START_ASSISTANT_BROADCAST, link_preview_options=None)
        uu, ug, usg, _ua_chat = 0, 0, 0, 0
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
             raise Exception("broadcast msg not found")
            # Broadcast to all dialogs
            async for dialog in session.get_dialogs():
                chat_id = dialog.chat.id
                chat_type = dialog.chat.type
                if str(chat_id) == str(-1001806816712):
                      continue
                try:
                    if chat_type == enums.ChatType.PRIVATE and uprivate:
                        await msg.copy(chat_id)
                        uu += 1

                    elif chat_type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP) and ugroup:
                        sent_message = await msg.copy(chat_id)  if not forwarding else await message_to_broadcast.forward(users[i])
                        if chat_type == enums.ChatType.SUPERGROUP:
                            usg += 1
                        else:
                            ug += 1

                    else:
                       continue
                    # Update progress
                    progress_text = (
                        f"Broadcasting via assistant...\n\n"
                        f"Private Chats: {uu}\n"
                        f"Groups: {ug}\n"
                        f"Supergroups: {usg}\n"
                    )
                    await XX.edit(progress_text)
                except FloodWait as e:
                               await asyncio.sleep(e.value)
                except Exception as e:
                    logger.info(f"Error broadcasting to {chat_id}: {e}")

        except Exception as e:
            logger.info(f"Error with session broadcast: {e}")
            await XX.reply(f"An error occurred during userbot broadcasting.{e}", link_preview_options=None)

    # Finalize broadcast summary
        await XX.edit(
        f"Broadcast completed!\n\n"
        f"Private Chats: {uu}\n"
        f"Groups: {ug}\n"
        f"Supergroups: {usg}\n"
    )


async def get_status(client):

  _start = datetime.datetime.now()
  u = g = sg = a_chat =  0 # Initialize counters
  user_data = await collection.find_one({"bot_id": client.me.id})
  mess=""

  if user_data:
    users = user_data.get('users', [])
    _progress_msg = ""

    if len(users) > 500:
        mess += (
            f"<b>BOT STATS:</b>\n"
            f"<blockquote><b>`Stored users = {len(users)}`</b>\n"
            f"<b>`Detailed stats skipped to avoid timeout`</b></blockquote>"
        )
        mess += ("\n\n<blockquote><b>CHOOSE THE OPTIONS BELOW⬇️⬇️ FOR BRODCASTING</b></blockquote>")
        broadcasts[client.me.id] = mess
        return mess

    chat_type_cache = dict(user_data.get('chat_type_cache', {}))

    for i, chat_id in enumerate(users):
        chat_type = await get_cached_chat_type(client, client.me.id, chat_id, chat_type_cache)
        if chat_type is None:
            continue # Skip if chat type could not be fetched

        if chat_type == enums.ChatType.PRIVATE:
            u += 1
        elif chat_type == enums.ChatType.GROUP:
            g += 1
        elif chat_type == enums.ChatType.SUPERGROUP:
            sg += 1
            try:
                user_s = await client.get_chat_member(users[i], int(client.me.id))
                if user_s.status in (
                    enums.ChatMemberStatus.OWNER,
                    enums.ChatMemberStatus.ADMINISTRATOR,
                ):
                    a_chat += 1
            except Exception as e:
                logger.info(f"Error getting chat member status for {users[i]}: {e}")
    mess += (
        f"""<b>BOT STATS:</b>
<blockquote><b>`Private chats = {u}</b>`
<b>`Groups = {g}`
<b>`Super Groups = {sg}`<b>
<b>`Admin in Chats = {a_chat}`</b></blockquote>""")

    uu = ug = usg  = ua_chat =0
    async for dialog in session.get_dialogs():
        try:
            if dialog.chat.type == enums.ChatType.PRIVATE:
                uu += 1
            elif dialog.chat.type == enums.ChatType.GROUP:
                ug += 1
            elif dialog.chat.type == enums.ChatType.SUPERGROUP:
                usg += 1
                user_s = await dialog.chat.get_member(int(session.me.id))
                if user_s.status in (
                    enums.ChatMemberStatus.OWNER,
                    enums.ChatMemberStatus.ADMINISTRATOR,
                ):
                    ua_chat += 1
        except Exception:
            pass

    mess += (
        f"""\n\n<b>ASSISTANT STATS:</b>
<blockquote><b>`Private Messages = {uu}`
<b>`Groups = {ug}`
<b>`Super Groups = {usg}`<b>
<b>`Admin in Chats = {ua_chat}`</b></blockquote>"""
    )
    mess += ("\n\n<blockquote><b>CHOOSE THE OPTIONS BELOW⬇️⬇️ FOR BRODCASTING</b></blockquote>")
    broadcasts[client.me.id] = mess
    return mess
  else:
    return


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


@Client.on_callback_query(filters.regex(r"toggle_(.*)"))
async def toggle_setting(client, callback_query):
    sender_id = client.me.id

    user_data = await user_sessions.find_one({"bot_id": sender_id})
    if not user_data:
        return await callback_query.answer(Messages.USER_DATA_NOT_FOUND, show_alert=True)
    setting_to_toggle = callback_query.data.split("_", 1)[1]
    current_value = user_data.get(setting_to_toggle)
    new_value = not current_value
    db_task(user_sessions.update_one(
        {"bot_id": sender_id},
        {"$set": {setting_to_toggle: new_value}}
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
        return await message.reply(Messages.USER_DATA_NOT_FOUND, link_preview_options=None)
    if not isinstance(message, CallbackQuery):
      if not message.reply_to_message:
        return await message.reply(Messages.REPLY_TO_BROADCAST, link_preview_options=None)
      broadcast_message[client.me.id] = [message.reply_to_message]
      broadcast_message[client.me.id].append(True if message.command[0].lower().startswith("f") else None)
    group = user_data.get('group')
    private = user_data.get('private')
    ugroup = user_data.get('ugroup')
    uprivate = user_data.get('uprivate')
    bot = user_data.get('bot')
    userbot = user_data.get('userbot')
    pin = user_data.get('pin')
    for_bot =[
            InlineKeyboardButton(f"Gʀᴏᴜᴘ {'✅' if group else '❌'}", callback_data="toggle_group"),
            InlineKeyboardButton(f"Pʀɪᴠᴀᴛᴇ {'✅' if private else '❌'}", callback_data="toggle_private"),
            InlineKeyboardButton(f"📌Pɪɴ {'✅' if pin else '❌'}", callback_data="toggle_pin"),]

    for_userbot = [
            InlineKeyboardButton(f"Gʀᴏᴜᴘ {'✅' if ugroup else '❌'}", callback_data="toggle_ugroup"),
            InlineKeyboardButton(f"Pʀɪᴠᴀᴛᴇ {'✅' if uprivate else '❌'}", callback_data="toggle_uprivate"),]
    buttons = [
            [InlineKeyboardButton(f"Fʀᴏᴍ ʙᴏᴛ {'⬇️' if bot else '❌'}", callback_data="toggle_bot"),], for_bot if bot else [],
        [
            InlineKeyboardButton(f"Fʀᴏᴍ ᴜꜱᴇʀʙᴏᴛ {'⬇️' if userbot else '❌'}", callback_data="toggle_userbot"),], for_userbot if userbot else [],
    ]


    buttons.append([InlineKeyboardButton("BROADCAST🚀🚀", callback_data="broadcast")])
    if isinstance(message, CallbackQuery):  # If it's a button click (CallbackQuery)
        if client.me.id not in broadcasts:
           await get_status(client)
        await message.edit_message_text(
            broadcasts[client.me.id],
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:  # If it's a normal command message
        mess = await message.reply(Messages.GETTING_CHATS, link_preview_options=None)
        await get_status(client)
        if broadcasts[client.me.id]:
           await mess.edit(
            broadcasts[client.me.id],
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        else:
           await message.reply(Messages.NO_DATA_FOUND, link_preview_options=None)
