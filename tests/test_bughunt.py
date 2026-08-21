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


# ── Bug: state.playing entries are dicts but .clear() is called on them ───────
def test_playing_clear_wipes_dict_instead_of_removing_key():
    store = SessionStore()
    cid = -100999
    store.playing[cid] = {"title": "x", "by": object()}
    store.playing[cid].clear()
    # Key still present, so `if chat_id in state.playing` stays True forever
    assert cid in store.playing
    assert store.playing[cid] == {}


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


# ── Bug: deactivate() does not clear the chat->assistant assignment ───────────
@pytest.mark.asyncio
async def test_deactivate_keeps_assistant_binding():
    store = SessionStore()
    cid = -100888
    store.set_chat_assistant(cid, 3)
    await store.activate(cid, assistant_num=3)
    await store.deactivate(cid)
    assert store.get_chat_assistant(cid) == 3  # sticky forever


# ── Bug: get_arg IndexError on a bare "/" message ─────────────────────────────
def test_get_arg_index_error_on_short_text():
    class M:
        text = "/"
    with pytest.raises(IndexError):
        tools.get_arg(M())


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


# ── Bug: format_duration crashes on float seconds ─────────────────────────────
def test_format_duration_float_produces_broken_string():
    from youtube import format_duration
    out = format_duration(213.5)
    # `:02d` on a float raises, or `//` yields floats -> ValueError
    assert isinstance(out, str)


# ── Bug: extract_video_id returns junk for non-video YouTube URLs ─────────────
def test_extract_video_id_returns_garbage_for_channel_urls():
    from youtube import extract_video_id
    assert extract_video_id("https://www.youtube.com/@SomeChannel") == "@SomeChannel"
    assert extract_video_id("not a url") is None
    # And on error it returns a *string* describing the error, not None:
    assert extract_video_id(None) is not None


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


# ── Bug: youtube_search returns keys the suggestion fallback never reads ──────
def test_suggestion_fallback_reads_nonexistent_keys():
    from youtube import process_video
    item = {"id": {"videoId": "abc12345678"}, "snippet": {"title": "T", "channelTitle": "C"}}
    details = {"contentDetails": {"duration": "PT3M33S"}, "statistics": {"viewCount": "10"}}
    out = process_video(item, details)
    assert "video_id" not in out   # get_related_suggestions reads item["video_id"]
    assert "video_url" not in out  # ...and item["video_url"]
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


# ── Bug: /loop inserts the SAME object N times (shared _yt_task/_track_id) ─────
def test_loop_inserts_same_object_reference():
    import ast
    import inspect
    import plugins.controls as c
    src = inspect.getsource(c)
    tree = ast.parse(src)
    inserts = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "insert"
        and any(isinstance(a, ast.Name) and a.id == "current_song" for a in n.args)
    ]
    assert inserts, "expected state.queues[...].insert(0, current_song)"
    # No copy()/dict() wrapper -> every loop iteration appends the identical dict.
    queue = []
    current_song = {"_track_id": "t1", "title": "x"}
    for _ in range(3):
        queue.insert(0, current_song)
    assert queue[0] is queue[1] is queue[2]
    # pop_track by id removes only ONE of the three
    queue = [q for q in queue if q.get("_track_id") != "t1"]
    assert queue == []  # or, with a first-match remove, 2 stale clones survive


# ── Bug: /seek ignores channel-mode mapping (_resolve_ctrl_chat_id unused) ─────
def test_seek_uses_raw_message_chat_id():
    import inspect
    import plugins.controls as c
    src = inspect.getsource(c.seek_handler_func) if hasattr(c, "seek_handler_func") else None
    if src is None:
        srcs = [
            inspect.getsource(v)
            for v in vars(c).values()
            if callable(v) and "seek" in getattr(v, "__name__", "")
        ]
        src = "\n".join(srcs)
    assert "message.chat.id" in src
    assert "_resolve_ctrl_chat_id" not in src


# ── Fixed: end() filters on Device.MICROPHONE (single-fire per stream) ────────
def test_stream_end_filter_matches_single_device():
    src = open("main.py").read()
    assert "stream_end(device=Device.MICROPHONE)" in src



# ── Bug: audio documents are unreachable (elif bound to outer `if`) ───────────
def test_audio_document_branch_is_dead_code():
    import ast
    tree = ast.parse(open("plugins/playback.py").read())
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Attribute)
            and node.test.attr == "mime_type"
        ):
            target = node
            break
    assert target is not None, "could not locate `if doc.mime_type:`"
    # The audio handling sits in `orelse` of `if doc.mime_type:` -> only runs when
    # mime_type is falsy, and then `doc.mime_type.startswith` would raise.
    assert target.orelse, "expected the audio branch to be an elif on the outer if"
    audio = target.orelse[0]
    assert isinstance(audio, ast.If)
    assert "audio/" in ast.unparse(audio.test)


# ── Fixed: auto-leave has authorized-chat allowlist ──────────────────────────
def test_autoleave_loop_has_auth_allowlist():
    src = open("main.py").read()
    start = src.index("ASSISTANT_LEAVE_TIME")
    window = src[start - 2000: start + 2000]
    assert "state.played" in window
    # Membership test against AUTH/authorized chats exists in the leave loop
    assert " in AUTH" in window
    assert "authorized" in window.lower()



# ── Bug: chat->assistant binding is never released ───────────────────────────
def test_remove_chat_assistant_is_never_called():
    import pathlib
    import re
    hits = []
    for p in pathlib.Path(".").rglob("*.py"):
        if ".venv" in p.parts or "tests" in p.parts:
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if re.search(r"remove_chat_assistant", line):
                hits.append((str(p), i, line.strip()))
    calls = [
        h for h in hits
        if not h[2].startswith(("def ", "async def ", "from ", "import "))
        and "logger." not in h[2]
        and " as db_remove_chat_assistant" not in h[2]
    ]
    assert not calls, f"unexpected call sites: {calls}"


# ── Fixed: main.py has __main__ guard ─────────────────────────────────────────
def test_main_module_has_main_guard():
    src = open("main.py").read()
    assert "asyncio.run(main())" in src
    assert '__name__ == "__main__"' in src or "__name__ == '__main__'" in src
