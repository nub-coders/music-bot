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
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ᴘʟᴀʏʟɪsᴛ", callback_data=f"{prefix}add_to_pl", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.ADD),
            ],
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
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▷",    callback_data=f"{prefix}resume", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.RESUME),
                InlineKeyboardButton("II",   callback_data=f"{prefix}pause",  style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.PAUSE),
                InlineKeyboardButton("‣‣I",  callback_data=f"{prefix}skip",   style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.SKIP),
                InlineKeyboardButton("▢",    callback_data=f"{prefix}end",    style=ButtonStyle.DANGER,  icon_custom_emoji_id=Emoji.STOP),
            ],
            [
                InlineKeyboardButton("‣ ᴘʟᴀʏ ɴᴏᴡ", callback_data=f"{prefix}playnow_{track_id}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.PLAY),
            ],
            [
                InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE),
            ],
        ])

    @staticmethod
    def playlist_select_markup(playlists: list, bot_username: str, chat_id: int) -> InlineKeyboardMarkup:
        """Ephemeral selector shown when tapping 'Add to Playlist' on Now Playing card."""
        rows = []
        # List user's existing playlists
        for pl in playlists:
            name = pl.get("name", "Playlist")
            count = len(pl.get("tracks", []))
            rows.append([
                InlineKeyboardButton(
                    f"📁 {name} ({count})",
                    callback_data=f"pl_add_{pl['id']}_{chat_id}",
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.MUSIC_NOTE,
                )
            ])
        # If user has less than 5 playlists, allow creating a new one via DM
        if len(playlists) < 5:
            rows.append([
                InlineKeyboardButton(
                    "➕ ᴄʀᴇᴀᴛᴇ ɴᴇᴡ ᴘʟᴀʏʟɪsᴛ",
                    url=f"https://t.me/{bot_username}?start=newpl_{chat_id}",
                    style=ButtonStyle.PRIMARY,
                    icon_custom_emoji_id=Emoji.ADD,
                )
            ])
        rows.append([
            InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE)
        ])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def playlist_hub_markup(playlists: list, bot_username: str) -> InlineKeyboardMarkup:
        """Root hub markup for /playlist command."""
        rows = []
        for pl in playlists:
            name = pl.get("name", "Playlist")
            count = len(pl.get("tracks", []))
            rows.append([
                InlineKeyboardButton(
                    f"📁 {name} ({count} tracks)",
                    callback_data=f"pl_open_{pl['id']}",
                    style=ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.MUSIC_NOTE,
                )
            ])
        if len(playlists) < 5:
            rows.append([
                InlineKeyboardButton(
                    "➕ ᴄʀᴇᴀᴛᴇ ɴᴇᴡ ᴘʟᴀʏʟɪsᴛ",
                    url=f"https://t.me/{bot_username}?start=newpl_0",
                    style=ButtonStyle.PRIMARY,
                    icon_custom_emoji_id=Emoji.ADD,
                )
            ])
        rows.append([
            InlineKeyboardButton("✖ ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE)
        ])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def playlist_manage_markup(playlist_id: str, bot_username: str, has_tracks: bool = True) -> InlineKeyboardMarkup:
        """Actions markup for a specific playlist."""
        rows = []
        if has_tracks:
            rows.append([
                InlineKeyboardButton("▷ ᴘʟᴀʏ ᴀʟʟ", callback_data=f"pl_play_{playlist_id}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id=Emoji.PLAY),
                InlineKeyboardButton("🔀 sʜᴜꜰꜰʟᴇ", callback_data=f"pl_shuffle_{playlist_id}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.REFRESH),
            ])
            rows.append([
                InlineKeyboardButton("📋 sᴇᴇ ᴀʟʟ sᴏɴɢs", callback_data=f"pl_songs_{playlist_id}_1", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.QUEUE_ICON),
            ])
        rows.append([
            InlineKeyboardButton("✏️ ʀᴇɴᴀᴍᴇ", url=f"https://t.me/{bot_username}?start=renamepl_{playlist_id}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.SETTINGS),
            InlineKeyboardButton("🗑 ᴅᴇʟᴇᴛᴇ", callback_data=f"pl_delpl_{playlist_id}", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.STOP),
        ])
        rows.append([
            InlineKeyboardButton("◀️ ʙᴀᴄᴋ ᴛᴏ ᴘʟᴀʏʟɪsᴛs", callback_data="pl_hub", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK),
        ])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def playlist_songs_markup(playlist_id: str, page: int, total_pages: int, page_items_count: int) -> InlineKeyboardMarkup:
        """Paginated songs viewer with individual track delete buttons."""
        rows = []
        # Row 1 & 2: Delete buttons for the songs on current page
        del_btns = [
            InlineKeyboardButton(f"❌ {i}", callback_data=f"pl_delsong_{playlist_id}_{page}_{i-1}", style=ButtonStyle.DANGER)
            for i in range(1, page_items_count + 1)
        ]
        if del_btns:
            # Chunk delete buttons into rows of up to 5
            for chunk_start in range(0, len(del_btns), 5):
                rows.append(del_btns[chunk_start:chunk_start + 5])

        # Pagination controls
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"pl_songs_{playlist_id}_{page-1}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK))
        nav_row.append(InlineKeyboardButton(f"{page}/{max(1, total_pages)}", callback_data="pl_noop", disabled=True))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"pl_songs_{playlist_id}_{page+1}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.NEXT))
        if nav_row:
            rows.append(nav_row)

        rows.append([
            InlineKeyboardButton("◀️ ʙᴀᴄᴋ ᴛᴏ ᴘʟᴀʏʟɪsᴛ", callback_data=f"pl_open_{playlist_id}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.BACK),
        ])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def playlist_delete_confirm_markup(playlist_id: str) -> InlineKeyboardMarkup:
        """Confirmation markup before deleting a playlist."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🗑 ʏᴇs, ᴅᴇʟᴇᴛᴇ", callback_data=f"pl_confirm_delpl_{playlist_id}", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.STOP),
                InlineKeyboardButton("✖ ɴᴏ, ᴄᴀɴᴄᴇʟ", callback_data=f"pl_open_{playlist_id}", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE),
            ]
        ])

    @staticmethod
    def progress_button(progress_text: str) -> InlineKeyboardButton:
        """Returns a native disabled inline button displaying playback progress."""
        return InlineKeyboardButton(
            text=progress_text,
            disabled=True,
            style=ButtonStyle.DEFAULT,
        )

    @staticmethod
    def force_play_markup(youtube_url):
        """Generates the markup for the force play results."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 sᴛʀᴇᴀᴍ ᴏɴ ʏᴏᴜᴛᴜʙᴇ", url=youtube_url, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ROCKET),
        ]])

    @staticmethod
    def suggestion_markup(suggestions: list = None, autoplay_enabled: bool = True):
        """Generates the markup for related video suggestions card controls."""
        autoplay_text = "ᴀᴜᴛᴏᴘʟᴀʏ: ON" if autoplay_enabled else "ᴀᴜᴛᴏᴘʟᴀʏ: OFF"
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("sᴛᴏᴘ", callback_data="sgstop", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.STOP),
                InlineKeyboardButton(autoplay_text, callback_data="sgtoggle", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.SETTINGS),
            ],
            [
                InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE),
            ]
        ])

    @staticmethod
    def stats_markup(selected_period: str = "24h") -> InlineKeyboardMarkup:
        """Generates the markup for stats period selection."""
        period = (selected_period or "24h").lower()
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📊 24h",
                    callback_data="stats_24h",
                    style=ButtonStyle.PRIMARY if period == "24h" else ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.STATS,
                ),
                InlineKeyboardButton(
                    "📅 Week",
                    callback_data="stats_week",
                    style=ButtonStyle.PRIMARY if period == "week" else ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.REFRESH,
                ),
                InlineKeyboardButton(
                    "📈 Overall",
                    callback_data="stats_overall",
                    style=ButtonStyle.PRIMARY if period == "overall" else ButtonStyle.DEFAULT,
                    icon_custom_emoji_id=Emoji.NEWS_STATS,
                ),
            ],
            [
                InlineKeyboardButton("✖ Close", callback_data="close", style=ButtonStyle.DANGER, icon_custom_emoji_id=Emoji.CLOSE),
            ],
        ])

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

