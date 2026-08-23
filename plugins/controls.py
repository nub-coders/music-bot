"""plugins/controls.py — Transport commands and inline buttons: seek/skip/end/pause/resume/loop."""

import uuid
from plugins._common import *  # noqa: F401,F403


def _transport_card(headline: str, pairs) -> str:
    """Public state-change announcement: the existing headline + a detail table.

    Mirrors ``_auth_card`` in ``admin_auth.py`` — the ``Messages.*`` constant is
    passed through verbatim, the table only adds context. Used by the transport
    commands whose effect the whole chat hears anyway, so these stay public.
    """
    return headline + rich_kv_table(pairs)


async def _resolve_ctrl_chat_id(client, update, is_channel: bool) -> int:
    """Resolve target chat id for playback controls, mapping group -> linked channel if channel_mode."""
    chat = update.message.chat if isinstance(update, CallbackQuery) else update.chat
    if is_channel:
        try:
            linked = (await client.get_chat(chat.id)).linked_chat
            if linked:
                return linked.id
        except Exception as e:
            logger.warning(f"Failed to get linked chat for {chat.id}: {e}")
    return chat.id


@Client.on_message(filters.command(["seek", "cseek", "seekback", "cseekback"]))
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
        is_channel = message.command[0].lower() in ("cseek", "cseekback")
        chat_id = await _resolve_ctrl_chat_id(client, message, is_channel)

        # Get seek value from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await rich_reply(
                message,
                rich_note(Messages.SEEK_NO_ARGS),
                ephemeral=True,
                client=client,
            )
            return

        try:
            seek_value = int(command_parts[1])
            if seek_value < 0:
                await rich_reply(
                    message,
                    rich_note(Messages.SEEK_NEGATIVE),
                    ephemeral=True,
                    client=client,
                )
                return
        except ValueError:
            await rich_reply(
                message,
                rich_note(Messages.SEEK_INVALID),
                ephemeral=True,
                client=client,
            )
            return

        # Check if there's a song playing
        if chat_id in state.playing and state.playing[chat_id]:
            current_song = state.playing[chat_id]
            duration_str = str(current_song.get('duration', 'N/A'))

            # Convert HH:MM:SS to total seconds safely
            try:
                if ":" in duration_str and duration_str not in ("N/A", "Live"):
                    duration_seconds = sum(
                        int(x) * 60 ** i
                        for i, x in enumerate(reversed(duration_str.split(":")))
                    )
                else:
                    duration_seconds = 0
            except (ValueError, TypeError):
                duration_seconds = 0

            # Check if bot is actually streaming by fetching elapsed time
            if chat_id not in state.played:
                await rich_reply(
                    message,
                    rich_note(Messages.ASSISTANT_NOT_STREAMING),
                    ephemeral=True,
                    client=client,
                )
                return

            played_in_seconds = int(time.time() - state.played[chat_id])

            # Check seek boundaries based on command
            is_forward = message.command[0].lower() in ("seek", "cseek")
            if is_forward:
                if duration_seconds <= 0:
                    await rich_reply(
                        message,
                        rich_note(Messages.SEEK_BEYOND_REMAINING),
                        ephemeral=True,
                        client=client,
                    )
                    return
                limit = duration_seconds - played_in_seconds
                error_msg = Messages.SEEK_BEYOND_REMAINING
            else:
                limit = played_in_seconds
                error_msg = Messages.SEEK_BEYOND_PLAYED

            if seek_value > limit:
                await rich_reply(
                    message,
                    rich_note(error_msg),
                    ephemeral=True,
                    client=client,
                )
                return

            total_seek = max(0, played_in_seconds + (seek_value if is_forward else -seek_value))

            # Set audio flags based on mode
            mode = current_song.get('mode', 'audio')
            audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None

            # Seek to specified position
            to_seek = format_duration(total_seek)
            yt_link = current_song.get('yt_link') or current_song.get('url')

            # Get stream URL (async-safe, thread-pooled)
            stream_url = await get_stream_url(yt_link)
            if not stream_url:
                stream_url = yt_link  # Fallback to original link

            # get_stream_url can take seconds (yt-dlp fallback). The track may
            # have ended, been skipped, or been replaced meanwhile -- seeking now
            # would restart the *old* song over whatever is currently playing.
            if state.playing.get(chat_id) is not current_song:
                logger.info(f"[seek] Track changed in chat {chat_id} while resolving stream URL; aborting seek")
                return

            active_cp = get_call_client(chat_id) or clients.get("call_py")
            if not active_cp:
                await rich_reply(
                    message,
                    rich_note(Messages.NO_STREAM),
                    ephemeral=True,
                    client=client,
                )
                return

            ffmpeg_params = f"-ss {to_seek} -to {duration_str}" if duration_seconds > 0 else f"-ss {to_seek}"
            await active_cp.play(
                chat_id,
                MediaStream(
                    stream_url,
                    AudioQuality.STUDIO,
                    VideoQuality.HD_720p,
                    video_flags=audio_flags,
                    ffmpeg_parameters=ffmpeg_params,
                ),
            )

            # Update played time based on command
            if is_forward:
                state.played[chat_id] -= seek_value
            else:  # seekback
                state.played[chat_id] += seek_value

            # Public: everyone in the chat hears the jump, so everyone sees why.
            await rich_reply(
                message,
                _transport_card(
                    Messages.SEEKED.format(to_seek, message.from_user.mention()),
                    [
                        (f"{EmojiTag.MUSIC_NOTE} ᴛʀᴀᴄᴋ", rich_esc(trim_title(str(current_song.get('title', 'N/A'))))),
                        (f"{EmojiTag.PLAY} ᴘᴏsɪᴛɪᴏɴ", rich_code(to_seek)),
                        (f"{EmojiTag.INFO} ᴅᴜʀᴀᴛɪᴏɴ", rich_code(duration_str)),
                    ],
                ),
                client=client,
            )
        else:
            await rich_reply(
                message,
                rich_note(Messages.ASSISTANT_NOT_STREAMING),
                ephemeral=True,
                client=client,
            )
    except Exception as e:
        logger.error(f"[seek] Error: {e}")
        await rich_reply(
            message,
            rich_note(Messages.ERROR_OCCURRED),
            ephemeral=True,
            client=client,
        )


