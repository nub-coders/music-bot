import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import tools
import youtube
from plugins import playback
from state import SessionStore


@pytest.fixture
def session(monkeypatch):
    store = SessionStore()
    monkeypatch.setattr(tools, "state", store)
    monkeypatch.setattr(playback, "state", store)
    return store


@pytest.fixture
def fake_playback(monkeypatch):
    bot = SimpleNamespace(me=SimpleNamespace(id=999, username="testbot"))
    call = SimpleNamespace(play=AsyncMock(), resume=AsyncMock(), pause=AsyncMock(), leave_call=AsyncMock())
    monkeypatch.setattr(tools, "clients", {"bot": bot, "call_py": call})
    monkeypatch.setattr(tools, "calls", {1: call})
    monkeypatch.setattr(tools, "get_call_client", lambda chat_id: call)
    monkeypatch.setattr(tools, "get_thumb", AsyncMock(return_value=None))
    monkeypatch.setattr(tools, "rich_send_blocks", AsyncMock(return_value=None))
    monkeypatch.setattr(tools, "rich_send", AsyncMock(return_value=None))
    monkeypatch.setattr(tools, "db_task", lambda coroutine: coroutine.close())
    return bot, call


def chat_and_message(chat_id):
    chat = SimpleNamespace(id=chat_id, type=tools.ChatType.SUPERGROUP, username="test", title="Test")
    message = SimpleNamespace(chat=chat, delete=AsyncMock())
    return chat, message


async def extraction(title="Resolved"):
    return (title, "1:00", "https://youtu.be/dQw4w9WgXcQ", None, None, None,
            "dQw4w9WgXcQ", "https://media.example/audio")


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_stage", ["reply", "resolution"])
async def test_cold_play_requests_start_once_and_queue_in_arrival_order(session, fake_playback, monkeypatch, blocked_stage):
    bot, _call = fake_playback
    chat, _message = chat_and_message(-1008001)
    user = SimpleNamespace(id=123456789, first_name="User", mention=lambda: "User")
    gate = asyncio.Event()
    started = asyncio.Event()

    def request(query):
        status = SimpleNamespace(chat=chat, delete=AsyncMock())

        async def reply(*args, **kwargs):
            if query == "first" and blocked_stage == "reply":
                started.set()
                await gate.wait()
            return status

        return SimpleNamespace(chat=chat, from_user=user, text="/play " + query, caption=None,
                               command=["play"], reply_to_message=None, delete=AsyncMock(),
                               reply=reply)

    async def resolve(query):
        if query == "first" and blocked_stage == "resolution":
            started.set()
            await gate.wait()
        return [(query, query)]

    monkeypatch.setattr(playback, "save_chat_type", lambda *args: None)
    monkeypatch.setattr(playback, "resolve_sources", resolve)
    async def resolve_track(query, **kwargs):
        return await extraction(query)

    monkeypatch.setattr(playback, "handle_youtube", resolve_track)
    monkeypatch.setattr(playback, "get_assistant", AsyncMock(return_value=(1, SimpleNamespace(), SimpleNamespace())))
    monkeypatch.setattr(session, "is_member_cached", lambda *args: True)
    monkeypatch.setattr(playback, "rich_send", AsyncMock(return_value=None))
    joins = AsyncMock()
    monkeypatch.setattr(playback, "join_call", joins)
    first = asyncio.create_task(playback.play_handler_func(bot, request("first")))
    await asyncio.wait_for(started.wait(), 1)
    second = asyncio.create_task(playback.play_handler_func(bot, request("second")))
    await asyncio.sleep(0)
    gate.set()
    await asyncio.wait_for(asyncio.gather(first, second), 2)
    assert [call.args[1] for call in joins.await_args_list] == ["first"]
    assert [entry["title"] for entry in session.queues[chat.id]] == ["second"]


