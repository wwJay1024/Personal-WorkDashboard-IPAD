from datetime import datetime, timezone

from fastapi import WebSocket
from loguru import logger


class WSManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.metadata: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        self.metadata[websocket] = {
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "user_agent": websocket.headers.get("user-agent", "unknown"),
        }
        logger.info("websocket connected; total={}", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.metadata.pop(websocket, None)
        logger.info("websocket disconnected; total={}", len(self.active_connections))

    async def send_personal(self, message: dict, websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)
