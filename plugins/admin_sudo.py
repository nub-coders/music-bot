"""plugins/admin_sudo.py — Sudo management: /sudolist /addsudo /rmsudo /reboot /powers."""

import sys
from plugins._common import *  # noqa: F401,F403


def _sudo_card(headline: str, user_id: int, status: str) -> str:
    """Ephemeral confirmation card for /addsudo and /rmsudo: the catalogued
    headline plus a compact id/status table."""
    return headline + rich_kv_table([
        (f"{EmojiTag.USER} ᴜsᴇʀ ɪᴅ", rich_code(user_id)),
        (f"{EmojiTag.SUDO} sᴛᴀᴛᴜs", f"<b>{status}</b>"),
    ])


# Sudo state lives in two places: the SUDOERS array in Mongo is authoritative, and
# the in-memory SUDO list is a mirror rebuilt from it at startup (main.py). These
# two helpers are the only sanctioned way to change either, so the pair cannot
# drift apart.
#
# The previous call sites used a bare asyncio.create_task() for the write and
# updated SUDO unconditionally afterwards. A failed write therefore vanished (a
# bare task's exception only surfaces if and when the task is garbage collected)
# while the reply still confirmed the change and the in-memory mirror still
# honoured it -- so the grant worked until the next restart and then silently did
# not. Awaiting the write is cheap; the caller reports failure instead.

async def _grant_sudo(client, user_id: int) -> bool:
    """Persist a sudo grant, then mirror it in memory. False if nothing was saved."""
    try:
        await push_to_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", user_id, upsert=True)
    except Exception as e:
        logger.error(f"[addsudo] Failed to persist SUDOERS grant for {user_id}: {e}", exc_info=True)
        return False
    if user_id not in SUDO:
        SUDO.append(user_id)
    return True


async def _revoke_sudo(client, user_id: int) -> bool:
    """Persist a sudo revocation, then mirror it in memory. False if nothing was saved."""
    try:
        await pull_from_array(user_sessions, {"bot_id": client.me.id}, "SUDOERS", user_id)
    except Exception as e:
        logger.error(f"[rmsudo] Failed to persist SUDOERS revocation for {user_id}: {e}", exc_info=True)
        return False
    # Guarded because list.remove() raises ValueError when the mirror has drifted
    # from the database -- the caller decided on the DB's copy, not this one.
    if user_id in SUDO:
        SUDO.remove(user_id)
    return True


@Client.on_message(filters.command("reboot") & filters.private)
async def reboot_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_bot_operator(user_id):
        return await rich_reply(message, rich_note(Messages.OWNER_SUDO_CMD), ephemeral=True, client=client)

    # Authorized: Reboot process
    await rich_reply(message, rich_note(Messages.REBOOTING), client=client)

    # Gracefully leave active calls and cleanup
    for cid in list(state.active):
        try:
            await remove_active_chat(client, cid)
        except Exception as e:
            logger.warning(f"[reboot] Error cleaning active chat {cid}: {e}")

    # Stop all assistant clients. Note: it is the pyrogram Clients that have
    # .stop() -- PyTgCalls (clients["calls"]) has no stop(), so calling it there
    # raised AttributeError that the bare except silently swallowed, leaving
    # every assistant session un-terminated across the os.execl re-exec.
    for idx, ast in clients.get("assistants", {}).items():
        try:
            await ast.stop()
        except Exception as e:
            logger.warning(f"[reboot] Error stopping assistant {idx}: {e}")

    # Close HTTP clients
    try:
        from thumbnails import close_session as close_thumbnail_session
        await close_thumbnail_session()
    except Exception as e:
        logger.debug(f"[reboot] Closing thumbnail HTTP session failed: {e}")
    try:
        from youtube import close_http_client
        await close_http_client()
    except Exception as e:
        logger.debug(f"[reboot] Closing YouTube HTTP client failed: {e}")

    # Restart process gracefully
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception:
        sys.exit(0)


