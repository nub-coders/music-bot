"""plugins/playback.py — /play command plus its media-download, thumbnail and queue helpers."""
import uuid
import html as _html

from plugins._common import *  # noqa: F401,F403
from sources import resolve_sources


def _bg(coro):
    """Fire-and-forget a coroutine, swallowing its result/exception so it never
    warns or blocks the caller. Used for cosmetic Telegram calls (message
    deletes) that must not sit on the /play critical path."""
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    return task


async def dend(client, update, channel_id= None):
    # Enhanced input validation
    try:
        chat_id = int(channel_id or update.chat.id)
        logger.debug(f"Dend processing - Validated chat_id: {chat_id} (type: {type(chat_id)})")
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Invalid chat_id: {e}. channel_id: {channel_id}, update.chat.id: {getattr(update.chat, 'id', 'N/A')}")
        return
    try:
        chat_id = int(channel_id or update.chat.id)  # Ensure integer chat_id
        if chat_id in state.queues and state.queues[chat_id]:
            next_song = state.queues[chat_id].pop(0)
            state.playing[chat_id] = next_song
            await join_call(
                next_song['message'],
                next_song['title'],
                next_song['yt_link'],
                next_song['chat'],
                next_song['by'],
                next_song['duration'],
                next_song['mode'],
                next_song['thumb'],
                next_song.get('stream_url'),
                yt_task=next_song.get('_yt_task'),
                queue_msg=next_song.get('queue_msg'),
            )
        else:
            logger.info(f"Song queue for chat {chat_id} is empty.")
            await state.delete_now_playing(chat_id)
            await client.leave_call(chat_id)
            await remove_active_chat(client, chat_id)
            if chat_id in state.playing:
                state.playing[chat_id].clear()
    except Exception as e:
        logger.error(f"Error in dend function: {e}")


def generate_thumbnail(video_path, thumb_path):
    try:
        reader = imageio.get_reader(video_path)
        frame = reader.get_data(0)
        image = Image.fromarray(frame)
        image.thumbnail((320, 320))
        image.save(thumb_path, "JPEG")
        return thumb_path
    except Exception:
        # Fallback to black thumbnail
        Image.new('RGB', (320, 320), (0, 0, 0)).save(thumb_path, "JPEG")
        return thumb_path


async def download_media_with_progress(client, msg, media_msg, type_of):
    start_time = time.time()
    filename = getattr(media_msg, 'file_name', 'file')
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}/{msg.chat.id}"
    os.makedirs(user_dir, exist_ok=True)
    try:
        file_path = await client.download_media(media_msg,file_name=f"{user_dir}/",
            progress=progress_bar,
            progress_args=(client, msg, type_of, filename, start_time))
        return file_path
    except Exception as e:
        print(f"Download error: {e}")
        return None


async def progress_bar(current, total, client, msg, type_of, filename, start_time):
    if total == 0:
        return

    try:
            progress_percent = current * 100 / total
            progress_message = f"{type_of} {filename}: {progress_percent:.2f}%\n"

            # Progress bar calculation
            progress_bar_length = 20
            num_ticks = int(progress_percent / (100 / progress_bar_length))
            progress_bar_text = '█' * num_ticks + '░' * (progress_bar_length - num_ticks)

            # Speed calculation
            elapsed_time = time.time() - start_time
            speed = current / (elapsed_time * 1024 * 1024) if elapsed_time > 0 else 0

            # Time remaining calculation
            time_left = (total - current) / (speed * 1024 * 1024) if speed > 0 else 0

            # Format message
            progress_message += (
                f"Speed: {speed:.2f} MB/s\n"
                f"Time left: {time_left:.2f}s\n"
                f"Size: {current/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n"
                f"[{progress_bar_text}]"
            )

            # Edit message with exponential backoff
            try:
              if random.choices([True, False], weights=[1, 20])[0]:
                await msg.edit(progress_message)
            except Exception as e:
                print(f"Progress update error: {e}")

    except Exception as e:
        print(f"Progress bar error: {e}")


def with_opencv(filename):
    # List of common audio file extensions
    audio_extensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.mp4', '.wma']
    file_ext = os.path.splitext(filename)[1].lower()

    # Handle audio files with mutagen
    if file_ext in audio_extensions:
        try:
            audio = File(filename)
            if audio is not None and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                duration = audio.info.length
                return int(duration)
            else:
                return 0
        except MutagenError:
            return 0
    # Handle video files with OpenCV
    else:
        video = cv2.VideoCapture(filename)
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps else 0
        video.release()
        return int(duration)


