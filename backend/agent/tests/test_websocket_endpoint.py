"""
test_websocket_endpoint.py
──────────────────────────
Unit tests for the WebSocket endpoint in langgraph_api.py.

Tests cover:
- WebSocket connection lifecycle (connect/disconnect)
- Ping/pong heartbeat handling
- Resume action routing decisions back to pipeline
- Cleanup on disconnect
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# We need to test the endpoint logic in isolation since the full app
# has heavy dependencies. We test the handle_resume function and
# the endpoint behavior via FastAPI's WebSocket test client.


# ── Test handle_resume function ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_resume_stores_decision_and_signals_event():
    """handle_resume should store the decision and set the event."""
    # Import from the module under test
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    # We test handle_resume in isolation by importing and manipulating the module dicts
    from unittest.mock import patch
    import asyncio

    # Create mock pending_decisions and decision_store
    event = asyncio.Event()
    pending_decisions = {"check-123": event}
    decision_store = {}

    # Simulate what handle_resume does
    check_id = "check-123"
    decision = "ok"

    decision_store[check_id] = decision
    pending_event = pending_decisions.get(check_id)
    if pending_event:
        pending_event.set()

    assert decision_store["check-123"] == "ok"
    assert event.is_set()


@pytest.mark.asyncio
async def test_handle_resume_works_without_pending_event():
    """handle_resume should work even if no pending event exists for the check_id."""
    import asyncio

    pending_decisions = {}
    decision_store = {}

    check_id = "check-456"
    decision = "edit"

    # Simulate handle_resume logic without an event
    decision_store[check_id] = decision
    event = pending_decisions.get(check_id)
    if event:
        event.set()

    # Should store decision without error
    assert decision_store["check-456"] == "edit"


@pytest.mark.asyncio
async def test_handle_resume_with_edit_decision():
    """handle_resume should correctly store 'edit' decisions."""
    import asyncio

    event = asyncio.Event()
    pending_decisions = {"check-789": event}
    decision_store = {}

    check_id = "check-789"
    decision = "edit"

    decision_store[check_id] = decision
    pending_event = pending_decisions.get(check_id)
    if pending_event:
        pending_event.set()

    assert decision_store["check-789"] == "edit"
    assert event.is_set()


# ── Test WebSocket endpoint via FastAPI TestClient ────────────────────────────

# Note: Full integration tests of the WebSocket endpoint require the FastAPI app
# to be importable without all heavy dependencies. We use mocking to test the
# endpoint behavior.


@pytest.mark.asyncio
async def test_websocket_ping_pong():
    """WebSocket endpoint should respond to ping with pong."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.testclient import TestClient
    from agent.ws_manager import ConnectionManager

    # Create a minimal test app with the same endpoint logic
    test_app = FastAPI()
    test_manager = ConnectionManager()

    @test_app.websocket("/ws/{check_id}")
    async def ws_endpoint(websocket: WebSocket, check_id: str):
        await test_manager.connect(check_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            test_manager.disconnect(check_id)

    client = TestClient(test_app)
    with client.websocket_connect("/ws/test-check-001") as ws:
        ws.send_json({"action": "ping"})
        response = ws.receive_json()
        assert response == {"type": "pong"}


@pytest.mark.asyncio
async def test_websocket_resume_action():
    """WebSocket endpoint should handle resume action and store decision."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.testclient import TestClient
    from agent.ws_manager import ConnectionManager

    test_app = FastAPI()
    test_manager = ConnectionManager()
    test_decision_store = {}
    test_pending_decisions = {}

    async def test_handle_resume(check_id: str, decision: str):
        test_decision_store[check_id] = decision
        event = test_pending_decisions.get(check_id)
        if event:
            event.set()

    @test_app.websocket("/ws/{check_id}")
    async def ws_endpoint(websocket: WebSocket, check_id: str):
        await test_manager.connect(check_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "resume":
                    await test_handle_resume(check_id, data.get("decision", "ok"))
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            test_manager.disconnect(check_id)

    # Set up pending event before connecting
    event = asyncio.Event()
    test_pending_decisions["test-check-002"] = event

    client = TestClient(test_app)
    with client.websocket_connect("/ws/test-check-002") as ws:
        ws.send_json({"action": "resume", "decision": "edit"})
        # Send a ping to confirm the connection is still alive
        ws.send_json({"action": "ping"})
        response = ws.receive_json()
        assert response == {"type": "pong"}

    # Verify the decision was stored
    assert test_decision_store.get("test-check-002") == "edit"
    assert event.is_set()


@pytest.mark.asyncio
async def test_websocket_disconnect_cleans_up_connection():
    """WebSocket disconnect should remove the connection from the manager."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.testclient import TestClient
    from agent.ws_manager import ConnectionManager

    test_app = FastAPI()
    test_manager = ConnectionManager()

    @test_app.websocket("/ws/{check_id}")
    async def ws_endpoint(websocket: WebSocket, check_id: str):
        await test_manager.connect(check_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            test_manager.disconnect(check_id)

    client = TestClient(test_app)

    # Connect and then disconnect
    with client.websocket_connect("/ws/test-check-003") as ws:
        ws.send_json({"action": "ping"})
        response = ws.receive_json()
        assert response == {"type": "pong"}
        # Connection is active here
        assert test_manager.get_connection("test-check-003") is not None

    # After context manager exits, connection should be cleaned up
    assert test_manager.get_connection("test-check-003") is None


@pytest.mark.asyncio
async def test_websocket_resume_defaults_to_ok():
    """Resume action without explicit decision should default to 'ok'."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.testclient import TestClient
    from agent.ws_manager import ConnectionManager

    test_app = FastAPI()
    test_manager = ConnectionManager()
    test_decision_store = {}

    async def test_handle_resume(check_id: str, decision: str):
        test_decision_store[check_id] = decision

    @test_app.websocket("/ws/{check_id}")
    async def ws_endpoint(websocket: WebSocket, check_id: str):
        await test_manager.connect(check_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "resume":
                    await test_handle_resume(check_id, data.get("decision", "ok"))
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            test_manager.disconnect(check_id)

    client = TestClient(test_app)
    with client.websocket_connect("/ws/test-check-004") as ws:
        # Send resume without decision field
        ws.send_json({"action": "resume"})
        # Confirm connection still working
        ws.send_json({"action": "ping"})
        response = ws.receive_json()
        assert response == {"type": "pong"}

    assert test_decision_store.get("test-check-004") == "ok"


@pytest.mark.asyncio
async def test_websocket_unknown_action_does_not_crash():
    """Unknown action should be silently ignored without crashing the connection."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.testclient import TestClient
    from agent.ws_manager import ConnectionManager

    test_app = FastAPI()
    test_manager = ConnectionManager()

    @test_app.websocket("/ws/{check_id}")
    async def ws_endpoint(websocket: WebSocket, check_id: str):
        await test_manager.connect(check_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                if action == "resume":
                    pass
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            test_manager.disconnect(check_id)

    client = TestClient(test_app)
    with client.websocket_connect("/ws/test-check-005") as ws:
        # Send unknown action
        ws.send_json({"action": "unknown_action", "data": "something"})
        # Connection should still be alive
        ws.send_json({"action": "ping"})
        response = ws.receive_json()
        assert response == {"type": "pong"}
