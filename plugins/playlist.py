"""plugins/playlist.py — Personal Multi-Playlist system for NUB Music Bot.

Features:
- Ephemeral 1-tap addition from Now Playing cards into any of user's playlists (max 5).
- DM redirection for creating new playlists and renaming with strict validation (1-10 alphanumeric chars).
- Full interactive playlist management via /playlist (browse, see songs, individual track delete, rename, delete).
- Group voice chat playback via /playplaylist and interactive buttons.
"""

import re
import datetime
import random

from plugins._common import *  # noqa: F401,F403
from plugins.playback import put_queue, dend

logger = logging.getLogger(__name__)

# Strict playlist name validation: 1-10 alphanumeric characters only (no spaces, symbols, or special chars)
PLAYLIST_NAME_REGEX = re.compile(r"^[a-zA-Z0-9]{1,10}$")

# In-memory transient state for users creating/renaming playlists in DM
# user_id -> {"chat_id": int, "track": dict | None}
pending_create_pl: dict[int, dict] = {}
# user_id -> {"playlist_id": str, "old_name": str}
pending_rename_pl: dict[int, dict] = {}


# ─── 1-Tap Now Playing Ephemeral Add Selector ──────────────────────────────────

@Client.on_callback_query(filters.regex(r"^c?add_to_pl$"))
async def add_to_playlist_callback(client: Client, callback_query: CallbackQuery):
    """Fired when a user taps '➕ ᴀᴅᴅ ᴛᴏ ᴘʟᴀʏʟɪsᴛ' on the Now Playing card.

    Sends an ephemeral message (visible only to this user) showing their existing
    playlists and a link to create a new one in DM if they have < 5 playlists.
    """
    user = callback_query.from_user
    if not user or user.id in BLOCK:
        await callback_query.answer("You are not allowed to perform this action.", show_alert=True)
        return

    is_channel = callback_query.data.startswith("c")
    chat_id = callback_query.message.chat.id
    if is_channel:
        try:
            linked = (await client.get_chat(chat_id)).linked_chat
            if linked:
                chat_id = linked.id
        except Exception:
            pass

    # Retrieve currently playing track
    current_song = state.playing.get(chat_id)
    if not current_song:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_NO_ACTIVE_SONG), show_alert=True)
        return

    track_title = trim_title(str(current_song.get("title", "Unknown Track")))
    playlists = await get_user_playlists(user.id)

    markup = Buttons.playlist_select_markup(playlists, client.me.username, chat_id)
    if playlists:
        text = Messages.PLAYLIST_SELECT_PROMPT.format(rich_esc(track_title))
    else:
        text = Messages.PLAYLIST_NO_PLAYLISTS_PROMPT.format(rich_esc(track_title))

    await rich_reply(
        callback_query,
        text,
        reply_markup=markup,
        ephemeral=True,
        client=client,
    )
    await callback_query.answer()