@Client.on_message(filters.command(["play", "vplay", "playforce", "vplayforce", "cplay", "cvplay", "cplayforce", "cvplayforce"]))
async def play_handler_func(client, message):
    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    by = message.from_user
    # Cosmetic: remove the user's "/play ..." command. Fire-and-forget so this
    # Telegram round-trip does not gate track resolution / the voice join.
    _bg(message.delete())

    # Check if user is banned using global BLOCK variable
    if message.from_user.id in BLOCK:
        return

    # Throttle rapid /play spam per user (owner/sudo exempt).
    if message.from_user.id != OWNER_ID and message.from_user.id not in SUDO:
        if not allow_play(message.from_user.id):
            await message.reply(Messages.RATE_LIMITED, link_preview_options=None)
            return

    command = message.command[0].lower()
    mode = "video" if command.startswith("v") or command.startswith("cv") else "audio"
    force_play = command.endswith("force")
    channel_mode = command.startswith("c")

    # Check if the command is sent in a group
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply(Messages.GROUP_ONLY, link_preview_options=None)
        return

    # Check for query or replied media upfront before sending processing message or locking chat
    has_media = bool(message.reply_to_message and message.reply_to_message.media)
    input_parts = (message.text or message.caption or "").split(maxsplit=1)
    raw_query = input_parts[1].strip() if len(input_parts) > 1 else ""

    if not has_media and not raw_query:
        await message.reply(f"{Messages.NO_QUERY_GIVEN}\n`/{command} query`", link_preview_options=None)
        return

    # Get the bot username and retrieve the session client ID from connector
    youtube_link = None

    # Determine if we need channel mode
    _chat = message.chat
    target_chat_id = message.chat.id
    # For channel commands, check for linked channel
    if channel_mode:
        linked_chat = (await client.get_chat(message.chat.id)).linked_chat
        if not linked_chat:
            await message.reply(Messages.NO_LINKED_CHANNEL, link_preview_options=None)
            return
        target_chat_id = linked_chat.id

    # Check queue for the target chat
    _current_queue = len(state.queues.get(target_chat_id, [])) if state.queues else 0

    massage = await message.reply(Messages.BOLT, link_preview_options=None)
    state.cancel_suggest(target_chat_id)
    # Atomic test-and-set under the per-chat lock: of two near-simultaneous /play
    # calls in the same chat, exactly one sees is_active=False (starts playback);
    # the other sees True and is routed to the enqueue branch. Closes the race
    # where both could read "not active" and both try to join/play.
    is_active = not await state.activate(target_chat_id)

    # Force-play interrupts/skips the active stream, so require admin/auth or current song owner.
    if force_play and is_active:
        current_song = state.playing.get(target_chat_id)
        current_owner_id = (
            getattr(current_song.get("by"), "id", None)
            if isinstance(current_song, dict)
            else None
        )
        if current_song and message.from_user.id != current_owner_id and not await is_authorized(
            client, message.chat.id, message.from_user.id
        ):
            await massage.edit(Messages.ADMIN_RESTRICTED_CMD)
            return

    youtube_link = None
    media_info = {}
    _yt_task = None
    _playlist_rest = []

    # Initialize title with a safe default to prevent unbound variable issues
    title = trim_title("Unknown Media")

    # Check if replied to media message
    if has_media:
        media_msg = message.reply_to_message
        media_type = None
        duration = 0
        thumbnail = None

        # Video handling
        if media_msg.video:
            media = media_msg.video
            media_type = "video"
            title = trim_title(media.file_name or "Telegram Video")
            duration = media.duration
            if media.thumbs:
                thumbnail = await client.download_media(media.thumbs[0].file_id)

        # Audio handling
        elif media_msg.audio:
            media = media_msg.audio
            media_type = "audio"
            title = trim_title(media.title or "Telegram Audio")
            duration = media.duration
            if media.thumbs:
                thumbnail = await client.download_media(media.thumbs[0].file_id)

        # Voice message handling
        elif media_msg.voice:
            media = media_msg.voice
            media_type = "voice"
            title = trim_title("Voice Message")
            duration = media.duration

        # Video note handling
        elif media_msg.video_note:
            media = media_msg.video_note
            media_type = "video_note"
            title = trim_title("Video Note")
            duration = media.duration
            if media.thumbs:
                thumbnail = await client.download_media(media.thumbs[0].file_id)
        elif media_msg.document:
            doc = media_msg.document
            media = media_msg.document
    # In Pyrogram, check the mime_type directly
            if doc.mime_type:
                if doc.mime_type.startswith("video/"):
                    media_type = "video"
                    title = trim_title(doc.file_name or "Telegram Video")
                    duration = getattr(doc, 'duration', 0)  # duration might not always be available
            elif doc.mime_type.startswith("audio/"):
                     media_type = "audio"
                     title = trim_title(doc.file_name or "Telegram Audio")
                     duration = getattr(doc, 'duration', 0)


            if media_type and doc.thumbs:
                thumbnail = await client.download_media(doc.thumbs[0].file_id,f"{user_dir}/")
        else:
            await massage.edit(Messages.UNSUPPORTED_MEDIA)
            return await remove_active_chat(client, target_chat_id)
        if not media_type:
            await massage.edit(Messages.UNSUPPORTED_MEDIA)
            return await remove_active_chat(client, target_chat_id)
        # For media messages
        youtube_link = await download_media_with_progress(
            client,
            massage,
            message.reply_to_message,
            "Media"
        )
        stream_url = None

        # Generate thumbnail if missing
        if not thumbnail and media_type in ["video", "video_note"]:
            try:
                thumbnail = await asyncio.to_thread(generate_thumbnail, youtube_link, f'{user_dir}/thumb.png')
            except Exception as e:
                print(e)
                thumbnail = None
        # Format duration
        if not duration or duration <=0:
            duration = await asyncio.to_thread(with_opencv, youtube_link)
        duration = format_duration(int(duration))
        media_info = {
            'title': title,
            'duration': duration,
            'thumbnail': thumbnail,
            'file_id': media.file_id,
            'media_type': media_type,
            'url': youtube_link
        }
    else:
        search_query = raw_query
        # Source seam: a playlist link expands into many per-track queries;
        # search text or a single video URL stays a one-element list.
        _sources = await resolve_sources(search_query)
        search_query = _sources[0][0]
        _playlist_rest = _sources[1:]

        # Placeholder values — join_call will wait for the task to resolve
        title = trim_title(search_query[:25])
        duration = None
        youtube_link = None
        thumbnail = None
        _channel_name = None
        _views = None
        video_id = None
        stream_url = None

        _yt_task = asyncio.create_task(handle_youtube(search_query))
        _yt_task.add_done_callback(
            lambda t: t.exception() if not t.cancelled() else None
        )

    # Start thumbnail generation in the background so the voice join is not blocked.
    # join_call will await the task only after streaming is already live.
    if media_info:
        thumb = asyncio.create_task(
            get_thumb(
                media_info['title'],
                media_info['duration'],
                media_info['thumbnail'],
                None,
                None,
                None,
            )
        )
    else:
        # join_call will create the thumb task once yt_task resolves
        thumb = None
    if thumb:
        thumb.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)

    # Retrieve the session client from the clients dictionary

    # Join the group (same for both regular and channel mode)
    if message.chat.username:
        # Public group
        try:
            try:
                joined_chat = await session.get_chat(message.chat.username)
            except Exception:
                joined_chat = await session.join_chat(message.chat.username)
        except (InviteHashExpired, ChannelPrivate):
            await massage.edit(f"Assistant is banned in this chat.\n\nPlease unban {session.me.username or session.me.id}")
            return await remove_active_chat(client, target_chat_id)
        except Exception as e:
            logger.error(f"[play] Failed to join group {target_chat_id}: {e}")
            await massage.edit("Failed to join the group. Please try again.")
            return await remove_active_chat(client, target_chat_id)
    else:
        # Private group — try to get/join without relying on privileges check.
        # Pyrogram often returns privileges=None for admins even when permissions
        # ARE granted, so we never pre-reject. We try directly and let Telegram's
        # API raise an error if something is actually missing.
        bot_member = await client.get_chat_member(message.chat.id, client.me.id)
        is_admin_or_owner = bot_member.status in (
            ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
        )

        # Step 1: Maybe the session is already a member — no join needed.
        try:
            joined_chat = await session.get_chat(message.chat.id)
            logger.info(f"[play] Session already in private group {message.chat.id}")
        except Exception:
            # Step 2: Not a member yet. Try to export invite link and join.
            if not is_admin_or_owner:
                await massage.edit(Messages.NEED_INVITE_PERMISSION)
                return await remove_active_chat(client, target_chat_id)
            try:
                invite_link = await client.export_chat_invite_link(message.chat.id)
                joined_chat = await session.join_chat(invite_link)
                logger.info(f"[play] Session joined private group {message.chat.id} via invite link")
            except (InviteHashExpired, ChannelPrivate):
                await massage.edit(
                    f"Assistant is banned in this chat.\n\nPlease unban "
                    f"{session.me.mention()}\nuser id: {session.me.id}"
                )
                return await remove_active_chat(client, target_chat_id)
            except Exception as e:
                # If Telegram rejects due to missing invite permission, tell the user
                err_str = str(e).lower()
                if "chat_admin_required" in err_str or "invite" in err_str or "forbidden" in err_str:
                    await massage.edit(Messages.NEED_INVITE_PERMISSION)
                else:
                    logger.error(f"[play] Failed to join private group {target_chat_id}: {e}")
                    await massage.edit("Failed to join the group. Please try again.")
                return await remove_active_chat(client, target_chat_id)


    # Set the target chat based on whether it's channel mode or not
    target_chat = None
    linked_chat = None
    if channel_mode:
        # For channel mode, use the linked chat
        linked_chat = (await session.get_chat(message.chat.id)).linked_chat
        if not linked_chat:
            await massage.edit(Messages.LINKED_CHANNEL_ERROR)
            return await remove_active_chat(client, target_chat_id)
        target_chat = linked_chat
    else:
        # For regular mode, use the joined chat
        target_chat = joined_chat

    track_id, put_entry = await put_queue(
        massage,
        trim_title(title),
        client,
        youtube_link,
        target_chat,
        by,
        duration,
        mode,
        thumb,
        force_play,
        stream_url,
        yt_task=_yt_task,
    )
    # Playlist: queue the remaining tracks behind the first. Each resolves
    # lazily via its own handle_youtube task when it reaches the queue head
    # (join_call awaits _yt_task), exactly like any normal queued search.
    for _url, _ptitle in _playlist_rest:
        _rest_task = asyncio.create_task(handle_youtube(_url))
        _rest_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        await put_queue(
            massage,
            trim_title(_ptitle or "Playlist track"),
            client,
            None,
            target_chat,
            by,
            None,
            mode,
            None,
            False,
            None,
            yt_task=_rest_task,
        )
    if _playlist_rest:
        await message.reply(
            Messages.PLAYLIST_QUEUED.format(len(_playlist_rest) + 1),
            link_preview_options=None,
        )
    if is_active and not force_play:
                if _yt_task and duration is None:
                    try:
                        yt_result = await _yt_task
                        if yt_result:
                            title = trim_title(yt_result[0]) if yt_result[0] else title
                            duration = yt_result[1] if yt_result[1] else "N/A"
                            youtube_link = yt_result[2] if yt_result[2] else youtube_link
                    except Exception:
                        duration = "N/A"
                position = len(state.queues.get(message.chat.id)) if state.queues.get(target_chat.id) else 1
                keyboard = Buttons.queue_markup(track_id, channel_mode)
                is_local_file = bool(youtube_link) and os.path.exists(youtube_link)
                video_id = extract_video_id(youtube_link) if youtube_link and not is_local_file else None
                _safe_title = _html.escape(trim_title(title))
                if video_id:
                    title_text = f'<a href="https://t.me/{client.me.username}?start=vidid_{video_id}"><b>{_safe_title}</b></a>'
                elif youtube_link and youtube_link.startswith("http"):
                    title_text = f'<a href="{youtube_link}"><b>{_safe_title}</b></a>'
                else:
                    title_text = f'<b>{_safe_title}</b>'
                queue_msg = await client.send_message(message.chat.id, Messages.QUEUE.format(mode, title_text, duration, position_tag(position)), reply_markup=keyboard, link_preview_options=None)
                if put_entry:
                    put_entry.queue_msg = queue_msg
                _bg(massage.delete())
                try:
                    await message.delete()
                except Exception:
                    pass


    else:
      await dend(client, massage, target_chat.id if channel_mode else None)
    try:
        await message.delete()
    except Exception:
        pass  # ponytail: bot may lack delete rights / service msg — non-fatal


async def put_queue(
    message,
    title,
    client,
    yt_link,
    chat,
    by,
    duration,
    audio_flags,
    thumb,
    forceplay=False,
    stream_url=None,
    track_id=None,
    yt_task=None,
):
    try:
        _duration_in_seconds = (time_to_seconds(duration) - 3) if duration else 0
    except Exception:
        _duration_in_seconds = 0
    track_id = track_id or uuid.uuid4().hex[:12]
    put = QueueEntry(
        message=message,
        title=trim_title(title),
        duration=duration,
        mode=audio_flags,
        yt_link=yt_link,
        chat=chat,
        by=by,
        session=client,
        thumb=thumb,
        stream_url=stream_url,
        _track_id=track_id,
        _yt_task=yt_task,
    )
    if forceplay:
        async with state.lock(chat.id):
            check = state.queues.get(chat.id)
            if check:
                state.queues[chat.id].insert(0, put)
            else:
                state.queues[chat.id] = []
                state.queues[chat.id].append(put)
    else:
        async with state.lock(chat.id):
            check = state.queues.get(chat.id)

            if not check:
               state.queues[chat.id] = []
            state.queues[chat.id].append(put)
    return track_id, put
