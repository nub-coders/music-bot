"""Tests for SessionStore (state.py) -- the per-chat locking that keeps two
near-simultaneous /play calls from both deciding they are the first."""
import asyncio

import pytest

from state import SessionStore


@pytest.fixture
def store():
    return SessionStore()


async def test_activate_returns_true_only_for_first_caller(store):
    assert await store.activate(-100) is True
    assert await store.activate(-100) is False


async def test_concurrent_activate_elects_exactly_one_starter(store):
    """The whole point of the per-chat lock: N racing /play calls in one chat must
    yield exactly one 'you start playback', not N."""
    results = await asyncio.gather(*(store.activate(-100) for _ in range(25)))
    assert results.count(True) == 1
    assert results.count(False) == 24


async def test_activate_rebinds_assistant_exclusively(store):
    await store.activate(-100, assistant_num=1)
    assert store.assistant_active[1] == {-100}

    await store.activate(-100, assistant_num=2)
    assert store.assistant_active[2] == {-100}
    assert -100 not in store.assistant_active[1], "chat must not stay bound to the old assistant"


async def test_deactivate_preserves_queue_and_playing(store):
    """deactivate() runs from recoverable error paths, so the queue must survive
    for the retry. Only explicit /end pops it."""
    store.queues[-100] = [{"title": "song"}]
    store.playing[-100] = {"title": "song"}
    await store.activate(-100, assistant_num=1)

    await store.deactivate(-100)

    assert -100 not in store.active
    assert store.assistant_active[1] == set()
    assert store.queues[-100] == [{"title": "song"}]
    assert store.playing[-100] == {"title": "song"}


async def test_activate_after_deactivate_is_first_again(store):
    await store.activate(-100)
    await store.deactivate(-100)
    assert await store.activate(-100) is True


async def test_pop_track_returns_entry_once(store):
    store.queues[-100] = [{"_track_id": "a"}, {"_track_id": "b"}]

    assert await store.pop_track(-100, "b") == {"_track_id": "b"}
    assert await store.pop_track(-100, "b") is None, "a second Play Now tap must not replay it"
    assert store.queues[-100] == [{"_track_id": "a"}]


async def test_concurrent_pop_track_yields_one_winner(store):
    store.queues[-100] = [{"_track_id": "a"}]
    results = await asyncio.gather(*(store.pop_track(-100, "a") for _ in range(10)))
    assert len([r for r in results if r is not None]) == 1


async def test_pop_track_missing_chat_is_none(store):
    assert await store.pop_track(-999, "a") is None


def test_membership_cache_expires(store, monkeypatch):
    store.mark_member(1, -100)
    assert store.is_member_cached(1, -100) is True

    real_time = __import__("time").time()
    monkeypatch.setattr("state.time.time", lambda: real_time + store.MEMBERSHIP_TTL + 1)
    assert store.is_member_cached(1, -100) is False
    assert (1, -100) not in store._membership, "expired entry should be evicted on read"


def test_forget_member_none_clears_every_assistant(store):
    store.mark_member(1, -100)
    store.mark_member(2, -100)
    store.mark_member(1, -200)

    store.forget_member(None, -100)

    assert store.is_member_cached(1, -100) is False
    assert store.is_member_cached(2, -100) is False
    assert store.is_member_cached(1, -200) is True, "other chats must be untouched"


def test_history_dedupes_and_caps_at_50(store):
    store.add_to_history(-100, "abc")
    store.add_to_history(-100, "abc")
    assert store.get_history_ids(-100) == {"abc"}

    for i in range(60):
        store.add_to_history(-100, f"v{i}")
    assert len(store.history[-100]) == 50
    assert "abc" not in store.get_history_ids(-100), "oldest entries should roll off"


def test_add_to_history_ignores_empty_and_non_str(store):
    store.add_to_history(-100, "")
    store.add_to_history(-100, "   ")
    store.add_to_history(-100, None)
    store.add_to_history(-100, 12345)
    assert store.get_history_ids(-100) == set()


def test_autoplay_defaults_true_then_persists(store):
    assert store.is_autoplay_enabled(-100) is True
    store.set_autoplay(-100, False)
    assert store.is_autoplay_enabled(-100) is False


async def test_cancel_suggest_cancels_pending_task(store):
    async def _never():
        await asyncio.sleep(3600)

    task = asyncio.create_task(_never())
    store.suggest_tasks[-100] = task

    assert store.cancel_suggest(-100) is True
    assert store.cancel_suggest(-100) is False, "task was already popped"

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_cancel_suggest_on_finished_task_is_false(store):
    async def _done():
        return None

    task = asyncio.create_task(_done())
    await task
    store.suggest_tasks[-100] = task
    assert store.cancel_suggest(-100) is False


async def test_delete_now_playing_swallows_delete_failure(store):
    class _Msg:
        deleted = False

        async def delete(self):
            _Msg.deleted = True
            raise RuntimeError("message already gone")

    store.set_now_playing(-100, _Msg())
    await store.delete_now_playing(-100)  # must not raise

    assert _Msg.deleted is True
    assert store.get_now_playing(-100) is None


def test_lock_is_stable_per_chat(store):
    assert store.lock(-100) is store.lock(-100)
    assert store.lock(-100) is not store.lock(-200)
