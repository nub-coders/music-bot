"""
utils/message.py — Styled message constants for NUB Music Bot.

Styling inspired by:
  • AsmSafone/MusicPlayer  → emoji | **Bold** pipe pattern
  • TheTeamAlexa/AlexaMusic → ᴜɴɪᴄᴏᴅᴇ sᴍᴀʟʟ-ᴄᴀᴘs headers, box-drawing chars
  • AnonymousX1025/AnonXMusic → HTML <b>, <u>, <i>, <blockquote> formatting
"""


class UniformFormat:
    """Allows dict-like access that always returns the same string."""
    def __init__(self, text):
        self.text = text

    def __getitem__(self, key):
        return self.text

    def get(self, key, default=None):
        return self.text


class Messages:

    # ──────────────────────────────────────────────
    #  🎵  PLAYBACK
    # ──────────────────────────────────────────────

    PLAY = UniformFormat(
        "<u><b>▶️ | ɴᴏᴡ sᴛʀᴇᴀᴍɪɴɢ</b></u>\n\n"
        "‣ <b>ᴍᴏᴅᴇ:</b> {}\n"
        "‣ <b>ᴛɪᴛʟᴇ:</b> {}\n"
        "‣ <b>ᴅᴜʀᴀᴛɪᴏɴ:</b> {}\n"
        "‣ <b>ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b> {}"
    )

    QUEUE = UniformFormat(
        "<u><b>➕ | ᴀᴅᴅᴇᴅ ᴛᴏ ǫᴜᴇᴜᴇ</b></u>\n\n"
        "‣ <b>ᴍᴏᴅᴇ:</b> {}\n"
        "‣ <b>ᴛɪᴛʟᴇ:</b> {}\n"
        "‣ <b>ᴅᴜʀᴀᴛɪᴏɴ:</b> {}\n"
        "‣ <b>ᴘᴏsɪᴛɪᴏɴ:</b> #{}"
    )

    NO_STREAM      = "❌ | <b>ɴᴏ ᴀᴄᴛɪᴠᴇ sᴛʀᴇᴀᴍ ʀɪɢʜᴛ ɴᴏᴡ.</b>"
    SKIPPING       = "⏭ | <b>sᴋɪᴘᴘɪɴɢ ᴄᴜʀʀᴇɴᴛ ᴛʀᴀᴄᴋ…</b>\n‣ <b>ʙʏ:</b> {}"
    SKIPPED_EMPTY  = "⏭ | <b>ǫᴜᴇᴜᴇ ɪs ɴᴏᴡ ᴇᴍᴘᴛʏ.</b>\n‣ <b>ʙʏ:</b> {}"
    RESUMED        = "▶️ | <b>ᴘʟᴀʏʙᴀᴄᴋ ʀᴇsᴜᴍᴇᴅ.</b>\n‣ <b>ʙʏ:</b> {}"
    PAUSED         = "⏸ | <b>ᴘʟᴀʏʙᴀᴄᴋ ᴘᴀᴜsᴇᴅ.</b>\n‣ <b>ʙʏ:</b> {}"
    STREAM_ENDED   = "⏹ | <b>sᴛʀᴇᴀᴍ ᴇɴᴅᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ.</b>"
    STREAM_ENDED_NOT_IN_CALL   = "⏹ | <b>sᴛʀᴇᴀᴍ ᴇɴᴅᴇᴅ</b> <i>(ᴀssɪsᴛᴀɴᴛ ᴡᴀs ɴᴏᴛ ɪɴ ᴄᴀʟʟ).</i>"
    ASSISTANT_NOT_STREAMING    = "❌ | <b>ᴀssɪsᴛᴀɴᴛ ɪs ɴᴏᴛ sᴛʀᴇᴀᴍɪɴɢ ᴀɴʏᴛʜɪɴɢ ʀɪɢʜᴛ ɴᴏᴡ.</b>"
    NO_ACTIVE_STREAM           = "❌ | <b>ɴᴏ ᴀᴄᴛɪᴠᴇ sᴛʀᴇᴀᴍ ꜰᴏᴜɴᴅ.</b>"
    SKIPPED_SUCCESS            = "✅ | <b>sᴋɪᴘᴘᴇᴅ ᴛᴏ ɴᴇxᴛ ᴛʀᴀᴄᴋ.</b>"
    QUEUE_EMPTY_STREAM_ENDED   = "⏺ | <b>ǫᴜᴇᴜᴇ ᴇɴᴅᴇᴅ. sᴛʀᴇᴀᴍ sᴛᴏᴘᴘᴇᴅ.</b>"

    AUTO_LEAVE_EMPTY = "⚠️ | <b>ɴᴏ ʟɪsᴛᴇɴᴇʀs ᴅᴇᴛᴇᴄᴛᴇᴅ.</b> <i>ʟᴇᴀᴠɪɴɢ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ.</i>"
    AUTO_LEAVE_ONE   = "⚠️ | <b>ᴏɴʟʏ ᴏɴᴇ ʟɪsᴛᴇɴᴇʀ ʀᴇᴍᴀɪɴᴇᴅ.</b> <i>ᴀssɪsᴛᴀɴᴛ ʟᴇꜰᴛ.</i>"
    ERROR_STREAM     = "❌ | <b>ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴀ ᴠᴀʟɪᴅ sᴛʀᴇᴀᴍ sᴏᴜʀᴄᴇ.</b>"
    QUEUE_EMPTY      = "⏺ | <b>ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ.</b>"

    # ──────────────────────────────────────────────
    #  🔐  ADMIN / AUTH
    # ──────────────────────────────────────────────

    ADMIN_UNKNOWN_USER       = "⚠️ | <b>ᴄᴀɴɴᴏᴛ ᴠᴇʀɪꜰʏ ᴀᴅᴍɪɴ sᴛᴀᴛᴜs ꜰᴏʀ ᴛʜɪs ᴜsᴇʀ.</b>"
    ADMIN_RESTRICTED_ACTION  = "🔐 | <b>ᴛʜɪs ᴀᴄᴛɪᴏɴ ɪs ʀᴇsᴛʀɪᴄᴛᴇᴅ ᴛᴏ ᴀᴅᴍɪɴs ᴏɴʟʏ.</b>"
    ADMIN_RESTRICTED_CMD     = "🔐 | <b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪs ʀᴇsᴛʀɪᴄᴛᴇᴅ ᴛᴏ ᴀᴅᴍɪɴs ᴏɴʟʏ.</b>"
    AUTH_FAILED              = "❌ | <b>ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ᴄʜᴇᴄᴋ ꜰᴀɪʟᴇᴅ.</b>"
    OWNER_AUTH_ALL           = "👮 | <b>ᴏᴡɴᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴇᴠᴇʀʏᴡʜᴇʀᴇ.</b>"
    USER_AUTH                = "✅ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ʜᴀs ʙᴇᴇɴ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.</b>"
    USER_ALREADY_AUTH        = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>"
    CANT_AUTH_SELF           = "❌ | <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ᴀɴᴏɴʏᴍᴏᴜs ᴜsᴇʀs.</b>"
    NOT_FROM_USER            = "❌ | <b>ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪs ɴᴏᴛ ꜰʀᴏᴍ ᴀ ᴜsᴇʀ.</b>"
    INVALID_USER_ID          = "❌ | <b>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ᴜsᴇʀ ɪᴅ.</b>"
    REPLY_OR_PROVIDE_ID      = "⚠️ | <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴜsᴇʀ ɪᴅ.</b>"
    CANT_REMOVE_AUTH_OWNER   = "❌ | <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴀᴜᴛʜᴏʀɪᴢᴀᴛɪᴏɴ ꜰʀᴏᴍ ᴏᴡɴᴇʀ.</b>"
    USER_REMOVED_AUTH        = "✅ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ʜᴀs ʙᴇᴇɴ ᴜɴᴀᴜᴛʜ'd.</b>"
    USER_NOT_AUTH            = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.</b>"

    # ──────────────────────────────────────────────
    #  🚫  BLOCKLIST
    # ──────────────────────────────────────────────

    USER_BLOCKED              = "🚫 | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴛᴏ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    USER_ALREADY_BLOCKED      = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ᴀʟʀᴇᴀᴅʏ ɪɴ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    CANT_BLOCK_SELF           = "❌ | <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙʟᴏᴄᴋ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ᴀɴᴏɴʏᴍᴏᴜs ᴜsᴇʀs.</b>"
    OWNER_BLOCK_RESTRICT      = "❌ | <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙʟᴏᴄᴋ ᴛʜᴇ ᴏᴡɴᴇʀ.</b>"
    REMOVED_FROM_BLOCKLIST    = "✅ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    NOT_IN_BLOCKLIST          = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ɴᴏᴛ ɪɴ ʙʟᴏᴄᴋʟɪsᴛ.</b>"
    NO_BLOCKLIST              = "⏺ | <b>ɴᴏ ʙʟᴏᴄᴋʟɪsᴛ ꜰᴏᴜɴᴅ.</b>"
    NO_USERS_BLOCKED          = "⏺ | <b>ɴᴏ ᴜsᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ʙʟᴏᴄᴋᴇᴅ.</b>"

    # ──────────────────────────────────────────────
    #  🔑  SUDO
    # ──────────────────────────────────────────────

    PAID_OWNER_CMD        = "🔑 | <b>ᴘᴀɪᴅ ᴏᴡɴᴇʀ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>"
    NO_SUDO_USERS         = "⏺ | <b>ɴᴏ sᴜᴅᴏ ᴜsᴇʀs ꜰᴏᴜɴᴅ.</b>"
    ERR_FETCH_SUDO        = "❌ | <b>ᴇʀʀᴏʀ ꜰᴇᴛᴄʜɪɴɢ sᴜᴅᴏ ʟɪsᴛ:</b> <code>{}</code>"
    OWNER_CMD             = "🔑 | <b>ᴏᴡɴᴇʀ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>"
    ALREADY_OWNER         = "⚠️ | <b>ᴛʜɪs ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴏᴡɴᴇʀ.</b>"
    USER_ADDED_SUDO       = "✅ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴛᴏ sᴜᴅᴏᴇʀs.</b>"
    USER_ALREADY_SUDO     = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ᴀʟʀᴇᴀᴅʏ ɪɴ sᴜᴅᴏᴇʀs.</b>"
    CANT_SUDO_SELF        = "❌ | <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴀᴅᴅ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ᴛʜᴇ ʙᴏᴛ ᴛᴏ sᴜᴅᴏᴇʀs.</b>"
    CANT_REMOVE_OWNER_SUDO= "❌ | <b>ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴏᴡɴᴇʀ ꜰʀᴏᴍ sᴜᴅᴏ ʟɪsᴛ.</b>"
    USER_NOT_IN_DB        = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ɴᴏᴛ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ.</b>"
    USER_REMOVED_SUDO     = "✅ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ sᴜᴅᴏᴇʀs.</b>"
    USER_NOT_IN_SUDO      = "⚠️ | <b>ᴜsᴇʀ</b> <code>{}</code> <b>ɪs ɴᴏᴛ ɪɴ sᴜᴅᴏ ʟɪsᴛ.</b>"
    CANT_REMOVE_SELF_SUDO = "❌ | <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ʏᴏᴜʀsᴇʟꜰ ᴏʀ ᴛʜᴇ ʙᴏᴛ ꜰʀᴏᴍ sᴜᴅᴏᴇʀs.</b>"

    # ──────────────────────────────────────────────
    #  🔎  SEEK
    # ──────────────────────────────────────────────

    SEEK_NO_ARGS         = "⚠️ | <b>ᴘʀᴏᴠɪᴅᴇ sᴇᴇᴋ ᴛɪᴍᴇ ɪɴ sᴇᴄᴏɴᴅs.</b>\n<i>ᴜsᴀɢᴇ: /seek &lt;seconds&gt;</i>"
    SEEK_NEGATIVE        = "❌ | <b>sᴇᴇᴋ ᴛɪᴍᴇ ᴄᴀɴɴᴏᴛ ʙᴇ ɴᴇɢᴀᴛɪᴠᴇ.</b>"
    SEEK_INVALID         = "❌ | <b>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ᴏꜰ sᴇᴄᴏɴᴅs.</b>"
    SEEK_BEYOND_REMAINING= "❌ | <b>ᴄᴀɴɴᴏᴛ sᴇᴇᴋ ʙᴇʏᴏɴᴅ ʀᴇᴍᴀɪɴɪɴɢ ᴅᴜʀᴀᴛɪᴏɴ.</b>"
    SEEK_BEYOND_PLAYED   = "❌ | <b>ᴄᴀɴɴᴏᴛ sᴇᴇᴋ ʙᴀᴄᴋ ᴍᴏʀᴇ ᴛʜᴀɴ ᴀʟʀᴇᴀᴅʏ ᴘʟᴀʏᴇᴅ.</b>"

    # ──────────────────────────────────────────────
    #  🔁  LOOP
    # ──────────────────────────────────────────────

    LOOP_NO_ARGS       = "⚠️ | <b>ᴘʀᴏᴠɪᴅᴇ ɴᴜᴍʙᴇʀ ᴏꜰ ʟᴏᴏᴘs.</b>\n<i>ᴜsᴀɢᴇ: /loop &lt;count&gt;</i>"
    LOOP_OUT_OF_BOUNDS = "❌ | <b>ʟᴏᴏᴘ ᴄᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 1 ᴀɴᴅ 20.</b>"
    LOOP_INVALID       = "❌ | <b>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ʟᴏᴏᴘ ᴄᴏᴜɴᴛ.</b>"

    # ──────────────────────────────────────────────
    #  ❌  ERRORS
    # ──────────────────────────────────────────────

    ERROR_OCCURRED      = "❌ | <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ:</b>"
    ERROR_PERMISSIONS   = "❌ | <b>ꜰᴀɪʟᴇᴅ ᴛᴏ ᴄʜᴇᴄᴋ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs.</b>"
    ERROR_USER_NOT_FOUND= "❌ | <b>ᴜsᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b> <i>ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɪᴅ.</i>"
    ERROR_DEL_MSG       = "❌ | <b>ᴇʀʀᴏʀ ᴅᴇʟᴇᴛɪɴɢ ᴍᴇssᴀɢᴇ:</b> <code>{}</code>"

    # ──────────────────────────────────────────────
    #  ⚙️  SYSTEM / STATUS
    # ──────────────────────────────────────────────

    LOADING              = "🔄 | <b>ʟᴏᴀᴅɪɴɢ…</b>"
    GETTING_STREAM_INFO  = "🔄 | <b>ꜰᴇᴛᴄʜɪɴɢ sᴛʀᴇᴀᴍ ɪɴꜰᴏ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ…</b>"
    GETTING_CHATS        = "🔄 | <b>ꜰᴇᴛᴄʜɪɴɢ ᴄʜᴀᴛs, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ…</b>"
    BOLT                 = "⚡ | <b>ᴘʀᴏᴄᴇssɪɴɢ…</b>"
    PROCESSING           = "🔄 | <b>ᴘʀᴏᴄᴇssɪɴɢ…</b>"
    PINGING              = "🔄 | <b>ᴘɪɴɢɪɴɢ…</b>"
    COLLECTING_STATS     = "📊 | <b>ᴄᴏʟʟᴇᴄᴛɪɴɢ sᴛᴀᴛs…</b>"
    REBOOTING            = "🔄 | <b>ʀᴇʙᴏᴏᴛɪɴɢ ʙᴏᴛ ᴘʀᴏᴄᴇss…</b>"

    # ──────────────────────────────────────────────
    #  📢  BROADCAST
    # ──────────────────────────────────────────────

    START_BOT_BROADCAST      = "📢 | <b>sᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀsᴛ ꜰʀᴏᴍ ʙᴏᴛ ᴀᴄᴄᴏᴜɴᴛ…</b>"
    START_ASSISTANT_BROADCAST= "📢 | <b>sᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀsᴛ ꜰʀᴏᴍ ᴀssɪsᴛᴀɴᴛ ᴀᴄᴄᴏᴜɴᴛ…</b>"
    REPLY_TO_BROADCAST       = "⚠️ | <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ɪᴛ.</b>"
    NO_MSG_FOR_BROADCAST     = "⚠️ | <b>ɴᴏ ᴍᴇssᴀɢᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ꜰᴏʀ ʙʀᴏᴀᴅᴄᴀsᴛ.</b>"

    # ──────────────────────────────────────────────
    #  🛠️  MISC / TOOLS
    # ──────────────────────────────────────────────

    OWNER_SUDO_CMD        = "🔑 | <b>ᴏᴡɴᴇʀ/sᴜᴅᴏ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>"
    BOT_OWNER_ONLY        = "🔑 | <b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ᴛᴏ ʙᴏᴛ ᴏᴡɴᴇʀ ᴏɴʟʏ.</b>"
    NO_TAGALL             = "⚠️ | <b>ɴᴏ ᴛᴀɢ-ᴀʟʟ sᴇssɪᴏɴ ꜰᴏᴜɴᴅ.</b>"
    DISMISS_MENTION       = "✅ | <b>ᴍᴇɴᴛɪᴏɴ ᴅɪsᴍɪssᴇᴅ.</b>"
    REPLY_TO_DEL          = "⚠️ | <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴅᴇʟᴇᴛᴇ ɪᴛ.</b>"
    GROUP_ONLY            = "⚠️ | <b>ᴘʟᴀʏ ᴄᴏᴍᴍᴀɴᴅs ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs.</b>"
    NO_LINKED_CHANNEL     = "⚠️ | <b>ᴛʜɪs ɢʀᴏᴜᴘ ʜᴀs ɴᴏ ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ.</b>"
    USER_DATA_NOT_FOUND   = "❌ | <b>ᴜsᴇʀ ᴅᴀᴛᴀ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b>"
    NO_DATA_FOUND         = "❌ | <b>ɴᴏ ᴅᴀᴛᴀ ꜰᴏᴜɴᴅ.</b>"
    USE_COMMAND_AS_USER   = "⚠️ | <b>ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴀs ᴀ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ.</b>"

    NO_PERM_END_SESSION = "🔐 | <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴇɴᴅ ᴛʜᴇ sᴇssɪᴏɴ.</b>"
    NO_PERM_SKIP        = "🔐 | <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ sᴋɪᴘ.</b>"
    NO_PERM_RESUME      = "🔐 | <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ʀᴇsᴜᴍᴇ.</b>"
    NO_PERM_PAUSE       = "🔐 | <b>ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴘᴀᴜsᴇ.</b>"

    # ──────────────────────────────────────────────
    #  🖼️  MEDIA / STICKERS
    # ──────────────────────────────────────────────

    STICKER_LONG         = "⚠️ | <b>sᴛɪᴄᴋᴇʀ ᴘʀᴏᴄᴇssɪɴɢ ᴍᴀʏ ᴛᴀᴋᴇ ʟᴏɴɢᴇʀ ꜰᴏʀ ʟᴀʀɢᴇ ᴘᴀᴄᴋs.</b>"
    REPLY_TO_PHOTO_OR_STICKER = "⚠️ | <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ sᴛɪᴄᴋᴇʀ.</b>"
    ONLY_MEDIA_ALLOWED   = "❌ | <b>ᴏɴʟʏ ᴘʜᴏᴛᴏs, ᴠɪᴅᴇᴏs, ɢɪꜰs, ᴀɴᴅ sᴛɪᴄᴋᴇʀs ᴀʀᴇ ᴀʟʟᴏᴡᴇᴅ.</b>"
    MEDIA_SIZE_EXCEED    = "❌ | <b>ᴍᴇᴅɪᴀ sɪᴢᴇ ᴍᴜsᴛ ʙᴇ ʙᴇʟᴏᴡ 5 ᴍʙ.</b>"
    ERROR_MEDIA_PROCESS  = "❌ | <b>ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ᴍᴇᴅɪᴀ:</b> <code>{}</code>"
    NOTHING_TO_UPDATE    = "⚠️ | <b>ɴᴏᴛʜɪɴɢ ᴛᴏ ᴜᴘᴅᴀᴛᴇ.</b>"
    WELCOME_TOO_LONG     = "⚠️ | <b>ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ ɪs ᴛᴏᴏ ʟᴏɴɢ.</b> <i>ᴍᴀx 4096 ᴄʜᴀʀᴀᴄᴛᴇʀs.</i>"
    WELCOME_RESET        = "✅ | <b>ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ ᴀɴᴅ ʟᴏɢᴏ ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇsᴇᴛ.</b>"
    UNSUPPORTED_MEDIA    = "❌ | <b>ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ.</b>"
    STICKER_NO_NAME      = "❌ | <b>sᴛɪᴄᴋᴇʀ ʜᴀs ɴᴏ ᴠᴀʟɪᴅ ɴᴀᴍᴇ.</b>"
    UNSUPPORTED_FILE     = "❌ | <b>ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ꜰɪʟᴇ ᴛʏᴘᴇ.</b>"
    REPLY_TO_MEDIA       = "⚠️ | <b>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ/ɢɪꜰ/sᴛɪᴄᴋᴇʀ ᴍᴇᴅɪᴀ ꜰɪʀsᴛ.</b>"
    CREATING_STICKER_PACK= "🔄 | <b>ᴄʀᴇᴀᴛɪɴɢ ᴀ ɴᴇᴡ sᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ…</b>"

    # ──────────────────────────────────────────────
    #  🔍  SEARCH
    # ──────────────────────────────────────────────

    NO_QUERY_MATCH = "❌ | <b>ɴᴏ ᴍᴀᴛᴄʜɪɴɢ ʀᴇsᴜʟᴛ ꜰᴏᴜɴᴅ.</b> <i>ᴛʀʏ ᴀɴᴏᴛʜᴇʀ ǫᴜᴇʀʏ.</i>"
    NO_QUERY_GIVEN = "⚠️ | <b>ɴᴏ ǫᴜᴇʀʏ ᴘʀᴏᴠɪᴅᴇᴅ.</b>"

    NEED_INVITE_PERMISSION = "⚠️ | <b>ɪ ɴᴇᴇᴅ</b> <i>\"ɪɴᴠɪᴛᴇ ᴜsᴇʀs ᴠɪᴀ ʟɪɴᴋ\"</i> <b>ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴊᴏɪɴ ᴛʜɪs ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ.</b>"
    LINKED_CHANNEL_ERROR   = "❌ | <b>ꜰᴀɪʟᴇᴅ ᴛᴏ ᴀᴄᴄᴇss ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ.</b>"
    NO_OPERATIONAL_DATA    = "❌ | <b>ɴᴏ ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ ᴅᴀᴛᴀ ꜰᴏᴜɴᴅ ꜰᴏʀ ᴛʜɪs ʙᴏᴛ.</b>"