@Client.on_callback_query(filters.regex("^(end|cend)$"))
@admin_only()
async def button_end_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_END_SESSION, show_alert=True)
        return

    try:
        is_channel = callback_query.data == "cend"
        chat_id = await _resolve_ctrl_chat_id(client, callback_query, is_channel)

        is_active = await is_active_chat(client, chat_id)
        state.cancel_suggest(chat_id)
        active_cp = get_call_client(chat_id) or clients.get("call_py")
        if is_active:
            # Clear the song queue and end the session
            await remove_active_chat(client, chat_id)
            state.queues.pop(chat_id, None)
            try:
                if active_cp:
                    await active_cp.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            state.playing.pop(chat_id, None)
            await state.delete_now_playing(chat_id)
            try:
                await rich_edit(callback_query, rich_note(Messages.STREAM_ENDED), reply_markup=None)
            except Exception:
                pass

            await callback_query.answer(Messages.STREAM_ENDED, show_alert=False)
        else:
            await remove_active_chat(client, chat_id)
            state.queues.pop(chat_id, None)
            try:
                if active_cp:
                    await active_cp.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            state.playing.pop(chat_id, None)
            await state.delete_now_playing(chat_id)
            try:
                await rich_edit(callback_query, rich_note(Messages.NO_STREAM), reply_markup=None)
            except Exception:
                pass

            await callback_query.answer(Messages.NO_ACTIVE_STREAM, show_alert=False)
    except NotInCallError:
        await remove_active_chat(client, chat_id)
        state.queues.pop(chat_id, None)
        state.playing.pop(chat_id, None)
        await state.delete_now_playing(chat_id)
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in end button handler: {e}")
        await callback_query.answer(Messages.ERROR_OCCURRED, show_alert=True)


