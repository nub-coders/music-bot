import json
import subprocess
import requests
import re
import asyncio
import math
import os
import sys
import shlex
import time
import gc
import shutil
import textwrap
import datetime
import magic
import psutil

from io import BytesIO
from urllib.parse import parse_qs, urlparse
from re import sub
from typing import Tuple, Optional
from functools import wraps

from pyrogram import Client, filters, enums
from pyrogram.enums import ButtonStyle
from pyrogram.errors.exceptions import InviteHashExpired, ChannelPrivate
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from pytgcalls import idle, PyTgCalls
from pytgcalls.types import AudioQuality, MediaStream, VideoQuality, ChatUpdate, StreamEnded
from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall

from PIL import Image, ImageDraw, ImageFont
from pymediainfo import MediaInfo


from config import *
from youtube import handle_youtube, get_video_details, extract_video_id, format_number, format_duration, time_to_seconds
from database import user_sessions, db_task, collection

import logging
logger = logging.getLogger(__name__)

from utils.message import Messages
from utils.button import Buttons


def extract_best_format_url(formats):
    """Extract the best available format URL"""
    if not formats:
        return None

    # Priority: combined format (video+audio) > video+audio > video only
    for f in formats:
        if (f.get("acodec") != "none" and 
            f.get("vcodec") != "none" and 
            f.get("url")):
            return f.get("url")

    # Fallback to first available URL
    for f in formats:
        if f.get("url"):
            return f.get("url")

    return None


async def get_stream_url(youtube_url: str):
    """Get direct stream URL from YouTube link using optimized yt-dlp extraction. Returns input as-is if not a YouTube URL."""
    
    # Check if it's a YouTube URL
    youtube_pattern = r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    if not re.match(youtube_pattern, youtube_url):
        logger.info(f"Not a YouTube URL, returning as-is: {youtube_url[:50]}...")
        return youtube_url
    
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "cookiesfrombrowser": ("firefox",),

        # Performance optimizations
        "extract_flat": False,  # We need full info
        "writethumbnail": False,
        "writeinfojson": False,
        "writedescription": False,
        "writesubtitles": False,
        "writeautomaticsub": False,

        # Network optimizations  
        "http_chunk_size": 10485760,  # 10MB chunks
        "retries": 1,  # Reduce retries for speed
        "fragment_retries": 1,

        # Skip unnecessary processing
        "skip_playlist_after_errors": 1,
    }

    try:
        import yt_dlp

        def _sync_extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"📥 Extracting stream URL from YouTube: {youtube_url}")
                info = ydl.extract_info(youtube_url, download=False)
                return extract_best_format_url(info.get("formats", []))

        stream_url = await asyncio.to_thread(_sync_extract)

        if stream_url:
            logger.info(f"✅ Successfully extracted stream URL")
        else:
            logger.warning(f"⚠️ Could not extract stream URL")

        return stream_url

    except Exception as e:
        logger.error(f"❌ Error extracting stream URL: {e}")
        return None


temporary = {}
active = set()  # set for O(1) membership checks
playing = {}
queues = {}
clients = {}
played = {}
linkage = {}
conversations = {}
connector = {}
songs_client = {}
owners = {}
spam_chats = []

# In-memory TTL cache for play-style format (avoids DB hit on every join_call)
_format_style_cache: dict[int, tuple[int, float]] = {}  # {owner_id: (style_index, expire_ts)}
_FORMAT_CACHE_TTL = 120  # seconds
broadcasts = {}
broadcast_message = {}
SUDO = []
AUTH = {}
BLOCK = []

# In-memory cache for admin.txt to avoid repeated disk reads
_admin_ids_cache = None
_admin_cache_mtime = 0.0

def get_admin_ids(admin_file: str) -> list:
    """Return cached admin IDs from admin.txt, refresh only when file changes."""
    global _admin_ids_cache, _admin_cache_mtime
    try:
        mtime = os.path.getmtime(admin_file)
        if _admin_ids_cache is None or mtime != _admin_cache_mtime:
            with open(admin_file, "r") as f:
                _admin_ids_cache = [int(line.strip()) for line in f if line.strip()]
            _admin_cache_mtime = mtime
        return _admin_ids_cache
    except Exception:
        return []

def clear_directory(directory_path):
    """Clear all files and subdirectories in the given directory."""
    if not os.path.exists(directory_path):
        logger.warning(f"Directory {directory_path} does not exist.")
        return
    if not os.path.isdir(directory_path):
        logger.warning(f"{directory_path} is not a directory.")
        return
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            logger.warning(f"Failed to delete {item_path}: {e}")



