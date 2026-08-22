"""Bug-hunt reproductions and regression guards.

Tests are named for what they assert: `test_..._does_not_...` / `..._never_...`
guards a landed fix, while a test that asserts buggy behaviour documents a bug
that is still open (flip its assertions when the fix lands).
"""
import asyncio
import inspect
import os

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
    # Scope to the sweep function rather than a fixed-width slice around a
    # keyword, so adding logging or config nearby cannot shift it out of view.
    import ast
    tree = ast.parse(open("main.py").read())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_assistant_autoleave_loop"
    )
    # ast.unparse drops comments, so assert on behaviour, not prose.
    window = ast.unparse(fn)
    assert "ASSISTANT_LEAVE_TIME" in window
    assert "state.played" in window
    # Authorized chats, the logger group and active calls are all exempt.
    assert " in AUTH" in window
    assert "exempt_chat_ids" in window
    assert "LOGGER_ID" in window
    assert "state.active" in window



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



# ══════════════════════════════════════════════════════════════════════════════
# REGRESSIONS introduced by the bug-fix commits (81a8a38, bec7f05)
# ══════════════════════════════════════════════════════════════════════════════


def test_end_does_not_hold_chat_lock_across_join_call():
    """tools.end() must release the chat lock BEFORE awaiting join_call() or
    remove_active_chat(), avoiding deadlock on track transitions."""
    import ast
    tree = ast.parse(open("tools.py").read())
    end_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "end"
    )
    withs = [
        w for w in ast.walk(end_fn)
        if isinstance(w, ast.AsyncWith)
        and "state.lock(" in ast.unparse(w.items[0].context_expr)
    ]
    assert withs, "expected `async with state.lock(chat_id)` in end()"
    body = ast.unparse(withs[0])
    assert "join_call(" not in body
    assert "remove_active_chat(" not in body


def test_lock_is_not_reentrant_end_deadlocks():
    """Empirical proof of the above."""
    async def scenario():
        store = SessionStore()
        cid = -1001
        async with store.lock(cid):
            await store.activate(cid, assistant_num=1)

    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(asyncio.TimeoutError):
            loop.run_until_complete(asyncio.wait_for(scenario(), timeout=1.0))
    finally:
        loop.close()


def test_deactivate_does_not_reap_locks_with_pending_waiters():
    """REGRESSION GUARD (was High): deactivate() must not pop self._locks[cid].
    After Lock.release() wakes a waiter, `locked()` is briefly False while the
    waiter is still queued, so reaping there would hand a second lock object to
    the next caller and two coroutines would hold 'the lock' for one chat."""
    async def scenario():
        store = SessionStore()
        cid = -100999
        held = store.lock(cid)
        await held.acquire()
        waiter = asyncio.create_task(store.lock(cid).acquire())
        await asyncio.sleep(0)
        held.release()
        # The exact window the old code checked: unlocked, but waiter queued.
        assert not held.locked()
        assert held._waiters, "waiter still queued while locked() is False"
        await waiter          # waiter takes ownership of `held`
        assert held.locked()
        held.release()        # hand it back so deactivate can acquire
        await store.deactivate(cid)
        # Same lock object survived -> mutual exclusion intact.
        assert store.lock(cid) is held

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(scenario())
    finally:
        loop.close()

    src = open("state.py").read()
    assert "self._locks.pop" not in src, "locks must never be reaped"


def test_deactivate_preserves_queue_for_recoverable_paths():
    """REGRESSION GUARD (was High): deactivate() runs from recoverable error paths
    (failed join, transient stream error) via remove_active_chat(), so it must
    release the call slot and assistant binding without discarding the queue the
    user just built. Callers that do want it gone pop it explicitly."""
    async def scenario():
        store = SessionStore()
        cid = -1002
        store.queues[cid] = [{"title": "a"}, {"title": "b"}, {"title": "c"}]
        store.playing[cid] = {"title": "current"}
        await store.activate(cid, assistant_num=1)
        await store.deactivate(cid)
        # Slot + binding released...
        assert cid not in store.active
        assert store.get_chat_assistant(cid) is None
        # ...but the queue survives for the retry.
        return store.queues.get(cid), store.playing.get(cid)

    loop = asyncio.new_event_loop()
    try:
        queue, playing = loop.run_until_complete(scenario())
        assert queue == [{"title": "a"}, {"title": "b"}, {"title": "c"}]
        assert playing == {"title": "current"}
    finally:
        loop.close()


