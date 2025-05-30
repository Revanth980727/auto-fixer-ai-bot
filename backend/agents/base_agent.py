
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.models import Ticket, AgentExecution, AgentType
from core.database import get_sync_db
from core.config import config
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.max_retries = config.agent_max_retries
        
    @abstractmethod
    async def process(self, ticket: Ticket, execution: AgentExecution) -> Dict[str, Any]:
        """Process a ticket and return results"""
        pass
    
    def create_execution(self, ticket: Ticket) -> int:
        """Create a new execution record for this agent and return its ID"""
        with next(get_sync_db()) as db:
            execution = AgentExecution(
                ticket_id=ticket.id,
                agent_type=self.agent_type.value,
                status="running"
            )
            db.add(execution)
            db.commit()
            db.refresh(execution)
            return execution.id
    
    def update_execution(self, execution_id: int, status: str, 
                        output_data: Optional[Dict] = None, 
                        error_message: Optional[str] = None,
                        logs: Optional[str] = None):
        """Update execution status and data"""
        with next(get_sync_db()) as db:
            execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if not execution:
                logger.error(f"Execution {execution_id} not found")
                return
                
            execution.status = status
            execution.completed_at = datetime.utcnow()
            
            if output_data:
                execution.output_data = output_data
            if error_message:
                execution.error_message = error_message
            if logs:
                execution.logs = logs
                
            db.add(execution)
            db.commit()
    
    def log_execution(self, execution_id: int, message: str):
        """Add log message to execution"""
        with next(get_sync_db()) as db:
            execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if not execution:
                logger.error(f"Execution {execution_id} not found")
                return
                
            current_logs = execution.logs or ""
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            new_log = f"[{timestamp}] {self.agent_type.value.upper()}: {message}\n"
            execution.logs = current_logs + new_log
            db.add(execution)
            db.commit()
            
    async def execute_with_retry(self, ticket: Ticket) -> Dict[str, Any]:
        """Execute agent with retry logic"""
        execution_id = self.create_execution(ticket)
        
        for attempt in range(self.max_retries + 1):
            try:
                self.log_execution(execution_id, f"Starting attempt {attempt + 1}/{self.max_retries + 1}")
                
                # Get fresh execution object for this attempt
                with next(get_sync_db()) as db:
                    execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
                    if not execution:
                        raise Exception(f"Execution {execution_id} not found")
                    
                    result = await self.process(ticket, execution)
                
                self.update_execution(execution_id, "completed", output_data=result)
                self.log_execution(execution_id, "Completed successfully")
                return result
                
            except Exception as e:
                error_msg = str(e)
                self.log_execution(execution_id, f"Error on attempt {attempt + 1}: {error_msg}")
                
                if attempt == self.max_retries:
                    self.update_execution(execution_id, "failed", error_message=error_msg)
                    self.log_execution(execution_id, f"Failed after {self.max_retries + 1} attempts")
                    
                    # Update ticket retry count
                    with next(get_sync_db()) as db:
                        ticket = db.query(Ticket).filter(Ticket.id == ticket.id).first()
                        if ticket:
                            ticket.retry_count += 1
                            db.add(ticket)
                            db.commit()
                    
                    raise e
                
                # Update retry count on execution
                with next(get_sync_db()) as db:
                    execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
                    if execution:
                        execution.retry_count += 1
                        db.add(execution)
                        db.commit()
                
        return {}
