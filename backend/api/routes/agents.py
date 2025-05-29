
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_sync_db
from core.models import AgentConfig, AgentExecution
from typing import List
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter()

class AgentStatusResponse(BaseModel):
    agent_type: str
    enabled: bool
    last_activity: datetime | None
    active_executions: int
    success_rate: float
    avg_response_time: float

@router.get("/status", response_model=List[AgentStatusResponse])
async def get_agent_status(db: Session = Depends(get_sync_db)):
    """Get status of all agents"""
    agent_types = ["intake", "planner", "developer", "qa", "communicator"]
    statuses = []
    
    for agent_type in agent_types:
        # Get or create agent config
        config = db.query(AgentConfig).filter(AgentConfig.agent_type == agent_type).first()
        if not config:
            config = AgentConfig(agent_type=agent_type, enabled=True)
            db.add(config)
            db.commit()
        
        # Calculate metrics
        recent_executions = db.query(AgentExecution).filter(
            AgentExecution.agent_type == agent_type,
            AgentExecution.started_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        active_count = len([ex for ex in recent_executions if ex.status == "running"])
        completed_executions = [ex for ex in recent_executions if ex.status in ["completed", "failed"]]
        
        success_rate = 0.0
        avg_response_time = 0.0
        
        if completed_executions:
            successful = len([ex for ex in completed_executions if ex.status == "completed"])
            success_rate = successful / len(completed_executions)
            
            response_times = []
            for ex in completed_executions:
                if ex.completed_at and ex.started_at:
                    delta = ex.completed_at - ex.started_at
                    response_times.append(delta.total_seconds())
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        statuses.append(AgentStatusResponse(
            agent_type=agent_type,
            enabled=config.enabled,
            last_activity=config.last_activity,
            active_executions=active_count,
            success_rate=success_rate,
            avg_response_time=avg_response_time
        ))
    
    return statuses

@router.post("/{agent_type}/toggle")
async def toggle_agent(agent_type: str, db: Session = Depends(get_sync_db)):
    """Enable or disable an agent"""
    config = db.query(AgentConfig).filter(AgentConfig.agent_type == agent_type).first()
    if not config:
        config = AgentConfig(agent_type=agent_type, enabled=True)
        db.add(config)
    else:
        config.enabled = not config.enabled
    
    db.commit()
    
    return {
        "agent_type": agent_type,
        "enabled": config.enabled,
        "message": f"Agent {'enabled' if config.enabled else 'disabled'}"
    }
