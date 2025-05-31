
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_sync_db
from core.models import AgentExecution, PatchAttempt, Ticket
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class DeveloperDebugResponse(BaseModel):
    execution_id: int
    ticket_id: int
    ticket_title: str
    status: str
    logs: str
    output_data: Dict[str, Any] | None
    error_message: str | None
    patch_attempts: List[Dict[str, Any]]
    started_at: datetime
    completed_at: datetime | None

@router.get("/executions", response_model=List[DeveloperDebugResponse])
async def get_developer_executions(
    limit: int = 10,
    ticket_id: int | None = None,
    db: Session = Depends(get_sync_db)
):
    """Get detailed Developer Agent execution logs and outputs"""
    
    query = db.query(AgentExecution).filter(
        AgentExecution.agent_type == "developer"
    )
    
    if ticket_id:
        query = query.filter(AgentExecution.ticket_id == ticket_id)
    
    executions = query.order_by(
        AgentExecution.started_at.desc()
    ).limit(limit).all()
    
    results = []
    for execution in executions:
        # Get ticket info
        ticket = db.query(Ticket).filter(Ticket.id == execution.ticket_id).first()
        
        # Get patch attempts for this execution
        patch_attempts = db.query(PatchAttempt).filter(
            PatchAttempt.execution_id == execution.id
        ).all()
        
        patch_data = []
        for patch in patch_attempts:
            patch_data.append({
                "id": patch.id,
                "target_file": patch.target_file,
                "confidence_score": patch.confidence_score,
                "success": patch.success,
                "patch_content_preview": patch.patch_content[:200] if patch.patch_content else None,
                "created_at": patch.created_at
            })
        
        results.append(DeveloperDebugResponse(
            execution_id=execution.id,
            ticket_id=execution.ticket_id,
            ticket_title=ticket.title if ticket else "Unknown",
            status=execution.status,
            logs=execution.logs or "",
            output_data=execution.output_data,
            error_message=execution.error_message,
            patch_attempts=patch_data,
            started_at=execution.started_at,
            completed_at=execution.completed_at
        ))
    
    return results

@router.get("/execution/{execution_id}", response_model=DeveloperDebugResponse)
async def get_developer_execution_detail(
    execution_id: int,
    db: Session = Depends(get_sync_db)
):
    """Get detailed information about a specific Developer Agent execution"""
    
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id,
        AgentExecution.agent_type == "developer"
    ).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Developer execution not found")
    
    # Get ticket info
    ticket = db.query(Ticket).filter(Ticket.id == execution.ticket_id).first()
    
    # Get patch attempts for this execution
    patch_attempts = db.query(PatchAttempt).filter(
        PatchAttempt.execution_id == execution.id
    ).all()
    
    patch_data = []
    for patch in patch_attempts:
        patch_data.append({
            "id": patch.id,
            "target_file": patch.target_file,
            "patch_content": patch.patch_content,
            "patched_code": patch.patched_code,
            "test_code": patch.test_code,
            "confidence_score": patch.confidence_score,
            "success": patch.success,
            "created_at": patch.created_at
        })
    
    return DeveloperDebugResponse(
        execution_id=execution.id,
        ticket_id=execution.ticket_id,
        ticket_title=ticket.title if ticket else "Unknown",
        status=execution.status,
        logs=execution.logs or "",
        output_data=execution.output_data,
        error_message=execution.error_message,
        patch_attempts=patch_data,
        started_at=execution.started_at,
        completed_at=execution.completed_at
    )
