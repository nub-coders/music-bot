"""Ephemeral per-chat session state, encapsulated in one object.

Replaces the bare module-level dicts that used to live in tools.py. Same data
shapes (so all the in-place list/dict mutations behave identically), but reached
through a single `state` instance and guarded by a per-chat asyncio.Lock so two
near-simultaneous /play calls in one chat can't both decide they're the first.

ponytail: single-process, in-memory. The seam is deliberate — swap the four
containers for Redis (keyed f"{bot_id}:{chat_id}") behind these same attributes/
methods to go multi-worker, without touching the ~80 call sites.
"""
import asyncio
from collections import defaultdict


class SessionStore:
    def __init__(self):
        self.queues = {}     # chat_id -> list[QueueEntry]
        self.playing = {}    # chat_id -> QueueEntry | dict
        self.played = {}     # chat_id -> int (unix ts playback started)
        self.active = set()  # chat_ids with an active voice chat
        # ponytail: one lock per chat_id, created on demand and never reaped;
        # locks are tiny, and a bot serving even 100k chats is well within budget.
        self._locks = defaultdict(asyncio.Lock)

    def lock(self, chat_id):
        """Per-chat lock. Wrap any queue/active read-modify-write in `async with`."""
        return self._locks[chat_id]

    async def activate(self, chat_id):
        """Atomically mark a chat active. Returns True iff it was NOT already active
        (i.e. this caller is the one that should start playback, not enqueue)."""
        async with self.lock(chat_id):
            was_active = chat_id in self.active
            self.active.add(chat_id)
            return not was_active

    async def pop_track(self, chat_id, track_id):
        """Remove and return the queued entry with this _track_id, or None if it
        is already gone (played, skipped, or claimed by another Play Now tap)."""
        async with self.lock(chat_id):
            queue = self.queues.get(chat_id) or []
            for i, entry in enumerate(queue):
                if entry.get("_track_id") == track_id:
                    return queue.pop(i)
        return None


state = SessionStore()
