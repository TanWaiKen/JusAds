"""
ws_manager.py
─────────────
WebSocket Connection Manager for the JusAds compliance pipeline.

Manages active WebSocket connections by check_id using FastAPI's native WebSocket support.
This is an in-memory connection tracker. Each check_id maps to one active WebSocket.
No external infrastructure (DynamoDB, API Gateway) is required.

Future deployment note: When deploying to Lambda/serverless, this transport layer
can be swapped to AWS API Gateway WebSocket APIs ($connect/$default/$disconnect routes
with DynamoDB connection tracking and boto3 apigatewaymanagementapi client) while
keeping the same JSON message protocol unchanged.
"""

from fastapi import WebSocket
from typing import Dict, Optional


class ConnectionManager:
    """Manages active WebSocket connections by check_id."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, check_id: str, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and register it by check_id."""
        await websocket.accept()
        self.active_connections[check_id] = websocket

    def disconnect(self, check_id: str) -> None:
        """Remove a WebSocket connection from the active set."""
        self.active_connections.pop(check_id, None)

    def get_connection(self, check_id: str) -> Optional[WebSocket]:
        """Get the active WebSocket for a check_id, or None."""
        return self.active_connections.get(check_id)

    async def send_message(self, check_id: str, data: dict) -> bool:
        """Send a JSON message to the connected client for a check_id.

        Returns True if the message was sent, False if no connection exists.
        """
        ws = self.active_connections.get(check_id)
        if ws:
            await ws.send_json(data)
            return True
        return False

    async def broadcast_node_status(
        self, check_id: str, node: str, status: str, description: str
    ) -> None:
        """Send a node_status event to the client.

        Args:
            check_id: The compliance check identifier.
            node: The pipeline node name (e.g. "compliance_check", "post_process").
            status: Node status - "completed" or "error".
            description: Human-readable progress string (max 200 chars).
        """
        await self.send_message(check_id, {
            "type": "node_status",
            "node": node,
            "status": status,
            "description": description,
        })

    async def send_interrupt(
        self, check_id: str, message: str, result: dict, options: list[str]
    ) -> None:
        """Send a human-in-the-loop interrupt to the client.

        Args:
            check_id: The compliance check identifier.
            message: A human-readable message describing what needs review.
            result: The full compliance result object.
            options: Available actions (e.g. ["ok", "edit"]).
        """
        await self.send_message(check_id, {
            "type": "interrupt",
            "data": {"message": message, "result": result, "options": options},
        })

    async def send_result(self, check_id: str, result: dict) -> None:
        """Send the final compliance result to the client.

        Args:
            check_id: The compliance check identifier.
            result: The complete compliance result payload.
        """
        await self.send_message(check_id, {"type": "result", "data": result})

    async def send_error(
        self, check_id: str, node: str, message: str, can_continue: bool
    ) -> None:
        """Send an error event to the client.

        Args:
            check_id: The compliance check identifier.
            node: The pipeline node where the error occurred.
            message: Human-readable error description.
            can_continue: Whether the check can continue despite this error.
        """
        await self.send_message(check_id, {
            "type": "error",
            "node": node,
            "message": message,
            "can_continue": can_continue,
        })
