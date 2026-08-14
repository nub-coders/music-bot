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
from collections import defaultdict, deque


class SessionStore:
    def __init__(self):
        self.queues = {}     # chat_id -> list[QueueEntry]
        self.playing = {}    # chat_id -> QueueEntry | dict
        self.played = {}     # chat_id -> int (unix ts playback started)
        self.active = set()  # chat_ids with an active voice chat
        self.suggest_tasks = {}      # chat_id -> asyncio.Task (active countdown task)
        self.last_played = {}        # chat_id -> dict (last played track info)
        self.autoplay_settings = {}  # chat_id -> bool (autoplay preference, default True)
        self.history = defaultdict(lambda: deque(maxlen=50))  # chat_id -> deque of recent video_ids
        # ponytail: one lock per chat_id, created on demand and never reaped;
        # locks are tiny, and a bot serving even 100k chats is well within budget.
        self._locks = defaultdict(asyncio.Lock)

    def lock(self, chat_id):
        """Per-chat lock. Wrap any queue/active read-modify-write in `async with`."""
        return self._locks[chat_id]

    def cancel_suggest(self, chat_id):
        """Cancel any pending suggestion countdown task for chat_id."""
        task = self.suggest_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_autoplay_enabled(self, chat_id) -> bool:
        """Return True if autoplay/suggest is enabled for chat_id (defaults to True)."""
        return self.autoplay_settings.get(chat_id, True)

    def set_autoplay(self, chat_id, enabled: bool):
        """Set autoplay preference for chat_id."""
        self.autoplay_settings[chat_id] = enabled

    def add_to_history(self, chat_id, video_id: str):
        """Record a played/suggested video ID in recent history for chat_id to prevent recommendation loops."""
        if video_id and isinstance(video_id, str):
            vid = video_id.strip()
            if vid:
                hist = self.history[chat_id]
                if vid not in hist:
                    hist.append(vid)

    def get_history_ids(self, chat_id) -> set:
        """Return set of recently played/suggested video IDs for chat_id."""
        return set(self.history.get(chat_id, []))

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
