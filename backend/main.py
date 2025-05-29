
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn
from api.routes import tickets, agents, metrics, logs, webhooks, manual
from core.database import init_db
from services.ticket_poller import TicketPoller
from services.agent_orchestrator import AgentOrchestrator
from core.websocket_manager import ConnectionManager

# Global instances
connection_manager = ConnectionManager()
ticket_poller = None
agent_orchestrator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    
    global ticket_poller, agent_orchestrator
    ticket_poller = TicketPoller()
    agent_orchestrator = AgentOrchestrator()
    
    # Start background tasks
    asyncio.create_task(ticket_poller.start_polling())
    asyncio.create_task(agent_orchestrator.start_processing())
    
    yield
    
    # Shutdown
    if ticket_poller:
        await ticket_poller.stop_polling()
    if agent_orchestrator:
        await agent_orchestrator.stop_processing()

app = FastAPI(
    title="AI Agent System",
    description="Autonomous AI system for bug fixing and code generation",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(manual.router, prefix="/api/manual", tags=["manual"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)

@app.get("/")
async def root():
    return {"message": "AI Agent System API", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": "connected",
            "ticket_poller": "running" if ticket_poller and ticket_poller.running else "stopped",
            "agent_orchestrator": "running" if agent_orchestrator and agent_orchestrator.running else "stopped"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