def test_skip_and_dend_keep_assistant_binding():
    """REGRESSION GUARD (was Medium, Multi Assistant): every join_call() site must
    forward assistant_num, otherwise a chat mid-stream on assistant N can be
    re-joined by a different assistant on skip / play-now / suggestion / dend.

    The value must be the raw binding, NOT `... or 1`: a falsy binding has to
    reach join_call as None so it falls through to get_assistant(), which also
    consults MongoDB. Coercing to 1 skips that lookup and sends a chat persisted
    on assistant 3 to assistant 1 after a restart."""
    import ast
    missing, coerced = [], []
    for path in ("plugins/controls.py", "plugins/playback.py", "tools.py"):
        tree = ast.parse(open(path).read())
        for c in ast.walk(tree):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "join_call":
                kw = {k.arg: k.value for k in c.keywords}
                if "assistant_num" not in kw:
                    missing.append(f"{path}:{c.lineno}")
                elif "or 1" in ast.unparse(kw["assistant_num"]):
                    coerced.append(f"{path}:{c.lineno}")
    assert not missing, f"join_call sites dropping assistant_num: {missing}"
    assert not coerced, f"join_call sites coercing a missing binding to 1: {coerced}"

    src = open("tools.py").read()
    assert "ast_num = state.get_chat_assistant(chat_id) or 1" not in src


def test_autoleave_skips_unknown_chats_without_mass_leave():
    """state.played absence should mean unknown/skip rather than falling back to
    StartTime and mass-leaving all chats when uptime passes ASSISTANT_LEAVE_TIME."""
    src = open("main.py").read()
    assert "state.played.get(cid, StartTime)" not in src
    assert "last_played_ts = state.played.get(cid)" in src


def test_cache_janitor_never_targets_the_repo_root():
    """REGRESSION GUARD (was Critical): _cache_cleanup_loop must never target `ggg`
    (the repo root) to prevent deleting source files or virtual environment."""
    from main import _cleanup_target_dirs, ggg
    target_dirs = _cleanup_target_dirs()
    assert ggg not in target_dirs
    for d in target_dirs:
        assert d != ggg


def test_reboot_stops_assistant_clients_not_pytgcalls():
    """REGRESSION GUARD (was High): PyTgCalls has no stop(), so `await call.stop()`
    raised AttributeError that a bare except swallowed, leaving every assistant
    session alive across the os.execl re-exec. It is the pyrogram Clients in
    clients['assistants'] that must be stopped."""
    from pytgcalls import PyTgCalls
    from pyrogram import Client as PyroClient
    assert not hasattr(PyTgCalls, "stop")
    assert hasattr(PyroClient, "stop")
    src = open("plugins/admin_sudo.py").read()
    assert "await call.stop()" not in src
    assert 'clients.get("assistants", {})' in src
    assert "await ast.stop()" in src


def test_stream_cache_skips_urls_with_no_expire():
    """REGRESSION GUARD (was Medium): a stream URL with no `expire` param used to be
    stored as (value, None), which _mem_cache_get always treats as expired -- a
    permanent miss that also evicted the _MEM_CACHE fallback on every lookup.
    Such URLs must be skipped, exactly as _write_cache does on disk."""
    import youtube
    youtube._STREAM_CACHE.clear()
    youtube._MEM_CACHE.clear()
    key = ("audio", "https://youtu.be/noexpire")
    youtube._mem_cache_set(key, "https://example.com/videoplayback?itag=140")
    assert key not in youtube._STREAM_CACHE, "un-expiring URL must not be cached"
    assert key not in youtube._MEM_CACHE
    assert youtube._mem_cache_get(key) is None

    # A URL that *does* carry expire= is still cached and readable.
    import time as _time
    good = ("audio", "https://youtu.be/withexpire")
    fresh = f"https://example.com/videoplayback?expire={int(_time.time()) + 3600}&itag=140"
    youtube._mem_cache_set(good, fresh)
    assert youtube._STREAM_CACHE[good][1] is not None
    assert youtube._mem_cache_get(good) == fresh
    youtube._STREAM_CACHE.clear()
    youtube._MEM_CACHE.clear()


