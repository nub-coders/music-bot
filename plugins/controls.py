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
        if message.chat.id in state.playing and state.playing[message.chat.id]:
            current_song = state.playing[message.chat.id]
            duration_str = str(current_song['duration'])

            # Convert HH:MM:SS to total seconds
            duration_seconds = sum(
                int(x) * 60 ** i
                for i, x in enumerate(reversed(duration_str.split(":")))
            )

            # Get call client from main.py

            # Check if bot is actually streaming by fetching elapsed time
            if message.chat.id not in state.played:
                await client.send_message(
                    message.chat.id,
                    "Assistant is not streaming anything!",
                link_preview_options=None)
                return

            played_in_seconds = int(time.time() - state.played[message.chat.id])

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
                state.played[message.chat.id] -= seek_value
            else:  # seekback
                state.played[message.chat.id] += seek_value

            await client.send_message(
                message.chat.id,
                f"<b>{EmojiTag.SUCCESS} sᴇᴇᴋᴇᴅ ᴛᴏ {to_seek}!</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {message.from_user.mention()}",
            link_preview_options=None)
        else:
            await client.send_message(
                message.chat.id,
                Messages.ASSISTANT_NOT_STREAMING,
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
        state.cancel_suggest(chat_id)
        if is_active:
            # Clear the song queue and end the session
            await remove_active_chat(client, chat_id)
            state.queues.pop(chat_id, None)
            try:
                await call_py.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            await callback_query.message.reply(
                f"<b>{EmojiTag.STOP} ǫᴜᴇᴜᴇ ᴄʟᴇᴀʀᴇᴅ</b>\n<b>‣ sᴛʀᴇᴀᴍɪɴɢ sᴛᴏᴘᴘᴇᴅ</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {callback_query.from_user.mention()}",
            link_preview_options=None)
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")

            state.playing.pop(chat_id, None)

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
            state.playing.pop(chat_id, None)

            await callback_query.answer(Messages.NO_ACTIVE_STREAM, show_alert=False)
    except NotInCallError:
        await remove_active_chat(client, chat_id)
        state.playing.pop(chat_id, None)
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
   chat_id = message.chat.id
   state.cancel_suggest(chat_id)
   is_active = await is_active_chat(client, chat_id)
   if is_active:
       await remove_active_chat(client, chat_id)
       state.queues.pop(chat_id, None)
       await client.send_message(message.chat.id,
f"<b>{EmojiTag.STOP} ǫᴜᴇᴜᴇ ᴄʟᴇᴀʀᴇᴅ</b>\n<b>‣ sᴛʀᴇᴀᴍɪɴɢ sᴛᴏᴘᴘᴇᴅ</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {message.from_user.mention()}",
            link_preview_options=None)
       await call_py.leave_call(message.chat.id)
       state.playing.pop(message.chat.id, None)
   else:
     await client.send_message(message.chat.id, Messages.NO_STREAM,
link_preview_options=None)
     await remove_active_chat(client, message.chat.id)
     await call_py.leave_call(message.chat.id)
     state.playing.pop(message.chat.id, None)
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM,
link_preview_options=None)
     state.playing.pop(message.chat.id, None)


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

        if chat_id in state.queues and len(state.queues[chat_id]) > 0:
            # There's a next song in queue
            next_song = state.queues[chat_id].pop(0)
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

            if chat_id in state.playing:
                state.playing[chat_id].clear()

            await callback_query.message.reply(Messages.SKIPPED_EMPTY.format(callback_query.from_user.mention()), link_preview_options=None)

            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")

            await callback_query.answer(Messages.QUEUE_EMPTY_STREAM_ENDED, show_alert=False)

    except NotInCallError:
        await remove_active_chat(client, chat_id)
        if chat_id in state.playing:
            state.playing[chat_id].clear()
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in skip button handler: {e}")
        await callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^c?playnow_"))
