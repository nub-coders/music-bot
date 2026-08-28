"""Tests for the two named privilege tiers in tools.py.

Every bot-level command used to inline its own variant of
`is_admin or is_bot_owner(uid) or uid in SUDO`, and the variants disagreed:
/leaveall dropped the ADMIN term entirely, and /blocklist wrapped its ADMIN
lookup in `os.path.exists(admin.txt)` even though get_admin_ids() has been
DB-backed since that file was retired -- so the whole ADMIN tier was skipped in
every INITIAL_ADMIN_IDS deployment. Both now go through is_bot_operator.

The grantor tier is separate on purpose: a sudoer must not be able to widen the
sudo list, so /addsudo, /rmsudo and /sudolist gate on is_owner_tier.
"""
import pytest

import plugins.admin_auth as admin_auth
import plugins.admin_sudo as admin_sudo
import plugins.info as info
import tools

OWNER = 1000
ADMIN_USER = 55
SUDO_USER = 66
STRANGER = 2222


@pytest.fixture(autouse=True)
def acl(monkeypatch, owner):
    """Owner 1000, one owner-tier admin, one sudoer.

    Patches the definitions in tools, not the plugins' star-imported copies:
    is_owner_tier / is_bot_operator resolve ADMIN and SUDO from tools at call
    time, so patching a plugin module's copy would be a no-op.
    """
    monkeypatch.setattr(tools, "ADMIN", [ADMIN_USER])
    monkeypatch.setattr(tools, "SUDO", [SUDO_USER])


# ── the predicates ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("user_id,expected", [
    (OWNER, True),
    (ADMIN_USER, True),
    (SUDO_USER, True),
    (STRANGER, False),
    (None, False),
    (0, False),
])
def test_bot_operator_tier(user_id, expected):
    assert tools.is_bot_operator(user_id) is expected


@pytest.mark.parametrize("user_id,expected", [
    (OWNER, True),
    (ADMIN_USER, True),
    (SUDO_USER, False),  # a sudoer may not grant sudo
    (STRANGER, False),
    (None, False),
    (0, False),
])
def test_owner_tier_excludes_sudoers(user_id, expected):
    assert tools.is_owner_tier(user_id) is expected


def test_ownerless_mode_matches_nobody_by_owner_id(owner, monkeypatch):
    """OWNER_ID == 0 is 'no owner'; only ADMIN/SUDO membership can still pass."""
    owner(0)
    monkeypatch.setattr(tools, "ADMIN", [])
    monkeypatch.setattr(tools, "SUDO", [])
    for candidate in (0, 1, OWNER, 999999):
        assert tools.is_bot_operator(candidate) is False
        assert tools.is_owner_tier(candidate) is False


def test_mirror_mutations_are_seen_immediately():
    """SUDO is mutated in place by _grant_sudo/_revoke_sudo, never rebound, so the
    predicate must not snapshot it."""
    assert tools.is_bot_operator(4242) is False
    tools.SUDO.append(4242)
    assert tools.is_bot_operator(4242) is True
    tools.SUDO.remove(4242)
    assert tools.is_bot_operator(4242) is False


# ── the two handlers that used to disagree ────────────────────────────────────

class FakeChat:
    def __init__(self, chat_id=-1001234567890):
        self.id = chat_id


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class FakeMessage:
    """Records the replies a handler produced, and nothing else."""

    def __init__(self, user_id, text="/leaveall"):
        self.from_user = FakeUser(user_id) if user_id is not None else None
        self.chat = FakeChat()
        self.text = text
        self.command = text.lstrip("/").split()
        self.id = 4242
        self.reply_to_message = None


@pytest.fixture
def replies(monkeypatch):
    """Capture rich_reply bodies from both handler modules under test."""
    captured = []

    async def _rich_reply(message, body, **kwargs):
        captured.append(body)
        return None

    monkeypatch.setattr(info, "rich_reply", _rich_reply)
    monkeypatch.setattr(admin_auth, "rich_reply", _rich_reply)
    return captured


def _denied(replies_list, module):
    return replies_list == [module.rich_note(module.Messages.OWNER_SUDO_CMD)]


async def test_leaveall_denies_a_stranger(fake_client, replies):
    await info.leave_all_handler(fake_client, FakeMessage(STRANGER))
    assert _denied(replies, info)


async def test_leaveall_denies_an_anonymous_sender(fake_client, replies):
    await info.leave_all_handler(fake_client, FakeMessage(None))
    assert _denied(replies, info)


@pytest.mark.parametrize("user_id", [OWNER, SUDO_USER, ADMIN_USER])
async def test_leaveall_admits_every_operator_tier(fake_client, replies, monkeypatch, user_id):
    """Regression: the ADMIN term was missing, so an owner-tier admin could reboot
    the bot but was refused here."""
    def _explode(*a, **k):
        raise AssertionError("handler proceeded past the auth gate, as expected")

    monkeypatch.setattr(info, "RichDraft", _explode)

    with pytest.raises(AssertionError, match="past the auth gate"):
        await info.leave_all_handler(fake_client, FakeMessage(user_id))
    assert replies == [], "an authorized operator must not be sent a denial"


async def test_blocklist_denies_a_stranger_before_touching_the_database(fake_client, replies, monkeypatch):
    class _Collection:
        async def find_one(self, *a, **k):
            raise AssertionError("denied /blocklist must not query Mongo")

    monkeypatch.setattr(admin_auth, "collection", _Collection())
    await admin_auth.blocklist_handler(fake_client, FakeMessage(STRANGER, "/blocklist"))
    assert _denied(replies, admin_auth)


@pytest.mark.parametrize("user_id", [OWNER, SUDO_USER, ADMIN_USER])
async def test_blocklist_admits_every_operator_tier(fake_client, replies, monkeypatch, user_id):
    """Regression: the ADMIN lookup sat behind `os.path.exists(admin.txt)`, so the
    owner-tier list was skipped in every deployment without that legacy file."""
    class _Collection:
        async def find_one(self, *a, **k):
            raise AssertionError("handler proceeded past the auth gate, as expected")

    monkeypatch.setattr(admin_auth, "collection", _Collection())

    with pytest.raises(AssertionError, match="past the auth gate"):
        await admin_auth.blocklist_handler(fake_client, FakeMessage(user_id, "/blocklist"))
    assert replies == []


async def test_sudolist_refuses_a_sudoer(fake_client, monkeypatch):
    """The grantor boundary: sudoers must not be able to inspect or widen the list."""
    captured = []

    async def _rich_reply(message, body, **kwargs):
        captured.append(body)
        return None

    class _Sessions:
        async def find_one(self, *a, **k):
            raise AssertionError("denied /sudolist must not query Mongo")

    monkeypatch.setattr(admin_sudo, "rich_reply", _rich_reply)
    monkeypatch.setattr(admin_sudo, "user_sessions", _Sessions())

    await admin_sudo.show_sudo_list(fake_client, FakeMessage(SUDO_USER, "/sudolist"))
    assert captured == [admin_sudo.rich_note(admin_sudo.Messages.PAID_OWNER_CMD)]
