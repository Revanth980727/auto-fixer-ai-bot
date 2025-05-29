
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from core.database import get_sync_db
from core.models import Ticket, AgentExecution, PatchAttempt
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class TicketResponse(BaseModel):
    id: int
    jira_id: str
    title: str
    description: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    retry_count: int
    assigned_agent: Optional[str]
    
    class Config:
        from_attributes = True

class TicketDetailResponse(TicketResponse):
    error_trace: Optional[str]
    estimated_files: Optional[dict]
    executions: List[dict]
    patches: List[dict]

@router.get("/", response_model=List[TicketResponse])
async def get_tickets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db)
):
    """Get list of tickets with optional filtering"""
    query = db.query(Ticket)
    
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    
    tickets = query.order_by(desc(Ticket.created_at)).offset(skip).limit(limit).all()
    return tickets

@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(ticket_id: int, db: Session = Depends(get_sync_db)):
    """Get detailed ticket information"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Get executions and patches
    executions = db.query(AgentExecution).filter(AgentExecution.ticket_id == ticket_id).all()
    patches = db.query(PatchAttempt).filter(PatchAttempt.ticket_id == ticket_id).all()
    
    return TicketDetailResponse(
        **ticket.__dict__,
        executions=[{
            "id": ex.id,
            "agent_type": ex.agent_type,
            "status": ex.status,
            "started_at": ex.started_at,
            "completed_at": ex.completed_at,
            "logs": ex.logs,
            "error_message": ex.error_message
        } for ex in executions],
        patches=[{
            "id": p.id,
            "confidence_score": p.confidence_score,
            "success": p.success,
            "commit_message": p.commit_message,
            "created_at": p.created_at
        } for p in patches]
    )

@router.post("/{ticket_id}/retry")
async def retry_ticket(ticket_id: int, db: Session = Depends(get_sync_db)):
    """Manually retry a failed ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = "todo"
    ticket.retry_count += 1
    ticket.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Ticket queued for retry", "ticket_id": ticket_id}

@router.post("/{ticket_id}/escalate")
async def escalate_ticket(ticket_id: int, db: Session = Depends(get_sync_db)):
    """Manually escalate a ticket"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = "escalated"
    ticket.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Ticket escalated", "ticket_id": ticket_id}