@Client.on_callback_query(filters.regex(r"^pl_add_([a-zA-Z0-9]+)_(-?\d+)$"))
async def add_track_to_selected_playlist(client: Client, callback_query: CallbackQuery):
    """Fired when user picks a specific playlist button from the ephemeral selector."""
    user = callback_query.from_user
    if not user or user.id in BLOCK:
        await callback_query.answer("You are not allowed to perform this action.", show_alert=True)
        return

    match = re.match(r"^pl_add_([a-zA-Z0-9]+)_(-?\d+)$", callback_query.data)
    if not match:
        return

    playlist_id, chat_id = match.group(1), int(match.group(2))
    current_song = state.playing.get(chat_id)
    if not current_song:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_NO_ACTIVE_SONG), show_alert=True)
        return

    target_pl = await get_playlist(user.id, playlist_id)
    if not target_pl:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_NOT_FOUND), show_alert=True)
        return

    track_info = {
        "title": current_song.get("title", "Unknown Track"),
        "duration": current_song.get("duration", "N/A"),
        "yt_link": current_song.get("yt_link", ""),
        "video_id": extract_video_id(current_song.get("yt_link", "")) or current_song.get("video_id", ""),
        "mode": current_song.get("mode", "audio"),
    }

    ok, msg_code = await add_track_to_playlist(user.id, playlist_id, track_info, max_tracks=50)
    pl_name = target_pl.get("name", "Playlist")
    trimmed_title = trim_title(track_info["title"])

    if ok:
        alert_msg = Messages.PLAYLIST_ADDED_SUCCESS.format(trimmed_title, pl_name)
        await callback_query.answer(clean_alert(alert_msg), show_alert=False)
        # Update ephemeral view with success notification
        success_card = (
            rich_heading(f"{EmojiTag.SUCCESS} ᴀᴅᴅᴇᴅ ᴛᴏ ᴘʟᴀʏʟɪsᴛ", 2)
            + rich_kv_table([
                (f"{EmojiTag.MUSIC_NOTE} ᴛʀᴀᴄᴋ", rich_esc(trimmed_title)),
                ("📁 ᴘʟᴀʏʟɪsᴛ", rich_code(pl_name)),
            ])
        )
        try:
            await ephemeral_edit(callback_query.message, success_card, reply_markup=None, client=client)
        except Exception:
            pass
    elif msg_code == "ALREADY_EXISTS":
        await callback_query.answer(clean_alert(Messages.PLAYLIST_TRACK_EXISTS.format(pl_name)), show_alert=True)
    elif msg_code == "MAX_TRACKS":
        await callback_query.answer(clean_alert(Messages.PLAYLIST_MAX_TRACKS.format(pl_name)), show_alert=True)
    else:
        await callback_query.answer(clean_alert(Messages.ERROR_OCCURRED), show_alert=True)


# ─── Playlist Hub (/playlist & /myplaylist) ───────────────────────────────────

def _build_playlist_hub_view(playlists: list) -> str:
    """Renders Screen A: Playlists Overview."""
    if not playlists:
        return rich_heading(f"{EmojiTag.MUSIC_NOTES} ᴍʏ ᴘʟᴀʏʟɪsᴛs", 1) + rich_note(Messages.PLAYLIST_EMPTY)

    rows = []
    for idx, pl in enumerate(playlists, 1):
        name = rich_esc(pl.get("name", "Playlist"))
        count = len(pl.get("tracks", []))
        created = datetime.datetime.fromtimestamp(pl.get("created_at", time.time())).strftime("%Y-%m-%d")
        rows.append((custom_digits(idx), f"<b>{name}</b>", rich_code(f"{count} track(s)"), rich_code(created)))

    return (
        rich_heading(f"{EmojiTag.MUSIC_NOTES} ᴍʏ ᴘʟᴀʏʟɪsᴛs ({len(playlists)}/5)", 1)
        + rich_table(["#", "ᴘʟᴀʏʟɪsᴛ", "ᴛʀᴀᴄᴋs", "ᴄʀᴇᴀᴛᴇᴅ"], rows)
        + rich_note(f"{EmojiTag.INFO} <i>Select a playlist below to play, view tracks, rename, or delete:</i>")
    )


@Client.on_message(filters.command(["playlist", "myplaylist"]))
async def playlist_hub_command(client: Client, message: Message):
    """Entry point for /playlist and /myplaylist commands."""
    user_id = message.from_user.id if message.from_user else message.chat.id
    playlists = await get_user_playlists(user_id)
    markup = Buttons.playlist_hub_markup(playlists, client.me.username)
    text = _build_playlist_hub_view(playlists)
    await rich_reply(message, text, reply_markup=markup, client=client)


@Client.on_callback_query(filters.regex(r"^pl_hub$"))
async def playlist_hub_callback(client: Client, callback_query: CallbackQuery):
    """Returns to Screen A (Playlists Hub)."""
    user_id = callback_query.from_user.id
    playlists = await get_user_playlists(user_id)
    markup = Buttons.playlist_hub_markup(playlists, client.me.username)
    text = _build_playlist_hub_view(playlists)
    await rich_edit(callback_query, text, reply_markup=markup, client=client)
    await callback_query.answer()


# ─── Screen B: Playlist Details & Management ──────────────────────────────────