async def button_playnow_handler(client: Client, callback_query: CallbackQuery):
    """Jump straight to a queued track — the button on its 'added to queue' card.

    Admins/auth users, plus whoever queued the currently-playing song (same rule
    the skip button uses). Not @admin_only() because the exemption depends on the
    active song's `by`, which is looked up dynamically.
    """
    user = callback_query.from_user
    if not user or user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_SKIP, show_alert=True)
        return
    if user.id != OWNER_ID and user.id not in SUDO and not allow_play(user.id):
        await callback_query.answer(Messages.RATE_LIMITED, show_alert=True)
        return

    data = callback_query.data
    try:
        # The button lives in the group; for cplay the queue lives under the
        # linked channel. Authorize against the group, pop from the queue's chat.
        auth_chat_id = callback_query.message.chat.id
        chat_id = (
            (await session.get_chat(auth_chat_id)).linked_chat.id
            if data.startswith("c")
            else auth_chat_id
        )
        track_id = data.split("_", 1)[1]

        # Check authorization: jumping straight to a track interrupts/skips the
        # currently playing track. The user must be an admin/auth user OR the
        # owner of the currently playing song (same authorization as /skip).
        current_song = state.playing.get(chat_id)
        current_owner_id = (
            getattr(current_song.get("by"), "id", None)
            if isinstance(current_song, dict)
            else None
        )
        if current_song and user.id != current_owner_id and not await is_authorized(
            client, auth_chat_id, user.id
        ):
            await callback_query.answer(Messages.ADMIN_RESTRICTED_ACTION, show_alert=True)
            return

        song = await state.pop_track(chat_id, track_id)
        if not song:
            await callback_query.answer(Messages.TRACK_GONE, show_alert=True)
            return

        await callback_query.answer()
        await callback_query.message.reply(
            Messages.PLAYING_NOW.format(user.mention()), link_preview_options=None)

        try:
            await call_py.pause(chat_id)
        except Exception as e:
            logger.warning(f"Could not pause before play-now: {e}")

        await join_call(
            song['message'],
            song['title'],
            song['yt_link'],
            song['chat'],
            song['by'],
            song['duration'],
            song['mode'],
            song['thumb'],
            song.get('stream_url'),
            yt_task=song.get('_yt_task'),
        )
    except Exception as e:
        logger.error(f"Error in play-now button handler: {e}")
        await callback_query.answer(Messages.ERROR_OCCURRED, show_alert=True)


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
        if message.chat.id in state.playing and state.playing[message.chat.id]:
            current_song = state.playing[message.chat.id]

            # Initialize queue for this chat if it doesn't exist
            if message.chat.id not in state.queues:
                state.queues[message.chat.id] = []

            # Add the current song to queue multiple times
            for _ in range(loop_count):
                state.queues[message.chat.id].insert(0, current_song)

            await client.send_message(
                message.chat.id,
                f"<b>{EmojiTag.LOOP} ᴄᴜʀʀᴇɴᴛ sᴏɴɢ ᴡɪʟʟ ʙᴇ ʀᴇᴘᴇᴀᴛᴇᴅ {loop_count} ᴛɪᴍᴇs!</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {message.from_user.mention()}",
            link_preview_options=None)
        else:
            await client.send_message(
                message.chat.id,
                Messages.ASSISTANT_NOT_STREAMING,
            link_preview_options=None)

    except Exception as e:
        logger.error(f"[controls] Error: {e}")
        await client.send_message(
            message.chat.id,
            Messages.ERROR_OCCURRED,
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
   if message.chat.id in state.queues:
    if len(state.queues[message.chat.id]) >0:
       next = state.queues[message.chat.id].pop(0)
       await client.send_message(message.chat.id, Messages.SKIPPING.format(message.from_user.mention()), link_preview_options=None)
       state.playing[message.chat.id] = next
       try:
          await call_py.pause(message.chat.id)
       except Exception:
          pass
       await join_call(next['message'], next['title'], next['yt_link'], next['chat'], next['by'], next['duration'], next['mode'], next['thumb'], next.get('stream_url'), yt_task=next.get('_yt_task'))
    else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(client, message.chat.id)
       await client.send_message(message.chat.id, Messages.SKIPPED_EMPTY.format(message.from_user.mention()), link_preview_options=None)
       state.playing[message.chat.id].clear()
   else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(client, message.chat.id)
       await client.send_message(message.chat.id,
              Messages.SKIPPED_EMPTY.format(message.from_user.mention()), link_preview_options=None)
       state.playing[message.chat.id].clear()
  except NotInCallError:
     await client.send_message(message.chat.id, Messages.NO_STREAM,
link_preview_options=None)
     state.playing[message.chat.id].clear()


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
                f"<b>{EmojiTag.RESUME} sᴏɴɢ ʀᴇsᴜᴍᴇᴅ. ᴜsᴇ ᴛʜᴇ ᴘᴀᴜsᴇ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴘᴀᴜsᴇ ᴀɢᴀɪɴ.</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {callback_query.from_user.mention()}",
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
                f"<b>{EmojiTag.PAUSE} sᴏɴɢ ᴘᴀᴜsᴇᴅ. ᴜsᴇ ᴛʜᴇ ʀᴇsᴜᴍᴇ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {callback_query.from_user.mention()}",
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


# ── Suggestion & Autoplay Callbacks / Commands ───────────────────────────────

@Client.on_callback_query(filters.regex(r"^sgplay_"))
async def suggestion_play_handler(client: Client, callback_query: CallbackQuery):
    """Play a suggested video immediately in audio mode."""
    user = callback_query.from_user
    if not user or user.id in BLOCK:
        await callback_query.answer("You are not allowed to perform this action.", show_alert=True)
        return
    if user.id != OWNER_ID and user.id not in SUDO and not allow_play(user.id):
        await callback_query.answer(Messages.RATE_LIMITED, show_alert=True)
        return

    chat_id = callback_query.message.chat.id
    vid = callback_query.data.split("sgplay_", 1)[1]
    url = f"https://www.youtube.com/watch?v={vid}"

    # Cancel countdown timer
    state.cancel_suggest(chat_id)

    await callback_query.answer("▶️ Starting playback…", show_alert=False)

    try:
        await callback_query.message.edit_text(
            f"▶️ <b>ᴘʟᴀʏɪɴɢ sᴜɢɢᴇsᴛɪᴏɴ:</b> <code>{vid}</code>…",
            reply_markup=None,
        )
    except Exception:
        pass

    try:
        state.add_to_history(chat_id, vid)
        yt_task = asyncio.create_task(handle_youtube(url))
        yt_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        last_info = state.last_played.get(chat_id) or {}
        chat_obj = last_info.get("chat") or callback_query.message.chat
        await join_call(
            callback_query.message,
            "Suggested Track",
            url,
            chat_obj,
            user,
            "N/A",
            "audio",
            None,
            stream_url=None,
            yt_task=yt_task,
        )
    except Exception as e:
        logger.error(f"[Suggest] Failed to play suggested track {vid}: {e}")
        await callback_query.message.reply(Messages.ERROR_OCCURRED, link_preview_options=None)


@Client.on_callback_query(filters.regex(r"^sgstop$"))
@admin_only()
async def suggestion_stop_handler(client: Client, callback_query: CallbackQuery):
    """Stop suggestion countdown and leave voice chat."""
    user = callback_query.from_user
    if not user or user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_END_SESSION, show_alert=True)
        return

    chat_id = callback_query.message.chat.id
    state.cancel_suggest(chat_id)

    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass

    await remove_active_chat(client, chat_id)
    state.playing.pop(chat_id, None)

    try:
        await callback_query.message.edit_text(
            f"<b>{EmojiTag.STOP} sᴛʀᴇᴀᴍ ᴇɴᴅᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ.</b>",
            reply_markup=None,
        )
    except Exception:
        pass

    await callback_query.answer(Messages.STREAM_ENDED, show_alert=False)


