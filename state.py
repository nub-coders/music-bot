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
import time
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
        self.now_playing_msgs = {}   # chat_id -> Message (active now-playing message)
        self.history = defaultdict(lambda: deque(maxlen=50))  # chat_id -> deque of recent video_ids
        self.chat_assistants = {}    # chat_id -> int (assigned assistant index 1..5)
        self.assistant_active = defaultdict(set)  # assistant_num -> set of active chat_ids
        # (assistant_num, chat_id) -> unix ts the assistant was confirmed a member.
        # Lets /play skip the get_chat -> create_chat_invite_link -> join_chat
        # round-trips on repeat plays in the same chat. Confirmations expire so a
        # kick/ban is re-discovered, and are dropped eagerly on any join failure.
        self._membership = {}
        # ponytail: one lock per chat_id, created on demand and never reaped;
        # locks are tiny, and a bot serving even 100k chats is well within budget.
        self._locks = defaultdict(asyncio.Lock)

    # ── Assistant membership cache ────────────────────────────────────────────
    MEMBERSHIP_TTL = 21600  # 6h: long enough to help, short enough to re-verify

    def is_member_cached(self, assistant_num: int, chat_id: int) -> bool:
        """True iff this assistant was recently confirmed to be in chat_id."""
        ts = self._membership.get((int(assistant_num), int(chat_id)))
        if ts is None:
            return False
        if (time.time() - ts) >= self.MEMBERSHIP_TTL:
            self._membership.pop((int(assistant_num), int(chat_id)), None)
            return False
        return True

    def mark_member(self, assistant_num: int, chat_id: int):
        """Record that this assistant is a confirmed member of chat_id."""
        self._membership[(int(assistant_num), int(chat_id))] = time.time()

    def forget_member(self, assistant_num: int | None, chat_id: int):
        """Drop cached membership. Pass assistant_num=None to clear every
        assistant for this chat (used when we cannot attribute the failure)."""
        cid = int(chat_id)
        if assistant_num is None:
            for key in [k for k in self._membership if k[1] == cid]:
                self._membership.pop(key, None)
        else:
            self._membership.pop((int(assistant_num), cid), None)

    def set_now_playing(self, chat_id, message):
        """Record the active now-playing message for chat_id."""
        self.now_playing_msgs[chat_id] = message

    def get_now_playing(self, chat_id):
        """Get the active now-playing message for chat_id."""
        return self.now_playing_msgs.get(chat_id)

    def pop_now_playing(self, chat_id):
        """Pop and return the active now-playing message for chat_id."""
        return self.now_playing_msgs.pop(chat_id, None)

    async def delete_now_playing(self, chat_id):
        """Safely delete and remove the active now-playing message for chat_id."""
        msg = self.pop_now_playing(chat_id)
        if msg:
            try:
                await msg.delete()
            except Exception:
                pass

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

    def set_chat_assistant(self, chat_id: int, assistant_num: int):
        """Record the active assistant index in memory for chat_id."""
        self.chat_assistants[int(chat_id)] = int(assistant_num)

    def get_chat_assistant(self, chat_id: int) -> int | None:
        """Retrieve the in-memory assigned assistant index for chat_id."""
        return self.chat_assistants.get(int(chat_id))

    def remove_chat_assistant(self, chat_id: int):
        """Remove the in-memory assistant assignment for chat_id."""
        self.chat_assistants.pop(int(chat_id), None)

    async def activate(self, chat_id: int, assistant_num: int | None = None):
        """Atomically mark a chat active. Returns True iff it was NOT already active
        (i.e. this caller is the one that should start playback, not enqueue)."""
        async with self.lock(chat_id):
            was_active = chat_id in self.active
            self.active.add(chat_id)
            if assistant_num is not None:
                for ast_idx, ast_set in self.assistant_active.items():
                    if ast_idx != int(assistant_num):
                        ast_set.discard(chat_id)
                self.assistant_active[int(assistant_num)].add(chat_id)
            return not was_active

    async def deactivate(self, chat_id: int):
        """Release a chat's voice-call slot and assistant binding.

        Deliberately does NOT touch `queues` or `playing`: deactivate() runs from
        recoverable error paths (a failed join, a transient stream error) where
        the caller still intends to retry with the queue intact. Callers that do
        want the queue gone (/stop, /end, kicked-from-VC) pop it explicitly.

        Locks are never reaped here either -- `locked()` goes briefly False
        between release() and the woken waiter resuming, so popping the lock
        there hands a *second* lock object to the pending waiter and both
        coroutines proceed as if they held it.
        """
        cid = int(chat_id)
        async with self.lock(cid):
            self.active.discard(cid)
            self.active.discard(chat_id)
            self.chat_assistants.pop(cid, None)
            for ast_set in self.assistant_active.values():
                ast_set.discard(cid)
                ast_set.discard(chat_id)
            self.now_playing_msgs.pop(cid, None)
            self.now_playing_msgs.pop(chat_id, None)

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

