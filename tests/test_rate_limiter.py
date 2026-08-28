"""Tests for the bounded per-key token buckets in rate_limiter.py.

`TokenBucketMap` used to retain a TokenBucket plus an asyncio.Lock for every key
it ever saw, so a long-lived bot leaked one pair per user id. Eviction has to stay
lossless: a key may only be dropped once its bucket has refilled to capacity, at
which point it is indistinguishable from a bucket that was never created.
"""
import time

import rate_limiter
from rate_limiter import TokenBucket, TokenBucketMap


# ── TokenBucket ───────────────────────────────────────────────────────────────

async def test_bucket_allows_up_to_capacity_then_throttles():
    bucket = TokenBucket(capacity=3, refill_per_sec=0.0)

    assert [await bucket.acquire() for _ in range(3)] == [True, True, True]
    assert await bucket.acquire() is False


async def test_bucket_refills_over_time():
    bucket = TokenBucket(capacity=2, refill_per_sec=10.0)
    assert await bucket.acquire(2) is True
    assert await bucket.acquire() is False

    bucket._last_ts -= 1.0  # simulate a second of elapsed refill
    assert await bucket.acquire() is True


# ── is_disposable ─────────────────────────────────────────────────────────────

async def test_recently_used_bucket_is_not_disposable():
    """Dropping a bucket mid-throttle would refund the caller's allowance."""
    bucket = TokenBucket(capacity=3, refill_per_sec=1 / 3)
    await bucket.acquire(3)

    assert bucket.is_disposable(time.time()) is False


async def test_fully_refilled_bucket_is_disposable():
    bucket = TokenBucket(capacity=3, refill_per_sec=1 / 3)
    await bucket.acquire(3)
    # capacity / refill_per_sec == 9s is the full-refill window.
    bucket._last_ts -= 9.0

    assert bucket.is_disposable(time.time()) is True


def test_non_refilling_bucket_is_never_disposable():
    """refill_per_sec <= 0 means a spent bucket never recovers, so it must persist."""
    bucket = TokenBucket(capacity=3, refill_per_sec=0.0)
    bucket._last_ts -= 10_000

    assert bucket.is_disposable(time.time()) is False


# ── TokenBucketMap eviction ───────────────────────────────────────────────────

async def test_map_does_not_sweep_below_threshold(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_SWEEP_AT", 5)
    m = TokenBucketMap(capacity=3, refill_per_sec=1 / 3)

    for key in range(4):
        await m.acquire(key)

    assert len(m) == 4


async def test_map_evicts_refilled_keys_once_over_threshold(monkeypatch):
    """Regression: the map grew without bound."""
    monkeypatch.setattr(rate_limiter, "_SWEEP_AT", 5)
    m = TokenBucketMap(capacity=3, refill_per_sec=1 / 3)

    for key in range(10):
        await m.acquire(key)
        m._buckets[key]._last_ts -= 9.0  # age it past the refill window
    assert len(m) <= 5, "idle keys should have been swept as new ones arrived"

    await m.acquire(999)
    assert 999 in m._buckets


async def test_sweep_keeps_actively_throttled_keys(monkeypatch):
    """The whole point: eviction must not hand a throttled user a fresh allowance."""
    monkeypatch.setattr(rate_limiter, "_SWEEP_AT", 3)
    m = TokenBucketMap(capacity=1, refill_per_sec=1 / 60)

    assert await m.acquire(1) is True
    assert await m.acquire(1) is False  # key 1 is now throttled for 60s

    for key in range(2, 20):
        await m.acquire(key)

    assert 1 in m._buckets, "throttled key was evicted"
    assert await m.acquire(1) is False, "eviction refunded the throttled allowance"


async def test_hard_ceiling_bounds_a_flood_of_throttled_keys(monkeypatch):
    """Backstop for the pathological case where every key is still throttled."""
    monkeypatch.setattr(rate_limiter, "_SWEEP_AT", 4)
    monkeypatch.setattr(rate_limiter, "_MAX_KEYS", 8)
    m = TokenBucketMap(capacity=1, refill_per_sec=1 / 3600)

    for key in range(50):
        await m.acquire(key)

    assert len(m) <= 9, f"map grew to {len(m)} despite the ceiling"


async def test_same_key_reuses_its_bucket():
    m = TokenBucketMap(capacity=2, refill_per_sec=0.0)

    assert await m.acquire(7) is True
    assert await m.acquire(7) is True
    assert await m.acquire(7) is False
    assert len(m) == 1