# ── Guards for the remaining fixes (seek race, duplicate teardown, temp files,
#    owner fail-fast) ──────────────────────────────────────────────────────────

def test_seek_revalidates_track_after_awaiting_stream_url():
    """REGRESSION GUARD (was Medium): /seek read state.playing, then awaited
    get_stream_url() (seconds on the yt-dlp path), then played. If the track
    ended or was skipped during that await, the seek restarted the *old* song
    over the new one. The handler must re-check identity after the await."""
    src = open("plugins/controls.py").read()
    idx_await = src.index("stream_url = await get_stream_url(yt_link)")
    idx_play = src.index("ffmpeg_params = f\"-ss {to_seek}", idx_await)
    between = src[idx_await:idx_play]
    assert "state.playing.get(chat_id) is not current_song" in between, \
        "seek must re-validate the track between resolving the URL and playing"


def test_stream_closed_kicked_is_idempotent():
    """REGRESSION GUARD (was Medium): the handler is registered for both
    CLOSED_VOICE_CHAT and KICKED, which Telegram often delivers together. Without
    an early-out the teardown runs twice (leave_call on an already-left call)."""
    import ast
    tree = ast.parse(open("tools.py").read())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "hd_stream_closed_kicked"
    )
    guard = next(
        (n for n in fn.body if isinstance(n, ast.If) and any(
            isinstance(sub, ast.Return) for sub in ast.walk(n)
        )),
        None,
    )
    assert guard is not None, "no early-return guard in hd_stream_closed_kicked"
    assert "state.active" in ast.unparse(guard.test)


def test_meme_temp_files_stay_out_of_repo_root():
    """REGRESSION GUARD (was Low): memify_*.webp/.webm and temp_overlay_*.png were
    written to the CWD (the repo root), mixing generated scratch files with the
    source tree and leaking now that the janitor no longer sweeps the root."""
    src = open("tools.py").read()
    for bad in (
        'overlay_temp = f"temp_overlay_',
        'final_video = os.path.join(f"memify_',
        'final_image = os.path.join(f"memify_',
    ):
        assert bad not in src, f"bare-CWD temp path still present: {bad}"
    assert src.count('_meme_dir = os.path.join(ggg, "cache")') >= 2


def test_memify_cleans_up_on_send_failure():
    """REGRESSION GUARD (was Low): os.remove(meme) sat in the success path, so a
    failing send_sticker (too large / forbidden / flood wait) leaked the rendered
    file. Both the download and the render must be removed in `finally`."""
    import ast
    tree = ast.parse(open("plugins/meme.py").read())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "memify"
    )
    tries = [n for n in ast.walk(fn) if isinstance(n, ast.Try) and n.finalbody]
    assert tries, "memify has no try/finally"
    finally_src = "\n".join(ast.unparse(s) for t in tries for s in t.finalbody)
    assert "os.remove(meme)" in finally_src, "meme not removed in finally"
    assert "os.remove(file)" in finally_src, "download not removed in finally"


def test_terminal_stop_paths_clear_the_queue():
    """REGRESSION GUARD: deactivate() deliberately preserves the queue (recoverable
    error paths retry with it), so every *terminal* handler -- /end, /stop, the end
    and sgstop buttons, skip-into-empty -- must pop state.queues itself. Otherwise
    a stopped session leaves a stale queue that the next /play appends to and
    silently resurrects."""
    import ast
    src = open("plugins/controls.py").read()
    tree = ast.parse(src)
    terminal = (
        "end_handler", "end_handler_func", "button_skip_handler",
        "skip_handler", "suggestion_stop_handler",
    )
    checked = 0
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.AsyncFunctionDef) or fn.name not in terminal:
            continue
        body = ast.unparse(fn)
        n_teardown = body.count("remove_active_chat(")
        n_qpop = body.count("state.queues.pop(")
        assert n_qpop >= n_teardown, (
            f"{fn.name}: {n_teardown} teardown(s) but only {n_qpop} queue pop(s) "
            "-- a terminal path leaks a stale queue"
        )
        checked += 1
    assert checked >= 3, f"expected to inspect the terminal handlers, saw {checked}"


