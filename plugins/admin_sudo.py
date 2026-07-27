"""plugins/admin_sudo.py — Sudo management: /sudolist /addsudo /rmsudo /reboot /powers."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command("reboot") & filters.private)
async def reboot_handler(client: Client, message: Message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    is_admin = user_id in get_admin_ids(admin_file)

    # Authorization check using global SUDO variable
    is_authorized = (
        is_admin or
        str(OWNER_ID) == str(user_id) or
        user_id in SUDO
    )

    if not is_authorized:
        return await message.reply(Messages.OWNER_SUDO_CMD, link_preview_options=None)

    # Authorized: Reboot process
    await message.reply(Messages.REBOOTING, link_preview_options=None)
    os.system(f"kill -9 {os.getpid()}")  # Hard kill (optional after client.stop())


@Client.on_message(filters.command("sudolist"))
async def show_sudo_list(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    is_admin = user_id in get_admin_ids(admin_file)

    # Check permissions
    is_authorized = is_admin or str(OWNER_ID) == str(user_id)

    if not is_authorized:
        return await message.reply(Messages.PAID_OWNER_CMD, link_preview_options=None)
    try:
        users_data = await user_sessions.find_one({"bot_id": client.me.id})
        sudo_users = users_data.get("SUDOERS", []) if users_data else []

        if not sudo_users:
            return await message.reply(Messages.NO_SUDO_USERS, link_preview_options=None)

        # Build the sudo list message
        sudo_list = ["**🔱 SUDO USERS LIST:**\n"]
        number = 1

        for user_id in sudo_users:
                try:
                    # Try to get user info from Telegram
                    user_info = await client.get_users(user_id)
                    user_mention = f"@{user_info.username}" if user_info.username else user_info.first_name
                    sudo_list.append(f"**{number}➤** {user_mention} [`{user_id}`]")
                except Exception:
                    # If can't get user info, just show the ID
                    sudo_list.append(f"**{number}➤** Unknown User [`{user_id}`]")
                number += 1

        # Add count at the bottom
        sudo_list.append(f"\n**Total SUDO Users:** `{number-1}`")

        # Send the message
        await message.reply("\n".join(sudo_list), link_preview_options=None)

    except Exception as e:
        logger.error(f"[sudolist] Failed to fetch sudo list: {e}")
        await message.reply(Messages.ERR_FETCH_SUDO, link_preview_options=None)


@Client.on_message(filters.command("addsudo"))
async def add_to_sudo(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    admin_ids = get_admin_ids(admin_file)
    is_admin = user_id in admin_ids

    is_authorized = is_admin or str(OWNER_ID) == str(user_id)

    if not is_authorized:
        return await message.reply(Messages.OWNER_CMD, link_preview_options=None)

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is already admin
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.ALREADY_OWNER, link_preview_options=None)

            # Check if trying to add self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if replied_user_id not in sudoers:
                    asyncio.create_task(push_to_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", replied_user_id, upsert=True))
                    await message.reply(Messages.USER_ADDED_SUDO.format(replied_user_id), link_preview_options=None)
                    SUDO.append(replied_user_id)
                else:
                    await message.reply(Messages.USER_ALREADY_SUDO.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.CANT_SUDO_SELF, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is already admin
                if target_user_id in get_admin_ids(admin_file):
                    return await message.reply(Messages.ALREADY_OWNER, link_preview_options=None)

                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if target_user_id not in sudoers:
                    asyncio.create_task(push_to_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", target_user_id, upsert=True))
                    await message.reply(Messages.USER_ADDED_SUDO.format(target_user_id), link_preview_options=None)
                    SUDO.append(target_user_id)
                else:
                    await message.reply(Messages.USER_ALREADY_SUDO.format(target_user_id), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("rmsudo"))
async def remove_from_sudo(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    admin_ids = get_admin_ids(admin_file)
    is_admin = user_id in admin_ids

    is_authorized = is_admin or (user_id == OWNER_ID)

    if not is_authorized:
        return await message.reply(Messages.OWNER_CMD, link_preview_options=None)

    # Handle reply to message
    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is an admin
            if replied_user_id in get_admin_ids(admin_file):
                return await message.reply(Messages.CANT_REMOVE_OWNER_SUDO, link_preview_options=None)

            # Check if trying to remove self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                if not users_data:
                    return await message.reply(Messages.USER_NOT_IN_DB.format(replied_user_id), link_preview_options=None)
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if replied_user_id in sudoers:
                    asyncio.create_task(pull_from_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", replied_user_id))
                    await message.reply(Messages.USER_REMOVED_SUDO.format(replied_user_id), link_preview_options=None)
                    SUDO.remove(replied_user_id)
                else:
                    await message.reply(Messages.USER_NOT_IN_SUDO.format(replied_user_id), link_preview_options=None)
            else:
                await message.reply(Messages.CANT_REMOVE_SELF_SUDO, link_preview_options=None)
        else:
            await message.reply(Messages.NOT_FROM_USER, link_preview_options=None)
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is an admin
                if target_user_id in get_admin_ids(admin_file):
                    return await message.reply(Messages.CANT_REMOVE_OWNER_SUDO, link_preview_options=None)

                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                if not users_data:
                    return await message.reply(Messages.USER_NOT_IN_DB.format(target_user_id), link_preview_options=None)
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if target_user_id in sudoers:
                    asyncio.create_task(pull_from_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", target_user_id))
                    await message.reply(Messages.USER_REMOVED_SUDO.format(target_user_id), link_preview_options=None)
                    SUDO.remove(target_user_id)
                else:
                    await message.reply(Messages.USER_NOT_IN_SUDO.format(target_user_id), link_preview_options=None)
            except ValueError:
                await message.reply(Messages.INVALID_USER_ID, link_preview_options=None)
        else:
            await message.reply(Messages.REPLY_OR_PROVIDE_ID, link_preview_options=None)


@Client.on_message(filters.command("powers") & filters.group)
@admin_only()
async def handle_power_command(client, message):
    try:
        # Get bot's permissions in the group
        bot_member = await client.get_chat_member(
            chat_id=message.chat.id,
            user_id=client.me.id if not message.reply_to_message else message.reply_to_message.from_user.id
        )

        # Get chat info
        chat = await client.get_chat(message.chat.id)

        # Create permission status message
        power_message = (
            f"🤖 **{'Bot' if not message.reply_to_message else message.reply_to_message.from_user.mention()} Permissions in {chat.title}**\n\n"
            "📋 **Basic Powers:**\n"
        )

        # Basic permissions
        permissions = {
            "can_delete_messages": "Delete Messages",
            "can_restrict_members": "Restrict Members",
            "can_promote_members": "Promote Members",
            "can_change_info": "Change Group Info",
            "can_invite_users": "Invite Users",
            "can_pin_messages": "Pin Messages",
            "can_manage_video_chats": "Manage Video Chats",
            "can_manage_chat": "Manage Chat",
            "can_manage_topics": "Manage Topics"
        }

        # Add permission statuses
        for perm, display_name in permissions.items():
            status = getattr(bot_member.privileges, perm, False)
            emoji = "✅" if status else "❌"
            power_message += f"{emoji} {display_name}\n"

        # Add administrative status
        power_message += "\n📊 **Status:**\n"
        if bot_member.status == enums.ChatMemberStatus.ADMINISTRATOR:
            power_message += "✨ Bot is an **Administrator**"
        elif bot_member.status == enums.ChatMemberStatus.MEMBER:
            power_message += "👤 Bot is a **Regular Member**"
        else:
            power_message += "❓ Bot Status: " + str(bot_member.status).title()

        # Add anonymous admin status if applicable
        if hasattr(bot_member.privileges, "is_anonymous"):
            anon_status = "✅" if bot_member.privileges.is_anonymous else "❌"
            power_message += f"\n{anon_status} Anonymous Admin"

        # Add custom title if exists
        if hasattr(bot_member, "custom_title") and bot_member.custom_title:
            power_message += f"\n👑 Custom Title: **{bot_member.custom_title}**"

        await message.reply(
            power_message,
        link_preview_options=None)

    except Exception as e:
        logger.error(f"Power check error: {e}")
        await message.reply(Messages.ERROR_PERMISSIONS, link_preview_options=None)