@Client.on_message(filters.command("sudolist"))
async def show_sudo_list(client, message):
    # /sudolist, /addsudo and /rmsudo are not private-only, so an anonymous group
    # admin or a linked channel can reach them with from_user unset. No identity
    # means nothing to authorize -- fail closed rather than raise on .id.
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await rich_reply(message, rich_note(Messages.ADMIN_UNKNOWN_USER), ephemeral=True, client=client)
    if not is_owner_tier(user_id):
        return await rich_reply(message, rich_note(Messages.PAID_OWNER_CMD), ephemeral=True, client=client)
    try:
        users_data = await user_sessions.find_one({"bot_id": client.me.id})
        sudo_users = users_data.get("SUDOERS", []) if users_data else []

        if not sudo_users:
            return await rich_reply(message, rich_note(Messages.NO_SUDO_USERS), ephemeral=True, client=client)

        # Build the sudo list table
        sudo_rows = []
        number = 1

        for user_id in sudo_users:
                try:
                    # Try to get user info from Telegram
                    user_info = await client.get_users(user_id)
                    user_mention = f"@{user_info.username}" if user_info.username else user_info.first_name
                    sudo_rows.append((rich_code(number), rich_esc(user_mention), rich_code(user_id)))
                except Exception:
                    # If can't get user info, just show the ID
                    sudo_rows.append((rich_code(number), "Unknown User", rich_code(user_id)))
                number += 1

        # Send the message, with the total count as a footer note
        await rich_reply(
            message,
            rich_heading(f"{EmojiTag.SUDO} sᴜᴅᴏ ᴜsᴇʀs", 1)
            + rich_table(["#", "ᴜsᴇʀ", "ɪᴅ"], sudo_rows)
            + rich_note(f"{EmojiTag.CROWN} <b>Total SUDO Users:</b> {rich_code(number - 1)}"),
            client=client,
        )

    except Exception as e:
        logger.error(f"[sudolist] Failed to fetch sudo list: {e}")
        await rich_reply(message, rich_note(Messages.ERR_FETCH_SUDO), ephemeral=True, client=client)


