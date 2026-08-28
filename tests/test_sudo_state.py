"""Tests for sudo grant/revoke persistence in plugins/admin_sudo.py.

Sudo state lives in two places: the SUDOERS array in Mongo (authoritative) and the
in-memory SUDO list (a mirror rebuilt at startup). The write path used to fire the
Mongo update through a bare `asyncio.create_task()` and then mutate SUDO
unconditionally, so a failed write disappeared while the reply still confirmed the
change -- the grant held until the next restart and then silently did not.
"""
import pytest

import plugins.admin_sudo as admin_sudo


class FakeCollection:
    def __init__(self, doc=None):
        self.doc = doc

    async def find_one(self, query, *args, **kwargs):
        return self.doc


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id
        self.is_self = False


class FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class FakeMessage:
    def __init__(self, user_id, text="/addsudo 555", chat_id=-100123):
        self.from_user = FakeUser(user_id) if user_id is not None else None
        self.sender_chat = FakeChat(-100999) if user_id is None else None
        self.chat = FakeChat(chat_id)
        self.id = 42
        self.text = text
        self.command = [text.lstrip("/").split()[0]]
        self.reply_to_message = None


@pytest.fixture
def sudo_env(monkeypatch, owner):
    """Owner 1000, no bot admins, empty SUDOERS, recorded writes."""
    writes = []

    async def _push(collection, filter, field, value, upsert=False):
        writes.append(("push", field, value))
        return None

    async def _pull(collection, filter, field, value, upsert=False):
        writes.append(("pull", field, value))
        return None

    replies = []

    async def _reply(message, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(admin_sudo, "user_sessions", FakeCollection(doc={"SUDOERS": []}))
    monkeypatch.setattr(admin_sudo, "get_admin_ids", lambda *a, **k: [])
    monkeypatch.setattr(admin_sudo, "SUDO", [])
    monkeypatch.setattr(admin_sudo, "push_to_array", _push)
    monkeypatch.setattr(admin_sudo, "pull_from_array", _pull)
    monkeypatch.setattr(admin_sudo, "rich_reply", _reply)
    return {"writes": writes, "replies": replies}


def _fail_writes(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("mongo unreachable")

    monkeypatch.setattr(admin_sudo, "push_to_array", _boom)
    monkeypatch.setattr(admin_sudo, "pull_from_array", _boom)


# ── _grant_sudo ───────────────────────────────────────────────────────────────

async def test_grant_persists_then_mirrors(fake_client, sudo_env):
    assert await admin_sudo._grant_sudo(fake_client, 555) is True
    assert sudo_env["writes"] == [("push", "SUDOERS", 555)]
    assert admin_sudo.SUDO == [555]


async def test_grant_reports_failure_and_does_not_mirror(fake_client, sudo_env, monkeypatch):
    """Regression: the mirror was updated even when the write never landed."""
    _fail_writes(monkeypatch)

    assert await admin_sudo._grant_sudo(fake_client, 555) is False
    assert admin_sudo.SUDO == [], "a failed write must not grant sudo in memory"


async def test_grant_is_idempotent_in_the_mirror(fake_client, sudo_env):
    await admin_sudo._grant_sudo(fake_client, 555)
    await admin_sudo._grant_sudo(fake_client, 555)

    assert admin_sudo.SUDO == [555]


# ── _revoke_sudo ──────────────────────────────────────────────────────────────

async def test_revoke_persists_then_mirrors(fake_client, sudo_env):
    admin_sudo.SUDO.append(555)

    assert await admin_sudo._revoke_sudo(fake_client, 555) is True
    assert sudo_env["writes"] == [("pull", "SUDOERS", 555)]
    assert admin_sudo.SUDO == []


async def test_revoke_reports_failure_and_keeps_the_mirror(fake_client, sudo_env, monkeypatch):
    admin_sudo.SUDO.append(555)
    _fail_writes(monkeypatch)

    assert await admin_sudo._revoke_sudo(fake_client, 555) is False
    assert admin_sudo.SUDO == [555], "a failed write must not revoke sudo in memory"


async def test_revoke_survives_a_drifted_mirror(fake_client, sudo_env):
    """The user is in the DB but not in SUDO -- the bare list.remove() raised here."""
    assert await admin_sudo._revoke_sudo(fake_client, 555) is True
    assert admin_sudo.SUDO == []


# ── /addsudo end to end ───────────────────────────────────────────────────────

async def test_addsudo_confirms_only_after_a_successful_write(fake_client, sudo_env):
    await admin_sudo.add_to_sudo(fake_client, FakeMessage(1000, text="/addsudo 555"))

    assert admin_sudo.SUDO == [555]
    assert sudo_env["writes"] == [("push", "SUDOERS", 555)]
    assert "555" in sudo_env["replies"][-1]


async def test_addsudo_reports_a_failed_write_instead_of_confirming(fake_client, sudo_env, monkeypatch):
    _fail_writes(monkeypatch)

    await admin_sudo.add_to_sudo(fake_client, FakeMessage(1000, text="/addsudo 555"))

    assert admin_sudo.SUDO == []
    assert sudo_env["replies"][-1] == admin_sudo.rich_note(admin_sudo.Messages.ERR_SUDO_WRITE)


async def test_addsudo_still_refuses_a_stranger(fake_client, sudo_env):
    await admin_sudo.add_to_sudo(fake_client, FakeMessage(2222, text="/addsudo 555"))

    assert sudo_env["writes"] == []
    assert admin_sudo.SUDO == []


# ── anonymous senders ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "handler_name,text",
    [
        ("show_sudo_list", "/sudolist"),
        ("add_to_sudo", "/addsudo 555"),
        ("remove_from_sudo", "/rmsudo 555"),
    ],
)
async def test_anonymous_sender_is_refused_without_raising(fake_client, sudo_env, handler_name, text):
    """These commands are not private-only, so from_user can be None."""
    handler = getattr(admin_sudo, handler_name)

    await handler(fake_client, FakeMessage(None, text=text))

    assert sudo_env["writes"] == []
    assert sudo_env["replies"][-1] == admin_sudo.rich_note(admin_sudo.Messages.ADMIN_UNKNOWN_USER)