@Client.on_callback_query(filters.regex(r"^pl_open_([a-zA-Z0-9]+)$"))
async def playlist_open_callback(client: Client, callback_query: CallbackQuery):
    """Opens Screen B: Specific playlist details and actions."""
    match = re.match(r"^pl_open_([a-zA-Z0-9]+)$", callback_query.data)
    if not match:
        return

    playlist_id = match.group(1)
    user_id = callback_query.from_user.id
    pl = await get_playlist(user_id, playlist_id)

    if not pl:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_NOT_FOUND), show_alert=True)
        # Return to hub if playlist no longer exists
        playlists = await get_user_playlists(user_id)
        markup = Buttons.playlist_hub_markup(playlists, client.me.username)
        text = _build_playlist_hub_view(playlists)
        return await rich_edit(callback_query, text, reply_markup=markup, client=client)

    tracks = pl.get("tracks", [])
    created_str = datetime.datetime.fromtimestamp(pl.get("created_at", time.time())).strftime("%Y-%m-%d %H:%M")
    has_tracks = bool(len(tracks) > 0)

    content = (
        rich_heading(f"📁 ᴘʟᴀʏʟɪsᴛ: {rich_esc(pl['name'])}", 1)
        + rich_kv_table([
            ("🏷 ɴᴀᴍᴇ", rich_code(pl['name'])),
            ("🎵 ᴛʀᴀᴄᴋs", rich_code(f"{len(tracks)} / 50")),
            ("📅 ᴄʀᴇᴀᴛᴇᴅ", rich_code(created_str)),
        ])
        + (rich_note(f"{EmojiTag.INFO} <i>Choose an action below:</i>") if has_tracks else rich_note(Messages.PLAYLIST_TRACKS_EMPTY))
    )

    markup = Buttons.playlist_manage_markup(playlist_id, client.me.username, has_tracks=has_tracks)
    await rich_edit(callback_query, content, reply_markup=markup, client=client)
    await callback_query.answer()


# ─── Screen C: Paginated Songs Viewer with Delete Buttons ─────────────────────

PAGE_SIZE = 10