@Client.on_message(filters.command("addsudo"))
async def add_to_sudo(client, message):
    admin_file = f"{ggg}/admin.txt"
    # See show_sudo_list.
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await rich_reply(message, rich_note(Messages.ADMIN_UNKNOWN_USER), ephemeral=True, client=client)
    if not is_owner_tier(user_id):
        return await rich_reply(message, rich_note(Messages.OWNER_CMD), ephemeral=True, client=client)

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is already admin
            if replied_user_id in get_admin_ids(admin_file):
                return await rich_reply(message, rich_note(Messages.ALREADY_OWNER), ephemeral=True, client=client)

            # Check if trying to add self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if replied_user_id not in sudoers:
                    if not await _grant_sudo(client, replied_user_id):
                        return await rich_reply(message, rich_note(Messages.ERR_SUDO_WRITE), ephemeral=True, client=client)
                    await rich_reply(message, _sudo_card(Messages.USER_ADDED_SUDO.format(replied_user_id), replied_user_id, "sᴜᴅᴏ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_ALREADY_SUDO.format(replied_user_id)), ephemeral=True, client=client)
            else:
                await rich_reply(message, rich_note(Messages.CANT_SUDO_SELF), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.NOT_FROM_USER), ephemeral=True, client=client)
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is already admin
                if target_user_id in get_admin_ids(admin_file):
                    return await rich_reply(message, rich_note(Messages.ALREADY_OWNER), ephemeral=True, client=client)

                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if target_user_id not in sudoers:
                    if not await _grant_sudo(client, target_user_id):
                        return await rich_reply(message, rich_note(Messages.ERR_SUDO_WRITE), ephemeral=True, client=client)
                    await rich_reply(message, _sudo_card(Messages.USER_ADDED_SUDO.format(target_user_id), target_user_id, "sᴜᴅᴏ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_ALREADY_SUDO.format(target_user_id)), ephemeral=True, client=client)
            except ValueError:
                await rich_reply(message, rich_note(Messages.INVALID_USER_ID), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.REPLY_OR_PROVIDE_ID), ephemeral=True, client=client)


@Client.on_message(filters.command("rmsudo"))
async def remove_from_sudo(client, message):
    admin_file = f"{ggg}/admin.txt"
    # See show_sudo_list.
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await rich_reply(message, rich_note(Messages.ADMIN_UNKNOWN_USER), ephemeral=True, client=client)
    if not is_owner_tier(user_id):
        return await rich_reply(message, rich_note(Messages.OWNER_CMD), ephemeral=True, client=client)

    # Handle reply to message
    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is an admin
            if replied_user_id in get_admin_ids(admin_file):
                return await rich_reply(message, rich_note(Messages.CANT_REMOVE_OWNER_SUDO), ephemeral=True, client=client)

            # Check if trying to remove self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                if not users_data:
                    return await rich_reply(message, rich_note(Messages.USER_NOT_IN_DB.format(replied_user_id)), ephemeral=True, client=client)
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if replied_user_id in sudoers:
                    if not await _revoke_sudo(client, replied_user_id):
                        return await rich_reply(message, rich_note(Messages.ERR_SUDO_WRITE), ephemeral=True, client=client)
                    await rich_reply(message, _sudo_card(Messages.USER_REMOVED_SUDO.format(replied_user_id), replied_user_id, "ʀᴇᴍᴏᴠᴇᴅ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_NOT_IN_SUDO.format(replied_user_id)), ephemeral=True, client=client)
            else:
                await rich_reply(message, rich_note(Messages.CANT_REMOVE_SELF_SUDO), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.NOT_FROM_USER), ephemeral=True, client=client)
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is an admin
                if target_user_id in get_admin_ids(admin_file):
                    return await rich_reply(message, rich_note(Messages.CANT_REMOVE_OWNER_SUDO), ephemeral=True, client=client)

                # Get current sudo users
                users_data = await user_sessions.find_one({"bot_id": client.me.id})
                if not users_data:
                    return await rich_reply(message, rich_note(Messages.USER_NOT_IN_DB.format(target_user_id)), ephemeral=True, client=client)
                sudoers = users_data.get("SUDOERS", []) if users_data else []
                if target_user_id in sudoers:
                    if not await _revoke_sudo(client, target_user_id):
                        return await rich_reply(message, rich_note(Messages.ERR_SUDO_WRITE), ephemeral=True, client=client)
                    await rich_reply(message, _sudo_card(Messages.USER_REMOVED_SUDO.format(target_user_id), target_user_id, "ʀᴇᴍᴏᴠᴇᴅ"), ephemeral=True, client=client)
                else:
                    await rich_reply(message, rich_note(Messages.USER_NOT_IN_SUDO.format(target_user_id)), ephemeral=True, client=client)
            except ValueError:
                await rich_reply(message, rich_note(Messages.INVALID_USER_ID), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.REPLY_OR_PROVIDE_ID), ephemeral=True, client=client)


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

        subject = (
            "Bot" if not message.reply_to_message
            else message.reply_to_message.from_user.mention()
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

        # Permission matrix
        permission_rows = []
        for perm, display_name in permissions.items():
            status = getattr(bot_member.privileges, perm, False)
            emoji = EmojiTag.SUCCESS if status else EmojiTag.ERROR
            permission_rows.append((display_name, emoji))

        # Administrative status
        if bot_member.status == enums.ChatMemberStatus.ADMINISTRATOR:
            membership = f"{EmojiTag.SPARKLE_STAR} <b>Administrator</b>"
        elif bot_member.status == enums.ChatMemberStatus.MEMBER:
            membership = f"{EmojiTag.USER} <b>Regular Member</b>"
        else:
            membership = "❓ " + rich_esc(str(bot_member.status).title())

        status_pairs = [(f"{EmojiTag.STATS} ᴍᴇᴍʙᴇʀsʜɪᴘ", membership)]

        # Anonymous admin status, if applicable
        if hasattr(bot_member.privileges, "is_anonymous"):
            anon_status = EmojiTag.SUCCESS if bot_member.privileges.is_anonymous else EmojiTag.ERROR
            status_pairs.append((f"{EmojiTag.SHIELD} ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ", anon_status))

        # Custom title if it exists
        if hasattr(bot_member, "custom_title") and bot_member.custom_title:
            status_pairs.append((f"{EmojiTag.CROWN} ᴄᴜsᴛᴏᴍ ᴛɪᴛʟᴇ", f"<b>{rich_esc(bot_member.custom_title)}</b>"))

        granted = sum(1 for _, emoji in permission_rows if emoji == EmojiTag.SUCCESS)
        power_message = (
            rich_heading(f"{EmojiTag.SHIELD} {subject} ᴘᴇʀᴍɪssɪᴏɴs", 1)
            + rich_note(f"{EmojiTag.USERS} <b>{rich_esc(chat.title)}</b> — {rich_code(f'{granted}/{len(permission_rows)}')} ᴘᴏᴡᴇʀs ᴘʀᴇsᴇɴᴛ")
            + rich_heading(f"{EmojiTag.KEY} ʙᴀsɪᴄ ᴘᴏᴡᴇʀs", 2)
            + rich_table(["Permission", "Granted"], permission_rows)
            + rich_heading(f"{EmojiTag.STATS} sᴛᴀᴛᴜs", 2)
            + rich_kv_table(status_pairs)
            + rich_details(
                "What do these mean?",
                rich_table(
                    ["Permission", "Effect"],
                    [
                        ("Delete Messages", "Remove any message in the chat."),
                        ("Restrict Members", "Mute, ban or limit members."),
                        ("Promote Members", "Grant or revoke other admins' rights."),
                        ("Change Group Info", "Edit the title, photo and description."),
                        ("Invite Users", "Add members and create invite links — required to bring the assistant in."),
                        ("Pin Messages", "Pin the now-playing card."),
                        ("Manage Video Chats", "Start and join voice chats — required for playback."),
                        ("Manage Chat", "Access admin tools and the recent-actions log."),
                        ("Manage Topics", "Create and edit forum topics."),
                    ],
                ),
            )
        )

        await rich_reply(message, power_message, client=client)

    except Exception as e:
        logger.error(f"Power check error: {e}")
        await rich_reply(message, rich_note(Messages.ERROR_PERMISSIONS), ephemeral=True, client=client)
