
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_sync_db
from core.models import Ticket, TicketStatus
from pydantic import BaseModel
from services.agent_orchestrator import AgentOrchestrator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class CreateTicketRequest(BaseModel):
    title: str
    description: str
    error_trace: str = ""
    priority: str = "medium"
    jira_id: str = ""

class AgentControlRequest(BaseModel):
    action: str  # "start", "stop", "restart"

# Global orchestrator instance (would be better to use dependency injection)
orchestrator_instance = None

@router.post("/tickets")
async def create_manual_ticket(
    ticket_data: CreateTicketRequest,
    db: Session = Depends(get_sync_db)
):
    """Manually create a ticket for testing"""
    try:
        # Generate a test JIRA ID if not provided
        if not ticket_data.jira_id:
            import uuid
            ticket_data.jira_id = f"TEST-{str(uuid.uuid4())[:8].upper()}"
        
        ticket = Ticket(
            jira_id=ticket_data.jira_id,
            title=ticket_data.title,
            description=ticket_data.description,
            error_trace=ticket_data.error_trace,
            priority=ticket_data.priority,
            status=TicketStatus.TODO
        )
        
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        logger.info(f"Created manual ticket: {ticket.jira_id}")
        
        return {
            "message": "Ticket created successfully",
            "ticket_id": ticket.id,
            "jira_id": ticket.jira_id
        }
        
    except Exception as e:
        logger.error(f"Error creating manual ticket: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/agents/control")
async def control_agents(
    control_data: AgentControlRequest,
    db: Session = Depends(get_sync_db)
):
    """Control the agent orchestrator"""
    global orchestrator_instance
    
    try:
        if control_data.action == "start":
            if not orchestrator_instance or not orchestrator_instance.running:
                from services.agent_orchestrator import AgentOrchestrator
                orchestrator_instance = AgentOrchestrator()
                # Start in background (would need proper task management in production)
                import asyncio
                asyncio.create_task(orchestrator_instance.start_processing())
                return {"message": "Agent orchestrator started"}
            else:
                return {"message": "Agent orchestrator already running"}
                
        elif control_data.action == "stop":
            if orchestrator_instance and orchestrator_instance.running:
                await orchestrator_instance.stop_processing()
                return {"message": "Agent orchestrator stopped"}
            else:
                return {"message": "Agent orchestrator not running"}
                
        elif control_data.action == "restart":
            if orchestrator_instance:
                await orchestrator_instance.stop_processing()
            
            from services.agent_orchestrator import AgentOrchestrator
            orchestrator_instance = AgentOrchestrator()
            import asyncio
            asyncio.create_task(orchestrator_instance.start_processing())
            return {"message": "Agent orchestrator restarted"}
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'start', 'stop', or 'restart'")
            
    except Exception as e:
        logger.error(f"Error controlling agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agents/status")
async def get_orchestrator_status():
    """Get orchestrator status"""
    global orchestrator_instance
    
    if orchestrator_instance:
        status = await orchestrator_instance.get_agent_status()
        return status
    else:
        return {
            "orchestrator_running": False,
            "message": "No orchestrator instance"
        }

@router.post("/tickets/{ticket_id}/force-retry")
async def force_retry_ticket(ticket_id: int, db: Session = Depends(get_sync_db)):
    """Force retry a ticket through the pipeline"""
    global orchestrator_instance
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if orchestrator_instance:
        await orchestrator_instance.retry_failed_ticket(ticket_id)
        return {"message": f"Ticket {ticket_id} queued for retry"}
    else:
        # Manual retry without orchestrator
        ticket.status = TicketStatus.TODO
        ticket.retry_count += 1
        ticket.updated_at = datetime.utcnow()
        db.add(ticket)
        db.commit()
        return {"message": f"Ticket {ticket_id} status reset to TODO"}
