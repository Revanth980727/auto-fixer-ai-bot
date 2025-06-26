
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
        
        logger.info("🔧 INTAKE AGENT INIT DEBUG:")
        logger.info(f"   - Max Retries: {self.max_retries}")
        logger.info(f"   - Force Reprocess: {config.jira_force_reprocess}")
        logger.info(f"   - Poll Interval: {config.agent_poll_interval}s")
    
    async def process(self, ticket: Ticket, execution_id: int) -> Dict[str, Any]:
        """Process incoming tickets from JIRA with enhanced debugging"""
        self.log_execution(execution_id, "Processing JIRA ticket intake")
        
        logger.debug(f"🎫 PROCESS TICKET DEBUG:")
        logger.debug(f"   - Ticket ID: {ticket.id}")
        logger.debug(f"   - JIRA ID: {ticket.jira_id}")
        logger.debug(f"   - Title: {ticket.title[:50]}...")
        logger.debug(f"   - Status: {ticket.status}")
        logger.debug(f"   - Priority: {ticket.priority}")
        
        # Validate ticket data
        if not ticket.jira_id or not ticket.title:
            logger.error(f"❌ Invalid ticket data: JIRA ID={ticket.jira_id}, Title={bool(ticket.title)}")
            raise ValueError("Invalid ticket data: missing JIRA ID or title")
        
        # Enrich ticket with additional JIRA data if needed
        self.log_execution(execution_id, f"Processing ticket {ticket.jira_id}")
        
        # Calculate priority score and complexity using configuration
        priority_score = self._calculate_priority_score(ticket)
        complexity_estimate = self._estimate_complexity(ticket)
        
        logger.info(f"🎯 TICKET PROCESSING COMPLETE:")
        logger.info(f"   - JIRA ID: {ticket.jira_id}")
        logger.info(f"   - Priority Score: {priority_score}")
        logger.info(f"   - Complexity: {complexity_estimate}")
        
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
        """Poll JIRA for new tickets and create them in our system with enhanced debugging"""
        logger.info("🚀 INTAKE AGENT - Starting comprehensive ticket polling")
        logger.info(f"🔧 POLLING CONFIG DEBUG:")
        logger.info(f"   - Force Reprocess: {config.jira_force_reprocess}")
        logger.info(f"   - Max Results: {config.jira_max_results}")
        logger.info(f"   - Max Total: {config.jira_max_total_results}")
        logger.info(f"   - Target Statuses: {config.jira_statuses}")
        
        try:
            jira_issues = await self.jira_client.fetch_new_tickets()
            logger.info(f"📥 INTAKE AGENT - Received {len(jira_issues)} issues from JIRA")
            
            if not jira_issues:
                logger.info("📭 INTAKE AGENT - No issues found in JIRA")
                logger.info("🔍 DEBUGGING TIPS:")
                logger.info("   - Check if your JIRA_STATUSES match exactly what's in JIRA")
                logger.info("   - Verify the JIRA project has tickets in the configured statuses")
                logger.info("   - Check JIRA permissions for the API token")
                return
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            with next(get_sync_db()) as db:
                for idx, issue in enumerate(jira_issues):
                    logger.debug(f"🎫 PROCESSING ISSUE {idx + 1}/{len(jira_issues)}")
                    
                    ticket_data = self.jira_client.format_ticket_data(issue)
                    jira_id = ticket_data["jira_id"]
                    
                    logger.debug(f"   - JIRA ID: {jira_id}")
                    logger.debug(f"   - Title: {ticket_data['title'][:50]}...")
                    
                    # Check if ticket already exists
                    existing = db.query(Ticket).filter(
                        Ticket.jira_id == jira_id
                    ).first()
                    
                    if existing:
                        logger.debug(f"   - Existing ticket found: ID={existing.id}")
                        if config.jira_force_reprocess:
                            logger.info(f"🔄 INTAKE AGENT - Force reprocessing existing ticket: {jira_id}")
                            logger.debug(f"   - Old title: {existing.title[:50]}...")
                            logger.debug(f"   - New title: {ticket_data['title'][:50]}...")
                            logger.debug(f"   - Old status: {existing.status}")
                            logger.debug(f"   - Will reset to: {TicketStatus.TODO}")
                            
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
                        logger.debug(f"   - Title: {ticket_data['title'][:100]}...")
                        logger.debug(f"   - Priority: {ticket_data['priority']}")
                        logger.debug(f"   - Description length: {len(ticket_data['description'])} chars")
                        logger.debug(f"   - Error trace present: {'Yes' if ticket_data['error_trace'] else 'No'}")
                        
                        ticket = Ticket(**ticket_data)
                        db.add(ticket)
                        created_count += 1
                
                # Commit all changes
                if created_count > 0 or updated_count > 0:
                    logger.info("💾 INTAKE AGENT - Committing database changes...")
                    db.commit()
                    logger.info("✅ INTAKE AGENT - Database changes committed successfully")
                else:
                    logger.info("📝 INTAKE AGENT - No database changes to commit")
            
            # Comprehensive final summary
            logger.info("📊 INTAKE AGENT - POLLING COMPLETE - COMPREHENSIVE SUMMARY:")
            logger.info(f"   ✨ Created: {created_count} new tickets")
            logger.info(f"   🔄 Updated: {updated_count} tickets (force reprocess)")
            logger.info(f"   ⏭️ Skipped: {skipped_count} existing tickets")
            logger.info(f"   📋 Total processed: {len(jira_issues)} JIRA issues")
            logger.info(f"   🎯 Success rate: {((created_count + updated_count) / len(jira_issues) * 100):.1f}%")
            
            if created_count == 0 and updated_count == 0 and len(jira_issues) > 0:
                logger.info("💡 INTAKE AGENT - All JIRA issues already exist in database")
                logger.info("🔧 TROUBLESHOOTING TIPS:")
                logger.info(f"   - To reprocess existing tickets, set JIRA_FORCE_REPROCESS=true")
                logger.info(f"   - Current force reprocess setting: {config.jira_force_reprocess}")
                logger.info(f"   - Database contains {skipped_count} existing tickets for this query")
            
            if created_count > 0 or updated_count > 0:
                logger.info("🎉 INTAKE AGENT - Successfully processed tickets!")
                logger.info("   - These tickets are now ready for the planning agent")
                logger.info(f"   - Next poll in {config.agent_poll_interval} seconds")
                        
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in ticket polling: {e}")
            logger.exception("Full error traceback:")
            logger.error("🔧 DEBUGGING SUGGESTIONS:")
            logger.error("   - Check JIRA API credentials and permissions")
            logger.error("   - Verify JIRA base URL is accessible")
            logger.error("   - Ensure database connectivity")
            logger.error(f"   - Current configuration: JIRA_BASE_URL={config.jira_base_url}")
    
    def _calculate_priority_score(self, ticket: Ticket) -> float:
        """Calculate priority score based on configured weights with debugging"""
        score = 0.5  # Base score
        
        logger.debug(f"🎯 PRIORITY CALCULATION DEBUG:")
        logger.debug(f"   - Base score: {score}")
        logger.debug(f"   - Ticket priority: {ticket.priority}")
        logger.debug(f"   - Available weights: {config.priority_weights}")
        
        # Adjust based on JIRA priority using configured weights
        priority_multiplier = config.priority_weights.get(ticket.priority.lower(), 0.5)
        score *= priority_multiplier
        logger.debug(f"   - After priority adjustment: {score} (multiplier: {priority_multiplier})")
        
        # Boost if error trace is present (configurable)
        if ticket.error_trace:
            score += config.priority_error_trace_boost
            logger.debug(f"   - Error trace boost applied: +{config.priority_error_trace_boost} = {score}")
        
        # Boost if title indicates severity using configured keywords
        urgent_keywords_found = [kw for kw in config.urgent_keywords if kw in ticket.title.lower()]
        if urgent_keywords_found:
            score += config.priority_urgent_keyword_boost
            logger.debug(f"   - Urgent keywords found: {urgent_keywords_found}")
            logger.debug(f"   - Urgent keyword boost applied: +{config.priority_urgent_keyword_boost} = {score}")
        
        final_score = min(score, 1.0)
        logger.debug(f"   - Final priority score: {final_score}")
        
        return final_score
    
    def _estimate_complexity(self, ticket: Ticket) -> str:
        """Estimate ticket complexity using configured thresholds with debugging"""
        logger.debug(f"🧮 COMPLEXITY ESTIMATION DEBUG:")
        logger.debug(f"   - Error trace present: {'Yes' if ticket.error_trace else 'No'}")
        logger.debug(f"   - Description length: {len(ticket.description)}")
        logger.debug(f"   - Threshold: {config.complexity_description_threshold}")
        
        if not ticket.error_trace:
            logger.debug(f"   - No error trace = high complexity")
            return "high"  # No error trace = harder to diagnose
        
        if len(ticket.description) < config.complexity_description_threshold:
            logger.debug(f"   - Short description = low complexity")
            return "low"
        elif "multiple files" in ticket.description.lower():
            logger.debug(f"   - Multiple files mentioned = high complexity")
            return "high"
        else:
            logger.debug(f"   - Default complexity: {config.complexity_default}")
            return config.complexity_default
