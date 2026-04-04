"""
utils/button.py — Inline keyboard definitions for NUB Music Bot.

Button label styling inspired by:
  • TheTeamAlexa/AlexaMusic → Unicode small-caps labels
  • AnonymousX1025/AnonXMusic → clean playback symbol buttons (▷ II ‣‣I ▢)
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ButtonStyle
from utils.emoji import Emoji


class Buttons:
    # ─── Help Menu Category Selector ───────────────────────────────────────
    HELP_HOME = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 ᴘʟᴀʏʙᴀᴄᴋ",    callback_data="commands_playback", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.MUSIC_NOTE),
            InlineKeyboardButton("🔐 ᴀᴜᴛʜ",          callback_data="commands_auth",     style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.AUTH_ICON),
        ],
        [
            InlineKeyboardButton("🚫 ʙʟᴏᴄᴋʟɪsᴛ",    callback_data="commands_blocklist", style=ButtonStyle.DANGER,   icon_custom_emoji_id=Emoji.BLOCKLIST_ICON),
            InlineKeyboardButton("🔑 sᴜᴅᴏ",           callback_data="commands_sudo",      style=ButtonStyle.PRIMARY,  icon_custom_emoji_id=Emoji.KEY),
        ],
        [
            InlineKeyboardButton("📢 ʙʀᴏᴀᴅᴄᴀsᴛ",    callback_data="commands_broadcast", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.BROADCAST),
            InlineKeyboardButton("🛠️ ᴛᴏᴏʟs",         callback_data="commands_tools",     style=ButtonStyle.DEFAULT,  icon_custom_emoji_id=Emoji.TOOLS),
        ],
        [
            InlineKeyboardButton("🎨 ᴋᴀɴɢ/ᴍᴇᴍᴇ",   callback_data="commands_kang",   style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.KANG),
            InlineKeyboardButton("📊 sᴛᴀᴛᴜs",        callback_data="commands_status", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.STATS),
        ],
        [
            InlineKeyboardButton("⚙️ ᴏᴡɴᴇʀ",        callback_data="commands_owner", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.SETTINGS),
            InlineKeyboardButton("🌐 ʀᴇᴘᴏ",          url="https://github.com/nub-coders/nub-music-bot", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.REPO),
        ],
        [InlineKeyboardButton("🏠 ʜᴏᴍᴇ",             callback_data="commands_back", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.HOME)],
    ])

    # ─── Back and Close ─────────────────────────────────────────────────────
    BACK  = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ʙᴀᴄᴋ",  callback_data="commands_all", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK)]])
    CLOSE = InlineKeyboardMarkup([[InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close",        style=ButtonStyle.DANGER,  icon_custom_emoji_id=Emoji.CLOSE)]])

    @staticmethod
    def auth_confirm_markup(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ᴄᴏɴꜰɪʀᴍ ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ", callback_data=f"auth_confirm_{user_id}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.SUCCESS)],
            [InlineKeyboardButton("✖ ᴄᴀɴᴄᴇʟ",                  callback_data="close",                   style=ButtonStyle.DANGER,  icon_custom_emoji_id=Emoji.CLOSE)],
        ])

    @staticmethod
    def start_markup(bot_username, ow_id, OWNER_ID, GROUP):
        """Generates the markup for the /start command."""
        buttons = [
            [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{bot_username}?startgroup=true", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ADD)],
            [InlineKeyboardButton("ℹ️ ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs",  callback_data="commands_all",                      style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.HELP)],
            [
                InlineKeyboardButton(
                    "👑 ᴄʀᴇᴀᴛᴏʀ",
                    user_id=OWNER_ID,
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.CROWN,
                ) if ow_id else InlineKeyboardButton(
                    "👑 ᴄʀᴇᴀᴛᴏʀ",
                    url="https://t.me/NubDockerbot",
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.CROWN,
                ),
                InlineKeyboardButton("💬 sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", url=f"https://t.me/{GROUP}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CHAT),
            ],
        ]
        return InlineKeyboardMarkup(buttons)

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
    def force_play_markup(youtube_url):
        """Generates the markup for the force play results."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 sᴛʀᴇᴀᴍ ᴏɴ ʏᴏᴜᴛᴜʙᴇ", url=youtube_url, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ROCKET),
        ]])

    @staticmethod
    def refresh_power_markup(chat_id):
        """Refresh bot power status mockup."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 ʀᴇꜰʀᴇsʜ", callback_data=f"refresh_power_{chat_id}", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.REFRESH),
        ]])

    @staticmethod
    def broadcast_markup():
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 ʙʀᴏᴀᴅᴄᴀsᴛ 🚀", callback_data="broadcast", icon_custom_emoji_id=Emoji.BROADCAST),
        ]])