@Client.on_message(filters.command(["end", "cend", "stop", "cstop"]))
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
   is_channel = message.command[0].lower() in ("cend", "cstop")
   chat_id = await _resolve_ctrl_chat_id(client, message, is_channel)
   state.cancel_suggest(chat_id)
   is_active = await is_active_chat(client, chat_id)
   active_cp = get_call_client(chat_id) or clients.get("call_py")
   if is_active:
        await remove_active_chat(client, chat_id)
        state.queues.pop(chat_id, None)
        await rich_reply(
            message,
            rich_note(Messages.QUEUE_CLEARED_STOPPED.format(message.from_user.mention())),
            client=client,
        )
        if active_cp:
            await active_cp.leave_call(chat_id)
        state.playing.pop(chat_id, None)
        await state.delete_now_playing(chat_id)
   else:
        await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)
        await remove_active_chat(client, chat_id)
        state.queues.pop(chat_id, None)
        if active_cp:
            await active_cp.leave_call(chat_id)
        state.playing.pop(chat_id, None)
        await state.delete_now_playing(chat_id)
  except NotInCallError:
      await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)
      state.playing.pop(chat_id, None)
      await state.delete_now_playing(chat_id)


@Client.on_callback_query(filters.regex(r"^(skip|cskip)$"))
@admin_only()
async def button_skip_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_SKIP, show_alert=True)
        return

    try:
        is_channel = callback_query.data == "cskip"
        chat_id = await _resolve_ctrl_chat_id(client, callback_query, is_channel)
        active_cp = get_call_client(chat_id) or clients.get("call_py")

        if chat_id in state.queues and len(state.queues[chat_id]) > 0:
            # There's a next song in queue
            next_song = state.queues[chat_id].pop(0)

            try:
                if active_cp:
                    await active_cp.pause(chat_id)
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
                queue_msg=next_song.get('queue_msg'),
                assistant_num=state.get_chat_assistant(chat_id),
            )
            await callback_query.answer(Messages.SKIPPED_SUCCESS, show_alert=False)
        else:
            # No more songs in queue
            try:
                if active_cp:
                    await active_cp.leave_call(chat_id)
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

            await remove_active_chat(client, chat_id)
            state.queues.pop(chat_id, None)
            state.playing.pop(chat_id, None)
            await state.delete_now_playing(chat_id)

            try:
                await rich_edit(callback_query, rich_note(Messages.QUEUE_EMPTY_STREAM_ENDED), reply_markup=None)
            except Exception:
                pass

            await callback_query.answer(Messages.QUEUE_EMPTY_STREAM_ENDED, show_alert=False)

    except NotInCallError:
        await remove_active_chat(client, chat_id)
        state.queues.pop(chat_id, None)
        state.playing.pop(chat_id, None)
        await state.delete_now_playing(chat_id)
        await callback_query.answer(Messages.STREAM_ENDED_NOT_IN_CALL, show_alert=False)
    except Exception as e:
        logger.error(f"Error in skip button handler: {e}")
        await callback_query.answer(Messages.ERROR_OCCURRED, show_alert=True)



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
        is_channel = data.startswith("c")
        chat_id = await _resolve_ctrl_chat_id(client, callback_query, is_channel)
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

        await callback_query.answer(clean_alert(Messages.PLAYING_NOW.format(user.first_name or "User")), show_alert=False)

        active_cp = get_call_client(chat_id) or clients.get("call_py")
        try:
            if active_cp:
                await active_cp.pause(chat_id)
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
            queue_msg=song.get('queue_msg'),
            assistant_num=state.get_chat_assistant(chat_id),
        )
    except Exception as e:
        logger.error(f"Error in play-now button handler: {e}")
        await callback_query.answer(Messages.ERROR_OCCURRED, show_alert=True)


