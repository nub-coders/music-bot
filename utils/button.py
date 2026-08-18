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
        """Generates category buttons tailored to the viewer's permission status."""
        rows = [
            [
                InlineKeyboardButton("🎵 ᴘʟᴀʏʙᴀᴄᴋ",    callback_data="commands_playback", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.MUSIC_NOTE),
                InlineKeyboardButton("🎨 ᴋᴀɴɢ/ᴍᴇᴍᴇ",   callback_data="commands_kang",     style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.KANG),
            ],
            [
                InlineKeyboardButton("🛠️ ᴛᴏᴏʟs",         callback_data="commands_tools",    style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.TOOLS),
                InlineKeyboardButton("📊 sᴛᴀᴛᴜs",        callback_data="commands_status",   style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.STATS),
            ],
        ]

        if is_admin or is_sudo or is_owner:
            rows.append([
                InlineKeyboardButton("🔐 ᴀᴜᴛʜ",          callback_data="commands_auth",     style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.AUTH_ICON),
            ])

        if is_sudo or is_owner:
            rows.append([
                InlineKeyboardButton("🚫 ʙʟᴏᴄᴋʟɪsᴛ",    callback_data="commands_blocklist", style=ButtonStyle.DANGER,  icon_custom_emoji_id=Emoji.BLOCKLIST_ICON),
                InlineKeyboardButton("🔑 sᴜᴅᴏ",           callback_data="commands_sudo",      style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.KEY),
            ])
            rows.append([
                InlineKeyboardButton("📢 ʙʀᴏᴀᴅᴄᴀsᴛ",    callback_data="commands_broadcast", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.BROADCAST),
            ])

        if is_owner:
            rows.append([
                InlineKeyboardButton("⚙️ ᴏᴡɴᴇʀ",        callback_data="commands_owner",     style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.SETTINGS),
            ])

        rows.append([
            InlineKeyboardButton("🏠 ʜᴏᴍᴇ",             callback_data="commands_home",      style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.HOME)
        ])
        return InlineKeyboardMarkup(rows)

    HELP_HOME = help_markup(is_admin=True, is_owner=True, is_sudo=True)

    # ─── Back ───────────────────────────────────────────────────────────────
    BACK  = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ʙᴀᴄᴋ",  callback_data="commands_all", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK)]])

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
            [
                InlineKeyboardButton("🌐 ʀᴇᴘᴏ", url="https://github.com/nub-coders/nub-music-bot", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.REPO),
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
    def font_markup():
        """Generates the markup for font selection command."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("sᴍᴀʟʟ ᴄᴀᴘs", callback_data="font_small_caps", style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("𝐁𝐨𝐥𝐝 𝐒𝐞𝐫𝐢𝐟", callback_data="font_bold_serif", style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("𝗕𝗼𝗹𝗱 𝗦𝗮𝗻𝘀",  callback_data="font_bold_sans",  style=ButtonStyle.PRIMARY),
                InlineKeyboardButton("𝙼𝚘𝚗𝚘𝚜𝚙𝚊𝚌𝚎",  callback_data="font_monospace",  style=ButtonStyle.PRIMARY),
            ],
            [
                InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE),
            ],
        ])

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