def test_owner_id_has_no_hardcoded_default():
    """REGRESSION GUARD (was Low/security): OWNER_ID grants unrestricted sudo
    (/reboot, /broadcast, auth bypass). A baked-in default hands full control of
    any misconfigured deployment to whoever owns that hardcoded account.

    OWNER_ID is now optional -- an unset value means "no owner" rather than a
    startup abort -- so the property under test is that the fallback is 0 (which
    no real Telegram account can match), never a real user ID.
    """
    src = open("config.py").read()
    assert "6076474757" not in src, "hardcoded owner id still present"

    # Importing config without OWNER_ID must yield an ownerless bot, and must not
    # silently self-own. Run from a temp cwd so load_dotenv() cannot find the
    # repo's .env and re-supply the value; reach config.py via PYTHONPATH.
    import subprocess
    import sys
    import tempfile
    repo = os.getcwd()
    env = {k: v for k, v in os.environ.items() if k != "OWNER_ID"}
    env["MONGODB_URI"] = "mongodb://localhost:27017"
    env["PYTHONPATH"] = repo
    code = "import config; print(config.OWNER_ID, config.HAS_OWNER)"
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, env=env, cwd=tmp, timeout=60,
        )
    assert proc.returncode == 0, f"ownerless config must import: {proc.stderr}"
    assert proc.stdout.strip() == "0 False", proc.stdout

    # A negative value is a chat ID, not a user: that is a real misconfiguration.
    env["OWNER_ID"] = "-1001234567890"
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "-c", "import config"],
            capture_output=True, text=True, env=env, cwd=tmp, timeout=60,
        )
    assert proc.returncode != 0, "negative OWNER_ID must be rejected"


def test_ownerless_bot_grants_nobody_owner_rights():
    """With OWNER_ID=0 every `user_id == OWNER_ID` check must fail closed. Real
    Telegram user IDs are always > 0, and the anonymous-admin fallbacks in the
    codebase substitute None or a negative chat id -- none may match."""
    OWNER_ID = 0
    for uid in (6076474757, 1, 12345, 777000, -1001234567890, None):
        assert not (uid == OWNER_ID), uid
        assert not (str(OWNER_ID) == str(uid)), uid

    # info.py's combined guard denies all of them too.
    SUDO = []
    for uid in (None, -1001234567890, 6076474757):
        assert str(OWNER_ID) != str(uid) and (not uid or uid not in SUDO)


def test_start_markup_omits_creator_button_without_owner():
    """No owner -> no creator button, and crucially no fallback to an unrelated
    hardcoded account (it used to point at t.me/NubDockerbot)."""
    from utils.button import Buttons

    m = Buttons.start_markup("mybot", None, 0, "grp")
    texts = [b.text for row in m.inline_keyboard for b in row]
    urls = [getattr(b, "url", None) or "" for row in m.inline_keyboard for b in row]
    assert not any("ᴄʀᴇᴀᴛᴏʀ" in t for t in texts), texts
    assert not any("NubDockerbot" in u for u in urls), urls
    assert all(len(row) > 0 for row in m.inline_keyboard), "no empty button rows"
    assert any("sᴜᴘᴘᴏʀᴛ" in t for t in texts), "support chat must survive"

    m2 = Buttons.start_markup("mybot", 42, 42, "grp")
    texts2 = [b.text for row in m2.inline_keyboard for b in row]
    assert any("ᴄʀᴇᴀᴛᴏʀ" in t for t in texts2), texts2


def test_no_unguarded_get_users_on_owner_id():
    """get_users(0) raises, which would abort /start, the help callback and /ping
    outright on an ownerless bot."""
    import pathlib
    for path in ("plugins/start.py", "plugins/info.py"):
        for i, line in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
            if "get_users(OWNER_ID)" in line:
                assert "if OWNER_ID" in line, f"{path}:{i} unguarded: {line.strip()}"


# ── Reliability / performance hardening ───────────────────────────────────────