@pytest.mark.asyncio
async def test_stop_during_extraction_cannot_restart_playback(session, fake_playback):
    _bot, call = fake_playback
    chat, message = chat_and_message(-1008002)
    await session.activate(chat.id)
    gate = asyncio.Event()

    async def resolve():
        await gate.wait()
        return await extraction()

    lookup = asyncio.create_task(resolve())
    play = asyncio.create_task(tools.join_call(message, "Pending", "https://youtu.be/dQw4w9WgXcQ",
                                             chat, "User", "N/A", "audio", None,
                                             yt_task=lookup, assistant_num=1))
    await asyncio.sleep(0)
    await session.deactivate(chat.id)
    gate.set()
    await asyncio.wait_for(play, 2)
    call.play.assert_not_awaited()
    assert chat.id not in session.active
    assert chat.id not in session.playing


@pytest.mark.asyncio
async def test_stop_cancels_suggestion_fetch_before_countdown(session, fake_playback, monkeypatch):
    _bot, call = fake_playback
    chat, message = chat_and_message(-1008003)
    await session.activate(chat.id)
    gate = asyncio.Event()
    fetching = asyncio.Event()

    async def suggestions(*args, **kwargs):
        fetching.set()
        await gate.wait()
        return [{"video_id": "dQw4w9WgXcQ", "title": "Related", "duration": "1:00"}]

    monkeypatch.setattr(tools, "get_related_suggestions", suggestions)
    joins = AsyncMock()
    monkeypatch.setattr(tools, "join_call", joins)
    last = {"title": "Old", "yt_link": "https://youtu.be/dQw4w9WgXcQ", "message": message,
            "chat": chat, "ui_chat_id": chat.id}
    setup = asyncio.create_task(tools._trigger_suggestions(call, chat.id, last))
    await asyncio.wait_for(fetching.wait(), 1)
    try:
        await session.deactivate(chat.id)
        gate.set()
        await asyncio.wait_for(setup, 1)
        assert chat.id not in session.suggest_tasks
        joins.assert_not_awaited()
    finally:
        session.cancel_suggest(chat.id)
        if not setup.done():
            setup.cancel()
        await asyncio.gather(setup, return_exceptions=True)


@pytest.mark.asyncio
async def test_deactivate_deletes_now_playing_panel(session):
    message = SimpleNamespace(delete=AsyncMock())
    session.set_now_playing(-1008004, message)
    await session.deactivate(-1008004)
    message.delete.assert_awaited_once()
    assert session.get_now_playing(-1008004) is None


@pytest.mark.asyncio
async def test_player_constructor_applies_media_egress_options(monkeypatch):
    options = AsyncMock(return_value={"ffmpeg_parameters": "-http_proxy http://127.0.0.1:1234",
                                      "ytdlp_parameters": "--proxy http://127.0.0.1:1234"})
    monkeypatch.setattr(tools, "media_options", options, raising=False)
    # Construction itself is synchronous; use a plain callable to capture parameters.
    captured = []
    monkeypatch.setattr(tools, "MediaStream", lambda *args, **kwargs: captured.append((args, kwargs)))
    # Keep flags available on the callable, just as the real constructor provides.
    tools.MediaStream.Flags = SimpleNamespace(IGNORE="ignore")
    await tools.make_media_stream("https://media.example/stream", "video", "-ss 00:10")
    options.assert_awaited_once_with("https://media.example/stream", "-ss 00:10")
    assert captured[0][1]["ffmpeg_parameters"].startswith("-http_proxy")
    assert "--proxy" in captured[0][1]["ytdlp_parameters"]


@pytest.mark.asyncio
async def test_queued_search_resolves_only_when_played_with_requested_mode(session, fake_playback, monkeypatch):
    bot, call = fake_playback
    chat, message = chat_and_message(-1008005)
    resolver = AsyncMock(return_value=await extraction())
    monkeypatch.setattr(tools, "handle_youtube", resolver)
    media = AsyncMock(side_effect=lambda source, mode: source)
    monkeypatch.setattr(tools, "make_media_stream", media)
    await playback.put_queue(message, "First", bot, "Artist - First", chat, "User", "1:00", "video", None)
    await playback.put_queue(message, "Second", bot, "Artist - Second", chat, "User", "1:00", "video", None)
    resolver.assert_not_awaited()
    await playback.dend(bot, message)
    resolver.assert_awaited_once_with("Artist - First", mode="video")
    call.play.assert_awaited_once_with(chat.id, "https://media.example/audio")
    assert [entry["yt_link"] for entry in session.queues[chat.id]] == ["Artist - Second"]


