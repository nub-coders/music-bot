import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import pytgcalls.ffmpeg
from pytgcalls.types.raw import AudioParameters, VideoParameters
from utils.pytgcalls_patch import (
    apply_pytgcalls_patch,
    patched_build_command,
    patched_check_stream,
    patched_cleanup_commands,
)
import youtube


def test_apply_pytgcalls_patch():
    apply_pytgcalls_patch()
    assert pytgcalls.ffmpeg.build_command == patched_build_command
    assert pytgcalls.ffmpeg.check_stream == patched_check_stream
    assert pytgcalls.ffmpeg.cleanup_commands == patched_cleanup_commands


def test_patched_build_command_injects_probe_flags_for_urls():
    audio_params = AudioParameters(bitrate=48000, channels=2)
    url = "https://rr5---sn-qxaelnls.googlevideo.com/videoplayback?expire=12345"
    cmd = patched_build_command("ffprobe", None, url, audio_params)
    assert cmd[0] == "ffprobe"
    assert "-analyzeduration" in cmd
    assert "-probesize" in cmd
    assert "-timeout" in cmd
    assert "-rw_timeout" in cmd
    assert url in cmd


def test_patched_build_command_local_file_intact():
    audio_params = AudioParameters(bitrate=48000, channels=2)
    file_path = "/tmp/song.mp3"
    cmd = patched_build_command("ffprobe", None, file_path, audio_params)
    assert cmd[0] == "ffprobe"
    assert file_path in cmd


@pytest.mark.asyncio
async def test_patched_check_stream_handles_timeout_gracefully_for_audio_url(monkeypatch):
    """When ffprobe times out on an audio URL, patched_check_stream should not raise TimeoutError."""
    fake_proc = MagicMock()
    fake_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    fake_proc.kill = MagicMock()
    fake_proc.wait = AsyncMock(return_value=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=fake_proc))

    audio_params = AudioParameters(bitrate=48000, channels=2)
    url = "https://example.com/audio_stream"

    # Should not raise TimeoutError
    await patched_check_stream(None, url, audio_params)
    assert fake_proc.kill.call_count >= 1


def test_evict_stream_cache():
    url = "https://www.youtube.com/watch?v=testevict"
    youtube._STREAM_CACHE[("audio", url)] = ("https://cdn.example.com/stream", 9999999999)
    youtube._MEM_CACHE[("audio", url)] = "https://cdn.example.com/stream"

    assert ("audio", url) in youtube._STREAM_CACHE
    youtube.evict_stream_cache(url, mode="audio")

    assert ("audio", url) not in youtube._STREAM_CACHE
    assert ("audio", url) not in youtube._MEM_CACHE
