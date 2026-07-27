"""Phase 4 concurrency: the /play test-and-set must have exactly one winner.

The race: two near-simultaneous /play calls in one chat both read is_active=False
before either flips it, so both try to start playback and corrupt the queue
position. state.activate() makes the check-and-set atomic under a per-chat lock.
"""
import asyncio

import pytest

from state import SessionStore


@pytest.mark.asyncio
async def test_activate_has_exactly_one_winner():
    store = SessionStore()
    chat_id = -1001234567890

    async def racer():
        # yield inside the window that used to be non-atomic; a broken
        # implementation lets several tasks observe "not active" here.
        started = await store.activate(chat_id)
        await asyncio.sleep(0)
        return started

    winners = sum(await asyncio.gather(*(racer() for _ in range(50))))
    assert winners == 1
    assert chat_id in store.active


@pytest.mark.asyncio
async def test_activate_distinct_chats_each_win():
    store = SessionStore()
    results = await asyncio.gather(*(store.activate(cid) for cid in range(20)))
    assert all(results)  # every distinct chat is its own first-caller