@Client.on_callback_query(filters.regex(r"^pl_songs_([a-zA-Z0-9]+)_(\d+)$"))
async def playlist_songs_callback(client: Client, callback_query: CallbackQuery):
    """Opens Screen C: Paginated song list with per-track delete buttons."""
    match = re.match(r"^pl_songs_([a-zA-Z0-9]+)_(\d+)$", callback_query.data)
    if not match:
        return

    playlist_id, page = match.group(1), int(match.group(2))
    user_id = callback_query.from_user.id
    pl = await get_playlist(user_id, playlist_id)

    if not pl:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_NOT_FOUND), show_alert=True)
        return

    tracks = pl.get("tracks", [])
    if not tracks:
        # Redirect back to Screen B if all songs were deleted
        return await playlist_open_callback(client, callback_query)

    total_pages = max(1, (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    page_tracks = tracks[start_idx:start_idx + PAGE_SIZE]

    song_rows = []
    for idx_on_page, t in enumerate(page_tracks, 1):
        global_num = start_idx + idx_on_page
        t_title = trim_title(str(t.get("title", "Unknown Track")), max_length=35)
        t_dur = str(t.get("duration", "N/A"))
        song_rows.append((custom_digits(global_num), f"<b>{rich_esc(t_title)}</b>", rich_code(t_dur)))

    content = (
        rich_heading(f"📋 {rich_esc(pl['name'])} — ᴛʀᴀᴄᴋs (ᴘᴀɢᴇ {page}/{total_pages})", 1)
        + rich_table(["#", "ᴛʀᴀᴄᴋ", "ᴅᴜʀᴀᴛɪᴏɴ"], song_rows)
        + rich_note(f"{EmojiTag.INFO} <i>Tap <code>[ ❌ # ]</code> below to remove a track from this page:</i>")
    )

    markup = Buttons.playlist_songs_markup(playlist_id, page, total_pages, len(page_tracks))
    await rich_edit(callback_query, content, reply_markup=markup, client=client)
    await callback_query.answer()


@Client.on_callback_query(filters.regex(r"^pl_delsong_([a-zA-Z0-9]+)_(\d+)_(\d+)$"))
async def playlist_delete_song_callback(client: Client, callback_query: CallbackQuery):
    """Deletes an individual song from a playlist and refreshes Screen C."""
    match = re.match(r"^pl_delsong_([a-zA-Z0-9]+)_(\d+)_(\d+)$", callback_query.data)
    if not match:
        return

    playlist_id = match.group(1)
    page = int(match.group(2))
    relative_idx = int(match.group(3))
    user_id = callback_query.from_user.id

    global_idx = (page - 1) * PAGE_SIZE + relative_idx
    ok = await remove_track_from_playlist(user_id, playlist_id, global_idx)

    if ok:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_SONG_DELETED), show_alert=False)
        # Fetch updated playlist to check remaining tracks
        pl = await get_playlist(user_id, playlist_id)
        if not pl or not pl.get("tracks"):
            return await playlist_open_callback(client, callback_query)

        # Check if page is still valid after deletion
        total_pages = max(1, (len(pl.get("tracks", [])) + PAGE_SIZE - 1) // PAGE_SIZE)
        if page > total_pages:
            page = total_pages
        # Refresh Screen C
        callback_query.data = f"pl_songs_{playlist_id}_{page}"
        await playlist_songs_callback(client, callback_query)
    else:
        await callback_query.answer(clean_alert(Messages.ERROR_OCCURRED), show_alert=True)


# ─── Playlist Deletion (Screen B confirmation) ────────────────────────────────

@Client.on_callback_query(filters.regex(r"^pl_delpl_([a-zA-Z0-9]+)$"))
async def playlist_delete_prompt_callback(client: Client, callback_query: CallbackQuery):
    """Prompts confirmation before deleting a playlist."""
    match = re.match(r"^pl_delpl_([a-zA-Z0-9]+)$", callback_query.data)
    if not match:
        return

    playlist_id = match.group(1)
    user_id = callback_query.from_user.id
    pl = await get_playlist(user_id, playlist_id)

    if not pl:
        await callback_query.answer(clean_alert(Messages.PLAYLIST_NOT_FOUND), show_alert=True)
        return

    content = (
        rich_heading(f"🗑 ᴅᴇʟᴇᴛᴇ ᴘʟᴀʏʟɪsᴛ: {rich_esc(pl['name'])}", 1)
        + rich_note(f"{EmojiTag.WARNING} <b>Are you sure you want to delete this playlist?</b>\n<i>This will permanently remove all {len(pl.get('tracks', []))} track(s).</i>")
    )
    markup = Buttons.playlist_delete_confirm_markup(playlist_id)
    await rich_edit(callback_query, content, reply_markup=markup, client=client)
    await callback_query.answer()


@Client.on_callback_query(filters.regex(r"^pl_confirm_delpl_([a-zA-Z0-9]+)$"))
async def playlist_confirm_delete_callback(client: Client, callback_query: CallbackQuery):
    """Permanently deletes the playlist."""
    match = re.match(r"^pl_confirm_delpl_([a-zA-Z0-9]+)$", callback_query.data)
    if not match:
        return

    playlist_id = match.group(1)
    user_id = callback_query.from_user.id
    pl = await get_playlist(user_id, playlist_id)
    pl_name = pl.get("name", "Playlist") if pl else "Playlist"

    await delete_playlist(user_id, playlist_id)
    await callback_query.answer(clean_alert(Messages.PLAYLIST_DELETED.format(pl_name)), show_alert=True)

    # Return to Screen A
    playlists = await get_user_playlists(user_id)
    markup = Buttons.playlist_hub_markup(playlists, client.me.username)
    text = _build_playlist_hub_view(playlists)
    await rich_edit(callback_query, text, reply_markup=markup, client=client)


# ─── Playlist Playback (Group Voice Chat) ─────────────────────────────────────

async def _play_playlist_tracks(client: Client, message_or_cb, playlist: dict, shuffle: bool = False, video_mode: bool = False, channel_mode: bool = False):
    """Core logic to queue and play all tracks from a playlist into the group's voice chat."""
    chat = message_or_cb.message.chat if isinstance(message_or_cb, CallbackQuery) else message_or_cb.chat
    by_user = message_or_cb.from_user

    # Determine target chat for channel mode
    target_chat_id = chat.id
    target_chat = chat
    if channel_mode:
        try:
            linked = (await client.get_chat(chat.id)).linked_chat
            if linked:
                target_chat_id = linked.id
                target_chat = linked
        except Exception:
            pass

    tracks = list(playlist.get("tracks", []))
    if not tracks:
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.answer(clean_alert(Messages.PLAYLIST_TRACKS_EMPTY), show_alert=True)
        else:
            await rich_reply(message_or_cb, rich_note(Messages.PLAYLIST_TRACKS_EMPTY), ephemeral=True, client=client)
        return

    if shuffle:
        random.shuffle(tracks)

    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.answer(f"▶️ Playing '{playlist['name']}' ({len(tracks)} tracks)...", show_alert=False)

    # Send status message
    status_msg = await client.send_message(
        chat.id,
        Messages.PLAYLIST_PLAYING.format(len(tracks), playlist['name']),
        link_preview_options=None,
    )

    is_active = not await state.activate(target_chat_id)

    mode = "video" if video_mode else "audio"

    # Queue all tracks
    for i, t in enumerate(tracks):
        _url = t.get("yt_link") or (f"https://www.youtube.com/watch?v={t['video_id']}" if t.get("video_id") else t.get("title"))
        _title = t.get("title", "Playlist track")
        _dur = t.get("duration", "N/A")

        # For the first track, create yt_task if needed
        yt_task = None
        if i == 0 and _url:
            yt_task = asyncio.create_task(handle_youtube(_url))
            yt_task.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)

        await put_queue(
            status_msg,
            trim_title(_title),
            client,
            _url,
            target_chat,
            by_user,
            _dur,
            mode,
            None,
            forceplay=False,
            stream_url=None,
            yt_task=yt_task,
        )

    if not is_active:
        # Chat was not active, trigger dend to start streaming immediately
        await dend(client, status_msg, target_chat_id if channel_mode else None)


