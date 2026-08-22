import re
import html as _html
import asyncio
import uuid
from dataclasses import dataclass
import os
import time
import shutil
import textwrap
import datetime

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType
from pyrogram.errors import ChatAdminRequired, ChatWriteForbidden

from pytgcalls.types import AudioQuality, MediaStream, VideoQuality, StreamEnded
from pytgcalls.exceptions import NoActiveGroupCall

from PIL import Image, ImageDraw, ImageFont
from pymediainfo import MediaInfo


from config import *
from youtube import extract_video_id, get_stream, get_related_suggestions, handle_youtube
from database import (
    user_sessions, db_task, collection,
    get_chat_assistant as db_get_chat_assistant,
    set_chat_assistant as db_set_chat_assistant,
    remove_chat_assistant as db_remove_chat_assistant,
    set_last_played as db_set_last_played,
)

import logging
logger = logging.getLogger(__name__)

from utils.message import Messages
from utils.button import Buttons
from utils.emoji import keycaps
from utils.rich_ui import (
    rich_caption, rich_code, rich_edit, rich_esc, rich_note, rich_send, rich_table,
)
from thumbnails import get_thumb


async def get_stream_url(youtube_url: str):
    """Direct stream URL for a YouTube link. Non-YouTube URLs are returned as-is.

    Delegates to youtube.get_stream, the single hardened extraction path
    (exec-arglist, 40s timeout, mem+disk cache, YT_COOKIES_FILE — no silent
    browser-profile fallback). This used to be a second, inferior yt-dlp
    Python-API implementation with no timeout or cache.
    """
    youtube_pattern = r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    if not re.match(youtube_pattern, youtube_url):
        logger.info(f"Not a YouTube URL, returning as-is: {youtube_url[:50]}...")
        return youtube_url

    return await get_stream(youtube_url)


from state import state  # state.queues / playing / played / active now live on this store

clients = {}
assistants = {}      # idx (1..5) -> Pyrogram Client
calls = {}           # idx (1..5) -> PyTgCalls instance
assistant_info = {}  # idx (1..5) -> dict(id, name, username, mention)
spam_chats = []


def get_assistant_count() -> int:
    """Return the total number of connected assistants."""
    return len(assistants) if assistants else 1


_assistant_alloc_lock = asyncio.Lock()


def get_least_loaded_assistant() -> int:
    """Return the assistant index (1..N) with the fewest active voice calls."""
    if not assistants:
        return 1
    active_keys = sorted(assistants.keys())

    def get_load(idx: int) -> int:
        active_count = len(state.assistant_active.get(idx, set()))
        assigned_active_count = sum(
            1 for cid in state.active
            if state.get_chat_assistant(cid) == idx and cid not in state.assistant_active.get(idx, set())
        )
        return active_count + assigned_active_count

    return min(active_keys, key=get_load)


async def get_assistant(chat_id: int):
    """
    Retrieve the assigned (assistant_num, userbot_client, pytgcalls_client) for chat_id.
    Resolution order: in-memory state -> MongoDB -> least-loaded allocation.
    Guarded by _assistant_alloc_lock to prevent concurrent allocation race conditions.
    """
    cid = int(chat_id)
    async with _assistant_alloc_lock:
        # 1. In-memory cache
        ast_num = state.get_chat_assistant(cid)
        if ast_num and ast_num in assistants:
            return ast_num, assistants[ast_num], calls.get(ast_num, clients.get("call_py"))
        elif ast_num:
            state.remove_chat_assistant(cid)

        # 2. Database persistent assignment
        db_num = await db_get_chat_assistant(cid)
        if db_num:
            if db_num in assistants:
                state.set_chat_assistant(cid, db_num)
                return db_num, assistants[db_num], calls.get(db_num, clients.get("call_py"))
            else:
                db_task(db_remove_chat_assistant(cid))

        # 3. Dynamic least-loaded allocation
        assigned = get_least_loaded_assistant()
        state.set_chat_assistant(cid, assigned)
        db_task(db_set_chat_assistant(cid, assigned))
        userbot = assistants.get(assigned, clients.get("session"))
        call_py = calls.get(assigned, clients.get("call_py"))
        return assigned, userbot, call_py


async def set_assistant(chat_id: int, assistant_num: int):
    """Explicitly assign an assistant index (1..N) to chat_id."""
    cid = int(chat_id)
    ast_num = int(assistant_num)
    state.set_chat_assistant(cid, ast_num)
    await db_set_chat_assistant(cid, ast_num)


