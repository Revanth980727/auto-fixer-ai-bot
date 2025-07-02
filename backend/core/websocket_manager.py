
from fastapi import WebSocket
from typing import List
import json

class WebSocketManager:
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

    async def broadcast_system_health_update(self, health_data: dict):
        """Broadcast system health status update"""
        await self.broadcast({
            "type": "system_health_update",
            "data": health_data
        })

    async def broadcast_pipeline_update(self, context_id: str, stage: str, status: str):
        """Broadcast pipeline execution update"""
        await self.broadcast({
            "type": "pipeline_update",
            "context_id": context_id,
            "stage": stage,
            "status": status
        })

    async def broadcast_metrics_update(self, metrics_data: dict):
        """Broadcast real-time metrics update"""
        await self.broadcast({
            "type": "metrics_update",
            "data": metrics_data
        })

    async def broadcast_circuit_breaker_event(self, service: str, state: str):
        """Broadcast circuit breaker state change"""
        await self.broadcast({
            "type": "circuit_breaker_event",
            "service": service,
            "state": state
        })
    
    async def broadcast_diff_preview(self, diff_id: str, diff_data: dict):
        """Broadcast interactive diff preview for real-time review"""
        await self.broadcast({
            "type": "diff_preview",
            "diff_id": diff_id,
            "diff_data": diff_data,
            "timestamp": diff_data.get("timestamp")
        })
    
    async def broadcast_approval_request(self, diff_id: str, approval_data: dict):
        """Broadcast approval request for user interaction"""
        await self.broadcast({
            "type": "approval_request",
            "diff_id": diff_id,
            "approval_options": approval_data.get("approval_options", []),
            "summary": approval_data.get("summary", {}),
            "requires_user_action": True
        })
    
    async def broadcast_approval_result(self, diff_id: str, decision: str, result: dict):
        """Broadcast approval decision result"""
        await self.broadcast({
            "type": "approval_result",
            "diff_id": diff_id,
            "decision": decision,
            "result": result,
            "timestamp": result.get("timestamp")
        })
