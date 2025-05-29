
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, TicketStatus
from core.database import get_sync_db
from services.jira_client import JIRAClient
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class IntakeAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.INTAKE)
        self.jira_client = JIRAClient()
    
    async def process(self, ticket: Ticket, execution: AgentExecution) -> Dict[str, Any]:
        """Process incoming tickets from JIRA"""
        self.log_execution(execution, "Processing JIRA ticket intake")
        
        # Validate ticket data
        if not ticket.jira_id or not ticket.title:
            raise ValueError("Invalid ticket data: missing JIRA ID or title")
        
        # Enrich ticket with additional JIRA data if needed
        self.log_execution(execution, f"Processing ticket {ticket.jira_id}")
        
        # Basic validation and categorization
        priority_score = self._calculate_priority_score(ticket)
        complexity_estimate = self._estimate_complexity(ticket)
        
        result = {
            "status": "processed",
            "priority_score": priority_score,
            "complexity_estimate": complexity_estimate,
            "ready_for_planning": True
        }
        
        self.log_execution(execution, f"Ticket processed with priority {priority_score}")
        return result
    
    async def poll_and_create_tickets(self):
        """Poll JIRA for new tickets and create them in our system"""
        logger.info("Polling JIRA for new tickets")
        
        try:
            jira_issues = await self.jira_client.fetch_new_tickets()
            
            for issue in jira_issues:
                ticket_data = self.jira_client.format_ticket_data(issue)
                
                # Check if ticket already exists
                with next(get_sync_db()) as db:
                    existing = db.query(Ticket).filter(
                        Ticket.jira_id == ticket_data["jira_id"]
                    ).first()
                    
                    if not existing:
                        ticket = Ticket(**ticket_data)
                        db.add(ticket)
                        db.commit()
                        logger.info(f"Created new ticket: {ticket.jira_id}")
                        
        except Exception as e:
            logger.error(f"Error in ticket polling: {e}")
    
    def _calculate_priority_score(self, ticket: Ticket) -> float:
        """Calculate priority score based on ticket properties"""
        score = 0.5  # Base score
        
        # Adjust based on JIRA priority
        priority_weights = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2
        }
        score *= priority_weights.get(ticket.priority.lower(), 0.5)
        
        # Boost if error trace is present
        if ticket.error_trace:
            score += 0.2
        
        # Boost if title indicates severity
        urgent_keywords = ["crash", "critical", "urgent", "blocking"]
        if any(keyword in ticket.title.lower() for keyword in urgent_keywords):
            score += 0.3
        
        return min(score, 1.0)
    
    def _estimate_complexity(self, ticket: Ticket) -> str:
        """Estimate ticket complexity"""
        if not ticket.error_trace:
            return "high"  # No error trace = harder to diagnose
        
        # Simple heuristics
        if len(ticket.description) < 100:
            return "low"
        elif "multiple files" in ticket.description.lower():
            return "high"
        else:
            return "medium"
