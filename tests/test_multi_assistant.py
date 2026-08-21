import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from state import SessionStore
import config
import tools


def test_config_multi_sessions():
    """Test that STRING_SESSIONS list correctly collects non-empty session strings."""
    assert isinstance(config.STRING_SESSIONS, list)
    assert hasattr(config, "AUTO_LEAVING_ASSISTANT")
    assert hasattr(config, "ASSISTANT_LEAVE_TIME")


def test_session_store_multi_assistant_state():
    """Test SessionStore per-assistant active tracking and chat-assistant mappings."""
    store = SessionStore()
    chat_1 = -100123456789
    chat_2 = -100987654321

    # Mapping
    store.set_chat_assistant(chat_1, 2)
    assert store.get_chat_assistant(chat_1) == 2
    assert store.get_chat_assistant(chat_2) is None

    store.remove_chat_assistant(chat_1)
    assert store.get_chat_assistant(chat_1) is None


@pytest.mark.asyncio
async def test_session_store_activate_and_deactivate():
    """Test activate/deactivate tracking per assistant."""
    store = SessionStore()
    chat_1 = -100111
    chat_2 = -100222

    # Activate chat 1 on Assistant 1
    res1 = await store.activate(chat_1, assistant_num=1)
    assert res1 is True
    assert chat_1 in store.active
    assert chat_1 in store.assistant_active[1]

    # Activate chat 2 on Assistant 2
    res2 = await store.activate(chat_2, assistant_num=2)
    assert res2 is True
    assert chat_2 in store.active
    assert chat_2 in store.assistant_active[2]

    # Deactivate chat 1
    await store.deactivate(chat_1)
    assert chat_1 not in store.active
    assert chat_1 not in store.assistant_active[1]
    assert chat_2 in store.active
    assert chat_2 in store.assistant_active[2]


def test_least_loaded_assistant():
    """Test get_least_loaded_assistant correctly picks the assistant with lowest active count."""
    # Reset tools state
    tools.assistants.clear()
    tools.calls.clear()
    tools.state.assistant_active.clear()

    # Set up 3 mock assistants
    tools.assistants[1] = MagicMock()
    tools.assistants[2] = MagicMock()
    tools.assistants[3] = MagicMock()

    # All have 0 active calls -> should pick first available (1)
    assert tools.get_least_loaded_assistant() == 1

    # Assistant 1 has 2 calls, Assistant 2 has 1 call, Assistant 3 has 0 calls
    tools.state.assistant_active[1] = {-1001, -1002}
    tools.state.assistant_active[2] = {-1003}
    tools.state.assistant_active[3] = set()

    assert tools.get_least_loaded_assistant() == 3

    # Assistant 3 gets a call -> now Assistant 2 and 3 both have 1 call -> should pick 2
    tools.state.assistant_active[3] = {-1004}
    assert tools.get_least_loaded_assistant() == 2


@pytest.mark.asyncio
async def test_get_assistant_routing_memory_and_db():
    """Test get_assistant resolves via memory, then DB, then least-loaded allocation."""
    tools.assistants.clear()
    tools.calls.clear()
    tools.state.chat_assistants.clear()
    tools.state.assistant_active.clear()

    ast1 = MagicMock()
    ast2 = MagicMock()
    call1 = MagicMock()
    call2 = MagicMock()

    tools.assistants[1] = ast1
    tools.assistants[2] = ast2
    tools.calls[1] = call1
    tools.calls[2] = call2

    chat_id = -100555

    with patch("tools.db_get_chat_assistant", new_callable=AsyncMock) as mock_db_get, \
         patch("tools.db_set_chat_assistant", new_callable=AsyncMock) as mock_db_set:

        # Case 1: Unassigned in memory and DB -> assign least-loaded (Assistant 1)
        mock_db_get.return_value = None
        num, u_client, cp_client = await tools.get_assistant(chat_id)
        assert num == 1
        assert u_client == ast1
        assert cp_client == call1
        assert tools.state.get_chat_assistant(chat_id) == 1

        # Case 2: In-memory cache hit
        mock_db_get.reset_mock()
        num, u_client, cp_client = await tools.get_assistant(chat_id)
        assert num == 1
        mock_db_get.assert_not_called()

        # Case 3: Memory miss but DB has Assistant 2
        tools.state.remove_chat_assistant(chat_id)
        mock_db_get.return_value = 2
        num, u_client, cp_client = await tools.get_assistant(chat_id)
        assert num == 2
        assert u_client == ast2
        assert cp_client == call2
        assert tools.state.get_chat_assistant(chat_id) == 2


@pytest.mark.asyncio
async def test_change_assistant_cycling():
    """Test change_assistant cycles sequentially through available assistants."""
    tools.assistants.clear()
    tools.calls.clear()
    tools.state.chat_assistants.clear()

    tools.assistants[1] = MagicMock()
    tools.assistants[2] = MagicMock()
    tools.assistants[3] = MagicMock()

    chat_id = -100777
    tools.state.set_chat_assistant(chat_id, 1)

    with patch("tools.db_set_chat_assistant", new_callable=AsyncMock):
        # 1 -> 2
        num, _, _ = await tools.change_assistant(chat_id)
        assert num == 2

        # 2 -> 3
        num, _, _ = await tools.change_assistant(chat_id)
        assert num == 3

        # 3 -> 1 (wrap-around)
        num, _, _ = await tools.change_assistant(chat_id)
        assert num == 1


