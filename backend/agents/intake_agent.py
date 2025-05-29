
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, TicketStatus
from core.database import get_sync_db
from core.config import config
from services.jira_client import JIRAClient
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class IntakeAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.INTAKE)
        self.jira_client = JIRAClient()
        # Load configuration values
        self.max_retries = config.agent_max_retries
    
    async def process(self, ticket: Ticket, execution: AgentExecution) -> Dict[str, Any]:
        """Process incoming tickets from JIRA"""
        self.log_execution(execution, "Processing JIRA ticket intake")
        
        # Validate ticket data
        if not ticket.jira_id or not ticket.title:
            raise ValueError("Invalid ticket data: missing JIRA ID or title")
        
        # Enrich ticket with additional JIRA data if needed
        self.log_execution(execution, f"Processing ticket {ticket.jira_id}")
        
        # Calculate priority score and complexity using configuration
        priority_score = self._calculate_priority_score(ticket)
        complexity_estimate = self._estimate_complexity(ticket)
        
        result = {
            "status": "processed",
            "priority_score": priority_score,
            "complexity_estimate": complexity_estimate,
            "ready_for_planning": True,
            "configuration_used": {
                "priority_weights": config.priority_weights,
                "complexity_threshold": config.complexity_description_threshold
            }
        }
        
        self.log_execution(execution, f"Ticket processed with priority {priority_score} and complexity {complexity_estimate}")
        return result
    
    async def poll_and_create_tickets(self):
        """Poll JIRA for new tickets and create them in our system"""
        logger.info("Polling JIRA for new tickets")
        
        try:
            jira_issues = await self.jira_client.fetch_new_tickets()
            logger.info(f"Found {len(jira_issues)} issues from JIRA")
            
            created_count = 0
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
                        created_count += 1
                        logger.info(f"Created new ticket: {ticket.jira_id}")
            
            logger.info(f"Created {created_count} new tickets from JIRA polling")
                        
        except Exception as e:
            logger.error(f"Error in ticket polling: {e}")
    
    def _calculate_priority_score(self, ticket: Ticket) -> float:
        """Calculate priority score based on configured weights"""
        score = 0.5  # Base score
        
        # Adjust based on JIRA priority using configured weights
        score *= config.priority_weights.get(ticket.priority.lower(), 0.5)
        
        # Boost if error trace is present (configurable)
        if ticket.error_trace:
            score += config.priority_error_trace_boost
        
        # Boost if title indicates severity using configured keywords
        if any(keyword in ticket.title.lower() for keyword in config.urgent_keywords):
            score += config.priority_urgent_keyword_boost
        
        return min(score, 1.0)
    
    def _estimate_complexity(self, ticket: Ticket) -> str:
        """Estimate ticket complexity using configured thresholds"""
        if not ticket.error_trace:
            return "high"  # No error trace = harder to diagnose
        
        # Use configured threshold for description length
        if len(ticket.description) < config.complexity_description_threshold:
            return "low"
        elif "multiple files" in ticket.description.lower():
            return "high"
        else:
            return config.complexity_default
