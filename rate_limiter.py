"""Token bucket and semaphore-based rate limiters for nub-music-bot.

Single-process in-memory; for multi-worker deploy, replace with Redis-backed
implementation (INCR + EXPIRE for token buckets, SETNX for distributed locks).
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TokenBucket:
    """Async token bucket with configurable capacity and refill rate.

    Thread/async-safe via internal lock.
    """
    capacity: int
    refill_per_sec: float
    _tokens: float = field(init=False)
    _last_ts: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last_ts = time.time()

    async def acquire(self, tokens: int = 1) -> bool:
        """Attempt to acquire tokens. Returns True if successful, False if throttled."""
        async with self._lock:
            now = time.time()
            # Refill
            elapsed = now - self._last_ts
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._last_ts = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def wait_for(self, tokens: int = 1, max_wait: float = 60.0) -> bool:
        """Wait until tokens are available, up to max_wait seconds."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if await self.acquire(tokens):
                return True
            # Estimate wait time
            need = tokens - self._tokens
            wait = min(need / self.refill_per_sec, 0.5) if self.refill_per_sec > 0 else 0.5
            await asyncio.sleep(wait)
        return await self.acquire(tokens)


class TokenBucketMap:
    """Per-key token buckets (e.g., per-user, per-chat)."""

    def __init__(self, capacity: int, refill_per_sec: float):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._buckets: Dict[int, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def _get_bucket(self, key: int) -> TokenBucket:
        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(self.capacity, self.refill_per_sec)
            return self._buckets[key]

    async def acquire(self, key: int, tokens: int = 1) -> bool:
        bucket = await self._get_bucket(key)
        return await bucket.acquire(tokens)

    async def wait_for(self, key: int, tokens: int = 1, max_wait: float = 60.0) -> bool:
        bucket = await self._get_bucket(key)
        return await bucket.wait_for(tokens, max_wait)


# ─── Global limiters ────────────────────────────────────────────────────────

# Broadcast: 20 burst, then 5/second (Telegram ~30 msg/sec global limit, stay well under)
_broadcast_limiter = TokenBucket(capacity=20, refill_per_sec=5.0)

# Per-user command throttling (already exists in tools.py as _play_buckets)
# Expose as TokenBucketMap for consistency
_command_limiter = TokenBucketMap(capacity=3, refill_per_sec=1/3)

# Semaphore to prevent concurrent broadcasts (prevents double-spend of global rate limit)
_broadcast_semaphore = asyncio.Semaphore(1)

# Lock for broadcast_message global dict (tools.py)
_broadcast_message_lock = asyncio.Lock()


def broadcast_message_lock() -> asyncio.Lock:
    """Return the lock for broadcast_message dict."""
    return _broadcast_message_lock


# ─── Public API ─────────────────────────────────────────────────────────────

async def allow_broadcast() -> bool:
    """Try to acquire a broadcast slot. Non-blocking."""
    return await _broadcast_limiter.acquire()


async def wait_broadcast_slot(max_wait: float = 300.0) -> bool:
    """Wait for a broadcast slot (for queueing)."""
    return await _broadcast_limiter.wait_for(max_wait=max_wait)


def broadcast_semaphore() -> asyncio.Semaphore:
    """Return the global broadcast semaphore."""
    return _broadcast_semaphore


async def allow_command(user_id: int) -> bool:
    """Check if user can execute a throttled command."""
    return await _command_limiter.acquire(user_id)


async def wait_command_slot(user_id: int, max_wait: float = 30.0) -> bool:
    return await _command_limiter.wait_for(user_id, max_wait=max_wait)


# ─── Back-compat for tools.py _play_buckets ────────────────────────────────

# Re-implement allow_play using the TokenBucketMap for consistency
async def allow_play(user_id: int, capacity: int = 3, refill_per_sec: float = 1 / 3) -> bool:
    """Async token bucket for play/render commands (back-compat)."""
    # Use a dedicated map for play commands
    if not hasattr(allow_play, "_map"):
        allow_play._map = TokenBucketMap(capacity, refill_per_sec)
    return await allow_play._map.acquire(user_id)
