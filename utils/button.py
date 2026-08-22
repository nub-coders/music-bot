"""
utils/button.py — Inline keyboard definitions for NUB Music Bot.
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ButtonStyle
from utils.emoji import Emoji


class Buttons:
    # ─── Help Menu Category Selector ───────────────────────────────────────
    @staticmethod
    def help_markup(is_admin: bool = False, is_owner: bool = False, is_sudo: bool = False) -> InlineKeyboardMarkup:
        """Generates minimized help category buttons with merged dropdowns."""
        rows = [
            [
                InlineKeyboardButton("🎵 ᴘʟᴀʏʙᴀᴄᴋ",    callback_data="commands_playback", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.MUSIC_NOTE),
                InlineKeyboardButton("🛠️ ᴛᴏᴏʟs & ɪɴꜰᴏ", callback_data="commands_tools",    style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.TOOLS),
            ],
        ]

        if is_admin or is_sudo or is_owner:
            rows.append([
                InlineKeyboardButton("🔐 ᴀᴅᴍɪɴ & sᴜᴅᴏ", callback_data="commands_admin", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.KEY),
            ])

        rows.append([
            InlineKeyboardButton("📋 ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs (ᴅʀᴏᴘᴅᴏᴡɴs)", callback_data="commands_all_dropdown", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.HELP),
        ])
        rows.append([
            InlineKeyboardButton("🏠 ʜᴏᴍᴇ", callback_data="commands_home", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.HOME)
        ])
        return InlineKeyboardMarkup(rows)

    HELP_HOME = help_markup(is_admin=True, is_owner=True, is_sudo=True)

    # ─── Back ───────────────────────────────────────────────────────────────
    BACK  = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ʙᴀᴄᴋ",  callback_data="commands_all", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK)]])

    @staticmethod
    def start_markup(bot_username, ow_id, OWNER_ID, GROUP):
        """Generates the markup for the /start command.

        When no owner is configured (OWNER_ID falsy) the creator button is left
        out entirely rather than pointing at an unrelated hardcoded account.
        """
        creator_row = []
        if OWNER_ID:
            creator_row.append(
                InlineKeyboardButton(
                    "👑 ᴄʀᴇᴀᴛᴏʀ",
                    user_id=OWNER_ID,
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.CROWN,
                )
            )
        creator_row.append(
            InlineKeyboardButton("💬 sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", url=f"https://t.me/{GROUP}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CHAT),
        )

        buttons = [
            [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{bot_username}?startgroup=true", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ADD)],
            [InlineKeyboardButton("ℹ️ ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs",  callback_data="commands_all",                      style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.HELP)],
            creator_row,
            [
                InlineKeyboardButton("🌐 ʀᴇᴘᴏ", url="https://github.com/nub-coders/nub-music-bot", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.REPO),
            ],
        ]
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def group_welcome_markup(bot_username: str, GROUP: str) -> InlineKeyboardMarkup:
        """Generates the markup shown when the bot is added to a group."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📖 ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs",
                url=f"https://t.me/{bot_username}?start=help",
                style=ButtonStyle.PRIMARY,
                icon_custom_emoji_id=Emoji.HELP,
            )],
            [
                InlineKeyboardButton(
                    "➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.ADD,
                ),
                InlineKeyboardButton(
                    "💬 sᴜᴘᴘᴏʀᴛ",
                    url=f"https://t.me/{GROUP}",
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.CHAT,
                ),
            ],
        ])

    @staticmethod
    def playback_markup(channel_mode=False):
        """Generates the markup for playback controls (AnonXMusic-style symbols)."""
        prefix = 'c' if channel_mode else ''
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▷",    callback_data=f"{prefix}resume", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.RESUME),
                InlineKeyboardButton("II",   callback_data=f"{prefix}pause",  style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.PAUSE),
                InlineKeyboardButton("‣‣I",  callback_data=f"{prefix}skip",   style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.SKIP),
                InlineKeyboardButton("▢",    callback_data=f"{prefix}end",    style=ButtonStyle.DANGER,  icon_custom_emoji_id=Emoji.STOP),
            ],
            [
                InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE),
            ],
        ])

    @staticmethod
    def queue_markup(track_id, channel_mode=False):
        """Playback controls plus a Play Now jump for this freshly queued track."""
        prefix = 'c' if channel_mode else ''
        rows = list(Buttons.playback_markup(channel_mode).inline_keyboard)
        rows.insert(1, [
            InlineKeyboardButton("‣ ᴘʟᴀʏ ɴᴏᴡ", callback_data=f"{prefix}playnow_{track_id}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.PLAY),
        ])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def force_play_markup(youtube_url):
        """Generates the markup for the force play results."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 sᴛʀᴇᴀᴍ ᴏɴ ʏᴏᴜᴛᴜʙᴇ", url=youtube_url, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ROCKET),
        ]])

    @staticmethod
    def suggestion_markup(suggestions: list, autoplay_enabled: bool = True):
        """Generates the markup for related video suggestions card."""
        play_row = []
        for i, item in enumerate(suggestions[:5], 1):
            vid = item.get("video_id")
            if vid:
                play_row.append(
                    InlineKeyboardButton(
                        f"▶️ {i}",
                        callback_data=f"sgplay_{vid}",
                        style=ButtonStyle.PRIMARY,
                        icon_custom_emoji_id=Emoji.PLAY,
                    )
                )

        autoplay_text = "🔄 ᴀᴜᴛᴏᴘʟᴀʏ: ON" if autoplay_enabled else "⏸ ᴀᴜᴛᴏᴘʟᴀʏ: OFF"
        control_row = [
            InlineKeyboardButton("⏹ sᴛᴏᴘ", callback_data="sgstop", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.STOP),
            InlineKeyboardButton(autoplay_text, callback_data="sgtoggle", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.SETTINGS),
        ]
        rows = []
        if play_row:
            rows.append(play_row)
        rows.append(control_row)
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def autoleave_markup():
        """Generates the markup for the auto-leave voice chat message."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🤖 ᴏᴜʀ ʙᴏᴛs",
                    url="https://t.me/+FbIuEWrOYlEwYzM1",
                    style=ButtonStyle.PRIMARY,
                    icon_custom_emoji_id=Emoji.USER,
                )
            ]
        ])