@Client.on_message(filters.command(["loop", "cloop"]))
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
        is_channel = message.command[0].lower() == "cloop"
        chat_id = await _resolve_ctrl_chat_id(client, message, is_channel)

        # Get loop count from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await rich_reply(
                message,
                rich_note(Messages.LOOP_NO_ARGS),
                ephemeral=True,
                client=client,
            )
            return

        try:
            loop_count = int(command_parts[1])
            if loop_count <= 0 or loop_count > 20:
                await rich_reply(
                    message,
                    rich_note(Messages.LOOP_OUT_OF_BOUNDS),
                    ephemeral=True,
                    client=client,
                )
                return
        except ValueError:
            await rich_reply(
                message,
                rich_note(Messages.LOOP_INVALID),
                ephemeral=True,
                client=client,
            )
            return

        # Check if there's a song playing
        if chat_id in state.playing and state.playing[chat_id]:
            current_song = state.playing[chat_id]

            async with state.lock(chat_id):
                # Initialize queue for this chat if it doesn't exist
                if chat_id not in state.queues:
                    state.queues[chat_id] = []

                # Add independent copies of the current song to queue
                for _ in range(loop_count):
                    entry = dict(current_song) if isinstance(current_song, dict) else dict(current_song.__dict__)
                    entry["_track_id"] = str(uuid.uuid4())[:8]
                    entry.pop("_yt_task", None)
                    entry.pop("queue_msg", None)
                    state.queues[chat_id].insert(0, entry)

            # Public: a queued repeat changes what the whole chat will hear next.
            await rich_reply(
                message,
                _transport_card(
                    Messages.SONG_LOOPED.format(loop_count, message.from_user.mention()),
                    [
                        (f"{EmojiTag.MUSIC_NOTE} ᴛʀᴀᴄᴋ", rich_esc(trim_title(str(current_song.get('title', 'N/A'))))),
                        (f"{EmojiTag.LOOP} ʀᴇᴘᴇᴀᴛs", rich_code(loop_count)),
                        (f"{EmojiTag.QUEUE_ICON} ǫᴜᴇᴜᴇ ʟᴇɴɢᴛʜ", rich_code(len(state.queues.get(chat_id, [])))),
                    ],
                ),
                client=client,
            )
        else:
            await rich_reply(
                message,
                rich_note(Messages.ASSISTANT_NOT_STREAMING),
                ephemeral=True,
                client=client,
            )

    except Exception as e:
        logger.error(f"[controls] Error: {e}")
        await rich_reply(
            message,
            rich_note(Messages.ERROR_OCCURRED),
            ephemeral=True,
            client=client,
        )


@Client.on_message(filters.command(["skip", "cskip"]))
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
   is_channel = message.command[0].lower() == "cskip"
   chat_id = await _resolve_ctrl_chat_id(client, message, is_channel)
   active_cp = get_call_client(chat_id) or clients.get("call_py")
   if chat_id in state.queues and len(state.queues[chat_id]) > 0:
       next = state.queues[chat_id].pop(0)
       await rich_reply(
           message,
           _transport_card(
               Messages.SKIPPING.format(message.from_user.mention()),
               [
                   (f"{EmojiTag.NEXT} ᴜᴘ ɴᴇxᴛ", rich_esc(trim_title(str(next.get('title', 'N/A'))))),
                   (f"{EmojiTag.QUEUE_ICON} ʀᴇᴍᴀɪɴɪɴɢ", rich_code(len(state.queues.get(chat_id, [])))),
               ],
           ),
           client=client,
       )
       state.playing[chat_id] = next
       try:
          if active_cp:
              await active_cp.pause(chat_id)
       except Exception:
          pass
       await join_call(
            next['message'],
            next['title'],
            next['yt_link'],
            next['chat'],
            next['by'],
            next['duration'],
            next['mode'],
            next['thumb'],
            next.get('stream_url'),
            yt_task=next.get('_yt_task'),
            queue_msg=next.get('queue_msg'),
            assistant_num=state.get_chat_assistant(chat_id),
        )
   else:
        if active_cp:
            await active_cp.leave_call(chat_id)
        await remove_active_chat(client, chat_id)
        state.queues.pop(chat_id, None)
        state.playing.pop(chat_id, None)
        await state.delete_now_playing(chat_id)
        await rich_reply(
            message,
            rich_note(Messages.SKIPPED_EMPTY.format(message.from_user.mention())),
            client=client,
        )
  except NotInCallError:
      await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)
      state.playing.pop(chat_id, None)
      await state.delete_now_playing(chat_id)


