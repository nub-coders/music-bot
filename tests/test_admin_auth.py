"""Authorization tests for plugins/admin_auth.py.

Two regressions are covered:

* `/authlist` (and its `/authusers` alias) had no permission check at all, while
  every sibling in the file has one. Any group member could list the user IDs
  privileged in that chat.
* `/block`, `/unblock` and `/blocklist` read `message.from_user.id` unguarded, so
  a message from an anonymous group admin or a linked channel (`from_user is
  None`) raised AttributeError instead of being refused.
"""
import pytest

import plugins._common as common
import plugins.admin_auth as admin_auth


class FakeCollection:
    """Records reads and writes so tests can assert nothing touched the DB."""

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
        self.is_self = False


class FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class FakeMessage:
    def __init__(self, user_id, chat_id=-100123, text="/block", command=None):
        self.from_user = FakeUser(user_id) if user_id is not None else None
        self.sender_chat = FakeChat(-100999) if user_id is None else None
        self.chat = FakeChat(chat_id)
        self.id = 42
        self.text = text
        self.command = command or [text.lstrip("/").split()[0]]
        self.reply_to_message = None


@pytest.fixture
def replies(monkeypatch):
    """Capture handler output and the @admin_only() denial notice separately.

    `admin_auth` gets its own `rich_reply` binding from the star import, so
    patching both namespaces tells us whether the handler body ran or the
    decorator refused before it.
    """
    body, denials = [], []

    async def _body_reply(message, text, **kwargs):
        body.append(text)

    async def _denial_reply(update, text, **kwargs):
        denials.append(text)

    monkeypatch.setattr(admin_auth, "rich_reply", _body_reply)
    monkeypatch.setattr(common, "rich_reply", _denial_reply)
    return {"body": body, "denials": denials}


@pytest.fixture
def no_db(monkeypatch, owner):
    """Swap both collections admin_auth writes through for recorders."""
    collection = FakeCollection(doc={"bot_id": 777, "busers": []})
    sessions = FakeCollection(doc={"bot_id": 777, "SUDOERS": []})
    monkeypatch.setattr(admin_auth, "collection", collection)
    monkeypatch.setattr(admin_auth, "user_sessions", sessions)
    monkeypatch.setattr(admin_auth, "get_admin_ids", lambda *a, **k: [])
    monkeypatch.setattr(admin_auth, "SUDO", [])
    monkeypatch.setattr(admin_auth, "db_task", lambda coro: None)
    return {"collection": collection, "sessions": sessions}


# ── /authlist gating ──────────────────────────────────────────────────────────

def test_authlist_is_wrapped_by_admin_only():
    """The decorator must stay applied; @wraps leaves __wrapped__ behind."""
    assert hasattr(admin_auth.authlist_handler, "__wrapped__")
    assert admin_auth.authlist_handler.__wrapped__.__name__ == "authlist_handler"


async def test_authlist_denies_unauthorized_user(fake_client, replies, monkeypatch):
    """Regression: any group member could read the chat's authorized-user IDs."""
    seen = []

    async def _deny(client, chat_id, user_id, allow_auth_users=True):
        seen.append((chat_id, user_id))
        return False

    monkeypatch.setattr(common, "is_authorized", _deny)
    monkeypatch.setattr(admin_auth, "AUTH", {"-100123": [11, 22]})

    await admin_auth.authlist_handler(fake_client, FakeMessage(2222, text="/authlist"))

    assert seen == [(-100123, 2222)], "the gate must actually be consulted"
    assert replies["body"] == [], "denied caller must not receive the authorized-user table"
    assert len(replies["denials"]) == 1


async def test_authlist_allows_authorized_user(fake_client, replies, monkeypatch):
    async def _allow(client, chat_id, user_id, allow_auth_users=True):
        return True

    monkeypatch.setattr(common, "is_authorized", _allow)
    monkeypatch.setattr(admin_auth, "AUTH", {"-100123": [11, 22]})

    await admin_auth.authlist_handler(fake_client, FakeMessage(1000, text="/authlist"))

    assert len(replies["body"]) == 1
    assert "11" in replies["body"][0] and "22" in replies["body"][0]
    assert replies["denials"] == []


async def test_authlist_denies_anonymous_sender(fake_client, replies, monkeypatch):
    """from_user is None for anonymous admins and channel posts."""
    async def _must_not_run(*args, **kwargs):
        raise AssertionError("is_authorized reached with no identity")

    async def _get_chat(chat_id):
        class _Chat:
            linked_chat = None
        return _Chat()

    monkeypatch.setattr(common, "is_authorized", _must_not_run)
    monkeypatch.setattr(admin_auth, "AUTH", {"-100123": [11, 22]})
    fake_client.get_chat = _get_chat

    await admin_auth.authlist_handler(fake_client, FakeMessage(None, text="/authlist"))

    assert replies["body"] == []
    assert len(replies["denials"]) == 1


# ── anonymous senders on /block /unblock /blocklist ───────────────────────────

@pytest.mark.parametrize(
    "handler_name,text",
    [
        ("block_user", "/block"),
        ("unblock_user", "/unblock"),
        ("blocklist_handler", "/blocklist"),
    ],
)
async def test_anonymous_sender_is_refused_without_raising(
    fake_client, replies, no_db, handler_name, text
):
    """Regression: `message.from_user.id` raised AttributeError on these."""
    handler = getattr(admin_auth, handler_name)

    await handler(fake_client, FakeMessage(None, text=text))

    assert len(replies["body"]) == 1
    assert "ᴠᴇʀɪꜰʏ" in replies["body"][0], "expected the cannot-verify notice"
    assert no_db["collection"].update_one_calls == []


async def test_anonymous_blocklist_costs_no_db_roundtrip(fake_client, replies, no_db):
    """The guard sits above the find_one, not below it."""
    await admin_auth.blocklist_handler(fake_client, FakeMessage(None, text="/blocklist"))

    assert no_db["sessions"].find_one_calls == []


# ── the normal paths still behave ─────────────────────────────────────────────

async def test_blocklist_still_denies_a_stranger(fake_client, replies, no_db):
    await admin_auth.blocklist_handler(fake_client, FakeMessage(2222, text="/blocklist"))

    assert len(replies["body"]) == 1
    assert replies["body"][0] == admin_auth.rich_note(admin_auth.Messages.OWNER_SUDO_CMD)


async def test_block_still_lets_the_owner_through(fake_client, replies, no_db):
    """Owner with no reply and no argument reaches the usage hint, not a denial."""
    await admin_auth.block_user(fake_client, FakeMessage(1000, text="/block"))

    assert len(replies["body"]) == 1
    assert replies["body"][0] == admin_auth.rich_note(admin_auth.Messages.REPLY_OR_PROVIDE_ID)