async def change_assistant(chat_id: int):
    """Switch to the next available assistant in the pool."""
    cid = int(chat_id)
    if not assistants:
        return 1, clients.get("session"), clients.get("call_py")
    available = sorted(assistants.keys())
    curr = state.get_chat_assistant(cid) or 1
    if curr in available:
        next_idx = available[(available.index(curr) + 1) % len(available)]
    else:
        next_idx = available[0]
    await set_assistant(cid, next_idx)
    return next_idx, assistants.get(next_idx), calls.get(next_idx)


def get_call_client(chat_id: int):
    """Retrieve the PyTgCalls instance responsible for this chat."""
    cid = int(chat_id)
    ast_num = state.get_chat_assistant(cid)
    if ast_num and ast_num in calls:
        return calls[ast_num]
    playing_info = state.playing.get(cid)
    if playing_info and isinstance(playing_info, dict) and "assistant_num" in playing_info:
        p_num = playing_info["assistant_num"]
        if p_num in calls:
            return calls[p_num]
    return clients.get("call_py")


def get_userbot_client(chat_id: int):
    """Retrieve the Pyrogram userbot Client responsible for this chat."""
    cid = int(chat_id)
    ast_num = state.get_chat_assistant(cid)
    if ast_num and ast_num in assistants:
        return assistants[ast_num]
    return clients.get("session")



@dataclass
class QueueEntry:
    """One queued track. Mapping-style reads (entry["title"], entry.get("x", d))
    are kept alongside attribute access so existing call sites work unchanged
    during the dict->dataclass transition. Field names match the old dict keys."""
    message: object
    title: object
    duration: object
    mode: object
    yt_link: object
    chat: object
    by: object
    session: object
    thumb: object
    stream_url: object = None
    _track_id: object = None
    _yt_task: object = None
    queue_msg: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __setitem__(self, key, value):
        setattr(self, key, value)


broadcasts = {}
broadcast_message = {}
SUDO = []
AUTH = {}
BLOCK = []
ADMIN = []  # owner-tier admin IDs, loaded from DB at startup (seeded via INITIAL_ADMIN_IDS)


# In-memory token bucket for throttling download/render-triggering commands per user.
# ponytail: single-process in-memory; move to Redis INCR+EXPIRE in Phase 4 for multi-worker.
_play_buckets = {}  # user_id -> (tokens: float, last_ts: float)


def allow_play(user_id: int, capacity: int = 3, refill_per_sec: float = 1 / 3) -> bool:
    """Token bucket: burst of `capacity`, then one action per ~3s. False = throttled."""
    now = time.time()
    tokens, last = _play_buckets.get(user_id, (float(capacity), now))
    tokens = min(capacity, tokens + (now - last) * refill_per_sec)
    if tokens < 1:
        _play_buckets[user_id] = (tokens, now)
        return False
    _play_buckets[user_id] = (tokens - 1, now)
    return True


def get_admin_ids(admin_file: str = "") -> list:
    """Return the in-memory admin ID list (DB-backed, populated at startup).

    Keeps the old file-path parameter for call-site compatibility; the argument
    is ignored — admins live in Mongo now, not admin.txt.
    """
    return ADMIN

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


def get_arg(message):
    msg = getattr(message, "text", "") or getattr(message, "caption", "") or ""
    if len(msg) < 2:
        return ""
    msg = msg.replace(" ", "", 1) if msg[1] == " " else msg
    split = msg[1:].replace("\n", " \n").split(" ")
    if " ".join(split[1:]).strip() == "":
        return ""
    return " ".join(split[1:])





async def remove_active_chat(chat_id):
    await state.deactivate(chat_id)
    db_task(db_remove_chat_assistant(chat_id))
    bot_client = clients.get("bot")
    bot_id = getattr(bot_client.me, "id", None) if bot_client and getattr(bot_client, "me", None) else "default"
    chat_dir = f"{ggg}/user_{bot_id}/{chat_id}"
    os.makedirs(chat_dir, exist_ok=True)
    clear_directory(chat_dir)


async def update_progress_button(message, duration_str, chat, markup):
    try:
        if not duration_str or duration_str in ("N/A", "Live", "0:00", "00:00") or ":" not in duration_str:
            return
        total_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration_str.split(":"))))
        if total_seconds <= 0:
            return

        while True:
            # Check elapsed time from pytgcalls
            try:
                elapsed_seconds = int(time.time() - state.played[chat.id])
            except Exception:
                break  # Song ended or chat removed

            # Stop updating if song changed
            try:
                song = state.playing.get(chat.id)
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
            # Uses the markup we built, not message.reply_markup: an icon only
            # survives a read-back if the echoed button still carries its style,
            # and the emoji vanishing on the first edit says it does not.
            keyboard = markup.inline_keyboard
            progress_row = [InlineKeyboardButton(text=progress_text, callback_data="ignore")]
            updated_keyboard = keyboard[:1] + [progress_row] + keyboard[1:]

            try:
                await message.edit_reply_markup(InlineKeyboardMarkup(updated_keyboard))
            except Exception:
                break  # Message deleted or bot lacks permission

            await asyncio.sleep(9)
    except Exception as e:
        logger.warning(f"Progress update error: {e}")