@Client.on_callback_query(filters.regex("^(resume|cresume)$"))
@admin_only()
async def button_resume_handler(client: Client, callback_query: CallbackQuery):
    # Use global BLOCK list (already loaded at startup) - no DB query needed
    if callback_query.from_user.id in BLOCK:
        await callback_query.answer(Messages.NO_PERM_RESUME, show_alert=True)
        return

    try:
        is_channel = callback_query.data == "cresume"
        chat_id = await _resolve_ctrl_chat_id(client, callback_query, is_channel)
        active_cp = get_call_client(chat_id) or clients.get("call_py")

        if await is_active_chat(client, chat_id):
            if active_cp:
                await active_cp.resume(chat_id)
            await callback_query.answer(clean_alert(Messages.RESUMED.format(callback_query.from_user.first_name or "User")), show_alert=False)
        else:
            await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)
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
        is_channel = callback_query.data == "cpause"
        chat_id = await _resolve_ctrl_chat_id(client, callback_query, is_channel)
        active_cp = get_call_client(chat_id) or clients.get("call_py")

        if await is_active_chat(client, chat_id):
            if active_cp:
                await active_cp.pause(chat_id)
            await callback_query.answer(clean_alert(Messages.PAUSED.format(callback_query.from_user.first_name or "User")), show_alert=False)
        else:
            await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)
    except NotInCallError:
        await callback_query.answer(Messages.ASSISTANT_NOT_STREAMING, show_alert=True)


@Client.on_message(filters.command(["resume", "cresume"]))
@admin_only()
async def resume_handler_func(client, message):
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   is_channel = message.command[0].lower() == "cresume"
   chat_id = await _resolve_ctrl_chat_id(client, message, is_channel)
   active_cp = get_call_client(chat_id) or clients.get("call_py")
   if await is_active_chat(client, chat_id):
       if active_cp:
           await active_cp.resume(chat_id)
       await rich_reply(message, rich_note(Messages.RESUMED.format(message.from_user.mention())), client=client)
   else:
       await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)
  except NotInCallError:
     await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)


@Client.on_message(filters.command(["pause", "cpause"]))
@admin_only()
async def pause_handler_func(client, message):
  # Use global BLOCK list (already loaded at startup) - no DB query needed
  if message.from_user.id in BLOCK:
       return
  try:
   is_channel = message.command[0].lower() == "cpause"
   chat_id = await _resolve_ctrl_chat_id(client, message, is_channel)
   active_cp = get_call_client(chat_id) or clients.get("call_py")
   if await is_active_chat(client, chat_id):
       if active_cp:
           await active_cp.pause(chat_id)
       await rich_reply(message, rich_note(Messages.PAUSED.format(message.from_user.mention())), client=client)
   else:
       await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)
  except NotInCallError:
     await rich_reply(message, rich_note(Messages.NO_STREAM), ephemeral=True, client=client)


# ── Suggestion & Autoplay Callbacks / Commands ───────────────────────────────