@pytest.mark.asyncio
async def test_retry_reconstructs_stream_with_egress_guards(session, fake_playback, monkeypatch):
    _bot, call = fake_playback
    chat, message = chat_and_message(-1008006)
    call.play.side_effect = [TimeoutError("timed out"), None]
    options = AsyncMock(return_value={"ffmpeg_parameters": "-protocol_whitelist http,https,tcp,tls,crypto"})
    monkeypatch.setattr(tools, "media_options", options)
    await tools.join_call(message, "Direct", None, chat, "User", "N/A", "audio", None,
                          stream_url="https://media.example/audio", assistant_num=1)
    assert call.play.await_count == 2
    assert options.await_count == 2
    assert session.playing[chat.id]["stream_url"] == "https://media.example/audio"


@pytest.fixture
def youtube_retry(monkeypatch, tmp_path):
    watch = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    stale = f"https://media.example/stale.mp4?expire={int(time.time()) + 3600}"
    fresh = "https://provider.invalid/stream/resolver/fresh"
    direct = "https://media.example/direct.mp4"
    response = SimpleNamespace(status_code=200, json=lambda: {"stream_url": fresh})
    provider = SimpleNamespace(get=AsyncMock(return_value=response))
    local = AsyncMock(return_value=None)
    ytdlp = AsyncMock(return_value=None)
    monkeypatch.setattr(youtube, "API_TOKEN", "test-resolver-token")
    monkeypatch.setattr(youtube, "BASE_URL", "https://provider.invalid")
    monkeypatch.setattr(youtube, "_api_fail_count", 0)
    monkeypatch.setattr(youtube, "_api_cooldown_until", 0)
    monkeypatch.setattr(youtube, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(youtube, "_MEM_CACHE", {})
    monkeypatch.setattr(youtube, "_STREAM_CACHE", {})
    monkeypatch.setattr(youtube, "get_http_client", lambda: provider)
    monkeypatch.setattr(youtube, "resolve_innertube", local)
    monkeypatch.setattr(youtube, "_run_yt_dlp", ytdlp)
    monkeypatch.setattr(tools, "make_media_stream", AsyncMock(side_effect=lambda source, mode: source))
    for mode in ("audio", "video"):
        youtube._mem_cache_set((mode, watch), stale)
        youtube._write_cache_sync(watch, stale, prefix=f"{mode}_")
    return SimpleNamespace(watch=watch, stale=stale, fresh=fresh, direct=direct,
                           response=response, provider=provider, local=local, ytdlp=ytdlp)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["audio", "video"])
async def test_timeout_refreshes_provider_before_blocked_youtube_fallback(session, fake_playback, youtube_retry, mode):
    _bot, call = fake_playback
    retry = youtube_retry
    chat, message = chat_and_message(-1008020)
    call.play.side_effect = [TimeoutError(), None]

    await tools.join_call(message, "Song", retry.watch, chat, "User", "1:00", mode, None,
                          stream_url=retry.stale, assistant_num=1)

    assert [attempt.args[1] for attempt in call.play.await_args_list] == [retry.stale, retry.fresh]
    assert session.playing[chat.id]["stream_url"] == retry.fresh
    retry.provider.get.assert_awaited_once()
    assert retry.provider.get.call_args.kwargs["params"] == {"q": retry.watch}
    retry.local.assert_not_awaited()
    retry.ytdlp.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["audio", "video"])
async def test_timeout_keeps_direct_fallback_after_fresh_provider_stream_fails(session, fake_playback, youtube_retry, mode):
    _bot, call = fake_playback
    retry = youtube_retry
    chat, message = chat_and_message(-1008021)
    call.play.side_effect = [TimeoutError(), TimeoutError(), None]
    retry.local.return_value = {"stream_url": retry.direct}

    await tools.join_call(message, "Song", retry.watch, chat, "User", "1:00", mode, None,
                          stream_url=retry.stale, assistant_num=1)

    assert [attempt.args[1] for attempt in call.play.await_args_list] == [retry.stale, retry.fresh, retry.direct]
    assert session.playing[chat.id]["stream_url"] == retry.direct
    retry.provider.get.assert_awaited_once()
    retry.local.assert_awaited_once_with(retry.watch, mode=mode)