async def count_listeners(chat_id: int) -> int:
    """Count non-bot, active human participants currently in the voice chat."""
    session = get_userbot_client(chat_id)
    if not session:
        return 1
    try:
        listeners = 0
        async for member in session.get_call_members(chat_id):
            if getattr(member, "is_left", False):
                continue
            session_id = getattr(session.me, "id", None) if hasattr(session, "me") and session.me else None
            if getattr(member, "is_self", False) or (session_id and getattr(member.chat, "id", None) == session_id):
                continue
            listeners += 1
        return listeners
    except Exception as e:
        logger.warning(f"[count_listeners] Could not fetch call members for chat {chat_id}: {e}")
        return 1


async def autoleave_vc(chat_id: int) -> bool:
    """
    Quickly check if voice chat has listeners. If empty, leave call and clean up immediately.
    Returns True if call was empty and left, False if listeners are present.
    """
    try:
        listeners = await count_listeners(chat_id)
        if listeners == 0:
            logger.info(f"[autoleave_vc] No listeners detected in chat {chat_id}. Leaving voice chat immediately.")
            call_py = get_call_client(chat_id)
            if call_py:
                try:
                    await call_py.leave_call(chat_id)
                except Exception:
                    pass
            state.queues.pop(chat_id, None)
            state.playing.pop(chat_id, None)
            await remove_active_chat(chat_id)
            await state.delete_now_playing(chat_id)
            bot = clients.get("bot")
            if bot:
                try:
                    await rich_send(
                        bot,
                        chat_id,
                        rich_note(Messages.AUTO_LEAVE_EMPTY),
                        reply_markup=Buttons.autoleave_markup(),
                    )
                except Exception:
                    pass
            return True
    except Exception as e:
        logger.warning(f"[autoleave_vc] Error: {e}")
    return False



async def _swap_in_photo(thumb_task, ui_chat_id, chat_id, text, keyboard, text_msg, chat, duration):
    """Replace a text now-playing message with the photo card once the render lands.
    Telegram can't edit text->media, so this is delete + resend — the card jumps to
    the bottom of a busy chat, which is why it's only the fallback when the render
    misses the send grace, not the normal path."""
    try:
        path = await thumb_task
    except Exception:
        return
    if not path:
        return
    try:
        photo_msg = await clients["bot"].send_photo(ui_chat_id, path, rich_caption(text), reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"[_swap_in_photo] send_photo failed, keeping text: {e}")
        return
    try:
        await text_msg.delete()
    except Exception:
        pass
    state.set_now_playing(chat_id, photo_msg)
    asyncio.create_task(update_progress_button(photo_msg, duration, chat, keyboard))


async def get_readable_time(seconds: int) -> str:
    return str(datetime.timedelta(seconds=int(seconds)))



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


async def run_cmd(args: list):
    """Execute a command (argv list, no shell) asynchronously and return (stdout, stderr, exit_code, pid)."""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode().strip() if stdout else "",
            stderr.decode().strip() if stderr else "",
            process.returncode,
            process.pid,
        )
    except FileNotFoundError as e:
        cmd_name = args[0] if args else "unknown"
        logger.error(f"[run_cmd] Executable not found: {cmd_name}")
        return ("", f"Executable not found: {cmd_name} ({e})", 127, -1)
    except Exception as e:
        logger.error(f"[run_cmd] Error executing {args}: {e}")
        return ("", str(e), 1, -1)


