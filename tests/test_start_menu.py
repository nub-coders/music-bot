from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyrogram.errors import ChatWriteForbidden, MessageNotModified

from plugins import start


@pytest.fixture
def menu(monkeypatch):
    monkeypatch.setattr(start, "OWNER_ID", 0)
    monkeypatch.setattr(start, "SUDO", [])
    monkeypatch.setattr(start, "is_bot_owner", lambda user_id: False)
    monkeypatch.setattr(start, "get_admin_ids", lambda path: [])
    monkeypatch.setattr(start, "gvarstatus", AsyncMock(return_value=None))
    monkeypatch.setattr(start, "format_welcome_message", AsyncMock(return_value="Welcome"))
    client = SimpleNamespace(me=SimpleNamespace(id=999, username="testbot"))
    callback = SimpleNamespace(
        data="commands_help",
        from_user=SimpleNamespace(id=123, mention=lambda: "User"),
        answer=AsyncMock(),
        message=SimpleNamespace(edit_caption=AsyncMock()),
    )
    return client, callback


@pytest.mark.asyncio
@pytest.mark.parametrize("page", ["help", "all", "playback", "tools", "home", "back"])
async def test_repeated_menu_click_is_acknowledged_without_error(menu, page):
    client, callback = menu
    callback.data = f"commands_{page}"
    callback.message.edit_caption.side_effect = MessageNotModified()

    await start.commands_callback(client, callback)

    callback.answer.assert_awaited_once_with()
    callback.message.edit_caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_other_menu_edit_errors_are_not_hidden(menu):
    client, callback = menu
    callback.message.edit_caption.side_effect = ChatWriteForbidden()

    with pytest.raises(ChatWriteForbidden):
        await start.commands_callback(client, callback)

    callback.answer.assert_awaited_once_with()