def is_streamable(file_path):
    """
    Check if a file is potentially streamable.

    Args:
        file_path (str): Path to the file to be checked

    Returns:
        bool: True if file is potentially streamable, False otherwise
    """
    # Check if file exists
    if not os.path.exists(file_path):
        return False

    # Supported streamable file extensions
    STREAMABLE_EXTENSIONS = {
        'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', 
                  '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'},
        'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', 
                  '.wma', '.m4a', '.opus'}
    }

    try:
        # Get file extension
        file_extension = os.path.splitext(file_path)[1].lower()

        # Use python-magic for MIME type detection
        mime = magic.Magic(mime=True)
        detected_mime_type = mime.from_file(file_path)

        # Check streamability based on MIME type and extension
        is_video_mime = detected_mime_type.startswith('video/')
        is_audio_mime = detected_mime_type.startswith('audio/')

        is_video_ext = file_extension in STREAMABLE_EXTENSIONS['video']
        is_audio_ext = file_extension in STREAMABLE_EXTENSIONS['audio']

        # Return True if any streaming condition is met
        return is_video_mime or is_audio_mime or is_video_ext or is_audio_ext

    except Exception:
        return False

def get_arg(message):
    msg = message.text
    msg = msg.replace(" ", "", 1) if msg[1] == " " else msg
    split = msg[1:].replace("\n", " \n").split(" ")
    if " ".join(split[1:]).strip() == "":
      return ""
    return " ".join(split[1:])



async def is_active_chat(chat_id):
    return chat_id in active

async def add_active_chat(chat_id):
    active.add(chat_id)

async def remove_active_chat(chat_id):
    active.discard(chat_id)
    chat_dir = f"{ggg}/user_{clients['bot'].me.id}/{chat_id}"
    os.makedirs(chat_dir, exist_ok=True)
    clear_directory(chat_dir)


async def autoleave_vc(message, duration_str, chat):
    """
    Automatically leave voice chat when only the bot remains in the call.
    """
    while True:
        try:
            # Stop if song changed (duration changed = new song)
            song = playing.get(chat.id)
            if song and str(song.get('duration')) != str(duration_str):
                break
        except Exception:
            pass

        try:
            # Count members with a simple integer — no need to build a list
            member_count = 0
            solo_bot = False
            async for member in clients["session"].get_call_members(chat.id):
                member_count += 1
                if member_count == 1 and member.chat.id == clients["session"].me.id:
                    solo_bot = True
                elif member_count > 1:
                    solo_bot = False
                    break

            if member_count == 1 and solo_bot:
                await asyncio.sleep(25)  # Confirm persistent emptiness

                # Recheck
                member_count = 0
                solo_bot = False
                async for member in clients["session"].get_call_members(chat.id):
                    member_count += 1
                    if member_count == 1 and member.chat.id == clients["session"].me.id:
                        solo_bot = True
                    elif member_count > 1:
                        solo_bot = False
                        break

                if member_count == 1 and solo_bot:
                    await clients["call_py"].leave_call(chat.id)
                    try:
                        queues[chat.id].clear()
                        playing[chat.id].clear()
                    except KeyError:
                        pass
                    await remove_active_chat(chat.id)  # called once
                    await clients["bot"].send_message(
                        message.chat.id,
                        Messages.AUTO_LEAVE_EMPTY,
                        link_preview_options=None
                    )
                    break

        except Exception as e:
            logger.warning(f"Autoleave error: {e}")
            break

        await asyncio.sleep(8)
async def pautoleave_vc(message, duration_str):
    """
    Automatically leave voice chat when members count is <= 1.
    """
    while True:
        try:
            song = playing.get(message.chat.id)
            if song and str(song.get('duration')) != str(duration_str):
                break
        except Exception:
            pass

        # Count members with a simple integer — no need for a full list
        member_count = 0
        try:
            async for _ in clients["session"].get_call_members(message.chat.id):
                member_count += 1
                if member_count > 1:  # early exit — we only care about <= 1
                    break
        except Exception:
            break

        if member_count <= 1:
            await asyncio.sleep(5)  # Confirm for 5 seconds

            member_count = 0
            async for _ in clients["session"].get_call_members(message.chat.id):
                member_count += 1
                if member_count > 1:
                    break

            if member_count <= 1:
                await clients["call_py"].leave_call(message.chat.id)
                queues.pop(message.chat.id, None)
                playing.pop(message.chat.id, None)
                await remove_active_chat(message.chat.id)
                await clients["bot"].send_message(
                    message.chat.id,
                    Messages.AUTO_LEAVE_ONE,
                    link_preview_options=None
                )
                break

        # Wait before next check
        await asyncio.sleep(10)


