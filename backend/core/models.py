
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

Base = declarative_base()

class TicketStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"

class AgentType(str, Enum):
    INTAKE = "intake"
    PLANNER = "planner"
    DEVELOPER = "developer"
    QA = "qa"
    COMMUNICATOR = "communicator"

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    jira_id = Column(String, unique=True, index=True)
    title = Column(String)
    description = Column(Text)
    error_trace = Column(Text)
    status = Column(String, default=TicketStatus.TODO)
    priority = Column(String, default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    retry_count = Column(Integer, default=0)
    assigned_agent = Column(String)
    estimated_files = Column(JSON)
    
    executions = relationship("AgentExecution", back_populates="ticket")
    patches = relationship("PatchAttempt", back_populates="ticket")
    github_pr = relationship("GitHubPR", back_populates="ticket", uselist=False)

class AgentExecution(Base):
    __tablename__ = "agent_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    agent_type = Column(String)
    status = Column(String, default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    logs = Column(Text)
    output_data = Column(JSON)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    ticket = relationship("Ticket", back_populates="executions")

class PatchAttempt(Base):
    __tablename__ = "patch_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    execution_id = Column(Integer, ForeignKey("agent_executions.id"))  # Fixed field name
    target_file = Column(String)
    patch_content = Column(Text)
    patched_code = Column(Text)
    test_code = Column(Text)
    commit_message = Column(String)
    confidence_score = Column(Float)
    base_file_hash = Column(String)
    patch_type = Column(String, default="unified_diff")
    test_results = Column(JSON)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="patches")
    execution = relationship("AgentExecution")

class GitHubPR(Base):
    __tablename__ = "github_prs"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    pr_number = Column(Integer)
    pr_url = Column(String)
    branch_name = Column(String)
    status = Column(String, default="open")
    merge_status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="github_pr")

class AgentConfig(Base):
    __tablename__ = "agent_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String, unique=True)
    enabled = Column(Boolean, default=True)
    config_data = Column(JSON)
    last_activity = Column(DateTime)
    
class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String)
    metric_value = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metric_metadata = Column(JSON)
