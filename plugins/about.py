"""plugins/about.py — /about user/chat info card."""

from plugins._common import *  # noqa: F401,F403


async def _build_and_send_user_info(client, message, user, chat, photo_path, create_copy_markup):
    """Build user-info response and send with optional profile photo."""
    response = (
        "👤 **User Info**\n"
        f"🆔 **ID**: `{user.id}`\n"
        f"📛 **Name**: {user.first_name}"
    )
    response += f" {user.last_name}\n" if user.last_name else "\n"
    if user.username:
        response += f"🌐 **Username**: @{user.username}\n"
    if user.is_restricted:
        response += "⚠️ **Account Restricted**: Yes\n"
        if user.restriction_reason:
            response += f"📝 **Restriction Reason**: {user.restriction_reason}\n"
    if user.is_scam:
        response += "🚫 **Scam Account**: Yes\n"
    if user.is_fake:
        response += "🎭 **Impersonator**: Yes\n"
    if chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        try:
            member = await client.get_chat_member(chat.id, user.id)
            status_map = {
                enums.ChatMemberStatus.OWNER: "👑 Owner",
                enums.ChatMemberStatus.ADMINISTRATOR: "🔧 Admin",
                enums.ChatMemberStatus.MEMBER: "👤 Member"
            }
            response += f"🎚 **Status**: {status_map.get(member.status, 'Unknown')}\n"
            if member.joined_date:
                response += f"📅 **Joined**: {member.joined_date.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            else:
                response += "📅 **Joined**: Unknown\n"
        except Exception:
            response += "🎚 **Status**: ❌ Not in group\n"
    markup = create_copy_markup(response)
    if user.photo:
        try:
            await client.download_media(user.photo.big_file_id, photo_path)
            await message.reply_photo(photo_path, caption=response, reply_markup=markup)
        except Exception:
            await message.reply(response, reply_markup=markup, link_preview_options=None)
    else:
        await message.reply(response, reply_markup=markup, link_preview_options=None)


@Client.on_message(filters.command("about"))
async def info_command(client: Client, message: Message):
    chat = message.chat
    replied = message.reply_to_message

    # Setup user directory
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    photo_path = f"{user_dir}/logo.jpg"

    def create_copy_markup(text: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Copy Info", copy_text=text, style=ButtonStyle.PRIMARY)
        ]])

    # Handle second argument if provided
    target_user = None
    sender_id = message.from_user.id
    if not sender_id == OWNER_ID:
        return await message.reply_text(Messages.BOT_OWNER_ONLY, link_preview_options=None)

    if len(message.command) >= 2:
        user_input = message.command[1]
        try:
            # Try to get user by ID first
            if user_input.isdigit():
                target_user = await client.get_users(int(user_input))
            else:
                # If not ID, try username (with or without @ symbol)
                username = user_input.strip('@')
                target_user = await client.get_users(username)
        except Exception:
            await message.reply(Messages.ERROR_USER_NOT_FOUND, link_preview_options=None)
            return

    if target_user:
        user = target_user
        await _build_and_send_user_info(client, message, user, chat, photo_path, create_copy_markup)
        return

    # Rest of the original code for replied messages and chat info remains the same
    if replied:
        if replied.sender_chat:
            sender_chat = replied.sender_chat
            if sender_chat.id == chat.id:
                response = (
                    "👤 **Anonymous Group Admin**\n"
                    f"🏷 **Title**: {sender_chat.title}\n"
                    f"🆔 **Chat ID**: `{sender_chat.id}`"
                )
            else:
                response = (
                    "📢 **Channel Info**\n"
                    f"🏷 **Title**: {sender_chat.title}\n"
                    f"🆔 **ID**: `{sender_chat.id}`\n"
                )
                if sender_chat.username:
                    response += f"🌐 **Username**: @{sender_chat.username}\n"
                if sender_chat.description:
                    response += f"📄 **Description**: {sender_chat.description[:300]}..."

            await message.reply(
                response,
                reply_markup=create_copy_markup(response),
            link_preview_options=None)

        else:
            user = await client.get_users(replied.from_user.id)
            await _build_and_send_user_info(client, message, user, chat, photo_path, create_copy_markup)

    else:
        if chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            full_chat = await client.get_chat(chat.id)

            admin_count = 0
            async for member in client.get_chat_members(
                chat.id,
                filter=enums.ChatMembersFilter.ADMINISTRATORS
            ):
                admin_count += 1

            response = (
                "👥 **Group Info**\n"
                f"🏷 **Title**: {full_chat.title}\n"
                f"🆔 **ID**: `{full_chat.id}`\n"
            )

            if full_chat.username:
                response += f"🌐 **Username**: @{full_chat.username}\n"
            response += (
                f"👥 **Members**: {full_chat.members_count}\n"
                f"🔧 **Admins**: {admin_count}\n"
            )

            await message.reply(
                response,
                reply_markup=create_copy_markup(response),
            link_preview_options=None)

        else:
            user = await client.get_users(chat.id)
            await _build_and_send_user_info(client, message, user, chat, photo_path, create_copy_markup)


@Client.on_callback_query(filters.regex("^close$"))
async def close_message(client, query):
    try:
        # Delete the original message
        await query.message.delete()
        # Send confirmation with mention and remove it after 5 seconds
        closed_msg = await client.send_message(
            query.message.chat.id,
            f"🗑 Message closed by {query.from_user.mention}",
        link_preview_options=None)
        await asyncio.sleep(5)
        await closed_msg.delete()
    except Exception as e:
        print(f"Error closing message: {e}")
