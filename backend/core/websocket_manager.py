
from fastapi import WebSocket
from typing import List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        message_str = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_ticket_update(self, ticket_id: int, status: str):
        """Broadcast ticket status update"""
        await self.broadcast({
            "type": "ticket_update",
            "ticket_id": ticket_id,
            "status": status
        })

    async def broadcast_agent_status(self, agent_type: str, status: str):
        """Broadcast agent status update"""
        await self.broadcast({
            "type": "agent_status",
            "agent_type": agent_type,
            "status": status
        })