@pytest.mark.asyncio
async def test_exhausted_stream_retries_clear_playback_once(session, fake_playback, youtube_retry):
    _bot, call = fake_playback
    retry = youtube_retry
    chat, message = chat_and_message(-1008022)
    call.play.side_effect = TimeoutError()
    await session.activate(chat.id)

    await tools.join_call(message, "Song", retry.watch, chat, "User", "1:00", "audio", None,
                          stream_url=retry.stale, assistant_num=1)

    assert [attempt.args[1] for attempt in call.play.await_args_list] == [retry.stale, retry.fresh]
    assert chat.id not in session.active
    assert chat.id not in session.playing
    retry.provider.get.assert_awaited_once()
    retry.ytdlp.assert_awaited_once()
    tools.rich_send.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("direct_available", [True, False])
async def test_provider_outage_uses_direct_resolution_once(session, fake_playback, youtube_retry, direct_available):
    _bot, call = fake_playback
    retry = youtube_retry
    chat, message = chat_and_message(-1008024)
    retry.response.status_code = 503
    retry.local.return_value = {"stream_url": retry.direct} if direct_available else None
    call.play.side_effect = [TimeoutError(), None]

    await tools.join_call(message, "Song", retry.watch, chat, "User", "1:00", "audio", None,
                          stream_url=retry.stale, assistant_num=1)

    retry.provider.get.assert_awaited_once()
    retry.local.assert_awaited_once_with(retry.watch, mode="audio")
    if direct_available:
        assert session.playing[chat.id]["stream_url"] == retry.direct
        retry.ytdlp.assert_not_awaited()
    else:
        call.play.assert_awaited_once_with(chat.id, retry.stale)
        retry.ytdlp.assert_awaited_once()
        assert chat.id not in session.active


@pytest.mark.asyncio
async def test_stop_during_provider_refresh_does_not_play_or_start_fallback(session, fake_playback, youtube_retry):
    _bot, call = fake_playback
    retry = youtube_retry
    chat, message = chat_and_message(-1008023)
    call.play.side_effect = TimeoutError()
    refreshing = asyncio.Event()
    release = asyncio.Event()

    async def resolve(*args, **kwargs):
        refreshing.set()
        await release.wait()
        return retry.response

    retry.provider.get.side_effect = resolve
    task = asyncio.create_task(tools.join_call(message, "Song", retry.watch, chat, "User", "1:00", "audio", None,
                                               stream_url=retry.stale, assistant_num=1))
    try:
        await asyncio.wait_for(refreshing.wait(), 1)
        await session.deactivate(chat.id)
        release.set()
        await asyncio.wait_for(task, 1)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    call.play.assert_awaited_once_with(chat.id, retry.stale)
    retry.local.assert_not_awaited()
    retry.ytdlp.assert_not_awaited()
    assert chat.id not in session.active
    assert chat.id not in session.playing


@pytest.mark.asyncio
async def test_obsolete_join_failure_cannot_clear_newer_session(session, fake_playback, monkeypatch):
    _bot, call = fake_playback
    chat, message = chat_and_message(-1008007)
    gate = asyncio.Event()
    resolving = asyncio.Event()

    async def old_resolution():
        resolving.set()
        await gate.wait()
        raise ValueError("old request failed")

    lookup = asyncio.create_task(old_resolution())
    old = asyncio.create_task(tools.join_call(message, "Old", "https://youtu.be/dQw4w9WgXcQ",
                                            chat, "User", "N/A", "audio", None,
                                            yt_task=lookup, assistant_num=1))
    await resolving.wait()
    generation = session.invalidate(chat.id)
    monkeypatch.setattr(tools, "make_media_stream", AsyncMock(side_effect=lambda source, mode: source))
    await tools.join_call(message, "New", None, chat, "User", "1:00", "audio", None,
                          stream_url="https://media.example/new", assistant_num=1, generation=generation)
    gate.set()
    await asyncio.wait_for(old, 2)
    call.play.assert_awaited_once_with(chat.id, "https://media.example/new")
    assert session.playing[chat.id]["title"] == "New"
    assert chat.id in session.active


