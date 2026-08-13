"""plugins/admin_auth.py — Authorisation: /auth /unauth /block /unblock /blocklist."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command("auth") & filters.group)
@admin_only()
async def auth_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    _user_id = message.from_user.id

    chat_id = message.chat.id

    # Use global AUTH variable and ensure chat exists
    if str(chat_id) not in AUTH:
        AUTH[str(chat_id)] = []

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if replied user is admin (use cache)
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.OWNER_AUTH_ALL, link_preview_options=None)

            # Check if user can be authorized
            if (replied_user_id != message.chat.id and
                not replied_message.from_user.is_self and
                not OWNER_ID == replied_user_id):

                # Check if user is already authorized in this chat using global AUTH
                if replied_user_id not in AUTH[str(chat_id)]:
                    AUTH[str(chat_id)].append(replied_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(user_sessions.update_one(
                        {"bot_id": client.me.id},
                        {"$set": {'auth_users': AUTH}},
                        upsert=True
                    ))
                    await message.reply(Messages.USER_AUTH.format(replied_user_id), link_preview_options=None)
                else:
                    await message.reply(Messages.USER_ALREADY_AUTH.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.CANT_AUTH_SELF, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_auth = int(command_parts[1])
                # Check if user is already authorized in this chat using global AUTH
                if user_id_to_auth not in AUTH[str(chat_id)]:
                    AUTH[str(chat_id)].append(user_id_to_auth)
                    # Update database to maintain persistence (low priority)
                    db_task(user_sessions.update_one(
                        {"bot_id": client.me.id},
                        {"$set": {'auth_users': AUTH}},
                        upsert=True
                    ))
                    await message.reply(Messages.USER_AUTH.format(user_id_to_auth), link_preview_options=None)
                else:
                    await message.reply(Messages.USER_ALREADY_AUTH.format(user_id_to_auth), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("unauth") & filters.group)
@admin_only()
async def unauth_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    chat_id = message.chat.id

    # Ensure chat exists in global AUTH
    if str(chat_id) not in AUTH:
        AUTH[str(chat_id)] = []

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if replied user is admin (use cache)
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.CANT_REMOVE_AUTH_OWNER, link_preview_options=None)

            # Check if user can be unauthorized using global AUTH
            if replied_user_id in AUTH[str(chat_id)]:
                AUTH[str(chat_id)].remove(replied_user_id)
                # Update database to maintain persistence (low priority)
                db_task(user_sessions.update_one(
                    {"bot_id": client.me.id},
                    {"$set": {'auth_users': AUTH}},
                    upsert=True
                ))
                await message.reply(Messages.USER_REMOVED_AUTH.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.USER_NOT_AUTH.format(replied_user_id), link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_unauth = int(command_parts[1])
                # Check if user is authorized in this chat using global AUTH
                if user_id_to_unauth in AUTH[str(chat_id)]:
                    AUTH[str(chat_id)].remove(user_id_to_unauth)
                    # Update database to maintain persistence (low priority)
                    db_task(user_sessions.update_one(
                        {"bot_id": client.me.id},
                        {"$set": {'auth_users': AUTH}},
                        upsert=True
                    ))
                    await message.reply(Messages.USER_REMOVED_AUTH.format(user_id_to_unauth), link_preview_options=None)
                else:
                    await message.reply(Messages.USER_NOT_AUTH.format(user_id_to_unauth), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("block"))
async def block_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    admin_ids = get_admin_ids(admin_file)
    is_admin = user_id in admin_ids

    # Check permissions using global SUDO variable
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in SUDO
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    # Check if the message is a reply
    if message.reply_to_message:
        replied_message = message.reply_to_message
        # If the replied message is from a user (and not from the bot itself)
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.OWNER_BLOCK_RESTRICT, link_preview_options=None)
            # Check if the replied user is the same as the current chat (group) id
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self and not OWNER_ID == replied_user_id:
                if replied_user_id not in BLOCK:
                    BLOCK.append(replied_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$push": {'busers': replied_user_id}},
                                        upsert=True))
                    await message.reply(Messages.USER_BLOCKED.format(replied_user_id), link_preview_options=None)
                else:
                   return await message.reply(Messages.USER_ALREADY_BLOCKED.format(replied_user_id), link_preview_options=None)

            else:
                await message.reply(Messages.CANT_BLOCK_SELF, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_block = int(command_parts[1])
                # Block the user with the provided user ID using global BLOCK
                if user_id_to_block not in BLOCK:
                    BLOCK.append(user_id_to_block)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$push": {'busers': user_id_to_block}},
                                        upsert=True
                                    ))
                    await message.reply(Messages.USER_BLOCKED.format(user_id_to_block), link_preview_options=None)
                else:
                   return await message.reply(Messages.USER_ALREADY_BLOCKED.format(user_id_to_block), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("unblock"))
async def unblock_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    is_admin = user_id in get_admin_ids(admin_file)

    # Check permissions using global SUDO variable
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in SUDO
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    if message.reply_to_message:
        replied_message = message.reply_to_message
        replied_user_id = replied_message.from_user.id

        # Check if user is in blocklist using global BLOCK
        if replied_user_id in BLOCK:
            BLOCK.remove(replied_user_id)
            # Update database to maintain persistence (low priority)
            db_task(collection.update_one({"bot_id": client.me.id},
                                {"$pull": {'busers': replied_user_id}},
                                upsert=True))
            await message.reply(Messages.REMOVED_FROM_BLOCKLIST.format(replied_user_id), link_preview_options=None)
        else:
            return await message.reply(Messages.NOT_IN_BLOCKLIST.format(replied_user_id), link_preview_options=None)

    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if user is in blocklist using global BLOCK
                if target_user_id in BLOCK:
                    BLOCK.remove(target_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$pull": {'busers': target_user_id}},
                                        upsert=True))
                    await message.reply(Messages.REMOVED_FROM_BLOCKLIST.format(target_user_id), link_preview_options=None)
                else:
                    return await message.reply(Messages.NOT_IN_BLOCKLIST.format(target_user_id), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("blocklist"))
async def blocklist_handler(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
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

    # Check for admin or owner


    # Fetch blocklist from the database
    user_data = await collection.find_one({"bot_id": client.me.id})
    if not user_data:
        return await message.reply(Messages.NO_BLOCKLIST, link_preview_options=None)

    blocked_users = user_data.get('busers', [])
    if not blocked_users:
        return await message.reply(Messages.NO_USERS_BLOCKED, link_preview_options=None)

    blocklist_text = f"<b>{EmojiTag.BLOCKED} ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs:</b>\n" + "\n".join([f"• <code>{user_id}</code>" for user_id in blocked_users])
    await message.reply_text(blocklist_text, link_preview_options=None)