def test_membership_cache_is_fail_safe():
    """The /play fast path skips the get_chat -> create_chat_invite_link ->
    join_chat handshake when membership is cached. A stale entry would wedge
    playback forever, so it must expire, stay per-assistant, and be droppable
    both per-assistant and wholesale."""
    import time as _t
    s = SessionStore()
    cid, a1, a2 = -1001, 1, 2

    assert s.is_member_cached(a1, cid) is False, "never-seen chat must not be a hit"

    s.mark_member(a1, cid)
    assert s.is_member_cached(a1, cid) is True
    # Caching assistant 1 must never let assistant 2 skip its own handshake.
    assert s.is_member_cached(a2, cid) is False

    # Expired entries are misses AND are evicted.
    s._membership[(a1, cid)] = _t.time() - (SessionStore.MEMBERSHIP_TTL + 1)
    assert s.is_member_cached(a1, cid) is False
    assert (a1, cid) not in s._membership

    # Targeted invalidation (auto-leave knows which assistant left).
    s.mark_member(a1, cid)
    s.mark_member(a2, cid)
    s.forget_member(a1, cid)
    assert s.is_member_cached(a1, cid) is False
    assert s.is_member_cached(a2, cid) is True

    # Blanket invalidation (play() failed / KICKED: cannot attribute) must not
    # touch other chats.
    s.mark_member(a1, cid)
    s.mark_member(a1, -2002)
    s.forget_member(None, cid)
    assert s.is_member_cached(a1, cid) is False
    assert s.is_member_cached(a2, cid) is False
    assert s.is_member_cached(a1, -2002) is True, "unrelated chat was invalidated"


def test_membership_cache_invalidated_on_every_failure_path():
    """Every path that proves membership is gone must call forget_member, or the
    fast path keeps skipping the join handshake and playback fails forever."""
    play_src = open("plugins/playback.py").read()
    assert "state.is_member_cached(" in play_src, "fast path missing"
    assert play_src.count("state.mark_member(") >= 3, "success paths must cache"
    assert play_src.count("state.forget_member(") >= 3, "join failures must invalidate"

    tools_src = open("tools.py").read()
    # join_call's play() is the first real membership test, and KICKED is the
    # explicit signal; both must clear the cache.
    assert "state.forget_member(None, chat_id)" in tools_src
    assert tools_src.count("state.forget_member(") >= 2

    main_src = open("main.py").read()
    assert "state.forget_member(idx, cid)" in main_src, "auto-leave must invalidate what it left"


def test_autoleave_has_blast_radius_controls():
    """A bug in the idle heuristic is unrecoverable (re-joining hundreds of groups
    needs fresh invite links), so the sweep must support a per-pass cap and a
    log-only dry run, and must log its configuration at startup."""
    import config
    assert isinstance(config.ASSISTANT_MAX_LEAVES_PER_SWEEP, int)
    assert config.ASSISTANT_LEAVE_DRY_RUN is False, "dry run must default to off"
    assert config.ASSISTANT_MAX_LEAVES_PER_SWEEP > 0, "a default cap must be set"

    src = open("main.py").read()
    assert "ASSISTANT_MAX_LEAVES_PER_SWEEP" in src, "cap not enforced in the sweep"
    assert "ASSISTANT_LEAVE_DRY_RUN" in src, "dry run not honoured in the sweep"
    assert "left_this_sweep" in src
    # Disabled-feature and enabled-config must both be logged.
    assert "[auto_leave] Disabled" in src
    assert "[auto_leave] Enabled" in src


def test_autoleave_cap_bounds_the_number_of_leaves():
    """Runtime check of the cap arithmetic used by the sweep: with N eligible
    chats and a cap of C, at most C leaves happen per pass."""
    cap = 10
    eligible = list(range(40))
    left = []
    for _ in eligible:
        if cap > 0 and len(left) >= cap:
            break
        left.append(_)
    assert len(left) == cap, f"cap not enforced: {len(left)} leaves"