async def convert_to_image(message, client) -> str | None:
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
            final_path = f"webp_to_png_{uuid.uuid4().hex[:8]}.png"
            path_s = await message.reply_to_message.download()
            im = Image.open(path_s)
            im.save(final_path, "PNG")
        else:
            path_s = await client.download_media(message.reply_to_message)
            final_path = f"lottie_{uuid.uuid4().hex[:8]}.png"
            await run_cmd([
                "lottie_convert.py", "--frame", "0",
                "-if", "lottie", "-of", "png", path_s, final_path,
            ])
    elif message.reply_to_message.audio:
        thumb = message.reply_to_message.audio.thumbs[0].file_id
        final_path = await client.download_media(thumb)
    elif message.reply_to_message.video or message.reply_to_message.animation:
        final_path = f"fetched_thumb_{uuid.uuid4().hex[:8]}.png"
        vid_path = await client.download_media(message.reply_to_message)
        await run_cmd([
            "ffmpeg", "-i", vid_path,
            "-filter:v", "scale=500:500", "-an", final_path,
        ])
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
        if fast_forward and s > 3:
            fract_ = 3 / s
            ff_f = round(fract_, 2)
            set_pts_ = ff_f - 0.01 if ff_f > fract_ else ff_f
            vf = f"setpts={set_pts_}*PTS,scale={width}:{height}"
        else:
            vf = f"scale={width}:{height}"
        fps_ = float(video_track.frame_rate) if video_track and video_track.frame_rate else 30.0
        cmd = [
            "ffmpeg", "-i", media,
            "-filter:v", vf,
            "-ss", "00:00:00", "-to", "00:00:03",
            "-an", "-c:v", "libvpx-vp9",
        ]
        if fps_ > 30:
            cmd += ["-r", "30"]
        cmd += ["-fs", "256K", resized_video]
        _, error, __, ___ = await run_cmd(cmd)
        os.remove(media)
        return resized_video

    image = Image.open(media)
    maxsize = 512
    scale = maxsize / max(image.width, image.height)
    new_size = (int(image.width * scale), int(image.height * scale))

    image = image.resize(new_size, Image.LANCZOS)
    resized_photo = f"sticker_{uuid.uuid4().hex[:8]}.png"
    image.save(resized_photo)
    os.remove(media)
    return resized_photo



