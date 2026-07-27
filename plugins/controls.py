"""plugins/controls.py — Transport commands and inline buttons: seek/skip/end/pause/resume/loop."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command(["seek", "seekback"]))
@admin_only()
async def seek_handler_func(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    # Check if user is banned using global variable
    if message.from_user.id in BLOCK:
        return

    try:
        # Get seek value from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await client.send_message(
                message.chat.id,
                Messages.SEEK_NO_ARGS,
            link_preview_options=None)
            return

        try:
            seek_value = int(command_parts[1])
            if seek_value < 0:
                await client.send_message(
                    message.chat.id,
                    Messages.SEEK_NEGATIVE,
                link_preview_options=None)
                return
        except ValueError:
            await client.send_message(
                message.chat.id,
                Messages.SEEK_INVALID,
            link_preview_options=None)
            return

        # Check if there's a song playing
        if message.chat.id in playing and playing[message.chat.id]:
            current_song = playing[message.chat.id]
            duration_str = str(current_song['duration'])

            # Convert HH:MM:SS to total seconds
            duration_seconds = sum(
                int(x) * 60 ** i
                for i, x in enumerate(reversed(duration_str.split(":")))
            )

            # Get call client from main.py

            # Check if bot is actually streaming by fetching elapsed time
            if message.chat.id not in played:
                await client.send_message(
                    message.chat.id,
                    "Assistant is not streaming anything!",
                link_preview_options=None)
                return

            played_in_seconds = int(time.time() - played[message.chat.id])

            # Check seek boundaries based on command
            is_forward = command_parts[0].lower() == "/seek"
            if is_forward:
                limit = duration_seconds - played_in_seconds
                error_msg = Messages.SEEK_BEYOND_REMAINING
            else:
                limit = played_in_seconds
                error_msg = Messages.SEEK_BEYOND_PLAYED

            if seek_value > limit:
                await client.send_message(
                    message.chat.id, error_msg, link_preview_options=None)
                return

            total_seek = played_in_seconds + (seek_value if is_forward else -seek_value)

            # Set audio flags based on mode
            mode = current_song['mode']
            audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None

            # Seek to specified position
            to_seek = format_duration(total_seek)
            yt_link = current_song['yt_link']

            # Get stream URL (async-safe, thread-pooled)
            stream_url = await get_stream_url(yt_link)
            if not stream_url:
                stream_url = yt_link  # Fallback to original link

            await call_py.play(
                message.chat.id,
                MediaStream(
                    stream_url,
                    AudioQuality.STUDIO,
                VideoQuality.HD_720p,
                    video_flags=audio_flags,
                    ffmpeg_parameters=f"-ss {to_seek} -to {duration_str}"
                ),
            )

            # Update played time based on command
            if is_forward:
                played[message.chat.id] -= seek_value
            else:  # seekback
                played[message.chat.id] += seek_value

            await client.send_message(
                message.chat.id,
                f"Seeked to {to_seek}!\n\nʙʏ: {message.from_user.mention()}",
            link_preview_options=None)
        else:
            await client.send_message(
                message.chat.id,
                "Assistant is not streaming anything!",
            link_preview_options=None)
    except Exception as e:
        logger.error(f"[seek] Error: {e}")
        await client.send_message(
            message.chat.id,
            Messages.ERROR_OCCURRED,
        link_preview_options=None)


@Client.on_callback_query(filters.regex("^(end|cend)$"))
@admin_only()
async def button_end_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_END_SESSION, show_alert=True)
        return

    try:

        # Determine the chat_id based on whether "cend" is used
        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cend"
            else callback_query.message.chat.id
        )

        is_active = await is_active_chat(client, chat_id)
        if is_active:
            # Clear the song queue and end the session
            await remove_active_chat(client, chat_id)
            queues.pop(chat_id, None)
            try:
                await call_py.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            await callback_query.message.reply(
                f"QUEUE CLEARED\nStreaming stopped\nRequested by: {callback_query.from_user.mention()}",
            link_preview_options=None)
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")

            playing.pop(chat_id, None)

            await callback_query.answer(Messages.STREAM_ENDED, show_alert=False)
        else:
            await remove_active_chat(client, chat_id)
            try:
                await call_py.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            await callback_query.message.reply(
                Messages.NO_STREAM,
            link_preview_options=None)
            playing.pop(chat_id, None)

            await callback_query.answer(Messages.NO_ACTIVE_STREAM, show_alert=False)
    except NotInCallError:
        await remove_active_chat(client, chat_id)
        playing.pop(chat_id, None)
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in end button handler: {e}")
        await callback_query.answer("An error occurred. Please try again.", show_alert=True)


@Client.on_message(filters.command("end"))
@admin_only()
async def end_handler_func(client, message):
  try:
         await message.delete()
  except Exception:
         pass
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   is_active = await is_active_chat(client, message.chat.id)
   if is_active:
       await remove_active_chat(client, message.chat.id)
       queues.pop(message.chat.id, None)
       await client.send_message(message.chat.id,
f"QUEUE CLEARED\nStreaming stopped\nRequested by: {message.from_user.mention()}",
            link_preview_options=None)
       await call_py.leave_call(message.chat.id)
       playing.pop(message.chat.id, None)
   else:
     await client.send_message(message.chat.id, Messages.NO_STREAM,
link_preview_options=None)
     await remove_active_chat(client, message.chat.id)
     await call_py.leave_call(message.chat.id)
     playing.pop(message.chat.id, None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM,
link_preview_options=None)
     playing.pop(message.chat.id, None)


@Client.on_callback_query(filters.regex(r"^(skip|cskip)$"))
@admin_only()
async def button_skip_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_SKIP, show_alert=True)
        return

    try:

        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cskip"
            else callback_query.message.chat.id
        )

        if chat_id in queues and len(queues[chat_id]) > 0:
            # There's a next song in queue
            next_song = queues[chat_id].pop(0)
            await callback_query.message.reply(Messages.SKIPPING.format(callback_query.from_user.mention()), link_preview_options=None)

            try:
                await clients['call_py'].pause(chat_id)
            except Exception as e:
                logger.warning(f"Could not pause before skip: {e}")

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
            )
            await callback_query.answer(Messages.SKIPPED_SUCCESS, show_alert=False)
        else:
            # No more songs in queue
            try:
                await clients['call_py'].leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            await remove_active_chat(client, chat_id)

            if chat_id in playing:
                playing[chat_id].clear()

            await callback_query.message.reply(Messages.SKIPPED_EMPTY.format(callback_query.from_user.mention()), link_preview_options=None)

            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")

            await callback_query.answer(Messages.QUEUE_EMPTY_STREAM_ENDED, show_alert=False)

    except NotInCallError:
        await remove_active_chat(client, chat_id)
        if chat_id in playing:
            playing[chat_id].clear()
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in skip button handler: {e}")
        await callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)


@Client.on_message(filters.command("loop"))
@admin_only()
async def loop_handler_func(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if message.from_user.id in BLOCK:
        return

    try:
        # Get loop count from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await client.send_message(
                message.chat.id,
                Messages.LOOP_NO_ARGS,
            link_preview_options=None)
            return

        try:
            loop_count = int(command_parts[1])
            if loop_count <= 0 or loop_count > 20:
                await client.send_message(
                    message.chat.id,
                    Messages.LOOP_OUT_OF_BOUNDS,
                link_preview_options=None)
                return
        except ValueError:
            await client.send_message(
                message.chat.id,
                Messages.LOOP_INVALID,
            link_preview_options=None)
            return

        # Check if there's a song playing
        if message.chat.id in playing and playing[message.chat.id]:
            current_song = playing[message.chat.id]

            # Initialize queue for this chat if it doesn't exist
            if message.chat.id not in queues:
                queues[message.chat.id] = []

            # Add the current song to queue multiple times
            for _ in range(loop_count):
                queues[message.chat.id].insert(0, current_song)

            await client.send_message(
                message.chat.id,
                f"Current song will be repeated {loop_count} times!\n\nʙʏ: {message.from_user.mention()}",
            link_preview_options=None)
        else:
            await client.send_message(
                message.chat.id,
                "Assistant is not streaming anything!",
            link_preview_options=None)

    except Exception as e:
        logger.error(f"[controls] Error: {e}")
        await client.send_message(
            message.chat.id,
            "❌ An error occurred. Please try again.",
        link_preview_options=None)


@Client.on_message(filters.command("skip"))
@admin_only()
async def skip_handler_func(client, message):
  try:
         await message.delete()
  except Exception:
         pass
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   if message.chat.id in queues:
    if len(queues[message.chat.id]) >0:
       next = queues[message.chat.id].pop(0)
       await client.send_message(message.chat.id, Messages.SKIPPING.format(message.from_user.mention()), link_preview_options=None)
       playing[message.chat.id] = next
       try:
          await call_py.pause(message.chat.id)
       except Exception:
          pass
       await join_call(next['message'], next['title'], next['yt_link'], next['chat'], next['by'], next['duration'], next['mode'], next['thumb'], next.get('stream_url'), yt_task=next.get('_yt_task'))
    else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(client, message.chat.id)
       await client.send_message(message.chat.id, Messages.SKIPPED_EMPTY.format(message.from_user.mention()), link_preview_options=None)
       playing[message.chat.id].clear()
   else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(client, message.chat.id)
       await client.send_message(message.chat.id,
              Messages.SKIPPED_EMPTY.format(message.from_user.mention()), link_preview_options=None)
       playing[message.chat.id].clear()
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM,
link_preview_options=None)
     playing[message.chat.id].clear()


@Client.on_callback_query(filters.regex("^(resume|cresume)$"))
@admin_only()
async def button_resume_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_RESUME, show_alert=True)
        return

    try:

        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cresume"
            else callback_query.message.chat.id
        )

        if await is_active_chat(client, chat_id):
            await call_py.resume(chat_id)
            await callback_query.message.reply(
                f"Song resumed. Use the Pause button to pause again.\n\nʙʏ: {callback_query.from_user.mention()}",
            link_preview_options=None)
        else:
            await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING)
    except NotInCallError:
        await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)


@Client.on_callback_query(filters.regex("^(pause|cpause)$"))
@admin_only()
async def button_pause_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_PAUSE, show_alert=True)
        return

    try:
        chat_id = (
            (await session.get_chat(callback_query.message.chat.id)).linked_chat.id
            if callback_query.data == "cpause"
            else callback_query.message.chat.id
        )

        if await is_active_chat(client, chat_id):
            await call_py.pause(chat_id)
            await callback_query.message.reply(
                f"Song paused. Use the Resume button to continue.\n\nʙʏ: {callback_query.from_user.mention()}",
            link_preview_options=None)
        else:
            await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING)
    except NotInCallError:
        await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)


@Client.on_message(filters.command("resume"))
@admin_only()
async def resume_handler_func(client, message):
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   if  await is_active_chat(client, message.chat.id):
       await call_py.resume(message.chat.id)
       await client.send_message(message.chat.id, Messages.RESUMED.format(message.from_user.mention()), link_preview_options=None)
   else:
       await client.send_message(message.chat.id, Messages.NO_STREAM, link_preview_options=None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM, link_preview_options=None)


@Client.on_message(filters.command("pause"))
@admin_only()
async def pause_handler_func(client, message):
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   if  await is_active_chat(client, message.chat.id):
       await call_py.pause(message.chat.id)
       await client.send_message(message.chat.id, Messages.PAUSED.format(message.from_user.mention()),
link_preview_options=None)
   else:
       await client.send_message(message.chat.id,  Messages.NO_STREAM, link_preview_options=None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM, link_preview_options=None)