@pytest.mark.asyncio
async def test_stale_deactivate_preserves_current_panel_and_queue(session):
    chat_id = -1008008
    old_generation = session.generation(chat_id)
    generation = session.invalidate(chat_id)
    await session.activate(chat_id, generation=generation)
    panel = SimpleNamespace(delete=AsyncMock())
    session.set_now_playing(chat_id, panel)
    session.queues[chat_id] = [{"title": "New queued track"}]
    assert await session.deactivate(chat_id, generation=old_generation) is False
    assert chat_id in session.active
    assert session.get_now_playing(chat_id) is panel
    assert session.queues[chat_id]
    panel.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_old_teardown_does_not_delete_media_after_new_play_reserves_chat(session, fake_playback, monkeypatch, tmp_path):
    _bot, _call = fake_playback
    chat_id = -1008009
    await session.activate(chat_id)
    media_dir = tmp_path / "user_999" / str(chat_id)
    media_dir.mkdir(parents=True)
    media = media_dir / "new-track.mp3"
    media.write_bytes(b"new playback media")
    monkeypatch.setattr(tools, "ggg", str(tmp_path))
    db_calls = []

    def schedule(coroutine):
        db_calls.append(coroutine)
        coroutine.close()

    monkeypatch.setattr(tools, "db_task", schedule)

    async def deleting_panel():
        # Telegram deletion yields long enough for a new /play to reserve the
        # same chat; a cold start retains the generation after the old stop.
        await session.activate(chat_id)

    session.set_now_playing(chat_id, SimpleNamespace(delete=deleting_panel))
    assert await tools.remove_active_chat(chat_id)
    assert chat_id in session.active
    assert media.read_bytes() == b"new playback media"
    assert not db_calls


@pytest.mark.asyncio
async def test_queue_insertion_waiting_for_lock_cannot_append_after_invalidation(session, fake_playback):
    bot, _call = fake_playback
    chat, message = chat_and_message(-1008010)
    lock = session.lock(chat.id)
    await lock.acquire()
    pending = asyncio.create_task(playback.put_queue(
        message, "Obsolete", bot, "Artist - Obsolete", chat, "User", "1:00", "audio", None))
    await asyncio.sleep(0)
    session.invalidate(chat.id)
    current = {"title": "Current queue"}
    session.queues[chat.id] = [current]
    lock.release()
    _track_id, entry = await asyncio.wait_for(pending, 1)
    assert entry is None
    assert session.queues[chat.id] == [current]


@pytest.mark.asyncio
async def test_obsolete_stream_end_waiting_for_lock_preserves_new_queue(session, fake_playback, monkeypatch):
    _bot, call = fake_playback
    chat, _message = chat_and_message(-1008011)
    await session.activate(chat.id)
    lock = session.lock(chat.id)
    await lock.acquire()
    joins = AsyncMock()
    monkeypatch.setattr(tools, "join_call", joins)
    pending = asyncio.create_task(tools.end(call, SimpleNamespace(chat_id=chat.id)))
    await asyncio.sleep(0)
    session.invalidate(chat.id)
    current = {"title": "Current playing"}
    queued = {"title": "Keep queued"}
    session.playing[chat.id] = current
    session.queues[chat.id] = [queued]
    lock.release()
    await asyncio.wait_for(pending, 1)
    assert session.playing[chat.id] is current
    assert session.queues[chat.id] == [queued]
    joins.assert_not_awaited()


@pytest.mark.asyncio
async def test_obsolete_autoleave_waiting_for_playback_lock_preserves_new_state(session, fake_playback, monkeypatch):
    _bot, call = fake_playback
    chat, _message = chat_and_message(-1008012)
    await session.activate(chat.id)
    monkeypatch.setattr(tools, "count_listeners", AsyncMock(return_value=0))
    lock = session.playback_lock(chat.id)
    await lock.acquire()
    pending = asyncio.create_task(tools.autoleave_vc(chat.id))
    await asyncio.sleep(0)
    session.invalidate(chat.id)
    current = {"title": "New playing"}
    queued = {"title": "New queue"}
    session.playing[chat.id] = current
    session.queues[chat.id] = [queued]
    lock.release()
    assert await asyncio.wait_for(pending, 1) is False
    assert session.playing[chat.id] is current
    assert session.queues[chat.id] == [queued]
    assert chat.id in session.active
    call.leave_call.assert_not_awaited()