async def add_text_img(image_path, text):
    font_size = 12

    if ";" in text:
        upper_text, lower_text = text.split(";", 1)
    else:
        upper_text = text
        lower_text = ""

    font_path = "default.ttf"
    if not os.path.exists(font_path):
        base_dir = os.path.dirname(__file__)
        font_path = os.path.join(base_dir, "default.ttf")

    is_video = str(image_path).endswith((".webm", ".mp4", ".mkv", ".mov"))

    if is_video:
        import subprocess
        import json
        import shutil

        image_width, image_height = 512, 512
        probed = False

        if shutil.which("ffprobe"):
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "json", image_path
                ]
                out = subprocess.check_output(probe_cmd)
                probe_data = json.loads(out)
                streams = probe_data.get("streams", [])
                if streams and "width" in streams[0] and "height" in streams[0]:
                    image_width = int(streams[0]["width"])
                    image_height = int(streams[0]["height"])
                    probed = True
            except Exception as e:
                logger.warning(f"[add_text_img] ffprobe probe failed: {e}")

        if not probed:
            try:
                from pymediainfo import MediaInfo
                _mi = MediaInfo.parse(image_path)
                vt = next((t for t in _mi.tracks if t.track_type == "Video"), None)
                if vt and vt.width and vt.height:
                    image_width = int(vt.width)
                    image_height = int(vt.height)
                    probed = True
            except Exception:
                pass

        if not probed:
            try:
                import cv2
                cap = cv2.VideoCapture(str(image_path))
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    image_width, image_height = w, h
                    probed = True
            except Exception:
                pass

        overlay = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_px = max(12, int(image_height * font_size) // 100)
        font = ImageFont.truetype(font_path, size=font_px)
        stroke_width = max(1, font_px // 18)

        char_width, char_height = draw.textbbox((0, 0), "A", font=font)[2:4]
        chars_per_line = max(1, image_width // max(1, char_width))
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
                    stroke_fill="black",
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
                    fill="white",
                    font=font,
                    stroke_width=stroke_width,
                    stroke_fill="black",
                )
                y += line_height

        # Scratch + output files belong in the cache dir, not the CWD (= repo
        # root), where they accumulate forever and mix with the source tree.
        _meme_dir = os.path.join(ggg, "cache")
        os.makedirs(_meme_dir, exist_ok=True)
        overlay_temp = os.path.join(_meme_dir, f"temp_overlay_{uuid.uuid4().hex[:8]}.png")
        overlay.save(overlay_temp)

        if not shutil.which("ffmpeg"):
            if os.path.exists(overlay_temp):
                os.remove(overlay_temp)
            raise RuntimeError("ffmpeg is not installed on this system. Please install ffmpeg to create video memes.")

        final_video = os.path.join(_meme_dir, f"memify_{uuid.uuid4().hex[:8]}.webm")
        try:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", image_path,
                "-i", overlay_temp,
                "-filter_complex", "[0:v][1:v]overlay=0:0",
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-b:v", "500k",
                "-an",
                "-t", "3",
                final_video
            ]
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return final_video
        finally:
            if os.path.exists(overlay_temp):
                os.remove(overlay_temp)

    img = Image.open(image_path).convert("RGBA")
    img_info = img.info
    image_width, image_height = img.size
    font_px = max(12, int(image_height * font_size) // 100)
    font = ImageFont.truetype(font_path, size=font_px)
    stroke_width = max(1, font_px // 18)
    draw = ImageDraw.Draw(img)

    char_width, char_height = draw.textbbox((0, 0), "A", font=font)[2:4]
    chars_per_line = max(1, image_width // max(1, char_width))
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
                stroke_fill="black",
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
                fill="white",
                font=font,
                stroke_width=stroke_width,
                stroke_fill="black",
            )
            y += line_height

    _meme_dir = os.path.join(ggg, "cache")
    os.makedirs(_meme_dir, exist_ok=True)
    final_image = os.path.join(_meme_dir, f"memify_{uuid.uuid4().hex[:8]}.webp")
    img.save(final_image, **{str(k): v for k, v in img_info.items()})
    return final_image




async def hd_stream_closed_kicked(client, update):
    logger.info(update)
    chat_id = update.chat_id
    # Registered for both CLOSED_VOICE_CHAT and KICKED, which Telegram often
    # delivers together; without this guard the second delivery re-runs the
    # whole teardown (leave_call on a call we already left, another round of
    # state pops) and logs spurious errors. state.active is the single source
    # of truth for "there is still something to tear down".
    if chat_id not in state.active:
        logger.debug(f"[hd_stream_closed_kicked] Chat {chat_id} already torn down; ignoring duplicate update")
        return
    # A KICKED update means membership is gone; drop the cached confirmation so
    # the next /play re-runs the join handshake rather than trusting it.
    state.forget_member(None, chat_id)
    await remove_active_chat(chat_id)
    state.queues.pop(chat_id, None)
    state.playing.pop(chat_id, None)


async def join_call(message, title, youtube_link, chat, by, duration, mode, thumb, stream_url=None, yt_task=None, queue_msg=None, assistant_num=None):
    """Join voice call and start streaming"""
    original_title = title
    title = trim_title(title)
    logger.debug(f"[join_call] Title trimmed from: {original_title} -> {title}")
    logger.info(f"[join_call] Starting join_call for chat {chat.id} (Title: {title}, Mode: {mode})")

    try:
        chat_id = chat.id
        ui_chat_id = message.chat.id if (message and hasattr(message, 'chat') and message.chat) else chat_id
        audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None

        # Clean up old messages: delete previous track's now-playing card and this track's queue card
        await state.delete_now_playing(chat_id)
        if queue_msg:
            try:
                await queue_msg.delete()
            except Exception:
                pass
        if message and message != queue_msg:
            try:
                await message.delete()
            except Exception:
                pass

        # ── Wait for YouTube task if we have no stream source or incomplete metadata ──
        # ponytail: await the task we depend on (up to 30s) instead of proceeding sourceless
        # or with placeholder duration/title.
        # shield so a timeout here never cancels the task the queue also holds.
        if (not stream_url or duration in (None, "N/A", "00:00", "") or title in ("Suggested Track", "Unknown Media", "Playlist track")) and yt_task:
            logger.info("[join_call] Awaiting YouTube task for stream and metadata (max 30s)...")
            result = None
            try:
                result = await asyncio.wait_for(asyncio.shield(yt_task), timeout=30)
            except asyncio.TimeoutError:
                logger.warning("[join_call] YouTube task not done after 30s — proceeding with available source")
            except Exception as e:
                logger.warning(f"[join_call] yt_task failed: {e}")

            if result:
                try:
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
                        if _vid_id and _vid_id != 'N/A':
                            state.add_to_history(chat_id, _vid_id)
                        logger.info(f"[join_call] YouTube task resolved — title='{title}', duration='{duration}'")
                except Exception as e:
                    logger.warning(f"[join_call] yt_task result failed: {e}")

        queue = state.queues.get(chat_id, [])

        position = len(queue)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[join_call] chat={chat_id} title='{title}' mode={mode} position={position} thumb={'set' if thumb else 'None'}")
        if stream_url:
            stream_source = stream_url
            logger.info(f"[join_call] Using provided stream URL: {stream_source[:100]}... (len={len(stream_source)})")
        elif youtube_link:
            logger.info(f"[join_call] Extracting stream URL from YouTube link: {youtube_link}")
            stream_source = await get_stream_url(youtube_link)
            if not stream_source:
                logger.warning("[join_call] Failed to extract stream URL, falling back to youtube_link")
                stream_source = youtube_link
            else:
                logger.info(f"[join_call] Successfully extracted stream URL: {stream_source[:100]}... (len={len(stream_source)})")
        else:
            logger.warning("[join_call] No stream_url or youtube_link provided")
            stream_source = None

        logger.debug(f"[join_call] Final stream source resolved: {stream_source[:120]}..." if stream_source else "[join_call] Final stream source resolved: None")
        if not stream_source:
            logger.error(f"[join_call] No stream source provided (neither stream_url nor youtube_link) for chat {chat_id}")
            if "bot" in clients and clients["bot"]:
                await rich_send(clients["bot"], chat.id, rich_note(Messages.ERROR_STREAM))
            return await remove_active_chat(chat_id)

        # Resolve the active assistant and PyTgCalls instance
        if assistant_num is None:
            ast_num, _userbot, call_py = await get_assistant(chat_id)
        else:
            ast_num = int(assistant_num)
            call_py = calls.get(ast_num, clients.get("call_py"))

        if not call_py:
            call_py = clients.get("call_py")

        logger.info(f"[join_call] Attempting to play: {title} via Assistant {ast_num} from {stream_source[:100]}... in chat {chat_id}")
        logger.debug(f"[join_call] Calling call_py.play (Assistant {ast_num}); audio_flags={audio_flags}")

        _jc_t0 = time.perf_counter()
        await call_py.play(
            chat_id,
            MediaStream(
                stream_source,
                AudioQuality.STUDIO,
                VideoQuality.HD_720p,
                video_flags=audio_flags,
            ),
        )
        _jc_call_ms = (time.perf_counter() - _jc_t0) * 1000
        logger.info(f"[join_call] ⏱ call_py.play() took {_jc_call_ms:.1f}ms for chat {chat_id} (Assistant {ast_num})")

        # Mark chat active with this assistant
        await state.activate(chat_id, assistant_num=ast_num)

        logger.debug(f"[join_call] Updating playing status for chat {chat_id}")
        state.playing[chat_id] = {
            "message": message,
            "title": title,
            "yt_link": youtube_link,
            "stream_url": stream_source,
            "chat": chat,
            "by": by,
            "duration": duration,
            "mode": mode,
            "thumb": thumb,
            "assistant_num": ast_num,
        }
        state.played[chat_id] = int(time.time())
        state.last_played[chat_id] = state.playing[chat_id]
        # Persist alongside the in-memory value: the auto-leave sweep needs to
        # tell "idle" from "unknown" after a restart, and state.played is
        # process-local. Fire-and-forget so playback never waits on Mongo.
        db_task(db_set_last_played(chat_id, state.played[chat_id]))
        logger.debug(f"[join_call] Playing status updated, timestamp: {state.played[chat_id]}")

        if "bot" in clients and clients["bot"] and getattr(clients["bot"], "me", None):
            logger.debug(f"[join_call] Scheduling playtime save to database for bot {clients['bot'].me.id}")
            db_task(collection.update_one(
                {"bot_id": clients["bot"].me.id},
                {"$push": {"dates": {"$each": [datetime.datetime.now()], "$slice": -5000}}},
                upsert=True
            ))

        logger.debug("[join_call] Creating inline keyboard for playback controls")
        is_channel = (ui_chat_id != chat_id) or (getattr(chat, 'type', None) in (ChatType.CHANNEL, "ChatType.CHANNEL"))
        keyboard = Buttons.playback_markup(channel_mode=is_channel)


        logger.debug("[join_call] Constructing message text with play_styles")
        mode_formatted = mode
        title_formatted = _html.escape(trim_title(title))

        video_id = extract_video_id(youtube_link) if youtube_link and not os.path.exists(youtube_link) else None
        bot_user = clients["bot"].me.username if "bot" in clients and clients["bot"] and getattr(clients["bot"], "me", None) else ""
        if video_id:
            state.add_to_history(chat_id, video_id)
            display_title = f'<a href="https://t.me/{bot_user}?start=vidid_{video_id}"><b>{title_formatted}</b></a>' if bot_user else f'<b>{title_formatted}</b>'
        elif youtube_link and youtube_link.startswith("http"):
            display_title = f'<a href="{youtube_link}"><b>{title_formatted}</b></a>'
        else:
            display_title = f'<b>{title_formatted}</b>'

        requester_mention = by.mention() if hasattr(by, 'mention') else (by if by else "User")

        text = Messages.PLAY.format(
            mode_formatted.capitalize(),
            display_title,
            duration,
            requester_mention,
        )

        logger.debug(f"[join_call] Sending now playing message to ui_chat_id {ui_chat_id}")
        sent_message = None

        # ── Fast-path: thumbnail already cached ──
        # If get_thumb returned immediately (cached file on disk), we already
        # have a finished Task with the path: send the photo card directly.
        # No intermediate text message, no photo-replace jump.
        if thumb and thumb.done() and not thumb.cancelled():
            try:
                path = thumb.result()
                if path and os.path.exists(path):
                    # Captions can't be rich; `text` is inline-tag only already.
                    sent_message = await clients["bot"].send_photo(
                        ui_chat_id, path, caption=rich_caption(text), reply_markup=keyboard,
                    )
            except Exception as e:
                logger.warning(f"[join_call] Cached photo send failed, falling back to text: {e}")
                sent_message = None

        if not sent_message and "bot" in clients and clients["bot"]:
            sent_message = await rich_send(
                clients["bot"], ui_chat_id, text, reply_markup=keyboard
            )

        if sent_message:
            state.set_now_playing(chat_id, sent_message)

        # ── Slow-path: thumbnail is still downloading / rendering ──
        # We sent a text message above; once the thumb task finishes, swap in
        # the photo card so the chat gets the full artwork without delay on voice join.
        if thumb and not thumb.done():
            asyncio.create_task(
                _swap_in_photo(
                    thumb, ui_chat_id, chat_id, text, keyboard,
                    sent_message, chat, duration,
                )
            )

        logger.info(f"[join_call] Successfully started playing: {title} in chat {chat_id} (Assistant {ast_num})")

        # In-place progress bar loop (cancelled via state.delete_now_playing or replaced)
        if sent_message and duration and duration not in ("N/A", "Live", "0:00", "00:00") and ":" in duration:
            asyncio.create_task(update_progress_button(sent_message, duration, chat, keyboard))

    except NoActiveGroupCall:
        logger.warning(f"[join_call] No active voice chat in {chat_id}. Cleaning up.")
        await remove_active_chat(chat_id)
        if "bot" in clients and clients["bot"]:
            await rich_send(clients["bot"], ui_chat_id, rich_note(Messages.NO_ACTIVE_VC))
    except Exception as e:
        logger.error(f"[join_call] Error playing media in chat {chat_id}: {str(e)}", exc_info=True)
        # play() is the first thing that actually exercises membership, so this is
        # where a stale "assistant is a member" cache entry surfaces (kicked,
        # banned, or left since we cached it). Drop it so the next /play redoes
        # the full join handshake instead of failing forever on the fast path.
        state.forget_member(None, chat_id)
        await remove_active_chat(chat_id)
        err_str = str(e).lower()
        if "bot" in clients and clients["bot"]:
            if "chat_admin_required" in err_str or "admin" in err_str:
                await rich_send(clients["bot"], ui_chat_id, rich_note(Messages.NEED_INVITE_PERMISSION))
            elif "user_already_participant" in err_str:
                logger.info(f"[join_call] Assistant was already in call for chat {chat_id}")
            else:
                await rich_send(clients["bot"], ui_chat_id, rich_note(Messages.ERROR_OCCURRED))


async def _trigger_suggestions(client, chat_id: int, last_song: dict):
    """
    Called when a chat's queue is empty and playback has ended.
    Fetches suggestions related to the last played track and posts an interactive
    suggestion card with a 5-second countdown to autoplay the top result.
    """
    try:
        last_vid = None
        seed_title = last_song.get("title", "")
        yt_link = last_song.get("yt_link", "")

        if yt_link:
            last_vid = extract_video_id(yt_link)
        if not last_vid and last_song.get("video_id"):
            last_vid = last_song.get("video_id")

        if not last_vid:
            logger.info(f"[Suggest] No video_id extractable for chat {chat_id} from {yt_link}; leaving call.")
            await state.delete_now_playing(chat_id)
            await client.leave_call(chat_id)
            await remove_active_chat(chat_id)
            return

        exclude_ids = state.get_history_ids(chat_id)
        exclude_ids.add(last_vid)

        suggestions = await get_related_suggestions(last_vid, exclude_ids=exclude_ids, limit=5)

        if not suggestions:
            logger.info(f"[Suggest] No related suggestions found for {last_vid} in chat {chat_id}; leaving call.")
            await state.delete_now_playing(chat_id)
            await client.leave_call(chat_id)
            await remove_active_chat(chat_id)
            return

        for s in suggestions:
            vid = s.get("video_id")
            if vid:
                state.add_to_history(chat_id, vid)

        lines = []
        for idx, item in enumerate(suggestions[:5], 1):
            s_title = trim_title(item.get("title", "Unknown"))
            s_artist = item.get("artist", "")
            s_dur = item.get("duration", "")
            lines.append((
                keycaps(idx),
                f"<b>{rich_esc(s_title)}</b>",
                f"<i>{rich_esc(s_artist)}</i>" if s_artist else "",
                rich_code(s_dur) if s_dur else "",
            ))
        # Native table replaces the old newline-joined bullet list; it fills the
        # same `{1}` slot of the SUGGESTION_CARD constants.
        items_text = rich_table(["#", "ᴛɪᴛʟᴇ", "ᴀʀᴛɪsᴛ", "ʟᴇɴɢᴛʜ"], lines)

        countdown_sec = 5
        display_seed = trim_title(seed_title)
        autoplay_enabled = state.is_autoplay_enabled(chat_id)

        if autoplay_enabled:
            card_text = Messages.SUGGESTION_CARD.format(display_seed, items_text, countdown_sec)
        else:
            card_text = Messages.SUGGESTION_CARD_NO_AUTOPLAY.format(display_seed, items_text)

        keyboard = Buttons.suggestion_markup(suggestions[:5], autoplay_enabled=autoplay_enabled)

        bot = clients.get("bot")
        if not bot:
            logger.warning("[Suggest] Bot client not available")
            await client.leave_call(chat_id)
            await remove_active_chat(chat_id)
            return

        sent_msg = await rich_send(
            bot,
            chat_id,
            card_text,
            reply_markup=keyboard,
        )

        if not autoplay_enabled:
            return

        async def _suggest_countdown():
            try:
                await asyncio.sleep(countdown_sec)
                # Quick recheck: if everyone left during countdown, cancel and leave immediately
                if await autoleave_vc(chat_id):
                    return

                top_track = suggestions[0]
                top_vid = top_track.get("video_id")
                top_url = top_track.get("url") or f"https://www.youtube.com/watch?v={top_vid}"
                top_title = top_track.get("title", "Autoplay track")
                top_dur = top_track.get("duration", "N/A")

                if top_vid:
                    state.add_to_history(chat_id, top_vid)

                try:
                    await rich_edit(
                        sent_msg,
                        rich_note(Messages.AUTOPLAYING_TITLE.format(trim_title(top_title))),
                        reply_markup=None,
                        client=bot,
                    )
                except Exception:
                    pass

                yt_task = asyncio.create_task(handle_youtube(top_url))
                yt_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

                by_user = "AUTO"
                chat_obj = last_song.get("chat") or getattr(sent_msg, 'chat', None)
                ast_num = state.get_chat_assistant(chat_id)
                await join_call(
                    sent_msg,
                    top_title,
                    top_url,
                    chat_obj,
                    by_user,
                    top_dur,
                    "audio",
                    None,
                    stream_url=None,
                    yt_task=yt_task,
                    assistant_num=ast_num,
                )
            except asyncio.CancelledError:
                pass
            except Exception as err:
                logger.warning(f"[Suggest] Countdown autoplay failed for chat {chat_id}: {err}")
                await client.leave_call(chat_id)
                await remove_active_chat(chat_id)
            finally:
                state.suggest_tasks.pop(chat_id, None)

        task = asyncio.create_task(_suggest_countdown())
        state.suggest_tasks[chat_id] = task

    except Exception as e:
        logger.warning(f"[Suggest] Error triggering suggestions for chat {chat_id}: {e}")
        try:
            await client.leave_call(chat_id)
            await remove_active_chat(chat_id)
        except Exception:
            pass


async def end(client, update):
    if "bot" in clients and clients["bot"] and getattr(clients["bot"], "me", None):
        db_task(collection.update_one(
            {"bot_id": clients["bot"].me.id},
            {"$push": {'dates': {"$each": [datetime.datetime.now()], "$slice": -5000}}},
            upsert=True
        ))
    try:
        chat_id = update.chat_id
        state.cancel_suggest(chat_id)

        # Hold the chat lock only for the queue read-modify-write. join_call and
        # remove_active_chat both re-acquire this same non-reentrant lock
        # (state.activate / state.deactivate), so awaiting them while holding it
        # deadlocks the stream_end handler and, because the lock is never
        # released, every later command for this chat.
        async with state.lock(chat_id):
            next_song = state.queues[chat_id].pop(0) if state.queues.get(chat_id) else None
            if next_song:
                state.playing[chat_id] = next_song
                state.last_played[chat_id] = next_song

        if next_song:
            ast_num = state.get_chat_assistant(chat_id)
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
                queue_msg=next_song.get('queue_msg'),
                assistant_num=ast_num,
            )
        else:
            logger.info(f"Song queue for chat {chat_id} is empty.")
            last_song = state.playing.pop(chat_id, None) or state.last_played.get(chat_id)
            if last_song:
                state.last_played[chat_id] = last_song

            if last_song:
                asyncio.create_task(_trigger_suggestions(client, chat_id, last_song))
            else:
                await state.delete_now_playing(chat_id)
                await client.leave_call(chat_id)
                await remove_active_chat(chat_id)
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
