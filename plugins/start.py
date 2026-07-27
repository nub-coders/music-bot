"""plugins/start.py — /start handler, welcome formatting, command menu, join logging."""

from plugins._common import *  # noqa: F401,F403


async def send_log_message(client, log_group_id, message, is_private):
    try:
        if is_private:
            user = message.from_user
            log_text = (
                "📥 **New User Started Bot**\n\n"
                f"**User Details:**\n"
                f"• Name: {user.first_name}\n"
                f"• Username: @{user.username if user.username else 'None'}\n"
                f"• User ID: `{user.id}`\n"
                f"• Is Premium: {'Yes' if user.is_premium else 'No'}\n"
                f"• DC ID: {user.dc_id if user.dc_id else 'Unknown'}\n"
                f"• Language: {user.language_code if user.language_code else 'Unknown'}\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            chat = message.chat
            try:
                members_count = await client.get_chat_members_count(chat.id)
            except Exception:
                members_count = "Unknown"
            try:
                invite_link = await client.export_chat_invite_link(chat.id)
            except Exception:
                invite_link = "Don't have invite right"
            log_text = (
                "📥 **Bot Added to New Group**\n\n"
                f"**Group Details:**\n"
                f"• Name: {chat.title}\n"
                f"• Chat ID: `{chat.id}`\n"
                f"• Type: {chat.type}\n"
                f"• Members: {members_count}\n"
                f"• Username: @{chat.username if chat.username else invite_link}\n"
                f"• Added By: {message.from_user.mention if message.from_user else 'Unknown'}\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        await asyncio.sleep(2)
        await client.send_message(
            chat_id=int(log_group_id),
            text=log_text,
            link_preview_options=None
        )
    except Exception as e:
        logger.info(f"Error sending log message: {str(e)}")


@Client.on_message(filters.command("start") | (filters.group & create_custom_filter))
async def user_client_start_handler(client, message):
    user_id = message.chat.id
    user_data = await collection.find_one({"bot_id": client.me.id})
    is_private = message.chat.type == enums.ChatType.PRIVATE
    should_log = False
    if user_data:
        users = user_data.get('users', {})
        if user_id not in users:
            asyncio.create_task(push_to_array(collection, {"bot_id": client.me.id}, 'users', user_id, upsert=True))
            should_log = True
    else:
        asyncio.create_task(set_fields(collection, {"bot_id": client.me.id}, {'users': [user_id]}, upsert=True))
        should_log = True
    if should_log:
        log_group = LOGGER_ID

        if log_group:
          try:
            await send_log_message(
                client=client,
                log_group_id=log_group,
                message=message,
                is_private=is_private
            )
          except Exception as e:
             logger.info(e)

    # Process video ID if provided in start command
    command_args = message.text.split() if message.text else "hh".split()
    if len(command_args) > 1 and '_' in command_args[1]:
        try:
            loading = await message.reply(Messages.GETTING_STREAM_INFO, link_preview_options=None)
            # Split the argument using underscore and get the video ID
            _, video_id = command_args[1].split('_', 1)

            # Get video details
            video_info = await get_video_details(video_id)

            if isinstance(video_info, dict):
                # Format numbers
                views = format_number(video_info['view_count'])

                # Create formatted message
                logger.info(video_info['thumbnail'])
                await loading.delete()
                caption = (
                    f"📝 **Title:** {video_info['title']}\n\n"
                    f"⏱ **Duration:** {video_info['duration']}\n"
                    f"👁 **Views:** {views}\n"
                    f"📺 **Channel:** {video_info['channel_name']}\n"
                )

                # Create inline keyboard with YouTube button
                keyboard = Buttons.force_play_markup(video_info['video_url'])

                # Send thumbnail as photo with caption and keyboard
                try:
                    return await message.reply_photo(
                        photo=video_info['thumbnail'],
                        caption=caption,
                        reply_markup=keyboard,
                        reply_to_message_id=message.id
                    )
                except Exception as e:
                    return await message.reply_text(
                        f"❌ Failed to send photo: {str(e)}\n\n{caption}",
                        reply_markup=keyboard,
                        reply_to_message_id=message.id,
                    link_preview_options=None)
            else:
                return await message.reply_text(
                    f"❌ Error: {video_info}",
                    reply_to_message_id=message.id,
                link_preview_options=None)

        except Exception as e:
            return await message.reply_text(
                f"❌ Error processing video ID: {str(e)}",
                reply_to_message_id=message.id,
            link_preview_options=None)

    # Handle logging

    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    editing = await message.reply(Messages.LOADING, link_preview_options=None)
    owner = await client.get_users(OWNER_ID)
    ow_id = owner.id if owner.username else None

    buttons_markup = Buttons.start_markup(client.me.username, ow_id, OWNER_ID, GROUP)
    import psutil
    _uptime = await get_readable_time((time.time() - StartTime))



    # Get system resources
    try:
        _cpu_cores = psutil.cpu_count() or "N/A"
        ram = psutil.virtual_memory()
        _ram_total = f"{ram.total / (1024**3):.2f} GB"
        disk = psutil.disk_usage('/')
        _disk_total = f"{disk.total / (1024**3):.2f} GB"
    except Exception:
        _cpu_cores = "N/A"
        _ram_total = "N/A"
        _disk_total = "N/A"
    try:
       _photu = None
       async for photo in client.get_chat_photos(client.me.id):
           _photu = photo.file_id

       # First try to get logo from user_dir
       logo_path_jpg = f"{user_dir}/logo.jpg"
       logo_path_mp4 = f"{user_dir}/logo.mp4"
       logo = None

       if os.path.exists(logo_path_mp4):
           logo = logo_path_mp4
       elif os.path.exists(logo_path_jpg):
           logo = logo_path_jpg
       else:
           logo = await gvarstatus(client.me.id, "LOGO") or (await client.download_media(client.me.photo.big_file_id, logo_path_jpg) if client.me.photo else "music.jpg")

       alive_logo = logo
       if type(logo) is bytes:
           alive_logo = logo_path_jpg
           with open(alive_logo, "wb") as fimage:
               fimage.write(base64.b64decode(logo))
           if 'video' in mime.from_file(alive_logo):
               alive_logo = rename_file(alive_logo, logo_path_mp4)




       greet_message = await gvarstatus(client.me.id, "WELCOME") or (
           "👋 <b>ʜᴇʏ {name}!</b>\n\n"
           "🎵 <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {botname}</b>\n\n"
           "<i>ᴀ ᴍᴜsɪᴄ ʙᴏᴛ ᴡɪᴛʜ ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ & ʜɪɢʜ-ǫᴜᴀʟɪᴛʏ sᴛʀᴇᴀᴍɪɴɢ.</i>\n\n"
           "<b><i>ᴜsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ.</i></b>"
       )

       send = client.send_video if alive_logo.endswith(".mp4") else client.send_photo
       await editing.delete()
       await send(
                user_id ,
                alive_logo,
                caption=await format_welcome_message(client, greet_message, user_id, message.from_user.mention() if message.chat.type == enums.ChatType.PRIVATE else (message.chat.title or ""))
,reply_markup=buttons_markup
            )
    except Exception as e:
      logger.info(e)


async def format_welcome_message(client, text, chat_id, user_or_chat_name):
    """Helper function to format welcome message with real data"""
    try:
        # Ensure user_or_chat_name is a string, even if None is passed
        user_or_chat_name = str(user_or_chat_name) if user_or_chat_name is not None else ""
        formatted_text = text
        formatted_text = formatted_text.replace("{name}", user_or_chat_name)
        formatted_text = formatted_text.replace("{id}", str(chat_id))
        formatted_text = formatted_text.replace("{botname}", client.me.mention())
        return formatted_text
    except Exception as e:
        logging.error(f"Error formatting welcome message: {str(e)}")
        return text  # Return original text if formatting fails


@Client.on_callback_query(filters.regex(r"commands_(.*)"))
async def commands_handler(client, callback_query):
    data = callback_query.data.split("_", 1)[1]          # Extract page name
    user_id = callback_query.from_user.id
    _admin_file = f"{ggg}/admin.txt"

    # --- Permission check (owner / admin / sudo) ---
    admin_ids = get_admin_ids(f"{ggg}/admin.txt")
    _is_admin = user_id in admin_ids or str(OWNER_ID) == str(user_id)
    owner = await client.get_users(OWNER_ID)
    ow_id = owner.id if owner.username else None

    # ---------- Command pages (text blocks) ----------
    playback_commands = (
        "<u><b>🎵 | ᴘʟᴀʏʙᴀᴄᴋ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /play  /vplay        — ǫᴜᴇᴜᴇ ʏᴏᴜᴛᴜʙᴇ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ\n"
        "‣ /queue               — sʜᴏᴡ ᴄᴜʀʀᴇɴᴛ ǫᴜᴇᴜᴇ (ᴜᴘ ᴛᴏ 20)\n"
        "‣ /playforce /vplayforce — ꜰᴏʀᴄᴇ ᴘʟᴀʏ (sᴋɪᴘ ᴄᴜʀʀᴇɴᴛ)\n"
        "‣ /cplay /cvplay       — ᴘʟᴀʏ ɪɴ ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ\n"
        "‣ /pause               — ᴘᴀᴜsᴇ sᴛʀᴇᴀᴍ\n"
        "‣ /resume              — ʀᴇsᴜᴍᴇ sᴛʀᴇᴀᴍ\n"
        "‣ /skip  /cskip        — ɴᴇxᴛ ᴛʀᴀᴄᴋ\n"
        "‣ /end  /cend          — sᴛᴏᴘ & ᴄʟᴇᴀʀ ǫᴜᴇᴜᴇ\n"
        "‣ /seek &lt;sec&gt;    — ᴊᴜᴍᴘ ꜰᴏʀᴡᴀʀᴅ\n"
        "‣ /seekback &lt;sec&gt; — ᴊᴜᴍᴘ ʙᴀᴄᴋᴡᴀʀᴅ\n"
        "‣ /loop &lt;1-20&gt;   — ʀᴇᴘᴇᴀᴛ ᴄᴜʀʀᴇɴᴛ sᴏɴɢ\n"
        "</blockquote>"
    )

    auth_commands = (
        "<u><b>🔐 | ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /auth &lt;reply|id&gt;   — ᴀʟʟᴏᴡ ᴜsᴇʀ ᴛᴏ ᴜsᴇ ᴘʟᴀʏᴇʀ\n"
        "‣ /unauth &lt;reply|id&gt; — ʀᴇᴍᴏᴠᴇ ᴛʜᴀᴛ ᴘᴇʀᴍɪssɪᴏɴ\n"
        "‣ /authlist              — ʟɪsᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs\n"
        "</blockquote>"
    )

    blocklist_commands = (
        "<u><b>🚫 | ʙʟᴏᴄᴋʟɪsᴛ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /block &lt;reply|id&gt;   — ʙʟᴏᴄᴋ ᴜsᴇʀ ꜰʀᴏᴍ ʙᴏᴛ\n"
        "‣ /unblock &lt;reply|id&gt; — ᴜɴʙʟᴏᴄᴋ ᴜsᴇʀ\n"
        "‣ /blocklist              — ᴠɪᴇᴡ ʙʟᴏᴄᴋᴇᴅ ʟɪsᴛ\n"
        "</blockquote>"
    )

    sudo_commands = (
        "<u><b>🔑 | sᴜᴅᴏ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /addsudo &lt;reply|id&gt; — ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ\n"
        "‣ /rmsudo &lt;reply|id&gt;  — ʀᴇᴍᴏᴠᴇ sᴜᴅᴏ ᴜsᴇʀ\n"
        "‣ /sudolist               — ʟɪsᴛ sᴜᴅᴏ ᴜsᴇʀs\n"
        "</blockquote>"
    )

    broadcast_commands = (
        "<u><b>📢 | ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /broadcast  — ᴄᴏᴘʏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴅɪᴀʟᴏɢs\n"
        "‣ /fbroadcast — ꜰᴏʀᴡᴀʀᴅ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴅɪᴀʟᴏɢs\n"
        "</blockquote>"
    )

    tools_commands = (
        "<u><b>🛠️ | ᴛᴏᴏʟs ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /del    — ᴅᴇʟᴇᴛᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ\n"
        "‣ /tagall — ᴍᴇɴᴛɪᴏɴ ᴀʟʟ ᴍᴇᴍʙᴇʀs\n"
        "‣ /cancel — ᴀʙᴏʀᴛ ʀᴜɴɴɪɴɢ ᴛᴀɢᴀʟʟ\n"
        "‣ /powers — sʜᴏᴡ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs\n"
        "</blockquote>"
    )

    kang_commands = (
        "<u><b>🎨 | sᴛɪᴄᴋᴇʀ & ᴍᴇᴍᴇ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /kang         — ᴄʟᴏɴᴇ sᴛɪᴄᴋᴇʀ/ᴘʜᴏᴛᴏ ᴛᴏ ʏᴏᴜʀ ᴘᴀᴄᴋ\n"
        "‣ /mmf &lt;text&gt; — ᴡʀɪᴛᴇ ᴛᴇxᴛ ᴏɴ ɪᴍᴀɢᴇ/sᴛɪᴄᴋᴇʀ\n"
        "</blockquote>"
    )

    status_commands = (
        "<u><b>📊 | sᴛᴀᴛᴜs & ɪɴꜰᴏ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /ping  — ʟᴀᴛᴇɴᴄʏ & ᴜᴘᴛɪᴍᴇ\n"
        "‣ /stats — ʙᴏᴛ ᴜsᴀɢᴇ sᴛᴀᴛs\n"
        "‣ /ac    — ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs\n"
        "‣ /about — ᴜsᴇʀ / ɢʀᴏᴜᴘ / ᴄʜᴀɴɴᴇʟ ɪɴꜰᴏ\n"
        "</blockquote>"
    )

    owner_commands = (
        "<u><b>⚙️ | ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs</b></u>\n"
        "<blockquote expandable>\n"
        "‣ /reboot       — ʀᴇsᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        "‣ /setwelcome   — sᴇᴛ ᴄᴜsᴛᴏᴍ /start ᴍᴇssᴀɢᴇ\n"
        "‣ /resetwelcome — ʀᴇsᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ & ʟᴏɢᴏ\n"
        "</blockquote>"
    )

    category_pages = {
        "playback": playback_commands,
        "auth": auth_commands,
        "blocklist": blocklist_commands,
        "sudo": sudo_commands,
        "broadcast": broadcast_commands,
        "tools": tools_commands,
        "kang": kang_commands,
        "status": status_commands,
    }

    # ---------- Navigation buttons ----------
    # --- Category Buttons replaced by Buttons.HELP_HOME ---


    back_markup = Buttons.BACK


    # ---------- Routing ----------
    if data == "all":
        await callback_query.answer()
        await callback_query.message.edit_caption(
            caption="<u><b>📜 | sᴇʟᴇᴄᴛ ᴀ ᴄᴏᴍᴍᴀɴᴅ ᴄᴀᴛᴇɢᴏʀʏ</b></u>",
            reply_markup=Buttons.HELP_HOME,
        )
    elif data in category_pages:
        await callback_query.answer()
        await callback_query.message.edit_caption(
            caption=category_pages[data],
            reply_markup=back_markup,
        )
    elif data == "owner":
        await callback_query.answer()
        await callback_query.message.edit_caption(caption=owner_commands, reply_markup=back_markup)
    elif data == "back":
            await callback_query.answer()
            _name = callback_query.from_user.mention()
            _botname = client.me.mention()
            greet_message = await gvarstatus(client.me.id, "WELCOME") or (
                "👋 <b>ʜᴇʏ {name}!</b>\n\n"
                "🎵 <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {botname}</b>\n\n"
                "<i>ᴀ ᴍᴜsɪᴄ ʙᴏᴛ ᴡɪᴛʜ ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ & ʜɪɢʜ-ǫᴜᴀʟɪᴛʏ sᴛʀᴇᴀᴍɪɴɢ.</i>\n\n"
                "<b><i>ᴜsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ.</i></b>"
            )
            greet_message = await format_welcome_message(client, greet_message, user_id, callback_query.from_user.mention())
            buttons_markup = Buttons.start_markup(client.me.username, ow_id, OWNER_ID, GROUP)
            await callback_query.message.edit_caption(
                caption=greet_message,
                reply_markup=buttons_markup,
            )
