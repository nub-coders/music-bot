"""
plugins/_common.py
Shared imports used by all plugin modules.
This file is NOT auto-loaded by Pyrogram (underscore prefix).
Every plugin file does: from plugins._common import *
"""

import asyncio
import datetime
import logging
import os
import re
import time
from functools import wraps

from pyrogram import Client, filters, enums
from pyrogram.enums import ChatType, ChatMemberStatus, ButtonStyle
from pyrogram.errors import (
    FloodWait, InviteHashExpired, ChannelPrivate,
    UserBlocked, PeerIdInvalid, MessageDeleteForbidden,
    StickersetInvalid, YouBlockedUser,
)
from pyrogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall
from pytgcalls.types import AudioQuality, MediaStream, VideoQuality

from config import *
from tools import (
    queues, playing, played, active, clients, spam_chats,
    SUDO, AUTH, BLOCK, TAGALL,
    get_admin_ids, get_readable_time, convert_bytes,
    join_call, remove_active_chat, get_stream_url,
    update_progress_button, autoleave_vc, pautoleave_vc,
    is_streamable, check_duration, trim_title,
    get_arg, clear_directory,
    gvarstatus,
)
from youtube import handle_youtube, extract_video_id, format_duration
from utils.message import Messages
from utils.button import Buttons
from utils.lang import get_str, get_lang, set_lang, LANGUAGES, lang_list_text
from database import (
    find_one, push_to_array, pull_from_array,
    set_fields, collection, user_sessions, db_task,
)

logger = logging.getLogger(__name__)