@Client.on_callback_query(filters.regex(r"^pl_play_([a-zA-Z0-9]+)$"))
async def playlist_play_callback(client: Client, callback_query: CallbackQuery):
    """Plays all playlist tracks in voice chat from button."""
    match = re.match(r"^pl_play_([a-zA-Z0-9]+)$", callback_query.data)
    if not match:
        return
    pl_id = match.group(1)
    user_id = callback_query.from_user.id
    pl = await get_playlist(user_id, pl_id)
    if not pl:
        return await callback_query.answer(clean_alert(Messages.PLAYLIST_NOT_FOUND), show_alert=True)

    if callback_query.message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await callback_query.answer(clean_alert(Messages.GROUP_ONLY), show_alert=True)

    await _play_playlist_tracks(client, callback_query, pl, shuffle=False)


@Client.on_callback_query(filters.regex(r"^pl_shuffle_([a-zA-Z0-9]+)$"))
async def playlist_shuffle_callback(client: Client, callback_query: CallbackQuery):
    """Shuffle-plays all playlist tracks in voice chat from button."""
    match = re.match(r"^pl_shuffle_([a-zA-Z0-9]+)$", callback_query.data)
    if not match:
        return
    pl_id = match.group(1)
    user_id = callback_query.from_user.id
    pl = await get_playlist(user_id, pl_id)
    if not pl:
        return await callback_query.answer(clean_alert(Messages.PLAYLIST_NOT_FOUND), show_alert=True)

    if callback_query.message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await callback_query.answer(clean_alert(Messages.GROUP_ONLY), show_alert=True)

    await _play_playlist_tracks(client, callback_query, pl, shuffle=True)