def test_get_call_client_resolution():
    """Test get_call_client returns the correct PyTgCalls instance."""
    tools.calls.clear()
    tools.state.chat_assistants.clear()
    tools.state.playing.clear()

    call1 = MagicMock()
    call2 = MagicMock()
    tools.calls[1] = call1
    tools.calls[2] = call2
    tools.clients["call_py"] = call1

    chat_id = -100888

    # Default fallback
    assert tools.get_call_client(chat_id) == call1

    # Assigned Assistant 2
    tools.state.set_chat_assistant(chat_id, 2)
    assert tools.get_call_client(chat_id) == call2


@pytest.mark.asyncio
async def test_activate_unassigned_does_not_pollute_assistant_load():
    """Verify that state.activate(chat_id) without assistant_num does not register
    phantom active calls under Assistant 1."""
    store = SessionStore()
    chat_a = -100999

    # 1. /play runs activate() without assistant_num
    first = await store.activate(chat_a)
    assert first is True
    assert chat_a in store.active
    assert chat_a not in store.assistant_active[1]
    assert len(store.assistant_active[1]) == 0

    # 2. join_call assigns Assistant 3
    await store.activate(chat_a, assistant_num=3)
    assert chat_a in store.assistant_active[3]
    assert chat_a not in store.assistant_active[1]

    # 3. Switching/re-activating to Assistant 2 cleans up Assistant 3
    await store.activate(chat_a, assistant_num=2)
    assert chat_a in store.assistant_active[2]
    assert chat_a not in store.assistant_active[3]
    assert chat_a not in store.assistant_active[1]


@pytest.mark.asyncio
async def test_concurrent_get_assistant_load_balancing():
    """Verify that concurrent get_assistant() calls from two distinct chats
    distribute across available assistants without race conditions."""
    import asyncio
    tools.assistants.clear()
    tools.calls.clear()
    tools.state.chat_assistants.clear()
    tools.state.assistant_active.clear()
    tools.state.active.clear()

    tools.assistants[1] = MagicMock()
    tools.assistants[2] = MagicMock()
    tools.calls[1] = MagicMock()
    tools.calls[2] = MagicMock()

    chat_a = -100111
    chat_b = -100222

    # Both chats marked active by /play
    await tools.state.activate(chat_a)
    await tools.state.activate(chat_b)

    async def slow_db_get(cid):
        await asyncio.sleep(0.01)  # Simulate DB latency yielding event loop
        return None

    with patch("tools.db_get_chat_assistant", side_effect=slow_db_get), \
         patch("tools.db_set_chat_assistant", new_callable=AsyncMock):

        res_a, res_b = await asyncio.gather(
            tools.get_assistant(chat_a),
            tools.get_assistant(chat_b),
        )

        num_a = res_a[0]
        num_b = res_b[0]

        # The two concurrent chats must get distinct assistants (1 and 2)
        assert {num_a, num_b} == {1, 2}


@pytest.mark.asyncio
async def test_assistant_autoleave_loop_respects_auth_and_startup_grace():
    """Verify that _assistant_autoleave_loop does not leave authorized chats or
    chats immediately after boot."""
    from main import _assistant_autoleave_loop
    import main as main_mod

    mock_ast = MagicMock()
    left_chats = []

    async def mock_leave(cid):
        left_chats.append(cid)

    mock_ast.leave_chat = AsyncMock(side_effect=mock_leave)

    auth_chat = MagicMock()
    auth_chat.id = -100901
    auth_chat.type = "supergroup"
    auth_chat.title = "Auth Chat"

    new_boot_chat = MagicMock()
    new_boot_chat.id = -100902
    new_boot_chat.type = "group"
    new_boot_chat.title = "Boot Chat"

    stale_chat = MagicMock()
    stale_chat.id = -100903
    stale_chat.type = "supergroup"
    stale_chat.title = "Stale Chat"

    async def mock_get_dialogs():
        for d in [
            MagicMock(chat=auth_chat),
            MagicMock(chat=new_boot_chat),
            MagicMock(chat=stale_chat),
        ]:
            yield d

    mock_ast.get_dialogs = mock_get_dialogs

    main_mod.assistants[1] = mock_ast
    main_mod.AUTH["-100901"] = [12345]  # Auth chat
    tools.state.active.clear()
    tools.state.assistant_active.clear()
    # auth_chat and new_boot_chat not in state.played (defaults to StartTime)
    # stale_chat played 10000s ago
    tools.state.played[-100903] = time.time() - 10000

    # Run loop for 1 iteration (break out via Exception or task cancellation)
    with patch("main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.side_effect = [None, None, asyncio.CancelledError()]
        try:
            await _assistant_autoleave_loop(check_interval_seconds=1)
        except asyncio.CancelledError:
            pass

    # Only the truly stale non-exempt chat should be left
    assert -100903 in left_chats
    assert -100901 not in left_chats  # Auth chat must NOT be left
    assert -100902 not in left_chats  # Unrecorded boot chat must NOT be left