@Client.on_callback_query(filters.regex(r"^sgtoggle$"))
@admin_only()
async def suggestion_toggle_handler(client: Client, callback_query: CallbackQuery):
    """Toggle autoplay on/off from suggestion card."""
    chat_id = callback_query.message.chat.id
    current = state.is_autoplay_enabled(chat_id)
    new_state = not current
    state.set_autoplay(chat_id, new_state)

    if not new_state:
        state.cancel_suggest(chat_id)

    await callback_query.answer("Autoplay: ON" if new_state else "Autoplay: OFF", show_alert=False)

    try:
        orig_markup = callback_query.message.reply_markup
        if orig_markup and orig_markup.inline_keyboard:
            rows = []
            for row in orig_markup.inline_keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data == "sgtoggle":
                        new_txt = "🔄 ᴀᴜᴛᴏᴘʟᴀʏ: ON" if new_state else "⏸ ᴀᴜᴛᴏᴘʟᴀʏ: OFF"
                        new_row.append(InlineKeyboardButton(new_txt, callback_data="sgtoggle", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.SETTINGS))
                    else:
                        new_row.append(btn)
                rows.append(new_row)
            await callback_query.message.edit_reply_markup(InlineKeyboardMarkup(rows))
    except Exception:
        pass


@Client.on_message(filters.command(["autoplay", "suggest"]))
async def autoplay_command_handler(client: Client, message):
    """View or toggle autoplay status. Members can view; only admins and auth users can switch."""
    if message.from_user and message.from_user.id in BLOCK:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None
    parts = message.text.split()
    current = state.is_autoplay_enabled(chat_id)
    status_str = "<b>ᴇɴᴀʙʟᴇᴅ</b>" if current else "<b>ᴅɪsᴀʙʟᴇᴅ</b>"

    is_admin = await is_authorized(client, chat_id, user_id, allow_auth_users=True) if user_id else False

    if len(parts) > 1:
        arg = parts[1].lower()
        if arg in ["status", "check", "info"]:
            return await message.reply(
                f"{EmojiTag.INFO} <b>ᴀᴜᴛᴏᴘʟᴀʏ sᴛᴀᴛᴜs:</b> {status_str}",
                link_preview_options=None,
            )

        if not is_admin:
            return await message.reply(
                f"{Messages.ADMIN_RESTRICTED_CMD}\n\n{EmojiTag.INFO} <b>ᴀᴜᴛᴏᴘʟᴀʏ ɪs ᴄᴜʀʀᴇɴᴛʟʏ:</b> {status_str}",
                link_preview_options=None,
            )

        if arg in ["on", "enable", "true", "1"]:
            state.set_autoplay(chat_id, True)
            await message.reply(Messages.AUTOPLAY_ENABLED, link_preview_options=None)
        elif arg in ["off", "disable", "false", "0"]:
            state.set_autoplay(chat_id, False)
            state.cancel_suggest(chat_id)
            await message.reply(Messages.AUTOPLAY_DISABLED, link_preview_options=None)
        else:
            await message.reply(
                f"{EmojiTag.INFO} <b>ᴜsᴀɢᴇ:</b> <code>/autoplay [on|off]</code>\n‣ <b>ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs:</b> {status_str}",
                link_preview_options=None,
            )
    else:
        if not is_admin:
            return await message.reply(
                f"{EmojiTag.INFO} <b>ᴀᴜᴛᴏᴘʟᴀʏ sᴛᴀᴛᴜs:</b> {status_str}\n<i>(Only admins & auth users can switch this setting)</i>",
                link_preview_options=None,
            )

        new_state = not current
        state.set_autoplay(chat_id, new_state)
        if not new_state:
            state.cancel_suggest(chat_id)
        if new_state:
            await message.reply(Messages.AUTOPLAY_ENABLED, link_preview_options=None)
        else:
            await message.reply(Messages.AUTOPLAY_DISABLED, link_preview_options=None)

