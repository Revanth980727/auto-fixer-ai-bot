
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_sync_db
from core.models import AgentExecution
from typing import List, Dict, Any

router = APIRouter()

@router.get("/", response_model=List[Dict[str, Any]])
def get_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_sync_db)):
    """Get system logs"""
    executions = db.query(AgentExecution).order_by(
        AgentExecution.started_at.desc()
    ).offset(skip).limit(limit).all()
    
    logs = []
    for execution in executions:
        if execution.logs:
            log_lines = execution.logs.strip().split('\n')
            for line in log_lines:
                if line.strip():
                    logs.append({
                        "timestamp": execution.started_at.isoformat(),
                        "agent_type": execution.agent_type,
                        "ticket_id": execution.ticket_id,
                        "message": line.strip(),
                        "level": "info"
                    })
    
    return logs[:limit]

@router.get("/agent/{agent_type}")
def get_agent_logs(agent_type: str, skip: int = 0, limit: int = 50, db: Session = Depends(get_sync_db)):
    """Get logs for a specific agent"""
    executions = db.query(AgentExecution).filter(
        AgentExecution.agent_type == agent_type
    ).order_by(AgentExecution.started_at.desc()).offset(skip).limit(limit).all()
    
    logs = []
    for execution in executions:
        if execution.logs:
            logs.append({
                "execution_id": execution.id,
                "ticket_id": execution.ticket_id,
                "timestamp": execution.started_at.isoformat(),
                "logs": execution.logs,
                "status": execution.status
            })
    
    return logs
