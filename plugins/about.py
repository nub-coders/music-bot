"""plugins/about.py — /about user/chat info card."""

from plugins._common import *  # noqa: F401,F403


def _copy_markup(html_text: str) -> InlineKeyboardMarkup:
    """Copy button for an info card.

    ``copy_text`` must be literal text, so the rich HTML is flattened with
    ``rich_to_plain`` — otherwise the user copies markup.
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "Copy Info",
            copy_text=rich_to_plain(html_text),
            style=ButtonStyle.PRIMARY,
            icon_custom_emoji_id=Emoji.CHAT,
        )
    ]])


async def _build_and_send_user_info(client, message, user, chat, photo_path, create_copy_markup):
    """Build user-info response and send with optional profile photo."""
    rows = [
        (f"{EmojiTag.KEY} ɪᴅ", rich_code(user.id)),
        (
            f"{EmojiTag.USER} ɴᴀᴍᴇ",
            rich_esc(f"{user.first_name}{f' {user.last_name}' if user.last_name else ''}"),
        ),
        (f"{EmojiTag.GLOBE} ᴜsᴇʀɴᴀᴍᴇ", f"@{rich_esc(user.username)}" if user.username else None),
        (f"{EmojiTag.WARNING} ʀᴇsᴛʀɪᴄᴛᴇᴅ", "<b>Yes</b>" if user.is_restricted else None),
        (
            f"{EmojiTag.INFO} ʀᴇsᴛʀɪᴄᴛɪᴏɴ ʀᴇᴀsᴏɴ",
            rich_esc(user.restriction_reason) if (user.is_restricted and user.restriction_reason) else None,
        ),
        (f"{EmojiTag.BLOCKED} sᴄᴀᴍ ᴀᴄᴄᴏᴜɴᴛ", "<b>Yes</b>" if user.is_scam else None),
        (f"{EmojiTag.WARNING} ɪᴍᴘᴇʀsᴏɴᴀᴛᴏʀ", "<b>Yes</b>" if user.is_fake else None),
    ]

    if chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        try:
            member = await client.get_chat_member(chat.id, user.id)
            status_map = {
                enums.ChatMemberStatus.OWNER: f"{EmojiTag.CROWN} Owner",
                enums.ChatMemberStatus.ADMINISTRATOR: f"{EmojiTag.SETTINGS} Admin",
                enums.ChatMemberStatus.MEMBER: f"{EmojiTag.USER} Member",
            }
            rows.append((f"{EmojiTag.SHIELD} sᴛᴀᴛᴜs", status_map.get(member.status, "Unknown")))
            rows.append((
                f"{EmojiTag.PIN} ᴊᴏɪɴᴇᴅ",
                rich_code(member.joined_date.strftime('%Y-%m-%d %H:%M:%S UTC')) if member.joined_date else "Unknown",
            ))
        except Exception:
            rows.append((f"{EmojiTag.SHIELD} sᴛᴀᴛᴜs", f"{EmojiTag.ERROR} Not in group"))

    response = rich_heading(f"{EmojiTag.USER} ᴜsᴇʀ ɪɴꜰᴏ", 1) + rich_kv_table(rows)
    markup = create_copy_markup(response)
    if user.photo:
        try:
            await client.download_media(user.photo.big_file_id, photo_path)
            # Captions cannot be rich -> flattened, keeping the inline tags only.
            await message.reply_photo(photo_path, caption=rich_caption(response), reply_markup=markup)
        except Exception:
            await rich_reply(message, response, reply_markup=markup, client=client)
        finally:
            try:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            except Exception:
                pass
    else:
        await rich_reply(message, response, reply_markup=markup, client=client)


@Client.on_message(filters.command("about"))
async def info_command(client: Client, message: Message):
    chat = message.chat
    replied = message.reply_to_message

    # Setup user directory
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    # NOT {user_dir}/logo.jpg: that path is the bot's own branding logo, read back
    # by /start and /setwelcome. Writing an arbitrary user's profile photo there
    # silently replaces the start-card image until the janitor sweeps it.
    photo_path = f"{user_dir}/about_{message.id}.jpg"

    def create_copy_markup(text: str) -> InlineKeyboardMarkup:
        return _copy_markup(text)

    # Handle second argument if provided
    target_user = None
    sender_id = message.from_user.id
    if not sender_id == OWNER_ID:
        return await rich_reply(message, rich_note(Messages.BOT_OWNER_ONLY), ephemeral=True, client=client)

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
            await rich_reply(message, rich_note(Messages.ERROR_USER_NOT_FOUND), ephemeral=True, client=client)
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
                response = rich_heading(f"{EmojiTag.USER} ᴀɴᴏɴʏᴍᴏᴜs ɢʀᴏᴜᴘ ᴀᴅᴍɪɴ", 1) + rich_kv_table([
                    (f"{EmojiTag.PIN} ᴛɪᴛʟᴇ", rich_esc(sender_chat.title)),
                    (f"{EmojiTag.KEY} ᴄʜᴀᴛ ɪᴅ", rich_code(sender_chat.id)),
                ])
            else:
                response = rich_heading(f"{EmojiTag.BROADCAST} ᴄʜᴀɴɴᴇʟ ɪɴꜰᴏ", 1) + rich_kv_table([
                    (f"{EmojiTag.PIN} ᴛɪᴛʟᴇ", rich_esc(sender_chat.title)),
                    (f"{EmojiTag.KEY} ɪᴅ", rich_code(sender_chat.id)),
                    (f"{EmojiTag.GLOBE} ᴜsᴇʀɴᴀᴍᴇ", f"@{rich_esc(sender_chat.username)}" if sender_chat.username else None),
                ])
                if sender_chat.description:
                    response += rich_details(
                        f"{EmojiTag.INFO} ᴅᴇsᴄʀɪᴘᴛɪᴏɴ",
                        rich_note(f"{rich_esc(sender_chat.description[:300])}..."),
                    )

            await rich_reply(
                message,
                response,
                reply_markup=create_copy_markup(response),
                client=client,
            )

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

            response = rich_heading(f"{EmojiTag.USERS} ɢʀᴏᴜᴘ ɪɴꜰᴏ", 1) + rich_kv_table([
                (f"{EmojiTag.PIN} ᴛɪᴛʟᴇ", rich_esc(full_chat.title)),
                (f"{EmojiTag.KEY} ɪᴅ", rich_code(full_chat.id)),
                (f"{EmojiTag.GLOBE} ᴜsᴇʀɴᴀᴍᴇ", f"@{rich_esc(full_chat.username)}" if full_chat.username else None),
                (f"{EmojiTag.USERS} ᴍᴇᴍʙᴇʀs", rich_code(full_chat.members_count)),
                (f"{EmojiTag.SETTINGS} ᴀᴅᴍɪɴs", rich_code(admin_count)),
            ])

            await rich_reply(
                message,
                response,
                reply_markup=create_copy_markup(response),
                client=client,
            )

        else:
            user = await client.get_users(chat.id)
            await _build_and_send_user_info(client, message, user, chat, photo_path, create_copy_markup)


@Client.on_callback_query(filters.regex("^close$"))
async def close_message(client, query):
    try:
        # Delete the original message
        await query.message.delete()
        # Ephemeral confirmation to the presser instead of a public message that
        # had to be swept up 5s later (falls back to the old public send + delete
        # in private chats, where ephemeral delivery is unsupported).
        closed_msg = await rich_answer(
            query,
            rich_note(f"{EmojiTag.CLOSE} Message closed by {query.from_user.mention}"),
            client=client,
        )
        if closed_msg is not None:
            await asyncio.sleep(5)
            # Handles both the ephemeral and the public-fallback case.
            await ephemeral_delete(closed_msg, client=client)
    except Exception as e:
        print(f"Error closing message: {e}")