async def update_progress_button(message, duration_str, chat):
    try:
        total_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration_str.split(":"))))

        while True:
            # Check elapsed time from pytgcalls
            try:
                elapsed_seconds = int(time.time() - played[chat.id])
            except Exception:
                break  # Song ended or chat removed

            # Stop updating if song changed
            try:
                song = playing.get(chat.id)
                if not song or str(song.get('duration')) != str(duration_str):
                    break
            except Exception:
                pass

            elapsed_str = time.strftime('%M:%S', time.gmtime(elapsed_seconds))

            # Progress bar (8 segments)
            progress_length = 8
            position = min(int((elapsed_seconds / total_seconds) * progress_length), progress_length)
            progress_bar = ("─ " * position + "▷" + "─ " * (progress_length - position - 1)).strip()
            progress_text = f"{elapsed_str} {progress_bar} {duration_str}"

            # Update keyboard in-place (insert progress bar between first and last rows)
            keyboard = message.reply_markup.inline_keyboard
            progress_row = [InlineKeyboardButton(text=progress_text, callback_data="ignore")]
            updated_keyboard = keyboard[:1] + [progress_row] + keyboard[1:]

            try:
                await message.edit_reply_markup(InlineKeyboardMarkup(updated_keyboard))
            except Exception:
                break  # Message deleted or bot lacks permission

            await asyncio.sleep(9)
    except Exception as e:
        logger.warning(f"Progress update error: {e}")


def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "ᴍ", "ʜ", "ᴅᴀʏs"]
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for i in range(len(time_list)):
        time_list[i] = str(time_list[i]) + time_suffix_list[i]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "
    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time



