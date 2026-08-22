"""plugins/admin_auth.py — Authorisation: /auth /unauth /block /unblock /blocklist."""

from plugins._common import *  # noqa: F401,F403


def _auth_card(headline: str, user_id: int, status: str) -> str:
    """Ephemeral confirmation card: the catalogued headline plus a compact
    user/id/status table. Shared by /auth /unauth /block /unblock so the four
    handlers stay visually consistent without duplicating markup."""
    return headline + rich_kv_table([
        (f"{EmojiTag.USER} ᴜsᴇʀ ɪᴅ", rich_code(user_id)),
        (f"{EmojiTag.SHIELD} sᴛᴀᴛᴜs", f"<b>{status}</b>"),
    ])


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
                return await rich_reply(message, rich_note(Messages.OWNER_AUTH_ALL), ephemeral=True, client=client)

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
                    await rich_reply(message, _auth_card(Messages.USER_AUTH.format(replied_user_id), replied_user_id, "ᴀᴜᴛʜᴏʀɪᴢᴇᴅ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_ALREADY_AUTH.format(replied_user_id)), ephemeral=True, client=client)
            else:
                await rich_reply(message, rich_note(Messages.CANT_AUTH_SELF), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.NOT_FROM_USER), ephemeral=True, client=client)
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
                    await rich_reply(message, _auth_card(Messages.USER_AUTH.format(user_id_to_auth), user_id_to_auth, "ᴀᴜᴛʜᴏʀɪᴢᴇᴅ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_ALREADY_AUTH.format(user_id_to_auth)), ephemeral=True, client=client)
            except ValueError:
                await rich_reply(message, rich_note(Messages.INVALID_USER_ID), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.REPLY_OR_PROVIDE_ID), ephemeral=True, client=client)


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
                return await rich_reply(message, rich_note(Messages.CANT_REMOVE_AUTH_OWNER), ephemeral=True, client=client)

            # Check if user can be unauthorized using global AUTH
            if replied_user_id in AUTH[str(chat_id)]:
                AUTH[str(chat_id)].remove(replied_user_id)
                # Update database to maintain persistence (low priority)
                db_task(user_sessions.update_one(
                    {"bot_id": client.me.id},
                    {"$set": {'auth_users': AUTH}},
                    upsert=True
                ))
                await rich_reply(message, _auth_card(Messages.USER_REMOVED_AUTH.format(replied_user_id), replied_user_id, "ᴜᴏᴀᴜᴛʜᴏʀɪᴢᴇᴅ"), ephemeral=True, client=client)
            else:
                await rich_reply(message, rich_note(Messages.USER_NOT_AUTH.format(replied_user_id)), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.NOT_FROM_USER), ephemeral=True, client=client)
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
                    await rich_reply(message, _auth_card(Messages.USER_REMOVED_AUTH.format(user_id_to_unauth), user_id_to_unauth, "ᴜᴏᴀᴜᴛʜᴏʀɪᴢᴇᴅ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_NOT_AUTH.format(user_id_to_unauth)), ephemeral=True, client=client)
            except ValueError:
                await rich_reply(message, rich_note(Messages.INVALID_USER_ID), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.REPLY_OR_PROVIDE_ID), ephemeral=True, client=client)


@Client.on_message(filters.command(["authlist", "authusers"]) & filters.group)
async def authlist_handler(client, message):
    chat_id = message.chat.id
    auth_users = AUTH.get(str(chat_id), [])
    if not auth_users:
        return await rich_reply(message, rich_note("<b>ɴᴏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs ɪɴ ᴛʜɪs ᴄʜᴀᴛ.</b>"), ephemeral=True, client=client)

    table = rich_table(
        ["#", "ᴜsᴇʀ ɪᴅ"],
        [(rich_code(i), rich_code(uid)) for i, uid in enumerate(auth_users, 1)],
    )
    body = table if len(auth_users) <= 10 else rich_details(
        f"sʜᴏᴡ ᴀʟʟ {len(auth_users)} ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs", table
    )
    authlist_text = (
        rich_heading(f"{EmojiTag.USER} ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs", 1)
        + body
        + rich_note(f"{EmojiTag.INFO} ᴜsᴇ {rich_code('/unauth <user id>')} ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴀᴄᴄᴇss.")
    )
    await rich_reply(message, authlist_text, client=client)


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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    # Check if the message is a reply
    if message.reply_to_message:
        replied_message = message.reply_to_message
        # If the replied message is from a user (and not from the bot itself)
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id
            if replied_user_id in get_admin_ids(admin_file):
                return await rich_reply(message, rich_note(Messages.OWNER_BLOCK_RESTRICT), ephemeral=True, client=client)
            # Check if the replied user is the same as the current chat (group) id
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self and not OWNER_ID == replied_user_id:
                if replied_user_id not in BLOCK:
                    BLOCK.append(replied_user_id)
                    # Update database to maintain persistence (low priority)
                    db_task(collection.update_one({"bot_id": client.me.id},
                                        {"$push": {'busers': replied_user_id}},
                                        upsert=True))
                    await rich_reply(message, _auth_card(Messages.USER_BLOCKED.format(replied_user_id), replied_user_id, "ʙʟᴏᴄᴋᴇᴅ"), ephemeral=True, client=client)
                else:
                   return await rich_reply(message, rich_note(Messages.USER_ALREADY_BLOCKED.format(replied_user_id)), ephemeral=True, client=client)

            else:
                await rich_reply(message, rich_note(Messages.CANT_BLOCK_SELF), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.NOT_FROM_USER), ephemeral=True, client=client)
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
                    await rich_reply(message, _auth_card(Messages.USER_BLOCKED.format(user_id_to_block), user_id_to_block, "ʙʟᴏᴄᴋᴇᴅ"), ephemeral=True, client=client)
                else:
                   return await rich_reply(message, rich_note(Messages.USER_ALREADY_BLOCKED.format(user_id_to_block)), ephemeral=True, client=client)
            except ValueError:
                await rich_reply(message, rich_note(Messages.INVALID_USER_ID), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.REPLY_OR_PROVIDE_ID), ephemeral=True, client=client)


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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

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
            await rich_reply(message, _auth_card(Messages.REMOVED_FROM_BLOCKLIST.format(replied_user_id), replied_user_id, "ᴜɴʙʟᴏᴄᴋᴇᴅ"), ephemeral=True, client=client)
        else:
            return await rich_reply(message, rich_note(Messages.NOT_IN_BLOCKLIST.format(replied_user_id)), ephemeral=True, client=client)

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
                    await rich_reply(message, _auth_card(Messages.REMOVED_FROM_BLOCKLIST.format(target_user_id), target_user_id, "ᴜɴʙʟᴏᴄᴋᴇᴅ"), ephemeral=True, client=client)
                else:
                    return await rich_reply(message, rich_note(Messages.NOT_IN_BLOCKLIST.format(target_user_id)), ephemeral=True, client=client)
            except ValueError:
                await rich_reply(message, rich_note(Messages.INVALID_USER_ID), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.REPLY_OR_PROVIDE_ID), ephemeral=True, client=client)


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
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    # Check for admin or owner


    # Fetch blocklist from the database
    user_data = await collection.find_one({"bot_id": client.me.id})
    if not user_data:
        return await rich_reply(message, rich_note(Messages.NO_BLOCKLIST), ephemeral=True, client=client)

    blocked_users = user_data.get('busers', [])
    if not blocked_users:
        return await rich_reply(message, rich_note(Messages.NO_USERS_BLOCKED), ephemeral=True, client=client)

    table = rich_table(
        ["#", "ᴜsᴇʀ ɪᴅ"],
        [(rich_code(i), rich_code(blocked_id)) for i, blocked_id in enumerate(blocked_users, 1)],
    )
    body = table if len(blocked_users) <= 10 else rich_details(
        f"sʜᴏᴡ ᴀʟʟ {len(blocked_users)} ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs", table
    )
    blocklist_text = (
        rich_heading(f"{EmojiTag.BLOCKED} ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs", 1)
        + body
        + rich_note(f"{EmojiTag.INFO} ᴜsᴇ {rich_code('/unblock <user id>')} ᴛᴏ ʀᴇᴏᴡ ᴀᴄᴄᴇss.")
    )
    await rich_reply(message, blocklist_text, client=client)
