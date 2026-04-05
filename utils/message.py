class UniformFormat:
    def __init__(self, text):
        self.text = text

    def __getitem__(self, key):
        return self.text

    def get(self, key, default=None):
        return self.text


class Messages:
    QUEUE = UniformFormat(
        """**➕ Added to Queue**
**Mode:** {}
**Title:** {}
**Duration:** {}
**Position:** #{}"""
    )

    PLAY = UniformFormat(
        """**▶ Now Playing**
**Mode:** {}
**Title:** {}
**Duration:** {}
**Requested by:** {}"""
    )

    NO_STREAM = "No active stream right now."
    SKIPPING = "**⏭ Skipping current track...**\nRequested by: {}"
    SKIPPED_EMPTY = "**Queue is empty now.**\nRequested by: {}"
    RESUMED = "**⏯ Playback resumed.**\nRequested by: {}"
    PAUSED = "**⏸ Playback paused.**\nRequested by: {}"
    AUTO_LEAVE_EMPTY = "No listeners detected. Leaving voice chat."
    AUTO_LEAVE_ONE = "Only one listener remained. Assistant left the voice chat."
    ERROR_STREAM = "Could not find a valid stream source."

    ADMIN_UNKNOWN_USER = "Cannot verify admin status for this user."
    ADMIN_RESTRICTED_ACTION = "This action is restricted to admins only."
    ADMIN_RESTRICTED_CMD = "This command is restricted to admins only."
    AUTH_FAILED = "Authorization check failed."

    SEEK_NO_ARGS = "Provide seek time in seconds. Usage: /seek <seconds>"
    SEEK_NEGATIVE = "Seek time cannot be negative."
    SEEK_INVALID = "Provide a valid number of seconds."
    SEEK_BEYOND_REMAINING = "Cannot seek beyond remaining duration."
    SEEK_BEYOND_PLAYED = "Cannot seek back more than already played duration."

    LOOP_NO_ARGS = "Provide number of loops. Usage: /loop <number>"
    LOOP_OUT_OF_BOUNDS = "Loop count must be between 1 and 20."
    LOOP_INVALID = "Provide a valid loop count."

    ERROR_OCCURRED = "An error occurred:"
    ERROR_PERMISSIONS = "Failed to check bot permissions."
    ERROR_USER_NOT_FOUND = "User not found. Provide a valid username or ID."

    QUEUE_EMPTY = "Queue is empty."
    OWNER_SUDO_CMD = "Owner/Sudo only command."
    NO_TAGALL = "No tag-all session found."
    DISMISS_MENTION = "Mention dismissed."
    ERROR_DEL_MSG = "Error deleting message: {}"
    REPLY_TO_DEL = "Reply to a message to delete it."
    OWNER_AUTH_ALL = "Owner is already authorized everywhere."
    USER_AUTH = "User {} has been authorized in this chat."
    USER_ALREADY_AUTH = "User {} is already authorized in this chat."
    CANT_AUTH_SELF = "You cannot authorize yourself or anonymous users."
    NOT_FROM_USER = "The replied message is not from a user."
    INVALID_USER_ID = "Provide a valid numeric user ID."
    REPLY_OR_PROVIDE_ID = "Reply to a user or provide a user ID."
    OWNER_BLOCK_RESTRICT = "You cannot block the owner."
    CANT_REMOVE_AUTH_OWNER = "You cannot remove authorization from owner."
    USER_REMOVED_AUTH = "User {} has been removed from authorized users."
    USER_NOT_AUTH = "User {} is not authorized in this chat."
    USER_BLOCKED = "User {} has been added to blocklist."
    USER_ALREADY_BLOCKED = "User {} is already in blocklist."
    CANT_BLOCK_SELF = "You cannot block yourself or anonymous users."
    REBOOTING = "Rebooting bot process..."
    REMOVED_FROM_BLOCKLIST = "User {} has been removed from blocklist."
    NOT_IN_BLOCKLIST = "User {} is not in blocklist."

    LOADING = "Loading..."
    GETTING_STREAM_INFO = "Fetching stream information, please wait..."
    GETTING_CHATS = "Fetching chats, please wait..."
    BOLT = "⚡ Processing..."

    START_BOT_BROADCAST = "Starting broadcast from bot account..."
    START_ASSISTANT_BROADCAST = "Starting broadcast from assistant account..."
    REPLY_TO_BROADCAST = "Reply to a message to broadcast it."

    NO_BLOCKLIST = "No blocklist found."
    NO_USERS_BLOCKED = "No users are currently blocked."
    GROUP_ONLY = "Play commands can only be used in groups."
    NO_LINKED_CHANNEL = "This group has no linked channel."
    USER_DATA_NOT_FOUND = "User data not found."
    NO_DATA_FOUND = "No data found."

    COLLECTING_STATS = "Collecting stats..."
    PINGING = "Pinging..."

    NO_PERM_END_SESSION = "You do not have permission to end the session."
    NO_PERM_SKIP = "You do not have permission to skip."
    NO_PERM_RESUME = "You do not have permission to resume."
    NO_PERM_PAUSE = "You do not have permission to pause."
    BOT_OWNER_ONLY = "This command is available to bot owner only."

    STREAM_ENDED = "Stream ended successfully."
    STREAM_ENDED_NOT_IN_CALL = "Stream ended (assistant was not in call)."
    ASSISTANT_NOT_STREAMING = "Assistant is not streaming anything right now."
    NO_ACTIVE_STREAM = "No active stream found."
    SKIPPED_SUCCESS = "Skipped to next track."
    QUEUE_EMPTY_STREAM_ENDED = "Queue ended. Stream stopped."

    NO_MSG_FOR_BROADCAST = "No message available for broadcast."
    USE_COMMAND_AS_USER = "Use this command as a user account."
    STICKER_LONG = "Sticker processing may take longer for large packs."
    REPLY_TO_PHOTO_OR_STICKER = "Reply to a photo or sticker."
    PROCESSING = "Processing..."
    ONLY_MEDIA_ALLOWED = "Only photos, videos, GIFs, and stickers are allowed."
    MEDIA_SIZE_EXCEED = "Media size must be below 5 MB."
    ERROR_MEDIA_PROCESS = "Error processing media: {}"
    NOTHING_TO_UPDATE = "Nothing to update."
    WELCOME_TOO_LONG = "Welcome message is too long. Max 4096 characters."
    WELCOME_RESET = "Welcome message and logo have been reset."

    UNSUPPORTED_MEDIA = "Unsupported media type."
    NO_QUERY_MATCH = "No matching result found. Try another query."
    NO_QUERY_GIVEN = "No query provided."
    NEED_INVITE_PERMISSION = "I need 'Invite Users via Link' permission to join this private group."
    LINKED_CHANNEL_ERROR = "Failed to access linked channel."
    NO_OPERATIONAL_DATA = "No operational data found for this bot."

    STICKER_NO_NAME = "Sticker has no valid name."
    UNSUPPORTED_FILE = "Unsupported file type."
    REPLY_TO_MEDIA = "Reply to photo/GIF/sticker media first."
    CREATING_STICKER_PACK = "Creating a new sticker pack..."

    PAID_OWNER_CMD = "Paid owner only command."
    NO_SUDO_USERS = "No sudo users found."
    ERR_FETCH_SUDO = "Error while fetching sudo list: {}"
    OWNER_CMD = "Owner only command."
    ALREADY_OWNER = "This user is already owner."
    USER_ADDED_SUDO = "User {} has been added to sudoers list."
    USER_ALREADY_SUDO = "User {} is already in sudoers list."
    CANT_SUDO_SELF = "You cannot add yourself or the bot to sudoers."
    CANT_REMOVE_OWNER_SUDO = "Cannot remove owner from sudo list."
    USER_NOT_IN_DB = "User {} is not in database."
    USER_REMOVED_SUDO = "User {} has been removed from sudoers list."
    USER_NOT_IN_SUDO = "User {} is not in sudoers list."
    CANT_REMOVE_SELF_SUDO = "You cannot remove yourself or the bot from sudoers."
