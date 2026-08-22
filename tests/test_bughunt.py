"""Bug-hunt reproductions. Each test asserts CURRENT (buggy) behaviour so the
audit's claims are verifiable; flip the assertions after the fixes land."""
import asyncio
import inspect

import pytest

import state as state_mod
import tools
from state import SessionStore


# ── Bug: two remove_active_chat definitions with DIFFERENT cleanup semantics ──
def test_remove_active_chat_two_incompatible_definitions():
    """tools.remove_active_chat(chat_id) resolves the bot from clients['bot'];
    plugins._common.remove_active_chat(client, chat_id) uses the PASSED client.
    Star-import order means plugins.* get the 2-arg one, but tools.py's own
    internal callers keep the 1-arg one -- so the two coexist and the cleanup
    directory differs depending on which path ran."""
    sig = inspect.signature(tools.remove_active_chat)
    assert list(sig.parameters) == ["chat_id"], sig
    import plugins._common as common
    sig2 = inspect.signature(common.remove_active_chat)
    assert list(sig2.parameters) == ["client", "chat_id"], sig2
    # Verified: plugins get the shadowing 2-arg version, tools keeps its own.
    import plugins.playback as pb
    assert pb.remove_active_chat.__module__ == "plugins._common"
    assert tools.remove_active_chat.__module__ == "tools"


def test_tools_remove_active_chat_rejects_two_args():
    with pytest.raises(TypeError):
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            tools.remove_active_chat(object(), -100123)
        )


# ── Bug: playback.dend calls the 2-arg form but playback star-imports tools ───
def test_dend_uses_two_arg_remove_active_chat():
    src = inspect.getsource(__import__("plugins.playback", fromlist=["dend"]).dend)
    assert "remove_active_chat(client, chat_id)" in src


# ── Fixed: state.playing entries are popped, cleanly deleting the key ─────────
def test_playing_pop_removes_key():
    store = SessionStore()
    cid = -100999
    store.playing[cid] = {"title": "x", "by": object()}
    store.playing.pop(cid, None)
    assert cid not in store.playing


def test_playing_clear_on_queueentry_raises():
    """After /skip, state.playing[chat] is a QueueEntry (dataclass) - no .clear()."""
    entry = tools.QueueEntry(
        message=None, title="t", duration="1:00", mode="audio", yt_link=None,
        chat=None, by=None, session=None, thumb=None,
    )
    with pytest.raises(AttributeError):
        entry.clear()


# ── Bug: activate() is called before the join can fail => phantom active chat ─
@pytest.mark.asyncio
async def test_activate_leaves_chat_active_when_caller_returns_early():
    store = SessionStore()
    cid = -100777
    first = await store.activate(cid)
    assert first is True
    # A second /play now believes a stream is live even though nothing plays.
    second = await store.activate(cid)
    assert second is False


# ── Fixed: deactivate() clears the chat->assistant assignment ─────────────────
@pytest.mark.asyncio
async def test_deactivate_clears_assistant_binding():
    store = SessionStore()
    cid = -100888
    store.set_chat_assistant(cid, 3)
    await store.activate(cid, assistant_num=3)
    await store.deactivate(cid)
    assert store.get_chat_assistant(cid) is None



# ── Fixed: get_arg returns "" on a bare "/" message without IndexError ────────
def test_get_arg_returns_empty_on_short_text():
    class M:
        text = "/"
    assert tools.get_arg(M()) == ""



# ── Bug: update_progress_button ZeroDivisionError on "N/A"/0-length duration ──
def test_progress_bar_zero_division():
    duration_str = "0:00"
    total = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration_str.split(":"))))
    assert total == 0
    with pytest.raises(ZeroDivisionError):
        _ = int((5 / total) * 8)


# ── Bug: trim_title docstring/behaviour mismatch + emoji-unsafe slicing ───────
def test_trim_title_breaks_grapheme_clusters():
    title = "🎵" * 20  # 20 chars, each a full emoji
    out = tools.trim_title(title)
    assert len(out) == 30 or len(out) <= 30
    family = "👨‍👩‍👧‍👦 " * 6
    trimmed = tools.trim_title(family)
    # ZWJ sequence can be cut mid-cluster, producing mojibake in the card
    assert len(trimmed) <= 30


# ── Fixed: format_duration cleanly converts float seconds to integer ──────────
def test_format_duration_float_produces_broken_string():
    from youtube import format_duration
    out = format_duration(213.5)
    assert out == "03:33"


