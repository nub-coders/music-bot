"""Tests for plugins/_common.is_authorized -- the shared answer behind
@admin_only() and every handler that gates transport controls."""
import pytest
from pyrogram.enums import ChatMemberStatus

import plugins._common as common
import tools

CHAT = -1001234567890


class FakeMember:
    def __init__(self, status):
        self.status = status


class FakeClient:
    """Counts get_chat_member round-trips so cache behaviour is observable."""

    def __init__(self, status=ChatMemberStatus.MEMBER, raises=None):
        self.status = status
        self.raises = raises
        self.calls = 0

    async def get_chat_member(self, chat_id, user_id):
        self.calls += 1
        if self.raises:
            raise self.raises
        return FakeMember(self.status)


@pytest.fixture(autouse=True)
def clean_auth_state(monkeypatch, owner):
    """Isolate the in-memory ACLs and the 60s admin-status cache per test.

    The `owner` fixture pins config.OWNER_ID to 1000. `is_authorized` delegates to
    `tools.is_bot_operator`, which reads `tools.ADMIN` / `tools.SUDO` and
    `config.OWNER_ID` directly, so patching this module's star-imported copies of
    those names would be a no-op -- patch the definitions instead.
    """
    monkeypatch.setattr(tools, "ADMIN", [])
    monkeypatch.setattr(tools, "SUDO", [])
    monkeypatch.setattr(common, "AUTH", {})
    common._admin_member_cache.clear()
    yield
    common._admin_member_cache.clear()


async def test_owner_authorized_without_telegram_call():
    client = FakeClient()
    assert await common.is_authorized(client, CHAT, 1000) is True
    assert client.calls == 0, "in-memory checks must short-circuit the API round-trip"


async def test_admin_list_member_authorized(monkeypatch):
    monkeypatch.setattr(tools, "ADMIN", [55])
    client = FakeClient()
    assert await common.is_authorized(client, CHAT, 55) is True
    assert client.calls == 0


async def test_sudo_member_authorized(monkeypatch):
    monkeypatch.setattr(tools, "SUDO", [66])
    client = FakeClient()
    assert await common.is_authorized(client, CHAT, 66) is True
    assert client.calls == 0


async def test_auth_user_allowed_only_when_flag_set(monkeypatch):
    monkeypatch.setattr(common, "AUTH", {str(CHAT): [77]})

    assert await common.is_authorized(FakeClient(), CHAT, 77, allow_auth_users=True) is True
    assert await common.is_authorized(FakeClient(), CHAT, 77, allow_auth_users=False) is False


async def test_auth_user_is_scoped_to_its_chat(monkeypatch):
    monkeypatch.setattr(common, "AUTH", {str(CHAT): [77]})
    assert await common.is_authorized(FakeClient(), -100999, 77) is False


@pytest.mark.parametrize("status,expected", [
    (ChatMemberStatus.OWNER, True),
    (ChatMemberStatus.ADMINISTRATOR, True),
    (ChatMemberStatus.MEMBER, False),
    (ChatMemberStatus.RESTRICTED, False),
    (ChatMemberStatus.LEFT, False),
    (ChatMemberStatus.BANNED, False),
])
async def test_chat_member_status_decides_fallback(status, expected):
    assert await common.is_authorized(FakeClient(status), CHAT, 999) is expected


async def test_chat_member_result_is_cached():
    client = FakeClient(ChatMemberStatus.ADMINISTRATOR)
    assert await common.is_authorized(client, CHAT, 999) is True
    assert await common.is_authorized(client, CHAT, 999) is True
    assert client.calls == 1, "second call should be served from _admin_member_cache"


async def test_cache_is_keyed_per_chat_and_user():
    client = FakeClient(ChatMemberStatus.ADMINISTRATOR)
    await common.is_authorized(client, CHAT, 999)
    await common.is_authorized(client, CHAT, 1001)
    await common.is_authorized(client, -100999, 999)
    assert client.calls == 3


async def test_expired_cache_entry_is_refetched(monkeypatch):
    client = FakeClient(ChatMemberStatus.ADMINISTRATOR)
    await common.is_authorized(client, CHAT, 999)

    status_value, _expires = common._admin_member_cache[(CHAT, 999)]
    common._admin_member_cache[(CHAT, 999)] = (status_value, 0)  # expired

    await common.is_authorized(client, CHAT, 999)
    assert client.calls == 2


async def test_get_chat_member_failure_fails_closed():
    client = FakeClient(raises=RuntimeError("peer id invalid"))
    assert await common.is_authorized(client, CHAT, 999) is False


async def test_unknown_user_denied_in_ownerless_mode(owner):
    """OWNER_ID == 0 must not match a caller; only the chat-admin fallback can pass.

    `str(0) == str(0)` is True, so without the HAS_OWNER gate any call site that
    passes a defaulted user_id of 0 would be treated as the owner.
    """
    owner(0)
    client = FakeClient(ChatMemberStatus.MEMBER)
    assert await common.is_authorized(client, CHAT, 0) is False
    assert await common.is_authorized(client, CHAT, 1000) is False
