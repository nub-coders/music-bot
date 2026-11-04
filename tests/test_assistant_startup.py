"""Assistant startup must exclude bot sessions before starting voice calls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pyrogram.types import User

import main as app
import media_guard
import thumbnails
import youtube


@pytest.fixture
def startup(monkeypatch):
    bot = SimpleNamespace(
        me=User(id=999, first_name="Music bot", is_bot=True),
        start=AsyncMock(),
    )
    clients_by_name = {"bot": bot}
    calls_by_name = {}
    sessions = {}
    voice_calls = {}

    def configure(*bot_flags):
        for idx, is_bot in enumerate(bot_flags, start=1):
            name = f"assistant_{idx}"
            client = SimpleNamespace(
                name=name,
                me=User(id=idx, first_name=f"Assistant {idx}", is_bot=is_bot),
                start=AsyncMock(),
                stop=AsyncMock(),
            )
            call = SimpleNamespace(start=AsyncMock(), add_handler=Mock())
            clients_by_name[name] = sessions[idx] = client
            calls_by_name[name] = voice_calls[idx] = call
        monkeypatch.setattr(app, "STRING_SESSIONS", [f"session-{idx}" for idx in sessions])

    monkeypatch.setattr(app, "Client", lambda name, **kwargs: clients_by_name[name])
    monkeypatch.setattr(app, "PyTgCalls", lambda client: calls_by_name[client.name])
    for name in ("assistants", "calls", "assistant_info", "clients", "AUTH"):
        monkeypatch.setattr(app, name, {})
    for name in ("SUDO", "BLOCK", "ADMIN", "INITIAL_ADMIN_IDS"):
        monkeypatch.setattr(app, name, [])
    monkeypatch.setattr(app, "STRING_SESSION", "")
    monkeypatch.setattr(app, "AUTO_LEAVING_ASSISTANT", True)
    monkeypatch.setattr(app, "log_ytdlp_version", Mock())
    for name in (
        "export_browser_cookies", "ensure_indexes", "setup_premium_emoji",
        "_cache_cleanup_loop", "refresh_cookies_loop", "_assistant_autoleave_loop",
    ):
        monkeypatch.setattr(app, name, AsyncMock())
    monkeypatch.setattr(app, "get_all_last_played", AsyncMock(return_value={}))
    for name in ("async_user_sessions", "async_collection"):
        monkeypatch.setattr(app, name, SimpleNamespace(
            find_one=AsyncMock(return_value={}), update_one=AsyncMock(),
        ))
    monkeypatch.setattr(app, "db_task", lambda coroutine: coroutine.close())

    async def idle():
        # Let the mocked background tasks finish before main returns.
        await asyncio.sleep(0)

    monkeypatch.setattr(app, "idle", AsyncMock(side_effect=idle))
    monkeypatch.setattr(thumbnails, "close_session", AsyncMock())
    monkeypatch.setattr(youtube, "close_http_client", AsyncMock())
    monkeypatch.setattr(media_guard, "close_media_proxy", AsyncMock())
    return SimpleNamespace(
        configure=configure, bot=bot, sessions=sessions, voice_calls=voice_calls,
    )


@pytest.mark.parametrize("rejected_idx", [1, 2])
async def test_bot_session_is_rejected_while_user_assistant_starts(
    startup, caplog, rejected_idx,
):
    startup.configure(rejected_idx == 1, rejected_idx == 2)

    await app.main()

    accepted_idx = 3 - rejected_idx
    rejected = startup.sessions[rejected_idx]
    accepted = startup.sessions[accepted_idx]
    rejected.start.assert_awaited_once()
    rejected.stop.assert_awaited_once()
    startup.voice_calls[rejected_idx].start.assert_not_awaited()
    accepted.start.assert_awaited_once()
    accepted.stop.assert_not_awaited()
    startup.voice_calls[accepted_idx].start.assert_awaited_once()
    assert app.assistants == {accepted_idx: accepted}
    assert app.calls == {accepted_idx: startup.voice_calls[accepted_idx]}
    assert set(app.assistant_info) == {accepted_idx}
    assert app.clients["session"] is accepted
    assert app.clients["assistants"] == {accepted_idx: accepted}
    startup.bot.start.assert_awaited_once()
    app._assistant_autoleave_loop.assert_awaited_once()
    assert f"Assistant {rejected_idx}" in caplog.text
    assert "bot account" in caplog.text
    assert "STRING_SESSION" in caplog.text
    assert "phone number" in caplog.text


async def test_only_bot_sessions_prevent_app_startup(startup, caplog):
    startup.configure(True)

    await app.main()

    startup.sessions[1].stop.assert_awaited_once()
    startup.voice_calls[1].start.assert_not_awaited()
    assert not app.assistants
    assert not app.calls
    assert not app.assistant_info
    startup.bot.start.assert_not_awaited()
    app._assistant_autoleave_loop.assert_not_called()
    assert "bot account" in caplog.text
    assert "No valid assistant sessions" in caplog.text


async def test_rejected_bot_is_excluded_even_if_disconnect_fails(startup, caplog):
    startup.configure(False, True)
    startup.sessions[2].stop.side_effect = RuntimeError("Disconnect failed")

    await app.main()

    startup.sessions[2].stop.assert_awaited_once()
    startup.voice_calls[2].start.assert_not_awaited()
    assert app.assistants == {1: startup.sessions[1]}
    assert set(app.calls) == {1}
    assert set(app.assistant_info) == {1}
    startup.bot.start.assert_awaited_once()
    assert "bot account" in caplog.text