@Client.on_callback_query(filters.regex(r"^sgplay_"))
async def suggestion_play_handler(client: Client, callback_query: CallbackQuery):
    """Play a suggested video immediately in audio mode."""
    user = callback_query.from_user
    if not user or user.id in BLOCK:
        await callback_query.answer(Messages.ADMIN_RESTRICTED_ACTION, show_alert=True)
        return
    if user.id != OWNER_ID and user.id not in SUDO and not allow_play(user.id):
        await callback_query.answer(Messages.RATE_LIMITED, show_alert=True)
        return

    chat_id = callback_query.message.chat.id
    vid = callback_query.data.split("sgplay_", 1)[1]
    url = f"https://www.youtube.com/watch?v={vid}"

    # Cancel countdown timer
    state.cancel_suggest(chat_id)

    await callback_query.answer(Messages.STARTING_PLAYBACK, show_alert=False)

    try:
        await rich_edit(
            callback_query,
            rich_note(Messages.PLAYING_SUGGESTION.format(vid)),
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
            assistant_num=state.get_chat_assistant(chat_id),
        )
    except Exception as e:
        logger.error(f"[Suggest] Failed to play suggested track {vid}: {e}")
        # Ephemeral to the presser; degrades to a public reply exactly like before.
        await rich_answer(callback_query, rich_note(Messages.ERROR_OCCURRED), client=client)


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
    active_cp = get_call_client(chat_id) or clients.get("call_py")

    try:
        if active_cp:
            await active_cp.leave_call(chat_id)
    except Exception:
        pass

    await remove_active_chat(client, chat_id)
    state.queues.pop(chat_id, None)
    state.playing.pop(chat_id, None)
    await state.delete_now_playing(chat_id)

    try:
        await rich_edit(
            callback_query,
            rich_note(Messages.STREAM_ENDED),
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


def _autoplay_panel(status_str: str) -> str:
    """Autoplay settings card: status table + collapsible option reference.

    ``status_str`` is the same pre-rendered ``<b>ᴇɴᴀʙʟᴇᴅ</b>``/``<b>ᴅɪsᴀʙʟᴇᴅ</b>``
    value the ``Messages.AUTOPLAY_*`` constants already interpolate.
    """
    return (
        rich_heading(f"{EmojiTag.SETTINGS} ᴀᴜᴛᴏᴘʟᴀʏ", 1)
        + rich_kv_table([
            (f"{EmojiTag.INFO} sᴛᴀᴛᴜs", status_str),
            (f"{EmojiTag.SHIELD} ᴄᴀɴ sᴡɪᴛᴄʜ", "<i>ᴀᴅᴍɪɴs &amp; ᴀᴜᴛʜ ᴜsᴇʀs</i>"),
        ])
        + rich_details(
            f"{EmojiTag.INFO} ᴏᴘᴛɪᴏɴs",
            rich_table(
                ["ᴄᴏᴍᴍᴀɴᴅ", "ᴇ꩖꩖ᴇᴄᴛ"],
                [
                    (rich_code("/autoplay"), "ᴛᴏɢɢʟᴇ ᴏɴ ⇄ ᴏ꩖꩖"),
                    (rich_code("/autoplay on"), "ᴇɴᴀʙʟᴇ sᴜɢɢᴇsᴛᴇᴅ ᴛʀᴀᴄᴋs"),
                    (rich_code("/autoplay off"), "sᴛᴏᴘ ᴀ꩖ᴛᴇʀ ᴛʜᴇ ǫᴜᴇᴜᴇ ᴇɴᴅs"),
                    (rich_code("/autoplay status"), "sʜᴏᴡ ᴛʜɪs ᴄᴀʀᴅ ᴏɴʟʏ"),
                ],
            ),
        )
    )


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
            return await rich_reply(
                message,
                _autoplay_panel(status_str),
                client=client,
            )

        if not is_admin:
            return await rich_reply(
                message,
                rich_note(Messages.ADMIN_RESTRICTED_CMD) + _autoplay_panel(status_str),
                ephemeral=True,
                client=client,
            )

        if arg in ["on", "enable", "true", "1"]:
            state.set_autoplay(chat_id, True)
            await rich_reply(message, rich_note(Messages.AUTOPLAY_ENABLED), ephemeral=True, client=client)
        elif arg in ["off", "disable", "false", "0"]:
            state.set_autoplay(chat_id, False)
            state.cancel_suggest(chat_id)
            await rich_reply(message, rich_note(Messages.AUTOPLAY_DISABLED), ephemeral=True, client=client)
        else:
            await rich_reply(
                message,
                rich_note(Messages.AUTOPLAY_USAGE.format(status_str)) + _autoplay_panel(status_str),
                ephemeral=True,
                client=client,
            )
    else:
        if not is_admin:
            return await rich_reply(
                message,
                rich_note(Messages.AUTOPLAY_ADMIN_ONLY_SWITCH.format(status_str)),
                ephemeral=True,
                client=client,
            )

        new_state = not current
        state.set_autoplay(chat_id, new_state)
        if not new_state:
            state.cancel_suggest(chat_id)
        if new_state:
            await rich_reply(message, rich_note(Messages.AUTOPLAY_ENABLED), ephemeral=True, client=client)
        else:
            await rich_reply(message, rich_note(Messages.AUTOPLAY_DISABLED), ephemeral=True, client=client)

