import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import is_dataclass

from utils.button import Buttons
from tools import QueueEntry, _trigger_suggestions, join_call
from state import state
from plugins.controls import _resolve_ctrl_chat_id
from pyrogram.types import CallbackQuery


def test_suggestion_markup_prefixes():
    # Group mode
    kb_group = Buttons.suggestion_markup(autoplay_enabled=True, channel_mode=False)
    assert kb_group.inline_keyboard[0][0].callback_data == "sgstop"
    assert kb_group.inline_keyboard[0][1].callback_data == "sgtoggle"

    # Channel mode
    kb_chan = Buttons.suggestion_markup(autoplay_enabled=True, channel_mode=True)
    assert kb_chan.inline_keyboard[0][0].callback_data == "csgstop"
    assert kb_chan.inline_keyboard[0][1].callback_data == "csgtoggle"


def test_queue_entry_has_ui_chat_id():
    assert is_dataclass(QueueEntry)
    entry = QueueEntry(
        message=None,
        title="Test Track",
        duration="3:45",
        mode="audio",
        yt_link="https://youtube.com/watch?v=12345678901",
        chat=MagicMock(id=-100200),
        by="User",
        session=None,
        thumb=None,
        ui_chat_id=-100100,
    )
    assert entry.ui_chat_id == -100100
    assert entry["ui_chat_id"] == -100100
    assert entry.get("ui_chat_id") == -100100


@pytest.mark.asyncio
async def test_resolve_ctrl_chat_id_channel_and_fallback():
    client = MagicMock()
    # Mock get_chat
    mock_linked = MagicMock(id=-1002896180369)
    mock_chat_full = MagicMock(linked_chat=mock_linked)
    client.get_chat = AsyncMock(return_value=mock_chat_full)

    # Explicit channel callback
    query_c = MagicMock(spec=CallbackQuery)
    query_c.message = MagicMock(chat=MagicMock(id=-1001111111111))
    resolved = await _resolve_ctrl_chat_id(client, query_c, is_channel=True)
    assert resolved == -1002896180369

    # Group callback but channel is active in state while group is not
    query_g = MagicMock(spec=CallbackQuery)
    query_g.message = MagicMock(chat=MagicMock(id=-1001111111111))
    state.active.add(-1002896180369)
    try:
        resolved_auto = await _resolve_ctrl_chat_id(client, query_g, is_channel=False)
        assert resolved_auto == -1002896180369
    finally:
        state.active.discard(-1002896180369)


@pytest.mark.asyncio
async def test_trigger_suggestions_sends_to_ui_chat_id():
    channel_id = -1002896180369
    group_id = -1001111111111

    last_msg = MagicMock()
    last_msg.chat.id = group_id
    last_song = {
        "yt_link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Never Gonna Give You Up",
        "chat": MagicMock(id=channel_id),
        "message": last_msg,
        "ui_chat_id": group_id,
    }

    mock_client = MagicMock()
    mock_bot = MagicMock()

    sent_blocks_chat_id = []

    async def fake_rich_send_blocks(bot, target_chat_id, blocks, **kwargs):
        sent_blocks_chat_id.append(target_chat_id)
        mock_msg = MagicMock()
        mock_msg.chat.id = target_chat_id
        return mock_msg

    with patch("tools.get_related_suggestions", new=AsyncMock(return_value=[{
        "video_id": "test1234567",
        "title": "Suggested Song",
        "artist": "Artist",
        "duration": "3:00",
    }])):
        with patch("tools.clients", {"bot": mock_bot}):
            with patch("tools.rich_send_blocks", side_effect=fake_rich_send_blocks):
                with patch("asyncio.sleep", new=AsyncMock()):
                    # Disable countdown auto-exec to test only the card send
                    state.set_autoplay(channel_id, False)
                    await _trigger_suggestions(mock_client, channel_id, last_song)

    # Must send to the group chat ID, NOT the channel ID where the bot is not a member!
    assert sent_blocks_chat_id == [group_id]


@pytest.mark.asyncio
async def test_trigger_suggestions_table_has_no_artist_column():
    channel_id = -1002896180369
    group_id = -1001111111111

    last_msg = MagicMock()
    last_msg.chat.id = group_id
    last_song = {
        "yt_link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Never Gonna Give You Up",
        "chat": MagicMock(id=channel_id),
        "message": last_msg,
        "ui_chat_id": group_id,
    }

    mock_client = MagicMock()
    mock_bot = MagicMock()

    captured_blocks = []

    async def fake_rich_send_blocks(bot, target_chat_id, blocks, **kwargs):
        captured_blocks.extend(blocks)
        mock_msg = MagicMock()
        mock_msg.chat.id = target_chat_id
        return mock_msg

    with patch("tools.get_related_suggestions", new=AsyncMock(return_value=[{
        "video_id": "test1234567",
        "title": "Suggested Song",
        "artist": "Should Not Be A Column",
        "duration": "3:00",
    }])):
        with patch("tools.clients", {"bot": mock_bot}):
            with patch("tools.rich_send_blocks", side_effect=fake_rich_send_blocks):
                with patch("asyncio.sleep", new=AsyncMock()):
                    state.set_autoplay(channel_id, False)
                    await _trigger_suggestions(mock_client, channel_id, last_song)

    table_block = next(b for b in captured_blocks if b.get("type") == "table")
    headers = [cell["text"] for cell in table_block["cells"][0]]
    assert headers == ["#", "ᴛɪᴛʟᴇ", "ʟᴇɴɢᴛʜ"]
    assert "ᴀʀᴛɪsᴛ" not in headers
    # Row cells check (3 columns: number, title button, length)
    row = table_block["cells"][1]
    assert len(row) == 3

    # Also test fallback path when rich_send_blocks returns None
    captured_text = []

    async def fake_rich_send(bot, target_chat_id, text, **kwargs):
        captured_text.append(text)
        mock_msg = MagicMock()
        mock_msg.chat.id = target_chat_id
        return mock_msg

    with patch("tools.get_related_suggestions", new=AsyncMock(return_value=[{
        "video_id": "test1234567",
        "title": "Suggested Song",
        "artist": "Should Not Be A Column",
        "duration": "3:00",
    }])):
        with patch("tools.clients", {"bot": mock_bot}):
            with patch("tools.rich_send_blocks", return_value=None):
                with patch("tools.rich_send", side_effect=fake_rich_send):
                    with patch("asyncio.sleep", new=AsyncMock()):
                        state.set_autoplay(channel_id, False)
                        await _trigger_suggestions(mock_client, channel_id, last_song)

    assert len(captured_text) == 1
    assert "ᴀʀᴛɪsᴛ" not in captured_text[0]
    assert "Should Not Be A Column" not in captured_text[0]

