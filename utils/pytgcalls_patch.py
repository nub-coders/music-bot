import asyncio
import logging
import subprocess
from json import JSONDecodeError, loads
from typing import Dict, List, Optional, Union

import pytgcalls.ffmpeg
from pytgcalls.exceptions import (
    ImageSourceFound,
    InvalidVideoProportion,
    LiveStreamFound,
    NoAudioSourceFound,
    NoVideoSourceFound,
)
FFmpegError = getattr(pytgcalls.ffmpeg, 'FFmpegError', Exception)
from pytgcalls.types.raw import AudioParameters, VideoParameters

logger = logging.getLogger(__name__)

# Store original functions
_orig_build_command = pytgcalls.ffmpeg.build_command
_orig_check_stream = pytgcalls.ffmpeg.check_stream
_orig_cleanup_commands = pytgcalls.ffmpeg.cleanup_commands


def patched_build_command(
    name: str,
    ffmpeg_parameters: Optional[str],
    path: Optional[str],
    stream_parameters: Union[AudioParameters, VideoParameters],
    before_commands: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
    is_livestream: bool = False,
) -> List[str]:
    """Enhanced build_command that injects network timeouts and probe boundaries for ffprobe."""
    cmd = _orig_build_command(
        name,
        ffmpeg_parameters,
        path,
        stream_parameters,
        before_commands,
        headers,
        is_livestream,
    )

    if name == 'ffprobe' and path and isinstance(path, str) and path.startswith(('http://', 'https://')):
        # Add fast analyze limits and network socket timeout (in microseconds)
        # to prevent ffprobe from blocking forever on slow/stalled streams.
        probe_opts = [
            '-analyzeduration', '3000000',
            '-probesize', '1048576',
            '-timeout', '8000000',
            '-rw_timeout', '8000000',
        ]
        # Insert right after 'ffprobe'
        if len(cmd) > 1:
            cmd = [cmd[0]] + probe_opts + cmd[1:]
        else:
            cmd = cmd + probe_opts

    return cmd