def convert_bytes(size: float) -> str:
    """humanize size"""
    if not size:
        return ""
    power = 1024
    t_n = 0
    power_dict = {0: " ", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    while size > power:
        size /= power
        t_n += 1
    return "{:.2f} {}B".format(size, power_dict[t_n])


def int_to_alpha(user_id: int) -> str:
    alphabet = "abcdefghij"
    return "".join(alphabet[int(d)] for d in str(user_id))


def alpha_to_int(user_id_alphabet: str) -> int:
    alphabet = "abcdefghij"
    return int("".join(str(alphabet.index(c)) for c in user_id_alphabet))




def seconds_to_min(seconds):
    if seconds is not None:
        seconds = int(seconds)
        d, h, m, s = (
            seconds // (3600 * 24),
            seconds // 3600 % 24,
            seconds % 3600 // 60,
            seconds % 3600 % 60,
        )
        if d > 0:
            return "{:02d}:{:02d}:{:02d}:{:02d}".format(d, h, m, s)
        elif h > 0:
            return "{:02d}:{:02d}:{:02d}".format(h, m, s)
        elif m > 0:
            return "{:02d}:{:02d}".format(m, s)
        elif s > 0:
            return "00:{:02d}".format(s)
    return "-"


def speed_converter(seconds, speed):
    speed = float(speed)
    if speed == 0.5:
        seconds = seconds * 2
    elif speed == 0.75:
        seconds = seconds + ((50 * seconds) // 100)
    elif speed == 1.5:
        seconds = seconds - ((25 * seconds) // 100)
    elif speed == 2.0:
        seconds = seconds - ((50 * seconds) // 100)
    collect = seconds
    if seconds is not None:
        seconds = int(seconds)
        d, h, m, s = (
            seconds // (3600 * 24),
            seconds // 3600 % 24,
            seconds % 3600 // 60,
            seconds % 3600 % 60,
        )
        if d > 0:
            return "{:02d}:{:02d}:{:02d}:{:02d}".format(d, h, m, s), collect
        elif h > 0:
            return "{:02d}:{:02d}:{:02d}".format(h, m, s), collect
        elif m > 0:
            return "{:02d}:{:02d}".format(m, s), collect
        elif s > 0:
            return "00:{:02d}".format(s), collect
    return "-"


def check_duration(file_path):
    command = [
        "ffprobe",
        "-loglevel",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = pipe.communicate()
    _json = json.loads(out)

    if "format" in _json:
        if "duration" in _json["format"]:
            return float(_json["format"]["duration"])

    if "streams" in _json:
        for s in _json["streams"]:
            if "duration" in s:
                return float(s["duration"])

    return "Unknown"


# frozenset for O(1) membership checks
formats = frozenset([
    "webm", "mkv", "flv", "vob", "ogv", "ogg", "rrc", "gifv", "mng",
    "mov", "avi", "qt", "wmv", "yuv", "rm", "asf", "amv", "mp4", "m4p",
    "m4v", "mpg", "mp2", "mpeg", "mpe", "mpv", "svi", "3gp", "3g2",
    "mxf", "roq", "nsv", "f4v", "f4p", "f4a", "f4b",
])

async def convert_to_image(message, client) -> [None, str]:
    """Convert Most Media Formats To Raw Image"""
    if not message:
        return None
    if not message.reply_to_message:
        return None
    final_path = None
    if not (
        message.reply_to_message.video
        or message.reply_to_message.photo
        or message.reply_to_message.sticker
        or message.reply_to_message.media
        or message.reply_to_message.animation
        or message.reply_to_message.audio
    ):
        return None
    if message.reply_to_message.photo:
        final_path = await message.reply_to_message.download()
    elif message.reply_to_message.sticker:
        if message.reply_to_message.sticker.mime_type == "image/webp":
            final_path = "webp_to_png_s_proton.png"
            path_s = await message.reply_to_message.download()
            im = Image.open(path_s)
            im.save(final_path, "PNG")
        else:
            path_s = await client.download_media(message.reply_to_message)
            final_path = "lottie_proton.png"
            cmd = (
                f"lottie_convert.py --frame 0 -if lottie -of png {path_s} {final_path}"
            )
            await run_cmd(cmd)
    elif message.reply_to_message.audio:
        thumb = message.reply_to_message.audio.thumbs[0].file_id
        final_path = await client.download_media(thumb)
    elif message.reply_to_message.video or message.reply_to_message.animation:
        final_path = "fetched_thumb.png"
        vid_path = await client.download_media(message.reply_to_message)
        await run_cmd(f"ffmpeg -i {vid_path} -filter:v scale=500:500 -an {final_path}")
    return final_path                                                                                     




async def resize_media(media: str, video: bool, fast_forward: bool) -> str:
    if video:
        _mi = MediaInfo.parse(media)
        video_track = next((t for t in _mi.tracks if t.track_type == "Video"), None)
        general_track = next((t for t in _mi.tracks if t.track_type == "General"), None)
        width = int(video_track.width) if video_track and video_track.width else 512
        height = int(video_track.height) if video_track and video_track.height else 512
        duration_ms = float(general_track.duration) if general_track and general_track.duration else 3000
        s = round(duration_ms) / 1000

        if height == width:
            height, width = 512, 512
        elif height > width:
            height, width = 512, -1
        elif width > height:
            height, width = -1, 512

        resized_video = f"{media}.webm"
        if fast_forward:
            if s > 3:
                fract_ = 3 / s
                ff_f = round(fract_, 2)
                set_pts_ = ff_f - 0.01 if ff_f > fract_ else ff_f
                cmd_f = f"-filter:v 'setpts={set_pts_}*PTS',scale={width}:{height}"
            else:
                cmd_f = f"-filter:v scale={width}:{height}"
        else:
            cmd_f = f"-filter:v scale={width}:{height}"
        fps_ = float(info_["frame_rate"])
        fps_cmd = "-r 30 " if fps_ > 30 else ""
        cmd = f"ffmpeg -i {media} {cmd_f} -ss 00:00:00 -to 00:00:03 -an -c:v libvpx-vp9 {fps_cmd}-fs 256K {resized_video}"
        _, error, __, ___ = await run_cmd(cmd)
        os.remove(media)
        return resized_video

    image = Image.open(media)
    maxsize = 512
    scale = maxsize / max(image.width, image.height)
    new_size = (int(image.width * scale), int(image.height * scale))

    image = image.resize(new_size, Image.LANCZOS)
    resized_photo = "sticker.png"
    image.save(resized_photo)
    os.remove(media)
    return resized_photo



async def add_text_img(image_path, text):
    font_size = 12
    stroke_width = 1

    if ";" in text:
        upper_text, lower_text = text.split(";")
    else:
        upper_text = text
        lower_text = ""

    img = Image.open(image_path).convert("RGBA")
    img_info = img.info
    image_width, image_height = img.size
    font = ImageFont.truetype(
        font="default.ttf",                                                                                       size=int(image_height * font_size) // 100,
    )
    draw = ImageDraw.Draw(img)

    char_width, char_height = draw.textbbox((0, 0), 'A', font=font)[2:4]
    chars_per_line = image_width // char_width
    top_lines = textwrap.wrap(upper_text, width=chars_per_line)
    bottom_lines = textwrap.wrap(lower_text, width=chars_per_line)

    if top_lines:
        y = 10
        for line in top_lines:
            line_width, line_height = draw.textbbox((0, 0), line, font=font)[2:4]
            x = (image_width - line_width) / 2
            draw.text(
                (x, y),
                line,
                fill="white",
                font=font,
                stroke_width=stroke_width,
            )
            y += line_height

    if bottom_lines:
        y = image_height - char_height * len(bottom_lines) - 15
        for line in bottom_lines:
            line_width, line_height = draw.textbbox((0, 0), line, font=font)[2:4]
            x = (image_width - line_width) / 2
            draw.text(
                (x, y),
                line,
                fill="black",
                font=font,
                stroke_width=stroke_width,
            )
            y += line_height

    final_image = os.path.join("memify.webp")
    img.save(final_image, **img_info)
    return final_image




async def hd_stream_closed_kicked(client, update):
    logger.info(update)
    chat_id = update.chat_id
    await remove_active_chat(chat_id)
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)


async def join_call(message, title, youtube_link, chat, by, duration, mode, thumb, stream_url=None, yt_task=None):
    """Join voice call and start streaming"""
    original_title = title
    title = trim_title(title)
    logger.debug(f"[join_call] Title trimmed from: {original_title} -> {title}")
    logger.info(f"[join_call] Starting join_call for chat {chat.id} (Title: {title}, Mode: {mode})")

    try:
        chat_id = chat.id
        audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None

        # ── Wait for YouTube task if we have no stream source yet ──────────────
        if not stream_url and not youtube_link and yt_task:
            for attempt in range(3):
                if yt_task.done():
                    break
                logger.info(
                    f"[join_call] No stream source yet — "
                    f"waiting for YouTube task (attempt {attempt + 1}/3)..."
                )
                await asyncio.sleep(1)

            if yt_task.done() and not yt_task.cancelled():
                try:
                    result = yt_task.result()
                    # handle_youtube returns:
                    # (title, duration, youtube_link, thumbnail,
                    #  channel_name, views, video_id, stream_url)
                    if result and result[2] and result[2] != 'N/A':
                        _title, _dur, _yt_link, _thumbnail, \
                            _channel, _views, _vid_id, _stream = result
                        if _yt_link and _yt_link != 'N/A':
                            youtube_link = _yt_link
                        if _stream and _stream != 'N/A':
                            stream_url = _stream
                        if _title and _title != 'N/A':
                            title = trim_title(_title)
                        if _dur and _dur != 'N/A':
                            duration = _dur
                        if thumb is None and _thumbnail and _thumbnail != 'N/A':
                            thumb = asyncio.create_task(
                                get_thumb(
                                    _title, str(_dur), _thumbnail,
                                    _channel, str(_views), _vid_id,
                                )
                            )
                            thumb.add_done_callback(
                                lambda t: t.exception() if not t.cancelled() else None
                            )
                        logger.info(f"[join_call] YouTube task resolved — title='{title}'")
                except Exception as e:
                    logger.warning(f"[join_call] yt_task result failed: {e}")
            else:
                logger.warning(f"[join_call] YouTube task not done after 3s — proceeding with None source")

        queue = queues.get(chat_id, [])
        position = len(queue)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[join_call] chat={chat_id} title='{title}' mode={mode} position={position} thumb={'set' if thumb else 'None'}")
        if stream_url:
            stream_source = stream_url
            logger.info(f"[join_call] Using provided stream URL: {stream_url[:100]}... (len={len(stream_url)})")
        elif youtube_link:
            logger.info(f"[join_call] Extracting stream URL from YouTube link: {youtube_link}")
            stream_source = await get_stream_url(youtube_link)
            if not stream_source:
                logger.warning(f"[join_call] Failed to extract stream URL, falling back to youtube_link")
                stream_source = youtube_link
            else:
                logger.info(f"[join_call] Successfully extracted stream URL: {stream_source[:100]}... (len={len(stream_source)})")
        else:
            logger.warning(f"[join_call] No stream_url or youtube_link provided")
            stream_source = None

        logger.debug(f"[join_call] Final stream source resolved: {stream_source[:120]}..." if stream_source else "[join_call] Final stream source resolved: None")
        if not stream_source:
            logger.error(f"[join_call] No stream source provided (neither stream_url nor youtube_link) for chat {chat_id}")
            await clients["bot"].send_message(chat.id, Messages.ERROR_STREAM, link_preview_options=None)
            return await remove_active_chat(chat_id)

        logger.info(f"[join_call] Attempting to play: {title} from {stream_source[:100]}... in chat {chat_id}")
        logger.debug(f"[join_call] Calling clients['call_py'].play with AudioQuality.MEDIUM and VideoQuality.HD_720p; audio_flags={audio_flags}")

        _jc_t0 = time.perf_counter()
        await clients["call_py"].play(
            chat_id,
            MediaStream(
                stream_source,
                AudioQuality.STUDIO,
                VideoQuality.HD_720p,
                video_flags=audio_flags,
            ),
        )
        _jc_call_ms = (time.perf_counter() - _jc_t0) * 1000
        logger.info(f"[join_call] ⏱ call_py.play() took {_jc_call_ms:.1f}ms for chat {chat_id}")

        logger.debug(f"[join_call] Updating playing status for chat {chat_id}")
        playing[chat_id] = {
            "message": message,
            "title": title,
            "yt_link": youtube_link,
            "stream_url": stream_source,
            "chat": chat,
            "by": by,
            "duration": duration,
            "mode": mode,
            "thumb": thumb
        }
        played[chat_id] = int(time.time())
        logger.debug(f"[join_call] Playing status updated, timestamp: {played[chat_id]}")

        logger.debug(f"[join_call] Scheduling playtime save to database for bot {clients['bot'].me.id}")
        db_task(collection.update_one(
            {"bot_id": clients["bot"].me.id},
            {"$push": {"dates": datetime.datetime.now()}},
            upsert=True
        ))

        logger.debug(f"[join_call] Creating inline keyboard for playback controls")
        keyboard = Buttons.playback_markup()


        logger.debug(f"[join_call] Constructing message text with play_styles")
        mode_formatted = mode
        title_formatted = title

        display_title = f"[{title_formatted}](https://t.me/{clients['bot'].me.username}?start=vidid_{extract_video_id(youtube_link)})" if youtube_link and not os.path.exists(youtube_link) else title_formatted

        try:
            _now = time.time()
            _cached = _format_style_cache.get(OWNER_ID)
            if _cached and _cached[1] > _now:
                style_index = _cached[0]
            else:
                _raw = await gvarstatus(OWNER_ID, "format")
                style_index = int(_raw or 11)
                _format_style_cache[OWNER_ID] = (style_index, _now + _FORMAT_CACHE_TTL)
        except Exception:
            style_index = 11
        logger.debug(f"[join_call] Using play_style index: {style_index}")

        message_text = Messages.PLAY.get(style_index, Messages.PLAY[11]).format(
            mode_formatted,
            display_title,
            duration,
            by.mention() if hasattr(by, 'mention') else by
        )

        logger.debug(f"[join_call] Sending playback notification to chat {message.chat.id}")
        _msg_t0 = time.perf_counter()
        if asyncio.isfuture(thumb) or asyncio.iscoroutine(thumb):
            try:
                thumb = await thumb
            except Exception as thumb_err:
                logger.warning(f"[join_call] Thumbnail task failed, sending text instead: {thumb_err}")
                thumb = None
        if thumb:
            try:
                sent_message = await clients["bot"].send_photo(
                    chat_id, thumb, message_text, reply_markup=keyboard
                )
                logger.info(f"[join_call] Playback notification sent with photo, message_id: {sent_message.id}")
            except Exception as photo_err:
                logger.warning(f"[join_call] Failed to send photo, sending as text instead: {photo_err}")
                sent_message = await clients["bot"].send_message(
                    chat_id, message_text, reply_markup=keyboard, 
                link_preview_options=None)
                logger.info(f"[join_call] Playback notification sent as text, message_id: {sent_message.id}")
        else:
            logger.warning(f"[join_call] Thumbnail is None, sending as text message")
            sent_message = await clients["bot"].send_message(
                chat_id, message_text, reply_markup=keyboard, 
            link_preview_options=None)
            logger.info(f"[join_call] Playback notification sent as text (no thumbnail), message_id: {sent_message.id}")
        _msg_ms = (time.perf_counter() - _msg_t0) * 1000
        logger.info(f"[join_call] ⏱ Now-playing message sent in {_msg_ms:.1f}ms for chat {chat_id}")

        logger.debug(f"[join_call] Creating progress update task for duration: {duration}")
        asyncio.create_task(update_progress_button(sent_message, duration, chat))

        try:
            logger.debug(f"[join_call] Attempting to delete original message")
            await message.delete()
            logger.debug(f"[join_call] Original message deleted successfully")
        except Exception as e:
            logger.warning(f"[join_call] Failed to delete original message: {e}")

        logger.info(f"[join_call] Completed successfully - Now streaming '{title}' in chat {chat_id}")

    except NoActiveGroupCall:
        logger.error(f"[join_call] NoActiveGroupCall exception for chat {chat.id} - No active group calls")
        await clients["bot"].send_message(chat.id, "ERROR: No active group calls", link_preview_options=None)
        return await remove_active_chat(chat.id)
    except Exception as e:
        logger.error(f"[join_call] Unexpected error in chat {chat.id}: {type(e).__name__} - {e}", exc_info=True)
        await clients["bot"].send_message(chat.id, f"ERROR: {e}", link_preview_options=None)
        return await remove_active_chat(chat.id)


async def end(client, update):
    db_task(collection.update_one(
        {"bot_id": clients["bot"].me.id},
        {"$push": {'dates': datetime.datetime.now()}},
        upsert=True
    ))
    try:
        if update.chat_id in queues and queues[update.chat_id]:
            next_song = queues[update.chat_id].pop(0)
            if update.chat_id in playing:
                if update.stream_type == StreamEnded.Type.VIDEO:
                    await client.leave_call(update.chat_id)
            playing[update.chat_id] = next_song
            await join_call(
                next_song['message'],
                next_song['title'],
                next_song['yt_link'],
                next_song['chat'],
                next_song['by'],
                next_song['duration'],
                next_song['mode'],
                next_song['thumb'],
                next_song.get('stream_url'),
                yt_task=next_song.get('_yt_task'),
            )
        else:
            logger.info(f"Song queue for chat {update.chat_id} is empty.")
            await client.leave_call(update.chat_id)
            await remove_active_chat(update.chat_id)
            playing[update.chat_id].clear()
    except Exception as e:
        logger.warning(f"Error in end function: {e}")






def trim_title(title):
    """
    Trim video title to 25 characters or 6 words, whichever is shorter.
    
    Args:
        title (str): The original video title
        
    Returns:
        str: The trimmed title
    """
    if not title:
        return ""
    
    # Split into words and take maximum 6 words
    words = title.split()
    if len(words) > 10:
        title = " ".join(words[:10])
    
    # If still longer than 25 characters, truncate
    if len(title) > 30:
        title = title[:30].rstrip()
    
    return title


# Aliases / helpers


async def get_user_data(user_id, key):
    user_data = await user_sessions.find_one({"user_id": user_id})
    if user_data and key in user_data:
        return user_data[key]
    return None

async def gvarstatus(user_id, key):
    return await get_user_data(user_id, key)




PLANS = {
    "standard": {"amount": 6900, "duration": 20, "merit": 0},   # ₹69 for 20 days
    "pro": {"amount": 17900, "duration": 60, "merit": 2}        # ₹180 for 60 days
}

# Appropriate tagall messages for when no text is provided
TAGALL = [
    "🎉 Hey everyone! Let's get this party started!",
    "📢 Attention all members! Something exciting is happening here!",
    "🌟 Good vibes only! Hope everyone is feeling awesome!",
    "💫 Just wanted to say hello to all our amazing members!",
    "🎵 Music brings us together! What's everyone listening to?",
    "🚀 Ready to rock and roll? Let's make some noise!",
    "✨ Spreading positive energy to all our wonderful members!",
    "🎊 Celebration time! Thanks for being part of this awesome community!",
    "🌈 Hope everyone is doing fantastic!",
    "🎭 Let's have some fun! What's everyone up to?",
    "🎨 Creativity flows here! Share your thoughts!",
    "🌺 Sending good wishes to all our lovely members!",
    "🎪 Welcome to our amazing community space!",
    "🌟 You all make this place special! Thank you!",
    "🎯 Let's make this awesome together!",
    "🎈 Balloon drop of positivity for everyone!",
    "🌻 Sunshine and smiles for all our members!",
    "🎼 Harmony and happiness to everyone here!",
    "🌙 Wishing everyone a wonderful time!",
    "⭐ You're all stars in this community!",
    "💝 Arre yaar, kya haal hai sabka? Miss kar raha tha sab ko!",
    "🔥 Dekho kaun aaya! Your favorite person is here 😉",
    "💕 Kya baat hai cuties, kitne sundar lag rahe ho!",
    "😘 Miss me? Of course you did! Main aa gaya hun 💫",
    "🥰 Hey gorgeous people! Tumhe dekh kar mood ban gaya!",
    "💖 Arey wah! Itne pyare log ek saath, my heart is full!",
    "🤗 Group hug time! Come here you lovely souls 💕",
    "✨ Tumlog ke bina group adhoora lagta hai yaar!",
    "💃 Dance karne ka mood hai! Kaun ready hai?",
    "🎶 Music on, vibe on! Let's make some memories!",
    "🌟 Shining bright like diamonds! That's all of you ✨",
    "💫 Kya scene hai? Someone looking extra cute 😍",
    "🔥 Hot people alert! Temperature badh gaya group mein 🌡️",
    "💕 Pyaar mohabbat ka mahaul hai! Love is in the air!",
    "😎 Cool gang assembled! Let's make this epic!",
    "🌈 Colors of happiness everywhere! Thanks to you all!",
    "💖 Heart melting moments with my favorite people!",
    "🥳 Party time! Sabko invite kar diya maine 🎉",
    "✨ Magic happens when we're all together!",
    "💝 Special delivery of love and good vibes for everyone!",
    "🌺 Fresh flowers ki tarah fresh vibes spread kar rahe ho!",
    "😘 Sending flying kisses to all my darlings! Catch them!",
    "💕 Romance in the air! Someone's looking absolutely stunning!",
    "🔥 Hotness overload! Can't handle so much beauty in one place!",
    "💫 Twinkling like stars! Each one of you is precious!",
    "🥰 Cuteness overload alert! My heart can't take it!",
    "🌹 Rose garden se bhi khoobsurat hai yeh group!",
    "💖 Dil churane wale log saare yahan present hain!",
    "😍 Eyes can't believe kitni beautiful souls yahan hain!",
    "🎭 Drama queens and kings! Entertainment guaranteed here!",
    "💃 Thumka lagane ka time! Who's ready to groove?",
    "🔥 Fire emoji bhi kam pad gaya tumhare hotness ke liye!",
    "💕 Cupid ne saare arrows yahan hi chala diye lagta hai!",
    "🌟 Celebrity vibes! Everyone's a star here ⭐",
    "😘 Muah muah! Virtual kisses for my favorite people!",
    "💖 Heart beats faster when I see you all online!",
    "🥳 Celebration mode on! Life's good with you guys!",
    "✨ Sparkling personalities! Diamonds bhi dull lage tumhare saamne!",
    "🌺 Blooming like flowers! Spring vibes everywhere!",
    "💫 Magical moments await! Ready for some fun?",
    "🦋 Butterfly effect! Your presence makes everything beautiful!",
    "💕 Love ke saamne sab chhota lagta hai! Especially when you're here!",
    "🔥 Spice conversations loading! Get ready!",
    "🌈 Rainbow vibes! That's how I feel when you're all here!",
    "😍 Can't stop staring! Beauty overload in this group!",
    "💖 Heartbeat skip kar gaya seeing you all active!",
    "🥰 Wish I could hug you all right now!",
    "🌟 Shining brighter than my future! And that's saying something!",
    "💝 Gift wrapped happiness! That's what you all are to me!",
    "😘 Flirt mode activated! Warning: Dangerous levels of charm ahead!",
    "🔥 Temperature rising! AC laga dena padega group mein!",
    "💕 Love potion ka effect! Everyone's under your spell!",
    "✨ Fairy tale vibes! Princess aur princes saare yahan hain!",
    "💖 Heartstrings pull ho rahe hain! Guitar baja dun kya?",
    "🥳 Party planning committee activated! Fun times ahead!",
    "🌺 Garden of Eden found! It's right here in this group!",
    "😍 Pinterest perfect! Tumhe screenshot lena padega!",
    "💫 Shooting star wishes come true! You all are proof!",
    "🦋 Heart and butterflies both dancing!",
    "💕 Romance novel ke characters lagte ho sab! Main character vibes!",
    "🔥 Too much hotness detected! Fire alarm beep kar raha hai!",
    "🌟 Hollywood celebrities bhi jealous honge tumse!",
    "😘 Everyone looks kissable! Kiss cam activated!",
    "💖 You healed my heartbreak hotel! Because you healed it!",
    "🥰 Teddy bear hugs for everyone! Soft and cuddly vibes!",
    "✨ Glitter bomb exploded! Sparkles everywhere because of you!",
    "🌈 You are my lucky charm! My fortune changed after meeting you!",
    "💝 Valentine's mood everyday! Romance never ends here!",
    "🔥 Spice girls and boys! Adding flavor to life!",
    "😍 Can't close my eyes! Beauty overload!",
    "💕 I need to write a love letter! Words fall short for you all!",
    "🥳 Celebration nation! Every moment is a festival with you guys!",
    "💖 Creating music with your presence! Heartbeat symphony!",
    "🌺 You all are a bouquet of happiness! Fresh and fragrant like you!",
    "😘 You have kissable lips! Lip sync battle!",
    "✨ Magic wand wave! And poof! Perfect people appeared!",
    "🦋 You transformed my world! Metamorphosis complete!",
    "💫 I wish upon a star! I hope to find someone like you!",
    "🔥 Doctor needed! Too much hotness detected!",
    "🌟 Everyone is Red carpet ready! Paparazzi will line up!",
    "💕 You are sweeter than chocolate! Got a sugar rush seeing you!",
    "😍 Beauty pageant winners! You all deserve a crown!",
    "💖 My heart is doing dhadak dhadak! Pulse rate check!",
    "🌈 You are my pot of gold! Lucky me to have you all!",
    "🎭 Drama queens assemble! Entertainment guaranteed always!",
    "💝 You have the gift of gab! Conversations flow like honey with you all!"
]
