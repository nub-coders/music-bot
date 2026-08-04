from utils.emoji import EmojiTag


class Messages:
    QUEUE = f"""<b>{EmojiTag.ADD} Added to Queue</b>
<b>Mode:</b> {{}}
<b>Title:</b> {{}}
<b>Duration:</b> {{}}
<b>Position:</b> #{{}}"""

    PLAY = f"""<b>{EmojiTag.PLAY} Now Playing</b>
<b>Mode:</b> {{}}
<b>Title:</b> {{}}
<b>Duration:</b> {{}}
<b>Requested by:</b> {{}}"""

    NO_STREAM = f"{EmojiTag.ERROR} No active stream right now."
    SKIPPING = f"<b>{EmojiTag.SKIP} Skipping current track...</b>\nRequested by: {{}}"
    SKIPPED_EMPTY = f"<b>{EmojiTag.SKIP} Queue is empty now.</b>\nRequested by: {{}}"
    RESUMED = f"<b>{EmojiTag.RESUME} Playback resumed.</b>\nRequested by: {{}}"
    PAUSED = f"<b>{EmojiTag.PAUSE} Playback paused.</b>\nRequested by: {{}}"
    AUTO_LEAVE_EMPTY = f"{EmojiTag.WARNING} No listeners detected. Leaving voice chat."
    AUTO_LEAVE_ONE = f"{EmojiTag.WARNING} Only one listener remained. Assistant left the voice chat."
    ERROR_STREAM = f"{EmojiTag.ERROR} Could not find a valid stream source."

    ADMIN_UNKNOWN_USER = f"{EmojiTag.WARNING} Cannot verify admin status for this user."
    ADMIN_RESTRICTED_ACTION = f"{EmojiTag.LOCK} This action is restricted to admins only."
    ADMIN_RESTRICTED_CMD = f"{EmojiTag.LOCK} This command is restricted to admins only."
    AUTH_FAILED = f"{EmojiTag.ERROR} Authorization check failed."

    SEEK_NO_ARGS = f"{EmojiTag.INFO} Provide seek time in seconds. Usage: /seek <seconds>"
    SEEK_NEGATIVE = f"{EmojiTag.ERROR} Seek time cannot be negative."
    SEEK_INVALID = f"{EmojiTag.ERROR} Provide a valid number of seconds."
    SEEK_BEYOND_REMAINING = f"{EmojiTag.WARNING} Cannot seek beyond remaining duration."
    SEEK_BEYOND_PLAYED = f"{EmojiTag.WARNING} Cannot seek back more than already played duration."

    LOOP_NO_ARGS = f"{EmojiTag.INFO} Provide number of loops. Usage: /loop <number>"
    LOOP_OUT_OF_BOUNDS = f"{EmojiTag.WARNING} Loop count must be between 1 and 20."
    LOOP_INVALID = f"{EmojiTag.ERROR} Provide a valid loop count."

    ERROR_OCCURRED = f"{EmojiTag.ERROR} An error occurred. Please try again."
    ERROR_PERMISSIONS = f"{EmojiTag.ERROR} Failed to check bot permissions."
    ERROR_USER_NOT_FOUND = f"{EmojiTag.ERROR} User not found. Provide a valid username or ID."

    QUEUE_EMPTY = f"{EmojiTag.QUEUE_ICON} Queue is empty."
    NOTHING_TO_SHUFFLE = f"{EmojiTag.WARNING} Need at least 2 tracks in the queue to shuffle."
    QUEUE_SHUFFLED = f"{EmojiTag.REFRESH} Shuffled {{}} upcoming track(s)."
    PLAYLIST_QUEUED = f"{EmojiTag.ADD} Added {{}} tracks from the playlist to the queue."
    OWNER_SUDO_CMD = f"{EmojiTag.KEY} Owner/Sudo only command."
    NO_TAGALL = f"{EmojiTag.WARNING} No tag-all session found."
    DISMISS_MENTION = f"{EmojiTag.SUCCESS} Mention dismissed."
    ERROR_DEL_MSG = f"{EmojiTag.ERROR} Error deleting message."
    REPLY_TO_DEL = f"{EmojiTag.INFO} Reply to a message to delete it."
    OWNER_AUTH_ALL = f"{EmojiTag.CROWN} Owner is already authorized everywhere."
    USER_AUTH = f"{EmojiTag.SUCCESS} User {{}} has been authorized in this chat."
    USER_ALREADY_AUTH = f"{EmojiTag.INFO} User {{}} is already authorized in this chat."
    CANT_AUTH_SELF = f"{EmojiTag.WARNING} You cannot authorize yourself or anonymous users."
    NOT_FROM_USER = f"{EmojiTag.WARNING} The replied message is not from a user."
    INVALID_USER_ID = f"{EmojiTag.ERROR} Provide a valid numeric user ID."
    REPLY_OR_PROVIDE_ID = f"{EmojiTag.INFO} Reply to a user or provide a user ID."
    OWNER_BLOCK_RESTRICT = f"{EmojiTag.WARNING} You cannot block the owner."
    CANT_REMOVE_AUTH_OWNER = f"{EmojiTag.WARNING} You cannot remove authorization from owner."
    USER_REMOVED_AUTH = f"{EmojiTag.SUCCESS} User {{}} has been removed from authorized users."
    USER_NOT_AUTH = f"{EmojiTag.WARNING} User {{}} is not authorized in this chat."
    USER_BLOCKED = f"{EmojiTag.BLOCKED} User {{}} has been added to blocklist."
    USER_ALREADY_BLOCKED = f"{EmojiTag.INFO} User {{}} is already in blocklist."
    CANT_BLOCK_SELF = f"{EmojiTag.WARNING} You cannot block yourself or anonymous users."
    REBOOTING = f"{EmojiTag.REFRESH} Rebooting bot process..."
    REMOVED_FROM_BLOCKLIST = f"{EmojiTag.SUCCESS} User {{}} has been removed from blocklist."
    NOT_IN_BLOCKLIST = f"{EmojiTag.INFO} User {{}} is not in blocklist."

    LOADING = f"{EmojiTag.LOADING} Loading..."
    GETTING_STREAM_INFO = f"{EmojiTag.LOADING} Fetching stream information, please wait..."
    GETTING_CHATS = f"{EmojiTag.LOADING} Fetching chats, please wait..."
    BOLT = f"{EmojiTag.BOLT} Processing..."

    START_BOT_BROADCAST = f"{EmojiTag.BROADCAST} Starting broadcast from bot account..."
    START_ASSISTANT_BROADCAST = f"{EmojiTag.BROADCAST} Starting broadcast from assistant account..."
    REPLY_TO_BROADCAST = f"{EmojiTag.INFO} Reply to a message to broadcast it."

    NO_BLOCKLIST = f"{EmojiTag.INFO} No blocklist found."
    NO_USERS_BLOCKED = f"{EmojiTag.INFO} No users are currently blocked."
    GROUP_ONLY = f"{EmojiTag.WARNING} Play commands can only be used in groups."
    NO_LINKED_CHANNEL = f"{EmojiTag.WARNING} This group has no linked channel."
    USER_DATA_NOT_FOUND = f"{EmojiTag.WARNING} User data not found."
    NO_DATA_FOUND = f"{EmojiTag.WARNING} No data found."

    COLLECTING_STATS = f"{EmojiTag.STATS} Collecting stats..."
    PINGING = f"{EmojiTag.PING} Pinging..."

    NO_PERM_END_SESSION = f"{EmojiTag.LOCK} You do not have permission to end the session."
    NO_PERM_SKIP = f"{EmojiTag.LOCK} You do not have permission to skip."
    NO_PERM_RESUME = f"{EmojiTag.LOCK} You do not have permission to resume."
    NO_PERM_PAUSE = f"{EmojiTag.LOCK} You do not have permission to pause."
    BOT_OWNER_ONLY = f"{EmojiTag.OWNER} This command is available to bot owner only."

    STREAM_ENDED = f"{EmojiTag.SUCCESS} Stream ended successfully."
    STREAM_ENDED_NOT_IN_CALL = f"{EmojiTag.INFO} Stream ended (assistant was not in call)."
    ASSISTANT_NOT_STREAMING = f"{EmojiTag.INFO} Assistant is not streaming anything right now."
    NO_ACTIVE_STREAM = f"{EmojiTag.ERROR} No active stream found."
    SKIPPED_SUCCESS = f"{EmojiTag.SUCCESS} Skipped to next track."
    QUEUE_EMPTY_STREAM_ENDED = f"{EmojiTag.QUEUE_ICON} Queue ended. Stream stopped."

    NO_MSG_FOR_BROADCAST = f"{EmojiTag.WARNING} No message available for broadcast."
    USE_COMMAND_AS_USER = f"{EmojiTag.WARNING} Use this command as a user account."
    STICKER_LONG = f"{EmojiTag.INFO} Sticker processing may take longer for large packs."
    REPLY_TO_PHOTO_OR_STICKER = f"{EmojiTag.INFO} Reply to a photo or sticker."
    PROCESSING = f"{EmojiTag.LOADING} Processing..."
    ONLY_MEDIA_ALLOWED = f"{EmojiTag.WARNING} Only photos, videos, GIFs, and stickers are allowed."
    MEDIA_SIZE_EXCEED = f"{EmojiTag.WARNING} Media size must be below 5 MB."
    ERROR_MEDIA_PROCESS = f"{EmojiTag.ERROR} Error processing media. Please try a different file."
    NOTHING_TO_UPDATE = f"{EmojiTag.INFO} Nothing to update."
    WELCOME_TOO_LONG = f"{EmojiTag.WARNING} Welcome message is too long. Max 4096 characters."
    WELCOME_RESET = f"{EmojiTag.SUCCESS} Welcome message and logo have been reset."

    UNSUPPORTED_MEDIA = f"{EmojiTag.WARNING} Unsupported media type."
    NO_QUERY_MATCH = f"{EmojiTag.ERROR} No matching result found. Try another query."
    NO_QUERY_GIVEN = f"{EmojiTag.INFO} No query provided."
    NEED_INVITE_PERMISSION = f"{EmojiTag.LOCK} I need 'Invite Users via Link' permission to join this private group."
    LINKED_CHANNEL_ERROR = f"{EmojiTag.ERROR} Failed to access linked channel."
    NO_OPERATIONAL_DATA = f"{EmojiTag.INFO} No operational data found for this bot."

    STICKER_NO_NAME = f"{EmojiTag.WARNING} Sticker has no valid name."
    UNSUPPORTED_FILE = f"{EmojiTag.WARNING} Unsupported file type."
    REPLY_TO_MEDIA = f"{EmojiTag.INFO} Reply to photo/GIF/sticker media first."
    CREATING_STICKER_PACK = f"{EmojiTag.KANG} Creating a new sticker pack..."

    PAID_OWNER_CMD = f"{EmojiTag.OWNER} Paid owner only command."
    NO_SUDO_USERS = f"{EmojiTag.INFO} No sudo users found."
    ERR_FETCH_SUDO = f"{EmojiTag.ERROR} Error while fetching sudo list."
    RATE_LIMITED = f"{EmojiTag.WARNING} You're sending play commands too fast. Please wait a moment."
    OWNER_CMD = f"{EmojiTag.OWNER} Owner only command."
    ALREADY_OWNER = f"{EmojiTag.INFO} This user is already owner."
    USER_ADDED_SUDO = f"{EmojiTag.SUCCESS} User {{}} has been added to sudoers list."
    USER_ALREADY_SUDO = f"{EmojiTag.INFO} User {{}} is already in sudoers list."
    CANT_SUDO_SELF = f"{EmojiTag.WARNING} You cannot add yourself or the bot to sudoers."
    CANT_REMOVE_OWNER_SUDO = f"{EmojiTag.WARNING} Cannot remove owner from sudo list."
    USER_NOT_IN_DB = f"{EmojiTag.WARNING} User {{}} is not in database."
    USER_REMOVED_SUDO = f"{EmojiTag.SUCCESS} User {{}} has been removed from sudoers list."
    USER_NOT_IN_SUDO = f"{EmojiTag.WARNING} User {{}} is not in sudoers list."
    CANT_REMOVE_SELF_SUDO = f"{EmojiTag.WARNING} You cannot remove yourself or the bot from sudoers."
