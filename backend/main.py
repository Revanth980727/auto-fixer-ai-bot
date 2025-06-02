
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from core.database import init_db
from core.websocket_manager import WebSocketManager
from api.routes import tickets, metrics, agents, webhooks, logs, manual, developer_debug
from services.agent_orchestrator import AgentOrchestrator
from services.ticket_poller import TicketPoller

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
websocket_manager = WebSocketManager()
agent_orchestrator = None
ticket_poller = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global agent_orchestrator, ticket_poller
    
    # Startup
    logger.info("Starting AI Agent System...")
    await init_db()
    
    # Initialize and start services
    agent_orchestrator = AgentOrchestrator()
    ticket_poller = TicketPoller()
    
    # Start background tasks
    orchestrator_task = asyncio.create_task(agent_orchestrator.start_processing())
    poller_task = asyncio.create_task(ticket_poller.start())
    
    logger.info("AI Agent System started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Agent System...")
    if agent_orchestrator:
        await agent_orchestrator.stop_processing()
    if ticket_poller:
        await ticket_poller.stop()
    
    # Cancel background tasks
    orchestrator_task.cancel()
    poller_task.cancel()
    
    try:
        await asyncio.gather(orchestrator_task, poller_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    
    logger.info("AI Agent System shut down")

app = FastAPI(
    title="AI Agent System",
    description="Production-ready autonomous bug fixing and code generation system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(manual.router, prefix="/api/manual", tags=["manual"])
app.include_router(developer_debug.router, prefix="/api/developer-debug", tags=["developer-debug"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

@app.get("/")
async def root():
    return {
        "message": "AI Agent System API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": "connected",
            "orchestrator": "running" if agent_orchestrator else "stopped",
            "poller": "running" if ticket_poller else "stopped"
        }
    }