async def patched_cleanup_commands(
    commands: List[str],
    process_name: Optional[str] = None,
    blacklist: Optional[List[str]] = None,
) -> List[str]:
    """Safe cleanup_commands that terminates subprocess on any timeout or decode failure."""
    proc_res = None
    try:
        proc_res = await asyncio.create_subprocess_exec(
            commands[0] if not process_name else process_name,
            '-h',
            'full',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(
            proc_res.communicate(),
            timeout=10,
        )
        result = stdout.decode('utf-8', errors='replace')
    except (asyncio.TimeoutError, TimeoutError, subprocess.TimeoutExpired, JSONDecodeError, Exception):
        if proc_res:
            try:
                proc_res.kill()
                await proc_res.wait()
            except Exception:
                pass
        return commands

    import re
    supported = re.findall(r'(?m)^ *(-\w+).*?\s+', result)
    supported += ['-i']
    new_commands = []
    ignore_next = False

    for v in commands:
        if len(v) > 0:
            if v[0] == '-':
                ignore_next = v not in supported or (blacklist is not None and v in blacklist)
            if not ignore_next:
                new_commands += [v]
            elif v[0] != '-':
                ignore_next = False
    return new_commands


async def patched_check_stream(
    ffmpeg_parameters: Optional[str],
    path: str,
    stream_parameters: Union[AudioParameters, VideoParameters],
    before_commands: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
):
    """Safe check_stream that handles timeouts, kills hanging ffprobe processes, and falls back gracefully."""
    ffprobe = None
    try:
        cmd = await patched_cleanup_commands(
            patched_build_command(
                'ffprobe',
                ffmpeg_parameters,
                path,
                stream_parameters,
                before_commands,
                headers,
                False,
            ),
        )
        ffprobe = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise FFmpegError('ffprobe not installed')

    stdout, stderr = b'', b''
    try:
        stdout, stderr = await asyncio.wait_for(
            ffprobe.communicate(),
            timeout=10,
        )
        result = loads(stdout.decode('utf-8', errors='replace')) or {}
        stream_list = result.get('streams', [])
        format_content = result.get('format', {})
        if 'No such file' in stderr.decode('utf-8', errors='replace'):
            raise FileNotFoundError()
    except (asyncio.TimeoutError, TimeoutError, subprocess.TimeoutExpired, JSONDecodeError) as err:
        if ffprobe:
            try:
                ffprobe.kill()
                await ffprobe.wait()
            except Exception:
                pass

        # For remote audio streams, if ffprobe timed out or failed to parse,
        # fallback gracefully without crashing playback.
        if isinstance(stream_parameters, AudioParameters) and isinstance(path, str) and path.startswith(('http://', 'https://')):
            logger.warning(
                f"[pytgcalls_patch] ffprobe probe timed out/failed ({type(err).__name__}) on audio URL; proceeding with default audio parameters"
            )
            return
        raise

    have_video = False
    is_image = True
    have_audio = False
    have_valid_video = False
    original_width, original_height = 0, 0

    for stream in stream_list:
        codec_type = stream.get('codec_type', '')
        codec_name = stream.get('codec_name', '')
        image_codecs = ['png', 'jpeg', 'jpg', 'mjpeg']
        if codec_type == 'video':
            is_image &= codec_name in image_codecs
            have_video = True
            original_width = int(stream.get('width', 0))
            original_height = int(stream.get('height', 0))
            if original_height and original_width:
                have_valid_video = True
        elif codec_type == 'audio':
            have_audio = True

    if isinstance(stream_parameters, VideoParameters):
        if not have_video:
            raise NoVideoSourceFound(path)
        if not have_valid_video:
            raise InvalidVideoProportion('Video proportion not found')

        ratio = float(original_width) / original_height
        new_w = min(original_width, stream_parameters.width)
        new_h = int(new_w / ratio)

        if new_h > stream_parameters.height and stream_parameters.adjust_by_height:
            new_h = stream_parameters.height
            new_w = int(new_h * ratio)

        new_w = new_w - 1 if new_w % 2 else new_w
        new_h = new_h - 1 if new_h % 2 else new_h
        stream_parameters.height = new_h
        stream_parameters.width = new_w
        if is_image:
            stream_parameters.frame_rate = 10
            raise ImageSourceFound(path)

    if isinstance(stream_parameters, AudioParameters) and not have_audio:
        # If ffprobe ran but stream_list is empty on a remote URL, allow stream to proceed
        if isinstance(path, str) and path.startswith(('http://', 'https://')):
            logger.warning(f"[pytgcalls_patch] No audio stream detected by ffprobe on {path[:60]}...; attempting playback anyway")
            return
        raise NoAudioSourceFound(path)

    if 'duration' not in format_content and isinstance(path, str) and path.startswith(('http://', 'https://')):
        raise LiveStreamFound(path)


def apply_pytgcalls_patch():
    """Apply the monkey-patch to pytgcalls.ffmpeg module and MediaStream."""
    pytgcalls.ffmpeg.build_command = patched_build_command
    pytgcalls.ffmpeg.check_stream = patched_check_stream
    pytgcalls.ffmpeg.cleanup_commands = patched_cleanup_commands

    # Also patch in media_stream module namespace if it imported check_stream / cleanup_commands directly
    try:
        import pytgcalls.types.stream.media_stream as ms
        ms.check_stream = patched_check_stream
        ms.cleanup_commands = patched_cleanup_commands
        ms.build_command = patched_build_command
    except Exception as e:
        logger.debug(f"[pytgcalls_patch] Could not patch media_stream module attributes directly: {e}")

    logger.info("[pytgcalls_patch] PyTgCalls ffmpeg probe timeout & process leak patch applied successfully")