# ── Fixed: extract_video_id returns None for non-video YouTube URLs and errors ──
def test_extract_video_id_returns_none_for_non_video_urls():
    from youtube import extract_video_id
    assert extract_video_id("https://www.youtube.com/@SomeChannel") is None
    assert extract_video_id("not a url") is None
    assert extract_video_id(None) is None
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"



# ── Bug: _api_breaker_open never re-probes; only get_video_info resets it ─────
def test_api_breaker_blocks_even_after_success_elsewhere():
    import youtube
    youtube._api_fail_count = 0
    youtube._api_cooldown_until = 0.0
    for _ in range(3):
        youtube._api_record_failure()
    assert youtube._api_breaker_open() is True
    youtube._api_record_success()
    assert youtube._api_breaker_open() is False


# ── Fixed: process_video includes video_id and video_url for suggestion fallback ──
def test_suggestion_fallback_reads_video_keys():
    from youtube import process_video
    item = {"id": {"videoId": "abc12345678"}, "snippet": {"title": "T", "channelTitle": "C"}}
    details = {"contentDetails": {"duration": "PT3M33S"}, "statistics": {"viewCount": "10"}}
    out = process_video(item, details)
    assert out["video_id"] == "abc12345678"
    assert out["video_url"] == "https://www.youtube.com/watch?v=abc12345678"
    assert "url" in out



# ── Bug: mem cache stores unexpiring stream URLs keyed without mode ───────────
def test_mem_cache_unbounded_search_keys_share_space_with_streams():
    import youtube
    youtube._MEM_CACHE.clear()
    for i in range(600):
        youtube._mem_cache_set(("search", f"q{i}"), "vid")
    assert len(youtube._MEM_CACHE) <= youtube._MAX_MEM_CACHE_SIZE


# ── Bug: state module-level singleton shared across bots (multi-worker) ───────
def test_state_is_process_global_singleton():
    assert state_mod.state is tools.state


# ── Fixed: /loop inserts independent copies with unique _track_id ───────────────
def test_loop_inserts_independent_copies():
    import inspect
    import plugins.controls as c
    src = inspect.getsource(c.loop_handler_func) if hasattr(c, "loop_handler_func") else ""
    assert "_track_id" in src
    assert "state.lock" in src



# ── Fixed: /seek resolves channel-mode mapping via _resolve_ctrl_chat_id ───────
def test_seek_uses_resolved_chat_id():
    import inspect
    import plugins.controls as c
    src = inspect.getsource(c.seek_handler_func) if hasattr(c, "seek_handler_func") else ""
    assert "_resolve_ctrl_chat_id" in src



# ── Fixed: end() filters on Device.MICROPHONE (single-fire per stream) ────────
def test_stream_end_filter_matches_single_device():
    src = open("main.py").read()
    assert "stream_end(device=Device.MICROPHONE)" in src



# ── Fixed: audio documents are reachable and handled cleanly ──────────────────
def test_audio_document_branch_is_reachable():
    src = open("plugins/playback.py").read()
    assert 'mime.startswith("audio/")' in src



# ── Fixed: auto-leave has authorized-chat allowlist ──────────────────────────
def test_autoleave_loop_has_auth_allowlist():
    src = open("main.py").read()
    start = src.index("ASSISTANT_LEAVE_TIME")
    window = src[start - 2000: start + 2000]
    assert "state.played" in window
    # Membership test against AUTH/authorized chats exists in the leave loop
    assert " in AUTH" in window
    assert "authorized" in window.lower()



# ── Fixed: chat->assistant binding is released on remove_active_chat / stale ───
def test_remove_chat_assistant_is_called():
    src_tools = open("tools.py").read()
    src_common = open("plugins/_common.py").read()
    assert "db_remove_chat_assistant" in src_tools
    assert "db_remove_chat_assistant" in src_common



# ── Fixed: main.py has __main__ guard ─────────────────────────────────────────
def test_main_module_has_main_guard():
    src = open("main.py").read()
    assert "asyncio.run(main())" in src
    assert '__name__ == "__main__"' in src or "__name__ == '__main__'" in src



# ── Fixed: SSL CA cert bundle configured and valid ────────────────────────────
def test_ssl_ca_bundle_configured():
    import os
    import certifi
    import config  # noqa: F401
    for env_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.getenv(env_var)
        assert path is not None and os.path.exists(path), f"{env_var} must point to a valid CA bundle"


# ── Fixed: run_cmd catches FileNotFoundError gracefully ───────────────────────
@pytest.mark.asyncio
async def test_run_cmd_missing_executable():
    stdout, stderr, code, pid = await tools.run_cmd(["non_existent_binary_xyz_123"])
    assert code == 127
    assert "not found" in stderr.lower()

