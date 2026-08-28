"""Authorization tests for the broadcast flow.

Every broadcast entry point must be gated: the /broadcast command, the panel
callback that actually fans out to every stored chat, and the setting toggles.
The callback previously had no check at all, and the toggle wrote to Mongo
before delegating to the handler that performed the check.
"""
import pytest

import plugins.broadcast as broadcast


class FakeCollection:
    """Records writes so tests can assert nothing was persisted on a denial."""

    def __init__(self, doc=None):
        self.doc = doc
        self.find_one_calls = []
        self.update_one_calls = []

    async def find_one(self, query, *args, **kwargs):
        self.find_one_calls.append(query)
        return self.doc

    async def update_one(self, query, update, **kwargs):
        self.update_one_calls.append((query, update))
        return None


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class FakeCallbackQuery:
    def __init__(self, user_id, data="broadcast"):
        self.from_user = FakeUser(user_id) if user_id is not None else None
        self.data = data
        self.answers = []

    async def answer(self, text=None, show_alert=None, **kwargs):
        self.answers.append({"text": text, "show_alert": show_alert})


@pytest.fixture
def owner_only(monkeypatch, owner):
    """Owner 1000 configured; no admin.txt admins; no DB sudoers."""
    coll = FakeCollection(doc={"bot_id": 777})
    monkeypatch.setattr(broadcast, "user_sessions", coll)
    monkeypatch.setattr(broadcast, "get_admin_ids", lambda *a, **k: [])
    return coll


# ── _is_broadcast_authorized ──────────────────────────────────────────────────

async def test_owner_is_authorized(fake_client, owner_only):
    assert await broadcast._is_broadcast_authorized(fake_client, 1000) is True


async def test_stranger_is_denied(fake_client, owner_only):
    assert await broadcast._is_broadcast_authorized(fake_client, 2222) is False


async def test_anonymous_sender_is_denied(fake_client, owner_only):
    """Anonymous admins and channel senders arrive with from_user is None; the
    check must fail closed rather than raising or passing."""
    assert await broadcast._is_broadcast_authorized(fake_client, None) is False


async def test_user_id_zero_is_denied(fake_client, owner_only):
    assert await broadcast._is_broadcast_authorized(fake_client, 0) is False


async def test_db_sudoer_is_authorized(fake_client, monkeypatch, owner):
    monkeypatch.setattr(broadcast, "user_sessions", FakeCollection(doc={"SUDOERS": [4242]}))
    monkeypatch.setattr(broadcast, "get_admin_ids", lambda *a, **k: [])

    assert await broadcast._is_broadcast_authorized(fake_client, 4242) is True
    assert await broadcast._is_broadcast_authorized(fake_client, 4243) is False


async def test_owner_tier_admin_is_authorized(fake_client, monkeypatch, owner):
    """get_admin_ids() is DB-backed and must be consulted even when the legacy
    admin.txt file is absent."""
    monkeypatch.setattr(broadcast, "user_sessions", FakeCollection(doc={}))
    monkeypatch.setattr(broadcast, "get_admin_ids", lambda *a, **k: [55])

    assert await broadcast._is_broadcast_authorized(fake_client, 55) is True


async def test_ownerless_mode_denies_everyone_without_sudo(fake_client, monkeypatch, owner):
    """OWNER_ID == 0 means 'no owner'. It must not match any caller."""
    monkeypatch.setattr(broadcast, "user_sessions", FakeCollection(doc={}))
    monkeypatch.setattr(broadcast, "get_admin_ids", lambda *a, **k: [])
    owner(0)

    for candidate in (0, 1, 1000, 999999):
        assert await broadcast._is_broadcast_authorized(fake_client, candidate) is False


async def test_missing_db_doc_is_denied_not_crashed(fake_client, monkeypatch, owner):
    monkeypatch.setattr(broadcast, "user_sessions", FakeCollection(doc=None))
    monkeypatch.setattr(broadcast, "get_admin_ids", lambda *a, **k: [])

    assert await broadcast._is_broadcast_authorized(fake_client, 2222) is False


# ── broadcast callback handler ────────────────────────────────────────────────

async def test_unauthorized_callback_never_reaches_the_send_loop(fake_client, owner_only, monkeypatch):
    """Regression: ^broadcast$ ran the full fan-out with no authorization check."""
    def _must_not_run():
        raise AssertionError("broadcast_semaphore() reached by an unauthorized user")

    monkeypatch.setattr(broadcast, "broadcast_semaphore", _must_not_run)
    cb = FakeCallbackQuery(2222)

    await broadcast.broadcast_callback_handler(fake_client, cb)

    assert len(cb.answers) == 1
    assert cb.answers[0]["show_alert"] is True


async def test_anonymous_callback_is_rejected(fake_client, owner_only, monkeypatch):
    def _must_not_run():
        raise AssertionError("broadcast_semaphore() reached by an anonymous sender")

    monkeypatch.setattr(broadcast, "broadcast_semaphore", _must_not_run)
    cb = FakeCallbackQuery(None)

    await broadcast.broadcast_callback_handler(fake_client, cb)

    assert cb.answers[0]["show_alert"] is True


async def test_authorized_callback_gets_past_the_auth_gate(fake_client, owner_only, monkeypatch):
    """The owner must not be rejected; we stop at the semaphore to avoid running
    the real fan-out."""
    class _LockedSem:
        def locked(self):
            return True

    monkeypatch.setattr(broadcast, "broadcast_semaphore", lambda: _LockedSem())
    cb = FakeCallbackQuery(1000)

    await broadcast.broadcast_callback_handler(fake_client, cb)

    assert cb.answers[0]["text"] == "Another broadcast is in progress. Please wait."


# ── toggle_setting ────────────────────────────────────────────────────────────

async def test_unauthorized_toggle_persists_nothing(fake_client, owner_only):
    """Regression: the setting was written to Mongo before the permission check."""
    cb = FakeCallbackQuery(2222, data="toggle_forward")

    await broadcast.toggle_setting(fake_client, cb)

    assert owner_only.update_one_calls == [], "denied toggle must not mutate broadcast settings"
    assert cb.answers[0]["show_alert"] is True


async def test_anonymous_toggle_persists_nothing(fake_client, owner_only):
    cb = FakeCallbackQuery(None, data="toggle_pin")

    await broadcast.toggle_setting(fake_client, cb)

    assert owner_only.update_one_calls == []


async def test_authorized_toggle_writes_flipped_value(fake_client, owner_only, monkeypatch):
    owner_only.doc = {"bot_id": 777, "forward": False}
    calls = []

    async def _fake_command_handler(client, message, user_data=None):
        calls.append(user_data)

    monkeypatch.setattr(broadcast, "broadcast_command_handler", _fake_command_handler)
    cb = FakeCallbackQuery(1000, data="toggle_forward")

    await broadcast.toggle_setting(fake_client, cb)

    assert len(owner_only.update_one_calls) == 1
    _query, update = owner_only.update_one_calls[0]
    assert update == {"$set": {"forward": True}}
    assert calls == [{"bot_id": 777, "forward": True}]
