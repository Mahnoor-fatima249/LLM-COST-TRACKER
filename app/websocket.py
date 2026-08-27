import json
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            dead = set()
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    dead.add(connection)
            self.active_connections[user_id] -= dead

    async def broadcast_cost_update(self, user_id: str, cost_data: dict):
        await self.send_to_user(user_id, {
            "type": "cost_update",
            "data": cost_data,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def send_alert(self, user_id: str, alert: dict):
        await self.send_to_user(user_id, {
            "type": "alert",
            "data": alert,
            "timestamp": datetime.utcnow().isoformat()
        })


manager = ConnectionManager()
