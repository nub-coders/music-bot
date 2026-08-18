from utils.emoji import EmojiTag


class Messages:
    # ── Playback & Queue Cards ─────────────────────────────────────────────
    PLAY = (
        f"{EmojiTag.PLAY} <b>ɴᴏᴡ ᴘʟᴀʏɪɴɢ</b>\n\n"
        "<b>‣ ᴛɪᴛʟᴇ:</b> {1}\n"
        "<b>‣ ᴅᴜʀᴀᴛɪᴏɴ:</b> <code>{2}</code>\n"
        "<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {3}\n"
        "<b>‣ ᴍᴏᴅᴇ:</b> <code>{0}</code>"
    )

    QUEUE = (
        f"{EmojiTag.ADD} <b>ᴀᴅᴅᴇᴅ ᴛᴏ ǫᴜᴇᴜᴇ</b>\n\n"
        "<b>‣ ᴛɪᴛʟᴇ:</b> {1}\n"
        "<b>‣ ᴅᴜʀᴀᴛɪᴏɴ:</b> <code>{2}</code>\n"
        "<b>‣ ᴘᴏsɪᴛɪᴏɴ:</b> {3}\n"
        "<b>‣ ᴍᴏᴅᴇ:</b> <code>{0}</code>"
    )

    # ── Controls Status ───────────────────────────────────────────────────
    NO_STREAM = f"{EmojiTag.ERROR} <b>ɴᴏ ᴀᴄᴛɪᴠᴇ sᴛʀᴇᴀᴍ ʀɪɢʜᴛ ɴᴏᴡ.</b>"
    SKIPPING = f"{EmojiTag.SKIP} <b>sᴋɪᴘᴘɪɴɢ ᴄᴜʀʀᴇɴᴛ ᴛʀᴀᴄᴋ...</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    SKIPPED_EMPTY = f"{EmojiTag.SKIP} <b>ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ ɴᴏᴡ.</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    RESUMED = f"{EmojiTag.RESUME} <b>ᴘʟᴀʏʙᴀᴄᴋ ʀᴇsᴜᴍᴇᴅ.</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    PAUSED = f"{EmojiTag.PAUSE} <b>ᴘʟᴀʏʙᴀᴄᴋ ᴘᴀᴜsᴇᴅ.</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    AUTO_LEAVE_EMPTY = f"{EmojiTag.WARNING} <b>ɴᴏ ʟɪsᴛᴇɴᴇʀs ᴅᴇᴛᴇᴄᴛᴇᴅ. ʟᴇᴀᴠɪɴɢ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ.</b>"
    AUTO_LEAVE_ONE = f"{EmojiTag.WARNING} <b>ᴏɴʟʏ ᴏɴᴇ ʟɪsᴛᴇɴᴇʀ ʀᴇᴍᴀɪɴᴇᴅ. ᴀssɪsᴛᴀɴᴛ ʟᴇꜰᴛ ᴄʜᴀᴛ.</b>"
    ERROR_STREAM = f"{EmojiTag.ERROR} <b>ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴀ ᴠᴀʟɪᴅ sᴛʀᴇᴀᴍ sᴏᴜʀᴄᴇ.</b>"

    # ── Autoplay & Suggestions ─────────────────────────────────────────────
    SUGGESTION_CARD = (
        f"{EmojiTag.MUSIC_NOTES} <b>ǫᴜᴇᴜᴇ ᴇɴᴅᴇᴅ • ʀᴇʟᴀᴛᴇᴅ sᴜɢɢᴇsᴛɪᴏɴs</b>\n\n"
        "<b>‣ sᴇᴇᴅ:</b> {0}\n"
        "⏳ <i>ᴀᴜᴛᴏᴘʟᴀʏɪɴɢ #1 ɪɴ <b>{2}</b>s…</i>\n\n"
        "{1}"
    )
    SUGGESTION_CARD_NO_AUTOPLAY = (
        f"{EmojiTag.MUSIC_NOTES} <b>ǫᴜᴇᴜᴇ ᴇɴᴅᴇᴅ • ʀᴇʟᴀᴛᴇᴅ sᴜɢɢᴇsᴛɪᴏɴs</b>\n\n"
        "<b>‣ sᴇᴇᴅ:</b> {0}\n"
        "<i>ᴄʜᴏᴏsᴇ ᴀ sᴏɴɢ ᴛᴏ ᴘʟᴀʏ ɴᴇxᴛ:</i>\n\n"
        "{1}"
    )
    AUTOPLAY_ENABLED = f"{EmojiTag.SUCCESS} <b>ᴀᴜᴛᴏᴘʟᴀʏ ᴇɴᴀʙʟᴇᴅ ꜰᴏʀ ᴛʜɪs ᴄʜᴀᴛ.</b>"
    AUTOPLAY_DISABLED = f"{EmojiTag.WARNING} <b>ᴀᴜᴛᴏᴘʟᴀʏ ᴅɪsᴀʙʟᴇᴅ ꜰᴏʀ ᴛʜɪs ᴄʜᴀᴛ.</b>"
    AUTOPLAY_STATUS = f"{EmojiTag.INFO} <b>ᴀᴜᴛᴏᴘʟᴀʏ sᴛᴀᴛᴜs:</b> {{}}"
    AUTOPLAY_USAGE = f"{EmojiTag.INFO} <b>ᴜsᴀɢᴇ:</b> <code>/autoplay [on|off]</code>\n‣ <b>ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs:</b> {{}}"
    AUTOPLAY_ADMIN_ONLY_SWITCH = f"{EmojiTag.INFO} <b>ᴀᴜᴛᴏᴘʟᴀʏ sᴛᴀᴛᴜs:</b> {{}}\n<i>(Only admins & auth users can switch this setting)</i>"
    AUTOPLAYING_TITLE = "▶️ <b>ᴀᴜᴛᴏᴘʟᴀʏɪɴɢ:</b> <b>{}</b>…"
    STARTING_PLAYBACK = "▶️ Starting playback…"
    PLAYING_SUGGESTION = "▶️ <b>ᴘʟᴀʏɪɴɢ sᴜɢɢᴇsᴛɪᴏɴ:</b> <code>{}</code>…"

    # ── Controls Notices & Actions ─────────────────────────────────────────
    SEEKED = f"{EmojiTag.SUCCESS} <b>sᴇᴇᴋᴇᴅ ᴛᴏ {{}}!</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    QUEUE_CLEARED_STOPPED = f"<b>{EmojiTag.STOP} ǫᴜᴇᴜᴇ ᴄʟᴇᴀʀᴇᴅ</b>\n<b>‣ sᴛʀᴇᴀᴍɪɴɢ sᴛᴏᴘᴘᴇᴅ</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    SONG_LOOPED = f"<b>{EmojiTag.LOOP} ᴄᴜʀʀᴇɴᴛ sᴏɴɢ ᴡɪʟʟ ʙᴇ ʀᴇᴘᴇᴀᴛᴇᴅ {{}} ᴛɪᴍᴇs!</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    SONG_RESUMED_NOTICE = f"<b>{EmojiTag.RESUME} sᴏɴɢ ʀᴇsᴜᴍᴇᴅ.</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    SONG_PAUSED_NOTICE = f"<b>{EmojiTag.PAUSE} sᴏɴɢ ᴘᴀᴜsᴇᴅ.</b>\n\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"

    # ── Admin & Auth ───────────────────────────────────────────────────────
    ADMIN_UNKNOWN_USER = f"{EmojiTag.WARNING} <b>ᴄᴀɴɴᴏᴛ ᴠᴇʀɪꜰʏ ᴀᴅᴍɪɴ sᴛᴀᴛᴜs ꜰᴏʀ ᴛʜɪs ᴜsᴇʀ.</b>"
    ADMIN_RESTRICTED_ACTION = f"{EmojiTag.LOCK} <b>ᴛʜɪs ᴀᴄᴛɪᴏɴ ɪs ʀᴇsᴛʀɪᴄᴛᴇᴅ ᴛᴏ ᴀᴅᴍɪɴs ᴏɴʟʏ.</b>"
    ADMIN_RESTRICTED_CMD = f"{EmojiTag.LOCK} <b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪs ʀᴇsᴛʀɪᴄᴛᴇᴅ ᴛᴏ ᴀᴅᴍɪɴs ᴏɴʟʏ.</b>"
    AUTH_FAILED = f"{EmojiTag.ERROR} <b>ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ᴄʜᴇᴄᴋ ꜰᴀɪʟᴇᴅ.</b>"

    # ── Seek & Loop ────────────────────────────────────────────────────────
    SEEK_NO_ARGS = f"{EmojiTag.INFO} <b>ᴘʀᴏᴠɪᴅᴇ sᴇᴇᴋ ᴛɪᴍᴇ ɪɴ sᴇᴄᴏɴᴅs.</b>\n<b>‣ ᴜsᴀɢᴇ:</b> <code>/seek &lt;seconds&gt;</code>"
    SEEK_NEGATIVE = f"{EmojiTag.ERROR} <b>sᴇᴇᴋ ᴛɪᴍᴇ ᴄᴀɴɴᴏᴛ ʙᴇ ɴᴇɢᴀᴛɪᴠᴇ.</b>"
    SEEK_INVALID = f"{EmojiTag.ERROR} <b>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ᴏꜰ sᴇᴄᴏɴᴅs.</b>"
    SEEK_BEYOND_REMAINING = f"{EmojiTag.WARNING} <b>ᴄᴀɴɴᴏᴛ sᴇᴇᴋ ʙᴇʏᴏɴᴅ ʀᴇᴍᴀɪɴɪɴɢ ᴅᴜʀᴀᴛɪᴏɴ.</b>"
    SEEK_BEYOND_PLAYED = f"{EmojiTag.WARNING} <b>ᴄᴀɴɴᴏᴛ sᴇᴇᴋ ʙᴀᴄᴋ ᴍᴏʀᴇ ᴛʜᴀɴ ᴀʟʀᴇᴀᴅʏ ᴘʟᴀʏᴇᴅ ᴅᴜʀᴀᴛɪᴏɴ.</b>"

    LOOP_NO_ARGS = f"{EmojiTag.INFO} <b>ᴘʀᴏᴠɪᴅᴇ ɴᴜᴍʙᴇʀ ᴏꜰ ʟᴏᴏᴘs.</b>\n<b>‣ ᴜsᴀɢᴇ:</b> <code>/loop &lt;1-20&gt;</code>"
    LOOP_OUT_OF_BOUNDS = f"{EmojiTag.WARNING} <b>ʟᴏᴏᴘ ᴄᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 1 ᴀɴᴅ 20.</b>"
    LOOP_INVALID = f"{EmojiTag.ERROR} <b>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ʟᴏᴏᴘ ᴄᴏᴜɴᴛ.</b>"

    # ── General Errors & Status ───────────────────────────────────────────
    ERROR_OCCURRED = f"{EmojiTag.ERROR} <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>"
    ERROR_PERMISSIONS = f"{EmojiTag.ERROR} <b>ꜰᴀɪʟᴇᴅ ᴛᴏ ᴄʜᴇᴄᴋ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs.</b>"
    ERROR_USER_NOT_FOUND = f"{EmojiTag.ERROR} <b>ᴜsᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ. ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɪᴅ.</b>"

    QUEUE_EMPTY = f"{EmojiTag.QUEUE_ICON} <b>ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ.</b>"
    NOTHING_TO_SHUFFLE = f"{EmojiTag.WARNING} <b>ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ 2 ᴛʀᴀᴄᴋs ɪɴ ǫᴜᴇᴜᴇ ᴛᴏ sʜᴜꜰꜰʟᴇ.</b>"
    QUEUE_SHUFFLED = f"{EmojiTag.REFRESH} <b>sʜᴜꜰꜰʟᴇᴅ {{}} ᴜᴘᴄᴏᴍɪɴɢ ᴛʀᴀᴄᴋ(s).</b>"
    PLAYLIST_QUEUED = f"{EmojiTag.ADD} <b>ᴀᴅᴅᴇᴅ {{}} ᴛʀᴀᴄᴋs ꜰʀᴏᴍ ᴘʟᴀʏʟɪsᴛ ᴛᴏ ǫᴜᴇᴜᴇ.</b>"
    OWNER_SUDO_CMD = f"{EmojiTag.KEY} <b>ᴏᴡɴᴇʀ/sᴜᴅᴏ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>"
    NO_TAGALL = f"{EmojiTag.WARNING} <b>ɴᴏ ᴛᴀɢ-ᴀʟʟ sᴇssɪᴏɴ ꜰᴏᴜɴᴅ.</b>"
    DISMISS_MENTION = f"{EmojiTag.SUCCESS} <b>ᴍᴇɴᴛɪᴏɴ ᴅɪsᴍɪssᴇᴅ.</b>"
    ERROR_DEL_MSG = f"{EmojiTag.ERROR} <b>ᴇʀʀᴏʀ ᴅᴇʟᴇᴛɪɴɢ ᴍᴇssᴀɢᴇ.</b>"
    REPLY_TO_DEL = f"{EmojiTag.INFO} <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴅᴇʟᴇᴛᴇ ɪᴛ.</b>"
    OWNER_AUTH_ALL = f"{EmojiTag.CROWN} <b>ᴏᴡɴᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴇᴠᴇʀʏᴡʜᴇʀᴇ.</b>"
    USER_AUTH = f"{EmojiTag.SUCCESS} <b>ᴜsᴇʀ {{}} ʜᴀs ʙᴇᴇɴ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.</b>"
    USER_ALREADY_AUTH = f"{EmojiTag.INFO} <b>ᴜsᴇʀ {{}} ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.</b>"
    CANT_AUTH_SELF = f"{EmojiTag.WARNING} <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ᴀɴᴏɴʏᴍᴏᴜs ᴜsᴇʀs.</b>"
    NOT_FROM_USER = f"{EmojiTag.WARNING} <b>ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪs ɴᴏᴛ ꜰʀᴏᴍ ᴀ ᴜsᴇʀ.</b>"
    INVALID_USER_ID = f"{EmojiTag.ERROR} <b>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ᴜsᴇʀ ɪᴅ.</b>"
    REPLY_OR_PROVIDE_ID = f"{EmojiTag.INFO} <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴜsᴇʀ ɪᴅ.</b>"
    OWNER_BLOCK_RESTRICT = f"{EmojiTag.WARNING} <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙʟᴏᴄᴋ ᴛʜᴇ ᴏᴡɴᴇʀ.</b>"
    CANT_REMOVE_AUTH_OWNER = f"{EmojiTag.WARNING} <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ꜰʀᴏᴍ ᴏᴡɴᴇʀ.</b>"
    USER_REMOVED_AUTH = f"{EmojiTag.SUCCESS} <b>ᴜsᴇʀ {{}} ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀs.</b>"
    USER_NOT_AUTH = f"{EmojiTag.WARNING} <b>ᴜsᴇʀ {{}} ɪs ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.</b>"
    USER_BLOCKED = f"{EmojiTag.BLOCKED} <b>ᴜsᴇʀ {{}} ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴛᴏ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    USER_ALREADY_BLOCKED = f"{EmojiTag.INFO} <b>ᴜsᴇʀ {{}} ɪs ᴀʟʀᴇᴀᴅʏ ɪɴ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    CANT_BLOCK_SELF = f"{EmojiTag.WARNING} <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙʟᴏᴄᴋ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ᴀɴᴏɴʏᴍᴏᴜs ᴜsᴇʀs.</b>"
    REBOOTING = f"{EmojiTag.REFRESH} <b>ʀᴇʙᴏᴏᴛɪɴɢ ʙᴏᴛ ᴘʀᴏᴄᴇss...</b>"
    REMOVED_FROM_BLOCKLIST = f"{EmojiTag.SUCCESS} <b>ᴜsᴇʀ {{}} ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    NOT_IN_BLOCKLIST = f"{EmojiTag.INFO} <b>ᴜsᴇʀ {{}} ɪs ɴᴏᴛ ɪɴ ʙʟᴏᴄᴋʟɪsᴛ.</b>"

    LOADING = f"{EmojiTag.LOADING} <b>ʟᴏᴀᴅɪɴɢ...</b>"
    GETTING_STREAM_INFO = f"{EmojiTag.LOADING} <b>ꜰᴇᴛᴄʜɪɴɢ sᴛʀᴇᴀᴍ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...</b>"
    GETTING_CHATS = f"{EmojiTag.LOADING} <b>ꜰᴇᴛᴄʜɪɴɢ ᴄʜᴀᴛs, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...</b>"
    BOLT = f"{EmojiTag.BOLT} <b>ᴘʀᴏᴄᴇssɪɴɢ...</b>"

    START_BOT_BROADCAST = f"{EmojiTag.BROADCAST} <b>sᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀsᴛ ꜰʀᴏᴍ ʙᴏᴛ ᴀᴄᴄᴏᴜɴᴛ...</b>"
    START_ASSISTANT_BROADCAST = f"{EmojiTag.BROADCAST} <b>sᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀsᴛ ꜰʀᴏᴍ ᴀssɪsᴛᴀɴᴛ ᴀᴄᴄᴏᴜɴᴛ...</b>"
    REPLY_TO_BROADCAST = f"{EmojiTag.INFO} <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ɪᴛ.</b>"

    NO_BLOCKLIST = f"{EmojiTag.INFO} <b>ɴᴏ ʙʟᴏᴄᴋʟɪsᴛ ꜰᴏᴜɴᴅ.</b>"
    NO_USERS_BLOCKED = f"{EmojiTag.INFO} <b>ɴᴏ ᴜsᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ʙʟᴏᴄᴋᴇᴅ.</b>"
    GROUP_ONLY = f"{EmojiTag.WARNING} <b>ᴘʟᴀʏ ᴄᴏᴍᴍᴀɴᴅs ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs.</b>"
    NO_LINKED_CHANNEL = f"{EmojiTag.WARNING} <b>ᴛʜɪs ɢʀᴏᴜᴘ ʜᴀs ɴᴏ ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ.</b>"
    USER_DATA_NOT_FOUND = f"{EmojiTag.WARNING} <b>ᴜsᴇʀ ᴅᴀᴛᴀ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b>"
    NO_DATA_FOUND = f"{EmojiTag.WARNING} <b>ɴᴏ ᴅᴀᴛᴀ ꜰᴏᴜɴᴅ.</b>"

    COLLECTING_STATS = f"{EmojiTag.STATS} <b>ᴄᴏʟʟᴇᴄᴛɪɴɢ sᴛᴀᴛs...</b>"
    PINGING = f"{EmojiTag.PING} <b>ᴘɪɴɢɪɴɢ...</b>"

    NO_PERM_END_SESSION = f"{EmojiTag.LOCK} <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴇɴᴅ sᴇssɪᴏɴ.</b>"
    NO_PERM_SKIP = f"{EmojiTag.LOCK} <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ sᴋɪᴘ.</b>"
    NO_PERM_RESUME = f"{EmojiTag.LOCK} <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ʀᴇsᴜᴍᴇ.</b>"
    NO_PERM_PAUSE = f"{EmojiTag.LOCK} <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴘᴀᴜsᴇ.</b>"
    BOT_OWNER_ONLY = f"{EmojiTag.OWNER} <b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ᴛᴏ ʙᴏᴛ ᴏᴡɴᴇʀ ᴏɴʟʏ.</b>"

    STREAM_ENDED = f"{EmojiTag.SUCCESS} <b>sᴛʀᴇᴀᴍ ᴇɴᴅᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ.</b>"
    STREAM_ENDED_NOT_IN_CALL = f"{EmojiTag.INFO} <b>sᴛʀᴇᴀᴍ ᴇɴᴅᴇᴅ (ᴀssɪsᴛᴀɴᴛ ᴡᴀs ɴᴏᴛ ɪɴ ᴄᴀʟʟ).</b>"
    ASSISTANT_NOT_STREAMING = f"{EmojiTag.INFO} <b>ᴀssɪsᴛᴀɴᴛ ɪs ɴᴏᴛ sᴛʀᴇᴀᴍɪɴɢ ᴀɴʏᴛʜɪɴɢ.</b>"
    NO_ACTIVE_STREAM = f"{EmojiTag.ERROR} <b>ɴᴏ ᴀᴄᴛɪᴠᴇ sᴛʀᴇᴀᴍ ꜰᴏᴜɴᴅ.</b>"
    SKIPPED_SUCCESS = f"{EmojiTag.SUCCESS} <b>sᴋɪᴘᴘᴇᴅ ᴛᴏ ɴᴇxᴛ ᴛʀᴀᴄᴋ.</b>"
    PLAYING_NOW = f"{EmojiTag.PLAY} <b>ᴊᴜᴍᴘɪɴɢ ᴛᴏ ᴛʜɪs ᴛʀᴀᴄᴋ...</b>\n<b>‣ ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {{}}"
    TRACK_GONE = f"{EmojiTag.INFO} <b>ᴛʜɪs ᴛʀᴀᴄᴋ ɪs ɴᴏ ʟᴏɴɢᴇʀ ɪɴ ᴛʜᴇ ǫᴜᴇᴜᴇ.</b>"
    QUEUE_EMPTY_STREAM_ENDED = f"{EmojiTag.QUEUE_ICON} <b>ǫᴜᴇᴜᴇ ᴇɴᴅᴇᴅ. sᴛʀᴇᴀᴍ sᴛᴏᴘᴘᴇᴅ.</b>"

    NO_MSG_FOR_BROADCAST = f"{EmojiTag.WARNING} <b>ɴᴏ ᴍᴇssᴀɢᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ꜰᴏʀ ʙʀᴏᴀᴅᴄᴀsᴛ.</b>"
    USE_COMMAND_AS_USER = f"{EmojiTag.WARNING} <b>ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴀs ᴀ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ.</b>"
    STICKER_LONG = f"{EmojiTag.INFO} <b>sᴛɪᴄᴋᴇʀ ᴘʀᴏᴄᴇssɪɴɢ ᴍᴀʏ ᴛᴀᴋᴇ ʟᴏɴɢᴇʀ ꜰᴏʀ ʟᴀʀɢᴇ ᴘᴀᴄᴋs.</b>"
    REPLY_TO_PHOTO_OR_STICKER = f"{EmojiTag.INFO} <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ sᴛɪᴄᴋᴇʀ.</b>"
    PROCESSING = f"{EmojiTag.LOADING} <b>ᴘʀᴏᴄᴇssɪɴɢ...</b>"
    ONLY_MEDIA_ALLOWED = f"{EmojiTag.WARNING} <b>ᴏɴʟʏ ᴘʜᴏᴛᴏs, ᴠɪᴅᴇᴏs, ɢɪꜰs, ᴀɴᴅ sᴛɪᴄᴋᴇʀs ᴀʀᴇ ᴀʟʟᴏᴡᴇᴅ.</b>"
    MEDIA_SIZE_EXCEED = f"{EmojiTag.WARNING} <b>ᴍᴇᴅɪᴀ sɪᴢᴇ ᴍᴜsᴛ ʙᴇ ʙᴇʟᴏᴡ 5 ᴍʙ.</b>"
    ERROR_MEDIA_PROCESS = f"{EmojiTag.ERROR} <b>ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ᴍᴇᴅɪᴀ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀ ᴅɪꜰꜰᴇʀᴇɴᴛ ꜰɪʟᴇ.</b>"
    NOTHING_TO_UPDATE = f"{EmojiTag.INFO} <b>ɴᴏᴛʜɪɴɢ ᴛᴏ ᴜᴘᴅᴀᴛᴇ.</b>"
    WELCOME_TOO_LONG = f"{EmojiTag.WARNING} <b>ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ ɪs ᴛᴏᴏ ʟᴏɴɢ. ᴍᴀx 4096 ᴄʜᴀʀᴀᴄᴛᴇʀs.</b>"
    WELCOME_RESET = f"{EmojiTag.SUCCESS} <b>ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ ᴀɴᴅ ʟᴏɢᴏ ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇsᴇᴛ.</b>"

    UNSUPPORTED_MEDIA = f"{EmojiTag.WARNING} <b>ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ.</b>"
    NO_QUERY_MATCH = f"{EmojiTag.ERROR} <b>ɴᴏ ᴍᴀᴛᴄʜɪɴɢ ʀᴇsᴜʟᴛ ꜰᴏᴜɴᴅ. ᴛʀʏ ᴀɴᴏᴛʜᴇʀ ǫᴜᴇʀʏ.</b>"
    NO_QUERY_GIVEN = f"{EmojiTag.INFO} <b>ɴᴏ ǫᴜᴇʀʏ ᴘʀᴏᴠɪᴅᴇᴅ.</b>"
    NEED_INVITE_PERMISSION = f"{EmojiTag.LOCK} <b>ɪ ɴᴇᴇᴅ 'ɪɴᴠɪᴛᴇ ᴜsᴇʀs ᴠɪᴀ ʟɪɴᴋ' ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴊᴏɪɴ.</b>"
    LINKED_CHANNEL_ERROR = f"{EmojiTag.ERROR} <b>ꜰᴀɪʟᴇᴅ ᴛᴏ ᴀᴄᴄᴇss ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ.</b>"
    NO_OPERATIONAL_DATA = f"{EmojiTag.INFO} <b>ɴᴏ ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ ᴅᴀᴛᴀ ꜰᴏᴜɴᴅ ꜰᴏʀ ᴛʜɪs ʙᴏᴛ.</b>"

    STICKER_NO_NAME = f"{EmojiTag.WARNING} <b>sᴛɪᴄᴋᴇʀ ʜᴀs ɴᴏ ᴠᴀʟɪᴅ ɴᴀᴍᴇ.</b>"
    UNSUPPORTED_FILE = f"{EmojiTag.WARNING} <b>ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ꜰɪʟᴇ ᴛʏᴘᴇ.</b>"
    REPLY_TO_MEDIA = f"{EmojiTag.INFO} <b>ʀᴇᴘʟʏ ᴛᴏ ᴘʜᴏᴛᴏ/ɢɪꜰ/sᴛɪᴄᴋᴇʀ ᴍᴇᴅɪᴀ ꜰɪʀsᴛ.</b>"
    CREATING_STICKER_PACK = f"{EmojiTag.KANG} <b>ᴄʀᴇᴀᴛɪɴɢ ᴀ ɴᴇᴡ sᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ...</b>"

    PAID_OWNER_CMD = f"{EmojiTag.OWNER} <b>ᴘᴀɪᴅ ᴏᴡɴᴇʀ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>"
    NO_SUDO_USERS = f"{EmojiTag.INFO} <b>ɴᴏ sᴜᴅᴏ ᴜsᴇʀs ꜰᴏᴜɴᴅ.</b>"
    ERR_FETCH_SUDO = f"{EmojiTag.ERROR} <b>ᴇʀʀᴏʀ ᴡʜɪʟᴇ ꜰᴇᴛᴄʜɪɴɢ sᴜᴅᴏ ʟɪsᴛ.</b>"
    RATE_LIMITED = f"{EmojiTag.WARNING} <b>ʏᴏᴜ'ʀᴇ sᴇɴᴅɪɴɢ ᴘʟᴀʏ ᴄᴏᴍᴍᴀɴᴅs ᴛᴏᴏ ꜰᴀsᴛ.</b>"
    OWNER_CMD = f"{EmojiTag.OWNER} <b>ᴏᴡɴᴇʀ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>"
    ALREADY_OWNER = f"{EmojiTag.INFO} <b>ᴛʜɪs ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴏᴡɴᴇʀ.</b>"
    USER_ADDED_SUDO = f"{EmojiTag.SUCCESS} <b>ᴜsᴇʀ {{}} ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴛᴏ sᴜᴅᴏᴇʀs.</b>"
    USER_ALREADY_SUDO = f"{EmojiTag.INFO} <b>ᴜsᴇʀ {{}} ɪs ᴀʟʀᴇᴀᴅʏ ɪɴ sᴜᴅᴏᴇʀs.</b>"
    CANT_SUDO_SELF = f"{EmojiTag.WARNING} <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴀᴅᴅ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ʙᴏᴛ ᴛᴏ sᴜᴅᴏᴇʀs.</b>"
    CANT_REMOVE_OWNER_SUDO = f"{EmojiTag.WARNING} <b>ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴏᴡɴᴇʀ ꜰʀᴏᴍ sᴜᴅᴏ ʟɪsᴛ.</b>"
    USER_NOT_IN_DB = f"{EmojiTag.WARNING} <b>ᴜsᴇʀ {{}} ɪs ɴᴏᴛ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ.</b>"
    USER_REMOVED_SUDO = f"{EmojiTag.SUCCESS} <b>ᴜsᴇʀ {{}} ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ sᴜᴅᴏᴇʀs.</b>"
    USER_NOT_IN_SUDO = f"{EmojiTag.WARNING} <b>ᴜsᴇʀ {{}} ɪs ɴᴏᴛ ɪɴ sᴜᴅᴏᴇʀs.</b>"
    CANT_REMOVE_SELF_SUDO = f"{EmojiTag.WARNING} <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ʏᴏᴜʀsᴇʟꜰ ꜰʀᴏᴍ sᴜᴅᴏᴇʀs.</b>"

    # ── Additional Catalog Strings ─────────────────────────────────────────
    CALL_CLIENT_NOT_READY = f"<b>{EmojiTag.ERROR} ᴄᴀʟʟ ᴄʟɪᴇɴᴛ ɴᴏᴛ ʀᴇᴀᴅʏ.</b>"
    ASSISTANT_BANNED = "Assistant is banned in this chat.\n\nPlease unban {}\nuser id: {}"
    FAILED_JOIN_GROUP = "Failed to join the group. Please try again."
    MMF_USAGE = "Please use `/mmf <text>`"
    MMF_DOWNLOAD_FAILED = "Failed to download media for memify."
    INVALID_FONT_SELECTION = "Invalid font style selection."
    HELP_CATEGORY_SELECT = f"<u><b>{EmojiTag.INFO} | sᴇʟᴇᴄᴛ ᴀ ᴄᴏᴍᴍᴀɴᴅ ᴄᴀᴛᴇɢᴏʀʏ</b></u>"
    GROUP_WELCOME = (
        f"{EmojiTag.MUSIC_NOTE} <b>ʜᴇʏ {{adder}}!</b> ᴛʜᴀɴᴋs ꜰᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ ᴛᴏ <b>{{group_name}}</b> 🎉\n\n"
        f"ɪ'ᴍ <b>{{botname}}</b> — ʏᴏᴜʀ ᴅᴇᴅɪᴄᴀᴛᴇᴅ ᴍᴜsɪᴄ ʙᴏᴛ.\n\n"
        f"{EmojiTag.MUSIC_NOTES} ᴄʀʏsᴛᴀʟ-ᴄʟᴇᴀʀ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ sᴛʀᴇᴀᴍɪɴɢ\n"
        f"{EmojiTag.BOLT} ʙʟᴀᴢɪɴɢ-ꜰᴀsᴛ ᴘʟᴀʏʙᴀᴄᴋ ᴡɪᴛʜ ǫᴜᴇᴜᴇ\n"
        f"{EmojiTag.GLOBE} ʏᴏᴜᴛᴜʙᴇ, sᴘᴏᴛɪꜰʏ & ᴍᴏʀᴇ\n\n"
        f"<i>ᴜsᴇ <code>/play [song]</code> ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ!</i>"
    )

