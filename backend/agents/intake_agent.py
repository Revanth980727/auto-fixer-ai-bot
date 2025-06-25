
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, TicketStatus
from core.database import get_sync_db
from core.config import config
from services.jira_client import JIRAClient
from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class IntakeAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.INTAKE)
        self.jira_client = JIRAClient()
        # Load configuration values
        self.max_retries = config.agent_max_retries
    
    async def process(self, ticket: Ticket, execution_id: int) -> Dict[str, Any]:
        """Process incoming tickets from JIRA"""
        self.log_execution(execution_id, "Processing JIRA ticket intake")
        
        # Validate ticket data
        if not ticket.jira_id or not ticket.title:
            raise ValueError("Invalid ticket data: missing JIRA ID or title")
        
        # Enrich ticket with additional JIRA data if needed
        self.log_execution(execution_id, f"Processing ticket {ticket.jira_id}")
        
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
        
        self.log_execution(execution_id, f"Ticket processed with priority {priority_score} and complexity {complexity_estimate}")
        return result
    
    async def poll_and_create_tickets(self):
        """Poll JIRA for new tickets and create them in our system"""
        logger.info("🚀 INTAKE AGENT - Starting ticket polling")
        
        try:
            jira_issues = await self.jira_client.fetch_new_tickets()
            logger.info(f"📥 INTAKE AGENT - Found {len(jira_issues)} issues from JIRA")
            
            if not jira_issues:
                logger.info("📭 INTAKE AGENT - No issues found in JIRA")
                return
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            with next(get_sync_db()) as db:
                for issue in jira_issues:
                    ticket_data = self.jira_client.format_ticket_data(issue)
                    jira_id = ticket_data["jira_id"]
                    
                    # Check if ticket already exists
                    existing = db.query(Ticket).filter(
                        Ticket.jira_id == jira_id
                    ).first()
                    
                    if existing:
                        if config.jira_force_reprocess:
                            # Update existing ticket if force reprocess is enabled
                            logger.info(f"🔄 INTAKE AGENT - Force reprocessing existing ticket: {jira_id}")
                            existing.title = ticket_data["title"]
                            existing.description = ticket_data["description"]
                            existing.priority = ticket_data["priority"]
                            existing.error_trace = ticket_data["error_trace"]
                            existing.updated_at = datetime.utcnow()
                            existing.status = TicketStatus.TODO  # Reset status for reprocessing
                            db.add(existing)
                            updated_count += 1
                        else:
                            logger.debug(f"⏭️ INTAKE AGENT - Skipping existing ticket: {jira_id}")
                            skipped_count += 1
                    else:
                        # Create new ticket
                        logger.info(f"✨ INTAKE AGENT - Creating new ticket: {jira_id}")
                        logger.debug(f"   Title: {ticket_data['title'][:50]}...")
                        logger.debug(f"   Priority: {ticket_data['priority']}")
                        logger.debug(f"   Description length: {len(ticket_data['description'])} chars")
                        logger.debug(f"   Error trace present: {'Yes' if ticket_data['error_trace'] else 'No'}")
                        
                        ticket = Ticket(**ticket_data)
                        db.add(ticket)
                        created_count += 1
                
                # Commit all changes
                if created_count > 0 or updated_count > 0:
                    db.commit()
                    logger.info("💾 INTAKE AGENT - Database changes committed")
            
            # Final summary
            logger.info(f"📊 INTAKE AGENT - Polling complete:")
            logger.info(f"   ✨ Created: {created_count} new tickets")
            logger.info(f"   🔄 Updated: {updated_count} tickets (force reprocess)")
            logger.info(f"   ⏭️ Skipped: {skipped_count} existing tickets")
            logger.info(f"   📋 Total processed: {len(jira_issues)} JIRA issues")
            
            if created_count == 0 and updated_count == 0 and len(jira_issues) > 0:
                logger.info("💡 INTAKE AGENT - Tip: All JIRA issues already exist in database")
                logger.info(f"   To reprocess existing tickets, set JIRA_FORCE_REPROCESS=true")
                        
        except Exception as e:
            logger.error(f"❌ INTAKE AGENT - Error in ticket polling: {e}")
            logger.exception("Full error traceback:")
    
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
