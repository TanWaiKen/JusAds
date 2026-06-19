"""
test_ws_manager.py
──────────────────
Unit tests for the WebSocket ConnectionManager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.ws_manager import ConnectionManager


@pytest.fixture
def manager():
    """Create a fresh ConnectionManager instance."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket with async methods."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ── Connection lifecycle tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_accepts_websocket_and_stores_connection(manager, mock_websocket):
    """connect() should accept the WebSocket and store it by check_id."""
    await manager.connect("check-001", mock_websocket)

    mock_websocket.accept.assert_called_once()
    assert manager.get_connection("check-001") is mock_websocket


@pytest.mark.asyncio
async def test_disconnect_removes_connection(manager, mock_websocket):
    """disconnect() should remove the connection from active set."""
    await manager.connect("check-001", mock_websocket)
    manager.disconnect("check-001")

    assert manager.get_connection("check-001") is None


def test_disconnect_nonexistent_check_does_not_raise(manager):
    """disconnect() with unknown check_id should not raise."""
    manager.disconnect("nonexistent-id")  # Should not raise


def test_get_connection_returns_none_for_unknown_id(manager):
    """get_connection() should return None for unknown check_id."""
    assert manager.get_connection("unknown") is None


@pytest.mark.asyncio
async def test_connect_replaces_existing_connection(manager, mock_websocket):
    """Connecting with same check_id should replace the previous connection."""
    ws2 = AsyncMock()
    ws2.accept = AsyncMock()

    await manager.connect("check-001", mock_websocket)
    await manager.connect("check-001", ws2)

    assert manager.get_connection("check-001") is ws2


# ── send_message tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_message_returns_true_when_connected(manager, mock_websocket):
    """send_message() should return True and send JSON when connection exists."""
    await manager.connect("check-001", mock_websocket)

    result = await manager.send_message("check-001", {"type": "test"})

    assert result is True
    mock_websocket.send_json.assert_called_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_send_message_returns_false_when_not_connected(manager):
    """send_message() should return False when no connection exists."""
    result = await manager.send_message("nonexistent", {"type": "test"})
    assert result is False


# ── broadcast_node_status tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_node_status_sends_correct_format(manager, mock_websocket):
    """broadcast_node_status() should send a properly formatted node_status message."""
    await manager.connect("check-001", mock_websocket)

    await manager.broadcast_node_status(
        "check-001", "compliance_check", "completed", "Analysis complete"
    )

    mock_websocket.send_json.assert_called_once_with({
        "type": "node_status",
        "node": "compliance_check",
        "status": "completed",
        "description": "Analysis complete",
    })


# ── send_interrupt tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_interrupt_sends_correct_format(manager, mock_websocket):
    """send_interrupt() should send a properly formatted interrupt message."""
    await manager.connect("check-001", mock_websocket)

    result_data = {"risk_percentage": 72, "violations": []}
    await manager.send_interrupt(
        "check-001", "Review required", result_data, ["ok", "edit"]
    )

    mock_websocket.send_json.assert_called_once_with({
        "type": "interrupt",
        "data": {
            "message": "Review required",
            "result": {"risk_percentage": 72, "violations": []},
            "options": ["ok", "edit"],
        },
    })


# ── send_result tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_result_sends_correct_format(manager, mock_websocket):
    """send_result() should send a properly formatted result message."""
    await manager.connect("check-001", mock_websocket)

    result_data = {"status": "verified", "risk_percentage": 25}
    await manager.send_result("check-001", result_data)

    mock_websocket.send_json.assert_called_once_with({
        "type": "result",
        "data": {"status": "verified", "risk_percentage": 25},
    })


# ── send_error tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_error_sends_correct_format(manager, mock_websocket):
    """send_error() should send a properly formatted error message."""
    await manager.connect("check-001", mock_websocket)

    await manager.send_error("check-001", "post_process", "Processing failed", True)

    mock_websocket.send_json.assert_called_once_with({
        "type": "error",
        "node": "post_process",
        "message": "Processing failed",
        "can_continue": True,
    })


@pytest.mark.asyncio
async def test_send_error_with_can_continue_false(manager, mock_websocket):
    """send_error() should correctly pass can_continue=False."""
    await manager.connect("check-001", mock_websocket)

    await manager.send_error("check-001", "compliance_check", "Fatal error", False)

    mock_websocket.send_json.assert_called_once_with({
        "type": "error",
        "node": "compliance_check",
        "message": "Fatal error",
        "can_continue": False,
    })
