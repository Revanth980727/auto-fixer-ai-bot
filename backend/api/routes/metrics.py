
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database import get_sync_db
from core.models import Ticket, AgentExecution, PatchAttempt
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List

router = APIRouter()

class SystemMetricsResponse(BaseModel):
    total_tickets: int
    completed_tickets: int
    failed_tickets: int
    escalated_tickets: int
    success_rate: float
    avg_resolution_time: float
    active_tickets: int

class AgentMetricsResponse(BaseModel):
    agent_type: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_execution_time: float

@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(db: Session = Depends(get_sync_db)):
    """Get overall system metrics"""
    total_tickets = db.query(func.count(Ticket.id)).scalar()
    completed_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == "completed").scalar()
    failed_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == "failed").scalar()
    escalated_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == "escalated").scalar()
    active_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status.in_(["todo", "in_progress", "testing"])).scalar()
    
    success_rate = (completed_tickets / total_tickets * 100) if total_tickets > 0 else 0
    
    # Calculate average resolution time for completed tickets
    completed_ticket_objects = db.query(Ticket).filter(Ticket.status == "completed").all()
    resolution_times = []
    
    for ticket in completed_ticket_objects:
        if ticket.updated_at and ticket.created_at:
            delta = ticket.updated_at - ticket.created_at
            resolution_times.append(delta.total_seconds() / 3600)  # Convert to hours
    
    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    
    return SystemMetricsResponse(
        total_tickets=total_tickets,
        completed_tickets=completed_tickets,
        failed_tickets=failed_tickets,
        escalated_tickets=escalated_tickets,
        success_rate=success_rate,
        avg_resolution_time=avg_resolution_time,
        active_tickets=active_tickets
    )

@router.get("/agents", response_model=List[AgentMetricsResponse])
async def get_agent_metrics(db: Session = Depends(get_sync_db)):
    """Get metrics for each agent type"""
    agent_types = ["intake", "planner", "developer", "qa", "communicator"]
    metrics = []
    
    for agent_type in agent_types:
        executions = db.query(AgentExecution).filter(AgentExecution.agent_type == agent_type).all()
        
        total_executions = len(executions)
        successful = len([ex for ex in executions if ex.status == "completed"])
        failed = len([ex for ex in executions if ex.status == "failed"])
        
        # Calculate average execution time
        execution_times = []
        for ex in executions:
            if ex.completed_at and ex.started_at:
                delta = ex.completed_at - ex.started_at
                execution_times.append(delta.total_seconds())
        
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        metrics.append(AgentMetricsResponse(
            agent_type=agent_type,
            total_executions=total_executions,
            successful_executions=successful,
            failed_executions=failed,
            avg_execution_time=avg_execution_time
        ))
    
    return metrics