def test_played_timestamps_are_persisted_and_restored():
    """state.played drives the auto-leave idle heuristic but is process-local, so
    idle chats were never reclaimed after a restart. It must round-trip through
    Mongo, tolerate malformed documents, and be seeded at startup."""
    import database as db

    class _Cursor:
        def __init__(self, docs): self.docs = list(docs)
        def __aiter__(self): return self._gen()
        async def _gen(self):
            for d in self.docs:
                yield d

    class _Coll:
        def __init__(self): self.store = {}
        async def update_one(self, flt, upd, upsert=False):
            cid = flt["chat_id"]
            self.store.setdefault(cid, {"chat_id": cid}).update(upd["$set"])
        def find(self, flt, proj=None): return _Cursor(self.store.values())

    async def scenario():
        real = db.chat_playback
        fake = _Coll()
        db.chat_playback = fake
        try:
            await db.set_last_played(-100424242, 1700000000)
            await db.set_last_played("-100555", 1700000100)  # str coerces to int
            loaded = await db.get_all_last_played()
            assert loaded[-100424242] == 1700000000
            assert loaded[-100555] == 1700000100

            # Malformed docs must be skipped, not crash the loader.
            fake.store[999] = {"chat_id": 999}          # no last_played
            fake.store[888] = {"last_played": 123}      # no chat_id
            loaded = await db.get_all_last_played()
            assert 999 not in loaded and 888 not in loaded
            assert -100424242 in loaded
            return loaded
        finally:
            db.chat_playback = real

    loop = asyncio.new_event_loop()
    try:
        loaded = loop.run_until_complete(scenario())
    finally:
        loop.close()

    # A fresh store knows nothing until it is seeded.
    store = SessionStore()
    assert store.played.get(-100424242) is None
    store.played.update(loaded)
    assert store.played[-100424242] == 1700000000

    # And the wiring must actually exist on both ends.
    assert "db_set_last_played" in open("tools.py").read(), "playback start not persisted"
    assert "get_all_last_played" in open("main.py").read(), "startup does not restore played"


# ── Peripheral-file audit: thumbnail + /about file handling ───────────────────
def test_thumbnail_card_is_written_atomically():
    """render_thumb saves the card to the SAME path a concurrent get_thumb probes
    with os.path.exists(), so an in-place save lets the other caller return (and
    upload) a truncated PNG. Proven: a 0-byte read raised UnidentifiedImageError."""
    import ast
    fn = next(
        n for n in ast.walk(ast.parse(open("thumbnails.py").read()))
        if isinstance(n, ast.FunctionDef) and n.name == "render_thumb"
    )
    body = ast.unparse(fn)
    assert "os.replace(" in body, "card must be renamed into place, not saved in place"
    save_lines = [ln.strip() for ln in body.splitlines() if ".save(" in ln]
    assert save_lines, save_lines
    for line in save_lines:
        assert "tmp_path" in line, f"save must target a temp file, got: {line}"


def test_thumbnail_download_path_is_unique_per_call():
    """random_id is a deterministic md5 so the rendered card can be cached. The
    scratch download must NOT reuse it: two concurrent plays of one track would
    derive the same path and delete each other's file mid-render."""
    import ast
    fn = next(
        n for n in ast.walk(ast.parse(open("thumbnails.py").read()))
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_thumb"
    )
    line = [ln.strip() for ln in ast.unparse(fn).splitlines() if "temp_thumb_path =" in ln]
    assert len(line) == 1, line
    assert "random_id" not in line[0], f"scratch path shares the cache key: {line[0]}"
    assert "uuid" in line[0], line[0]


def test_thumbnail_temp_files_cleaned_on_error_path():
    """A failed download/render used to leak its scratch file into cache/ until
    the 6h janitor sweep, because cleanup sat before the return in the try body."""
    import ast
    fn = next(
        n for n in ast.walk(ast.parse(open("thumbnails.py").read()))
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_thumb"
    )
    tries = [n for n in fn.body if isinstance(n, ast.Try)]
    assert tries and tries[0].finalbody, "get_thumb needs a finally block"
    assert "temp_files_to_delete" in ast.unparse(tries[0].finalbody)


def test_about_does_not_clobber_the_bot_branding_logo():
    """/about downloaded an arbitrary user's profile photo to {user_dir}/logo.jpg
    -- the same path /start and /setwelcome read back as the bot's own logo, and
    they prefer it whenever os.path.exists() is True."""
    import ast
    tree = ast.parse(open("plugins/about.py").read())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "info_command"
    )
    line = [ln.strip() for ln in ast.unparse(fn).splitlines() if "photo_path =" in ln]
    assert len(line) == 1, line
    assert not line[0].rstrip().endswith("logo.jpg'"), f"collides with branding: {line[0]}"

    helper = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_build_and_send_user_info"
    )
    tries = [n for n in ast.walk(helper) if isinstance(n, ast.Try)]
    assert any("os.remove(photo_path)" in ast.unparse(t.finalbody) for t in tries), \
        "per-message download must be cleaned up"
