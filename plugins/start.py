"""plugins/start.py — /start handler, welcome formatting, command menu, join logging."""

from plugins._common import *  # noqa: F401,F403


def _cmd_page(title: str, rows, open: bool = False) -> str:
    """One help page section wrapped inside native Telegram <details> and <summary> dropdown tags."""
    tbl = rich_table(["ᴄᴏᴍᴍᴀɴᴅ", "ᴅᴇsᴄʀɪᴘᴛɪᴏɴ"], rows)
    return rich_details(summary=title, body=tbl, open=open)


async def send_log_message(client, log_group_id, message, is_private):
    try:
        if is_private:
            user = message.from_user
            log_text = rich_heading(f"{EmojiTag.ADD} ɴᴇᴡ ᴜsᴇʀ sᴛᴀʀᴛᴇᴅ ʙᴏᴛ", 1) + rich_kv_table([
                (f"{EmojiTag.USER} ɴᴀᴍᴇ", rich_esc(user.first_name)),
                (f"{EmojiTag.GLOBE} ᴜsᴇʀɴᴀᴍᴇ", f"@{rich_esc(user.username)}" if user.username else "<i>None</i>"),
                (f"{EmojiTag.KEY} ᴜsᴇʀ ɪᴅ", rich_code(user.id)),
                (f"{EmojiTag.STAR} ᴘʀᴇᴍɪᴜᴍ", "Yes" if user.is_premium else "No"),
                (f"{EmojiTag.INFO} ᴅᴄ ɪᴅ", rich_code(user.dc_id) if user.dc_id else "Unknown"),
                (f"{EmojiTag.CHAT} ʟᴀɴɢᴜᴀɢᴇ", rich_code(user.language_code) if user.language_code else "Unknown"),
                (f"{EmojiTag.LOADING} ᴛɪᴍᴇ", rich_code(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
            ])
        else:
            chat = message.chat
            try:
                members_count = await client.get_chat_members_count(chat.id)
            except Exception:
                members_count = "Unknown"
            try:
                from datetime import datetime as _dt, timedelta as _td, timezone as _tz
                _expire = _dt.now(_tz.utc) + _td(seconds=60)
                _link_obj = await client.create_chat_invite_link(chat.id, member_limit=1, expire_date=_expire)
                invite_link = _link_obj.invite_link
            except Exception:
                invite_link = "No invite permission"
            log_text = rich_heading(f"{EmojiTag.ADD} ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɴᴇᴡ ɢʀᴏᴜᴘ", 1) + rich_kv_table([
                (f"{EmojiTag.PIN} ɴᴀᴍᴇ", rich_esc(chat.title)),
                (f"{EmojiTag.KEY} ᴄʜᴀᴛ ɪᴅ", rich_code(chat.id)),
                (f"{EmojiTag.INFO} ᴛʏᴘᴇ", rich_code(chat.type)),
                (f"{EmojiTag.USERS} ᴍᴇᴍʙᴇʀs", rich_code(members_count)),
                (
                    f"{EmojiTag.GLOBE} ᴜsᴇʀɴᴀᴍᴇ",
                    f"@{rich_esc(chat.username)}" if chat.username else rich_esc(invite_link),
                ),
                (f"{EmojiTag.USER} ᴀᴅᴅᴇᴅ ʙʏ", message.from_user.mention if message.from_user else "Unknown"),
                (f"{EmojiTag.LOADING} ᴛɪᴍᴇ", rich_code(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
            ])
        await asyncio.sleep(2)
        await rich_send(client, int(log_group_id), log_text)
    except Exception as e:
        logger.info(f"Error sending log message: {str(e)}")


@Client.on_message(filters.command("start") & filters.private)
async def user_client_start_handler(client, message):
    user_id = message.chat.id
    user_data = await collection.find_one({"bot_id": client.me.id})
    should_log = False
    if user_data:
        users = user_data.get('users', {})
        if user_id not in users:
            asyncio.create_task(push_to_array(collection, {"bot_id": client.me.id}, 'users', user_id, upsert=True))
            should_log = True
    else:
        asyncio.create_task(set_fields(collection, {"bot_id": client.me.id}, {'users': [user_id]}, upsert=True))
        should_log = True
    if should_log and LOGGER_ID:
        try:
            await send_log_message(client=client, log_group_id=LOGGER_ID, message=message, is_private=True)
        except Exception as e:
            logger.info(e)

    # Check for help argument in start command
    command_args = message.text.split() if message.text else []
    if len(command_args) > 1 and command_args[1].lower() == "help":
        admin_ids = get_admin_ids(f"{ggg}/admin.txt")
        users_data = await user_sessions.find_one({"bot_id": client.me.id})
        sudoers = users_data.get("SUDOERS", []) if users_data else []
        uid = message.from_user.id if message.from_user else message.chat.id
        is_owner = str(uid) == str(OWNER_ID)
        is_admin = uid in admin_ids or is_owner
        is_sudo = uid in sudoers or is_owner

        markup = Buttons.help_markup(is_admin=is_admin, is_owner=is_owner, is_sudo=is_sudo)
        return await rich_reply(
            message,
            Messages.HELP_CATEGORY_SELECT,
            reply_markup=markup,
            client=client,
        )

    # Process video ID if provided in start command
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
                # Caption-bound (photo card) -> built rich, flattened for caption.
                _card = rich_heading(f"{EmojiTag.MUSIC_NOTE} {rich_esc(video_info['title'])}", 1) + rich_kv_table([
                    (f"{EmojiTag.LOADING} ᴅᴜʀᴀᴛɪᴏɴ", rich_code(video_info['duration'])),
                    (f"{EmojiTag.STATS} ᴠɪᴇᴡs", rich_code(views)),
                    (f"{EmojiTag.USER} ᴄʜᴀɴɴᴇʟ", rich_code(video_info['channel_name'])),
                ])
                caption = rich_caption(_card)

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
                    logger.error(f"[start] Failed to send photo: {e}")
                    # Text fallback can be fully rich (no caption constraint).
                    return await rich_reply(message, _card, reply_markup=keyboard, client=client)
            else:
                return await rich_reply(
                    message,
                    rich_note(f"{EmojiTag.ERROR} <b>Error:</b> {rich_esc(video_info)}"),
                    client=client,
                )

        except Exception as e:
            return await rich_reply(
                message,
                rich_note(f"{EmojiTag.ERROR} <b>Error processing video ID:</b> {rich_code(e)}"),
                client=client,
            )

    # ── Send PM alive card ──────────────────────────────────────────────────
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    editing = await message.reply(Messages.LOADING, link_preview_options=None)
    # No owner configured -> never call get_users(0); it raises and would abort /start.
    owner = await client.get_users(OWNER_ID) if OWNER_ID else None
    ow_id = owner.id if (owner and owner.username) else None

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
           _photu = getattr(photo, "big_file_id", getattr(photo, "file_id", None))

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
            f"{EmojiTag.USER} <b>ʜᴇʏ {{name}}!</b>\n\n"
            f"{EmojiTag.MUSIC_NOTE} <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {{botname}}</b>\n\n"
            "<i>ᴀ ᴍᴜsɪᴄ ʙᴏᴛ ᴡɪᴛʜ ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ & ʜɪɢʜ-ǫᴜᴀʟɪᴛʏ sᴛʀᴇᴀᴍɪɴɢ.</i>\n\n"
            "<b><i>ᴜsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ.</i></b>"
        )

       send = client.send_video if alive_logo.endswith(".mp4") else client.send_photo
       await editing.delete()
       await send(
                user_id,
                alive_logo,
                caption=await format_welcome_message(client, greet_message, user_id, message.from_user.mention()),
                reply_markup=buttons_markup,
            )
    except Exception as e:
      logger.info(e)


@Client.on_message(filters.group & create_custom_filter)
async def bot_added_to_group_handler(client, message):
    """Fires when the bot itself is added to a group. Sends a personal thank-you welcome."""
    group_name = message.chat.title or "ᴛʜɪs ɢʀᴏᴜᴘ"
    adder = message.from_user.mention() if message.from_user else "ʏᴏᴜ"

    # Log the group add
    user_id = message.chat.id
    user_data = await collection.find_one({"bot_id": client.me.id})
    if not user_data or user_id not in user_data.get('users', []):
        asyncio.create_task(push_to_array(collection, {"bot_id": client.me.id}, 'users', user_id, upsert=True))
        if LOGGER_ID:
            try:
                await send_log_message(client=client, log_group_id=LOGGER_ID, message=message, is_private=False)
            except Exception as e:
                logger.info(e)

    caption = Messages.GROUP_WELCOME.format(
        adder=adder,
        group_name=group_name,
        botname=client.me.mention(),
    )
    markup = Buttons.group_welcome_markup(client.me.username, GROUP)

    # Resolve logo
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    logo_path_jpg = f"{user_dir}/logo.jpg"
    logo_path_mp4 = f"{user_dir}/logo.mp4"

    try:
        if os.path.exists(logo_path_mp4):
            logo = logo_path_mp4
        elif os.path.exists(logo_path_jpg):
            logo = logo_path_jpg
        elif client.me.photo:
            logo = await client.download_media(client.me.photo.big_file_id, logo_path_jpg)
        else:
            logo = "music.jpg"

        send = client.send_video if logo.endswith(".mp4") else client.send_photo
        await send(message.chat.id, logo, caption=caption, reply_markup=markup)
    except Exception as e:
        logger.info(f"[group_welcome] Failed to send photo, falling back to text: {e}")
        await message.reply(caption, reply_markup=markup, link_preview_options=None)




async def format_welcome_message(client, text, chat_id, user_or_chat_name):
    """Helper function to format welcome message with real data"""
    try:
        botname = client.me.mention()
        formatted_text = text.format(name=user_or_chat_name, botname=botname)
        return formatted_text
    except Exception as e:
        logger.info(f"Error formatting welcome message: {e}")
        return text


@Client.on_callback_query(filters.regex("^commands_"))
async def commands_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    admin_ids = get_admin_ids(f"{ggg}/admin.txt")
    is_owner = bool(OWNER_ID) and str(OWNER_ID) == str(user_id)
    is_sudo = is_owner or user_id in SUDO
    is_admin = is_owner or is_sudo or (user_id in admin_ids)
    owner = await client.get_users(OWNER_ID) if OWNER_ID else None
    ow_id = owner.id if (owner and owner.username) else None

    # ---------- Command pages (rich blocks, flattened at the caption call) ----------
    playback_commands = _cmd_page(
        f"{EmojiTag.MUSIC_NOTE} ᴘʟᴀʏʙᴀᴄᴋ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.PLAY} <mark><code>/play</code></mark> <code>/vplay</code>", "ǫᴜᴇᴜᴇ ʏᴏᴜᴛᴜʙᴇ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ"),
            (f"{EmojiTag.QUEUE_ICON} <mark><code>/queue</code></mark> <code>/cqueue</code>", "sʜᴏᴡ ᴄᴜʀʀᴇɴᴛ ǫᴜᴇᴜᴇ (ᴜᴘ ᴛᴏ 20)"),
            (f"{EmojiTag.ROCKET} <mark><code>/playforce</code></mark> <code>/cplayforce</code>", "꩖ᴏʀᴄᴇ ᴘʟᴀʏ (sᴋɪᴘ ᴄᴜʀʀᴇɴᴛ)"),
            (f"{EmojiTag.GLOBE} <mark><code>/cplay</code></mark> <code>/cvplay</code>", "ᴘʟᴀʏ ɪɴ ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ"),
            (f"{EmojiTag.MUSIC_NOTE} <mark><code>/np</code></mark> <code>/nowplaying</code>", "sʜᴏᴡ ᴄᴜʀʀᴇɴᴛʟʏ ᴘʟᴀʏɪɴɢ ᴛʀᴀᴄᴋ"),
            (f"{EmojiTag.PAUSE} <mark><code>/pause</code></mark> <code>/cpause</code>", "ᴘᴀᴜsᴇ sᴛʀᴇᴀᴍ"),
            (f"{EmojiTag.RESUME} <mark><code>/resume</code></mark> <code>/cresume</code>", "ʀᴇsᴜᴍᴇ sᴛʀᴇᴀᴍ"),
            (f"{EmojiTag.SKIP} <mark><code>/skip</code></mark> <code>/cskip</code>", "ɴᴇxᴛ ᴛʀᴀᴄᴋ"),
            (f"{EmojiTag.STOP} <mark><code>/end</code></mark> <code>/cstop</code>", "sᴛᴏᴘ &amp; ᴄʟᴇᴀʀ ǫᴜᴇᴜᴇ"),
            (f"{EmojiTag.REFRESH} <mark><code>/shuffle</code></mark> <code>/cshuffle</code>", "sʜᴜғғʟᴇ ǫᴜᴇᴜᴇᴅ ᴛʀᴀᴄᴋs"),
            (f"{EmojiTag.NEXT} <mark><code>/seek &lt;sec&gt;</code></mark> <code>/cseek</code>", "ᴊᴜᴍᴘ ꩖ᴏʀᴡᴀʀᴅ"),
            (f"{EmojiTag.BACK} <mark><code>/seekback &lt;sec&gt;</code></mark> <code>/cseekback</code>", "ᴊᴜᴍᴘ ʙᴀᴄᴋᴡᴀʀᴅ"),
            (f"{EmojiTag.LOOP} <mark><code>/loop &lt;1-20&gt;</code></mark> <code>/cloop</code>", "ʀᴇᴘᴇᴀᴛ ᴄᴜʀʀᴇɴᴛ sᴏɴɢ"),
            (f"{EmojiTag.SETTINGS} <mark><code>/autoplay [on|off]</code></mark>", "ᴛᴏɢɢʟᴇ ᴀᴜᴛᴏᴘʟᴀʏ &amp; sᴜɢɢᴇsᴛɪᴏɴs"),
        ],
        open=True,
    )

    auth_commands = _cmd_page(
        f"{EmojiTag.LOCK} ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.LOCK} <mark><code>/auth &lt;reply|id&gt;</code></mark>", "ᴀʟʟᴏᴡ ᴜsᴇʀ ᴛᴏ ᴜsᴇ ᴘʟᴀʏᴇʀ"),
            (f"{EmojiTag.UNLOCK} <mark><code>/unauth &lt;reply|id&gt;</code></mark>", "ʀᴇᴍᴏᴠᴇ ᴛʜᴀᴛ ᴘᴇʀᴍɪssɪᴏɴ"),
            (f"{EmojiTag.USER} <mark><code>/authlist</code></mark>", "ʟɪsᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs"),
        ],
    )

    blocklist_commands = _cmd_page(
        f"{EmojiTag.BLOCKED} ʙʟᴏᴄᴋʟɪsᴛ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.BLOCKED} <mark><code>/block &lt;reply|id&gt;</code></mark>", "ʙʟᴏᴄᴋ ᴜsᴇʀ ꩖ʀᴏᴍ ʙᴏᴛ"),
            (f"{EmojiTag.SUCCESS} <mark><code>/unblock &lt;reply|id&gt;</code></mark>", "ᴜɴʙʟᴏᴄᴋ ᴜsᴇʀ"),
            (f"{EmojiTag.USERS} <mark><code>/blocklist</code></mark>", "ᴠɪᴇᴡ ʙʟᴏᴄᴋᴇᴅ ʟɪsᴛ"),
        ],
    )

    sudo_commands = _cmd_page(
        f"{EmojiTag.KEY} sᴜᴅᴏ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.KEY} <mark><code>/addsudo &lt;reply|id&gt;</code></mark>", "ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ"),
            (f"{EmojiTag.CLOSE} <mark><code>/rmsudo &lt;reply|id&gt;</code></mark>", "ʀᴇᴍᴏᴠᴇ sᴜᴅᴏ ᴜsᴇʀ"),
            (f"{EmojiTag.CROWN} <mark><code>/sudolist</code></mark>", "ʟɪsᴛ sᴜᴅᴏ ᴜsᴇʀs"),
        ],
    )

    broadcast_commands = _cmd_page(
        f"{EmojiTag.BROADCAST} ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (
                f"{EmojiTag.BROADCAST} <mark><code>/broadcast</code></mark> <code>/fbroadcast</code>",
                "ᴏᴘᴇɴ ʙʀᴏᴀᴅᴄᴀsᴛ ᴘᴀɴᴇʟ ᴡɪᴛʜ ᴄᴏᴘʏ / ꩖ᴏʀᴡᴀʀᴅ &amp; ᴛᴀʀɢᴇᴛ ᴛᴏɢɢʟᴇs",
            ),
        ],
    )

    tools_commands = _cmd_page(
        f"{EmojiTag.TOOLS} ᴛᴏᴏʟs ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.CLOSE} <mark><code>/del</code></mark>", "ᴅᴇʟᴇᴛᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ"),
            (f"{EmojiTag.USERS} <mark><code>/tagall</code></mark>", "ᴍᴇɴᴛɪᴏɴ ᴀʟʟ ᴍᴇᴍʙᴇʀs"),
            (f"{EmojiTag.ERROR} <mark><code>/cancel</code></mark>", "ᴀʙᴏʀᴛ ʀᴜɴɴɪɴɢ ᴛᴀɢᴀʟʟ"),
            (f"{EmojiTag.SHIELD} <mark><code>/powers</code></mark>", "sʜᴏᴡ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs"),
        ],
    )

    kang_commands = _cmd_page(
        f"{EmojiTag.KANG} sᴛɪᴄᴋᴇʀ &amp; ᴍᴇᴍᴇ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.KANG} <mark><code>/kang</code></mark>", "ᴄʟᴏɴᴇ sᴛɪᴄᴋᴇʀ/ᴘʜᴏᴛᴏ ᴛᴏ ʏᴏᴜʀ ᴘᴀᴄᴋ"),
            (f"{EmojiTag.TOOLS} <mark><code>/mmf &lt;text&gt;</code></mark>", "ᴡʀɪᴛᴇ ᴛᴇxᴛ ᴏɴ ɪᴍᴀɢᴇ/sᴛɪᴄᴋᴇʀ"),
        ],
    )

    status_commands = _cmd_page(
        f"{EmojiTag.STATS} sᴛᴀᴛᴜs &amp; ɪɴ꩖ᴏ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.PING} <mark><code>/ping</code></mark>", "ʟᴀᴛᴇɴᴄʏ &amp; ᴜᴘᴛɪᴍᴇ"),
            (f"{EmojiTag.STATS} <mark><code>/stats</code></mark>", "ʙᴏᴛ ᴜsᴀɢᴇ sᴛᴀᴛs"),
            (f"{EmojiTag.CHAT} <mark><code>/ac</code></mark>", "ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs"),
            (f"{EmojiTag.INFO} <mark><code>/about</code></mark>", "ᴜsᴇʀ / ɢʀᴏᴜᴘ / ᴄʜᴀɴɴᴇʟ ɪɴ꩖ᴏ"),
            (f"{EmojiTag.USER} <mark><code>/assistants</code></mark>", "ʟɪsᴛ ᴀssɪsᴛᴀɴᴛ ᴜsᴇʀʙᴏᴛs"),
            (f"{EmojiTag.SETTINGS} <mark><code>/changeassistant</code></mark>", "sᴡɪᴛᴄʜ ᴀssɪsᴛᴀɴᴛ for ᴄʜᴀᴛ"),
            (f"{EmojiTag.GLOBE} <mark><code>/lang</code></mark> <code>/setlang</code>", "ᴄʜᴀɴɢᴇ ʙᴏᴛ ʟᴀɴɢᴜᴀɢᴇ"),
        ],
    )

    owner_commands = _cmd_page(
        f"{EmojiTag.SETTINGS} ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs",
        [
            (f"{EmojiTag.REFRESH} <mark><code>/reboot</code></mark>", "ʀᴇsᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
            (f"{EmojiTag.PIN} <mark><code>/setwelcome</code></mark>", "sᴇᴛ ᴄᴜsᴛᴏᴍ <code>/start</code> ᴍᴇssᴀɢᴇ"),
            (f"{EmojiTag.CLOSE} <mark><code>/resetwelcome</code></mark>", "ʀᴇsᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ &amp; ʟᴏɢᴏ"),
            (f"{EmojiTag.BLOCKED} <mark><code>/leaveall</code></mark>", "ᴍᴀᴋᴇ ᴀssɪsᴛᴀɴᴛs ʟᴇᴀᴠᴇ ᴀʟʟ ᴄʜᴀᴛs"),
        ],
    )

    # Merged dropdown pages (combines multiple categories into interactive collapsible sections)
    merged_all = (
        playback_commands + "\n" +
        tools_commands + "\n" +
        status_commands + "\n" +
        kang_commands +
        ("\n" + auth_commands if (is_admin or is_sudo or is_owner) else "") +
        ("\n" + blocklist_commands + "\n" + sudo_commands + "\n" + broadcast_commands if (is_sudo or is_owner) else "") +
        ("\n" + owner_commands if is_owner else "")
    )

    merged_tools = tools_commands + "\n" + status_commands + "\n" + kang_commands

    merged_admin = (
        (auth_commands if (is_admin or is_sudo or is_owner) else "") +
        ("\n" + blocklist_commands + "\n" + sudo_commands + "\n" + broadcast_commands if (is_sudo or is_owner) else "") +
        ("\n" + owner_commands if is_owner else "")
    )

    category_pages = {
        "playback": playback_commands,
        "auth": auth_commands,
        "blocklist": blocklist_commands,
        "sudo": sudo_commands,
        "broadcast": broadcast_commands,
        "tools": merged_tools,
        "kang": kang_commands,
        "status": status_commands,
        "owner": owner_commands,
        "admin": merged_admin,
        "all_dropdown": merged_all,
    }

    # ---------- Routing ----------
    if data in ("all", "help"):
        await callback_query.answer()
        await callback_query.message.edit_caption(
            caption=Messages.HELP_CATEGORY_SELECT,
            reply_markup=Buttons.help_markup(is_admin=is_admin, is_owner=is_owner, is_sudo=is_sudo),
        )
    elif data in category_pages:
        # Permission checks for restricted categories
        if data in ("owner", "admin") and not (is_admin or is_sudo or is_owner):
            return await callback_query.answer(clean_alert(Messages.ADMIN_RESTRICTED_ACTION), show_alert=True)
        if data == "owner" and not is_owner:
            return await callback_query.answer(clean_alert(Messages.BOT_OWNER_ONLY), show_alert=True)
        if data in ("sudo", "broadcast", "blocklist") and not is_sudo:
            return await callback_query.answer(clean_alert(Messages.OWNER_SUDO_CMD), show_alert=True)
        if data == "auth" and not is_admin:
            return await callback_query.answer(clean_alert(Messages.ADMIN_RESTRICTED_ACTION), show_alert=True)

        await callback_query.answer()
        # Caption-bound: the help menu lives on the start card's photo/video.
        await callback_query.message.edit_caption(
            caption=rich_caption(category_pages[data]),
            reply_markup=Buttons.BACK,
        )
    elif data in ("home", "back"):
        await callback_query.answer()
        greet_message = await gvarstatus(client.me.id, "WELCOME") or (
            f"{EmojiTag.USER} <b>ʜᴇʏ {{name}}!</b>\n\n"
            f"{EmojiTag.MUSIC_NOTE} <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {{botname}}</b>\n\n"
            "<i>ᴀ ᴍᴜsɪᴄ ʙᴏᴛ ᴡɪᴛʜ ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ & ʜɪɢʜ-ǫᴜᴀʟɪᴛʏ sᴛʀᴇᴀᴍɪɴɢ.</i>\n\n"
            "<b><i>ᴜsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ.</i></b>"
        )
        greet_message = await format_welcome_message(client, greet_message, user_id, callback_query.from_user.mention())
        buttons_markup = Buttons.start_markup(client.me.username, ow_id, OWNER_ID, GROUP)
        await callback_query.message.edit_caption(
            caption=greet_message,
            reply_markup=buttons_markup,
        )


@Client.on_message(filters.command(["help", "cmds", "commands"]))
async def help_command_handler(client: Client, message: Message):
    """Handles /help command directly in private or group chats."""
    is_private = message.chat.type == enums.ChatType.PRIVATE
    user_id = message.from_user.id if message.from_user else message.chat.id

    if is_private:
        admin_ids = get_admin_ids(f"{ggg}/admin.txt")
        users_data = await user_sessions.find_one({"bot_id": client.me.id})
        sudoers = users_data.get("SUDOERS", []) if users_data else []
        is_owner = str(user_id) == str(OWNER_ID)
        is_admin = user_id in admin_ids or is_owner
        is_sudo = user_id in sudoers or is_owner

        markup = Buttons.help_markup(is_admin=is_admin, is_owner=is_owner, is_sudo=is_sudo)
        await rich_reply(
            message,
            Messages.HELP_CATEGORY_SELECT,
            reply_markup=markup,
            client=client,
        )
    else:
        # Group chat: send inline button pointing to bot PM
        bot_username = client.me.username
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 ᴏᴘᴇɴ ʜᴇʟᴘ ᴍᴇɴᴜ", url=f"https://t.me/{bot_username}?start=help", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.HELP)]
        ])
        await rich_reply(
            message,
            rich_note(f"{EmojiTag.INFO} <b>ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴏᴘᴇɴ ᴛʜᴇ ʜᴇʟᴘ ᴍᴇɴᴜ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ:</b>"),
            reply_markup=keyboard,
            client=client,
        )

