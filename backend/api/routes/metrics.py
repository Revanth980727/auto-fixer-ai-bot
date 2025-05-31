
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database import get_sync_db
from core.models import Ticket, AgentExecution, PatchAttempt
from services.metrics_collector import metrics_collector
from services.pipeline_context import context_manager
from services.repository_analyzer import RepositoryAnalyzer
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Dict, Any

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

class AdvancedMetricsResponse(BaseModel):
    system_health: Dict[str, Any]
    agent_performance: Dict[str, Any]
    pipeline_summary: List[Dict[str, Any]]
    circuit_breakers: Dict[str, Any]

@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(db: Session = Depends(get_sync_db)):
    """Get overall system metrics"""
    # ... keep existing code (basic metrics calculation) the same ...
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
    """Get metrics for each agent type using MetricsCollector"""
    agent_performance = metrics_collector.get_agent_performance_summary()
    metrics = []
    
    for agent_type, perf_data in agent_performance.items():
        metrics.append(AgentMetricsResponse(
            agent_type=agent_type,
            total_executions=perf_data.get("total_executions", 0),
            successful_executions=perf_data.get("success_count", 0),
            failed_executions=perf_data.get("error_count", 0),
            avg_execution_time=perf_data.get("avg_duration", 0)
        ))
    
    return metrics

@router.get("/advanced", response_model=AdvancedMetricsResponse)
async def get_advanced_metrics():
    """Get advanced metrics from MetricsCollector and PipelineContext"""
    system_health = metrics_collector.get_system_health_status()
    agent_performance = metrics_collector.get_agent_performance_summary()
    active_contexts = context_manager.get_all_active_contexts()
    
    circuit_breakers = {}
    for service, breaker in metrics_collector.circuit_breakers.items():
        circuit_breakers[service] = {
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "last_failure_time": breaker.last_failure_time
        }
    
    return AdvancedMetricsResponse(
        system_health=system_health,
        agent_performance=agent_performance,
        pipeline_summary=active_contexts,
        circuit_breakers=circuit_breakers
    )

@router.get("/health")
async def get_system_health():
    """Get real-time system health status"""
    return metrics_collector.get_system_health_status()

@router.get("/performance-trends")
async def get_performance_trends(hours: int = 24):
    """Get performance trends over specified time period"""
    return metrics_collector.get_performance_trends(hours)

@router.get("/repository-analysis")
async def get_repository_analysis():
    """Get repository analysis data"""
    analyzer = RepositoryAnalyzer()
    return await analyzer.analyze_repository()

@router.get("/charts")
async def get_charts_data(db: Session = Depends(get_sync_db)):
    """Get enhanced metrics data for charts using MetricsCollector"""
    # Get performance summary from MetricsCollector
    agent_performance = metrics_collector.get_agent_performance_summary()
    pipeline_performance = metrics_collector.get_pipeline_performance_summary()
    
    # Success rate trend from MetricsCollector
    success_rate = []
    for i in range(7):
        date = datetime.now() - timedelta(days=6-i)
        date_str = date.strftime("%Y-%m-%d")
        
        # Use MetricsCollector data if available, fallback to DB
        total_tickets = db.query(func.count(Ticket.id)).filter(
            func.date(Ticket.created_at) == date.date()
        ).scalar()
        
        completed_tickets = db.query(func.count(Ticket.id)).filter(
            func.date(Ticket.created_at) == date.date(),
            Ticket.status == "completed"
        ).scalar()
        
        rate = (completed_tickets / total_tickets * 100) if total_tickets > 0 else 0
        success_rate.append({"date": date_str, "rate": rate})
    
    # Agent activity from MetricsCollector
    agent_activity = []
    for agent_type, perf_data in agent_performance.items():
        agent_activity.append({
            "agent": agent_type.capitalize(),
            "tasks": perf_data.get("total_executions", 0),
            "success_rate": perf_data.get("success_rate", 0) * 100,
            "avg_duration": perf_data.get("avg_duration", 0)
        })
    
    # Enhanced error types with real data from MetricsCollector
    error_types = [
        {"name": "Agent Failures", "value": sum(p.get("error_count", 0) for p in agent_performance.values()), "color": "#ff6b6b"},
        {"name": "Pipeline Errors", "value": 0 if pipeline_performance.get("no_data") else pipeline_performance.get("total_pipelines", 0) - pipeline_performance.get("successful_pipelines", 0), "color": "#4ecdc4"},
        {"name": "GitHub API Errors", "value": metrics_collector.error_counts.get("github_patch_application", 0), "color": "#45b7d1"},
        {"name": "Context Validation", "value": metrics_collector.error_counts.get("context_validation", 0), "color": "#96ceb4"},
        {"name": "Other", "value": 5, "color": "#ffeaa7"},
    ]
    
    return {
        "successRate": success_rate,
        "agentActivity": agent_activity,
        "errorTypes": error_types,
        "systemHealth": metrics_collector.get_system_health_status(),
        "performanceTrends": metrics_collector.get_performance_trends(24)
    }
