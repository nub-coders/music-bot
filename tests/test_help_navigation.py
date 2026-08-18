"""
tests/test_help_navigation.py — Callback smoke test for every help button, navigation contracts, and role-based visibility.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.button import Buttons
from utils.message import Messages
from plugins.start import commands_callback


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.me = MagicMock()
    client.me.id = 123456
    client.me.username = "testmusicbot"
    client.me.mention = MagicMock(return_value="@testmusicbot")

    owner_user = MagicMock()
    owner_user.id = 6076474757
    owner_user.username = "botowner"
    client.get_users = AsyncMock(return_value=owner_user)
    return client


def make_callback_query(data: str, user_id: int):
    cq = MagicMock()
    cq.data = data
    cq.from_user = MagicMock()
    cq.from_user.id = user_id
    cq.from_user.mention = MagicMock(return_value=f"@user_{user_id}")
    cq.message = MagicMock()
    cq.message.edit_caption = AsyncMock()
    cq.answer = AsyncMock()
    return cq


class TestHelpButtonSmoke:
    """Smoke test ensuring every help category callback resolves without raising exceptions."""

    ALL_CATEGORIES = [
        "playback",
        "auth",
        "blocklist",
        "sudo",
        "broadcast",
        "tools",
        "kang",
        "status",
        "owner",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("category", ALL_CATEGORIES)
    async def test_owner_can_access_all_categories(self, mock_client, category):
        owner_id = 6076474757
        cq = make_callback_query(f"commands_{category}", user_id=owner_id)

        with patch("plugins.start.OWNER_ID", owner_id), \
             patch("plugins.start.SUDO", []), \
             patch("plugins.start.get_admin_ids", return_value=[]):
            await commands_callback(mock_client, cq)

        cq.answer.assert_called_once()
        cq.message.edit_caption.assert_called_once()
        args, kwargs = cq.message.edit_caption.call_args
        assert kwargs.get("reply_markup") == Buttons.BACK
        assert len(kwargs.get("caption", "")) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("public_category", ["playback", "tools", "kang", "status"])
    async def test_regular_user_can_access_public_categories(self, mock_client, public_category):
        regular_user_id = 99999999
        cq = make_callback_query(f"commands_{public_category}", user_id=regular_user_id)

        with patch("plugins.start.OWNER_ID", 6076474757), \
             patch("plugins.start.SUDO", []), \
             patch("plugins.start.get_admin_ids", return_value=[]):
            await commands_callback(mock_client, cq)

        cq.answer.assert_called_once()
        cq.message.edit_caption.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("restricted_category", ["owner", "sudo", "broadcast", "blocklist", "auth"])
    async def test_regular_user_blocked_from_restricted_categories(self, mock_client, restricted_category):
        regular_user_id = 99999999
        cq = make_callback_query(f"commands_{restricted_category}", user_id=regular_user_id)

        with patch("plugins.start.OWNER_ID", 6076474757), \
             patch("plugins.start.SUDO", []), \
             patch("plugins.start.get_admin_ids", return_value=[]):
            await commands_callback(mock_client, cq)

        # Must reject with alert toast and NOT edit caption
        cq.answer.assert_called_once()
        _, kwargs = cq.answer.call_args
        assert kwargs.get("show_alert") is True
        cq.message.edit_caption.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_can_access_auth_category(self, mock_client):
        admin_user_id = 7777777
        cq = make_callback_query("commands_auth", user_id=admin_user_id)

        with patch("plugins.start.OWNER_ID", 6076474757), \
             patch("plugins.start.SUDO", []), \
             patch("plugins.start.get_admin_ids", return_value=[admin_user_id]):
            await commands_callback(mock_client, cq)

        cq.answer.assert_called_once()
        cq.message.edit_caption.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("sudo_category", ["sudo", "broadcast", "blocklist"])
    async def test_sudo_user_can_access_sudo_categories(self, mock_client, sudo_category):
        sudo_user_id = 8888888
        cq = make_callback_query(f"commands_{sudo_category}", user_id=sudo_user_id)

        with patch("plugins.start.OWNER_ID", 6076474757), \
             patch("plugins.start.SUDO", [sudo_user_id]), \
             patch("plugins.start.get_admin_ids", return_value=[]):
            await commands_callback(mock_client, cq)

        cq.answer.assert_called_once()
        cq.message.edit_caption.assert_called_once()


class TestNavigationContracts:
    """Verifies commands_all / commands_help and commands_home / commands_back routing contracts."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("help_action", ["all", "help"])
    async def test_help_action_opens_category_menu(self, mock_client, help_action):
        user_id = 1111111
        cq = make_callback_query(f"commands_{help_action}", user_id=user_id)

        with patch("plugins.start.OWNER_ID", 6076474757), \
             patch("plugins.start.SUDO", []), \
             patch("plugins.start.get_admin_ids", return_value=[]):
            await commands_callback(mock_client, cq)

        cq.answer.assert_called_once()
        cq.message.edit_caption.assert_called_once()
        args, kwargs = cq.message.edit_caption.call_args
        assert kwargs.get("caption") == Messages.HELP_CATEGORY_SELECT

    @pytest.mark.asyncio
    @pytest.mark.parametrize("home_action", ["home", "back"])
    async def test_home_action_returns_to_start_screen(self, mock_client, home_action):
        user_id = 1111111
        cq = make_callback_query(f"commands_{home_action}", user_id=user_id)

        with patch("plugins.start.OWNER_ID", 6076474757), \
             patch("plugins.start.SUDO", []), \
             patch("plugins.start.get_admin_ids", return_value=[]), \
             patch("plugins.start.gvarstatus", AsyncMock(return_value=None)):
            await commands_callback(mock_client, cq)

        cq.answer.assert_called_once()
        cq.message.edit_caption.assert_called_once()


class TestRoleBasedHelpMarkup:
    """Verifies that help_markup filters buttons correctly for each tier."""

    def test_regular_user_sees_only_public_and_home(self):
        markup = Buttons.help_markup(is_admin=False, is_owner=False, is_sudo=False)
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "commands_playback" in callbacks
        assert "commands_kang" in callbacks
        assert "commands_tools" in callbacks
        assert "commands_status" in callbacks
        assert "commands_home" in callbacks

        # Restricted buttons must NOT be present
        assert "commands_auth" not in callbacks
        assert "commands_blocklist" not in callbacks
        assert "commands_sudo" not in callbacks
        assert "commands_broadcast" not in callbacks
        assert "commands_owner" not in callbacks

    def test_admin_sees_auth_in_addition_to_public(self):
        markup = Buttons.help_markup(is_admin=True, is_owner=False, is_sudo=False)
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "commands_auth" in callbacks
        assert "commands_sudo" not in callbacks
        assert "commands_owner" not in callbacks

    def test_sudo_sees_sudo_blocklist_broadcast(self):
        markup = Buttons.help_markup(is_admin=True, is_owner=False, is_sudo=True)
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "commands_auth" in callbacks
        assert "commands_blocklist" in callbacks
        assert "commands_sudo" in callbacks
        assert "commands_broadcast" in callbacks
        assert "commands_owner" not in callbacks

    def test_owner_sees_all_categories(self):
        markup = Buttons.help_markup(is_admin=True, is_owner=True, is_sudo=True)
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "commands_owner" in callbacks
        assert "commands_sudo" in callbacks
        assert "commands_broadcast" in callbacks
        assert "commands_blocklist" in callbacks
        assert "commands_auth" in callbacks
        assert "commands_playback" in callbacks
        assert "commands_home" in callbacks
