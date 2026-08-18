"""
tests/test_messages_and_buttons.py — Unit tests for centralized message catalog, suggestion formatting, and playback buttons.
"""

from utils.button import Buttons
from utils.message import Messages
from pyrogram.enums import ButtonStyle
from utils.emoji import Emoji


def test_playback_markup():
    markup = Buttons.playback_markup()
    assert len(markup.inline_keyboard) == 2
    row0 = markup.inline_keyboard[0]
    row1 = markup.inline_keyboard[1]

    assert len(row0) == 4
    # Resume, Pause, Skip, End
    assert row0[0].callback_data == "resume"
    assert row0[1].callback_data == "pause"
    assert row0[2].callback_data == "skip"
    assert row0[3].callback_data == "end"

    # Close button
    assert len(row1) == 1
    assert row1[0].callback_data == "close"


def test_playback_markup_channel_mode():
    markup = Buttons.playback_markup(channel_mode=True)
    row0 = markup.inline_keyboard[0]
    assert row0[0].callback_data == "cresume"
    assert row0[1].callback_data == "cpause"
    assert row0[2].callback_data == "cskip"
    assert row0[3].callback_data == "cend"


def test_suggestion_markup():
    suggestions = [
        {"video_id": "vid1", "title": "Track 1", "duration": "3:20"},
        {"video_id": "vid2", "title": "Track 2", "duration": "4:10"},
    ]
    markup = Buttons.suggestion_markup(suggestions, autoplay_enabled=True)
    assert len(markup.inline_keyboard) == 2

    # Play row
    play_row = markup.inline_keyboard[0]
    assert len(play_row) == 2
    assert play_row[0].callback_data == "sgplay_vid1"
    assert play_row[1].callback_data == "sgplay_vid2"

    # Control row
    control_row = markup.inline_keyboard[1]
    assert len(control_row) == 2
    assert control_row[0].callback_data == "sgstop"
    assert control_row[1].callback_data == "sgtoggle"
    assert "ON" in control_row[1].text


def test_suggestion_card_layout_positions_items_at_bottom():
    seed = "Last Played Track"
    items = "1️⃣ <b>Song A</b> <code>[3:30]</code>\n2️⃣ <b>Song B</b> <code>[4:00]</code>"
    countdown = 5

    card_text = Messages.SUGGESTION_CARD.format(seed, items, countdown)
    # The formatted suggestion items {1} must appear at the bottom directly above buttons
    assert card_text.endswith(items)
    assert seed in card_text
    assert f"{countdown}" in card_text


def test_suggestion_card_no_autoplay_layout_positions_items_at_bottom():
    seed = "Last Played Track"
    items = "1️⃣ <b>Song A</b> <code>[3:30]</code>\n2️⃣ <b>Song B</b> <code>[4:00]</code>"

    card_text = Messages.SUGGESTION_CARD_NO_AUTOPLAY.format(seed, items)
    assert card_text.endswith(items)
    assert seed in card_text


def test_messages_catalog_formats():
    assert "sᴇᴇᴋᴇᴅ ᴛᴏ 03:20" in Messages.SEEKED.format("03:20", "@user")
    assert "ǫᴜᴇᴜᴇ ᴄʟᴇᴀʀᴇᴅ" in Messages.QUEUE_CLEARED_STOPPED.format("@user")
    assert "ʀᴇᴘᴇᴀᴛᴇᴅ 5 ᴛɪᴍᴇs" in Messages.SONG_LOOPED.format(5, "@user")
    assert "ʀᴇsᴜᴍᴇᴅ" in Messages.SONG_RESUMED_NOTICE.format("@user")
    assert "ᴘᴀᴜsᴇᴅ" in Messages.SONG_PAUSED_NOTICE.format("@user")
