"""WebSocket handler for real-time updates."""

import asyncio
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        self.connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(websocket)

    async def broadcast(self, event: str, data: dict) -> None:
        """Broadcast an event to all connected clients."""
        if not self.connections:
            return

        message = {"event": event, "data": data}
        disconnected = set()

        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.connections.discard(conn)

    async def send_personal(self, websocket: WebSocket, event: str, data: dict) -> None:
        """Send a message to a specific client."""
        try:
            await websocket.send_json({"event": event, "data": data})
        except Exception:
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.connections)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time updates.

    Events sent to clients:
    - connected: Initial connection confirmation
    - scan_started: A scan has begun
    - scan_progress: Scan progress update
    - scan_complete: Scan finished successfully
    - scan_error: Scan failed
    - new_alert: A new alert was triggered

    Clients can send:
    - ping: Server responds with pong
    - subscribe: Subscribe to specific ticker updates (future)
    """
    await manager.connect(websocket)

    # Send connection confirmation
    await manager.send_personal(
        websocket,
        "connected",
        {"message": "Connected to WSB Tracker", "clients": manager.connection_count},
    )

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            # Handle client messages
            if data.get("type") == "ping":
                await manager.send_personal(websocket, "pong", {"timestamp": data.get("timestamp")})
            elif data.get("type") == "subscribe":
                # Future: handle ticker-specific subscriptions
                await manager.send_personal(
                    websocket,
                    "subscribed",
                    {"tickers": data.get("tickers", [])},
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