@Client.on_message(filters.command(["playplaylist", "playpl", "myplay", "vplayplaylist", "vplaypl", "cplayplaylist", "cvplayplaylist"]))
async def play_playlist_command(client: Client, message: Message):
    """Plays a playlist via command: /playplaylist [playlist_name]."""
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await rich_reply(message, rich_note(Messages.GROUP_ONLY), ephemeral=True, client=client)

    cmd = message.command[0].lower()
    video_mode = cmd.startswith("v") or cmd.startswith("cv")
    channel_mode = cmd.startswith("c")

    user_id = message.from_user.id if message.from_user else message.chat.id
    playlists = await get_user_playlists(user_id)

    if not playlists:
        return await rich_reply(message, rich_note(Messages.PLAYLIST_EMPTY), ephemeral=True, client=client)

    args = message.text.split(maxsplit=1)
    query_name = args[1].strip() if len(args) > 1 else ""

    target_pl = None
    if query_name:
        for pl in playlists:
            if pl.get("name", "").lower() == query_name.lower():
                target_pl = pl
                break
        if not target_pl:
            return await rich_reply(
                message,
                rich_note(f"{EmojiTag.ERROR} <b>No playlist found with name:</b> <code>{rich_esc(query_name)}</code>"),
                ephemeral=True,
                client=client,
            )
    elif len(playlists) == 1:
        target_pl = playlists[0]
    else:
        # Prompt user to choose which playlist to play
        rows = [
            [InlineKeyboardButton(f"📁 {pl['name']} ({len(pl.get('tracks', []))})", callback_data=f"pl_play_{pl['id']}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.PLAY)]
            for pl in playlists
        ]
        rows.append([InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE)])
        return await rich_reply(
            message,
            rich_heading(f"{EmojiTag.PLAY} ᴘʟᴀʏ ᴘʟᴀʏʟɪsᴛ", 2) + rich_note("<i>Select which playlist to play in voice chat:</i>"),
            reply_markup=InlineKeyboardMarkup(rows),
            client=client,
        )

    await _play_playlist_tracks(client, message, target_pl, shuffle=False, video_mode=video_mode, channel_mode=channel_mode)


# ─── DM Text Handler for Pending Create & Rename ───────────────────────────────

@Client.on_message(filters.private & filters.text & ~filters.command(["start", "help", "cancel", "playlist", "myplaylist"]))
async def dm_playlist_input_handler(client: Client, message: Message):
    """Captures text in DM when a user is in the middle of creating or renaming a playlist."""
    user_id = message.from_user.id if message.from_user else message.chat.id
    input_text = message.text.strip()

    # 1. Handle Rename Playlist
    if user_id in pending_rename_pl:
        pl_data = pending_rename_pl[user_id]
        pl_id = pl_data.get("playlist_id")

        if not PLAYLIST_NAME_REGEX.match(input_text):
            return await rich_reply(message, Messages.PLAYLIST_INVALID_NAME, client=client)

        ok, msg_code = await rename_playlist(user_id, pl_id, input_text)
        if ok:
            pending_rename_pl.pop(user_id, None)
            await rich_reply(message, Messages.PLAYLIST_RENAMED.format(rich_esc(input_text)), client=client)
        elif msg_code == "NAME_EXISTS":
            await rich_reply(message, Messages.PLAYLIST_NAME_EXISTS, client=client)
        else:
            pending_rename_pl.pop(user_id, None)
            await rich_reply(message, Messages.PLAYLIST_NOT_FOUND, client=client)
        return

    # 2. Handle Create Playlist
    if user_id in pending_create_pl:
        create_data = pending_create_pl[user_id]
        pending_track = create_data.get("track")

        if not PLAYLIST_NAME_REGEX.match(input_text):
            return await rich_reply(message, Messages.PLAYLIST_INVALID_NAME, client=client)

        ok, msg_code, new_pl = await create_playlist(user_id, input_text, max_playlists=5)
        if ok and new_pl:
            pending_create_pl.pop(user_id, None)
            if pending_track:
                await add_track_to_playlist(user_id, new_pl["id"], pending_track, max_tracks=50)
                await rich_reply(
                    message,
                    Messages.PLAYLIST_CREATED_AND_ADDED.format(rich_esc(input_text), rich_esc(trim_title(pending_track.get("title", "Song")))),
                    client=client,
                )
            else:
                await rich_reply(
                    message,
                    Messages.PLAYLIST_CREATED.format(rich_esc(input_text)),
                    client=client,
                )
        elif msg_code == "NAME_EXISTS":
            await rich_reply(message, Messages.PLAYLIST_NAME_EXISTS, client=client)
        elif msg_code == "MAX_PLAYLISTS":
            pending_create_pl.pop(user_id, None)
            await rich_reply(message, Messages.PLAYLIST_MAX_REACHED, client=client)
        else:
            pending_create_pl.pop(user_id, None)
            await rich_reply(message, Messages.ERROR_OCCURRED, client=client)
        return
