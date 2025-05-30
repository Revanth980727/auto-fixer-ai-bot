
import asyncio
from typing import Dict, Any
from core.models import Ticket, TicketStatus, AgentType
from core.database import get_sync_db
from core.config import config
from agents.intake_agent import IntakeAgent
from agents.planner_agent import PlannerAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from agents.communicator_agent import CommunicatorAgent
from services.jira_client import JIRAClient
import logging

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self):
        self.running = False
        self.agents = {
            AgentType.INTAKE: IntakeAgent(),
            AgentType.PLANNER: PlannerAgent(),
            AgentType.DEVELOPER: DeveloperAgent(),
            AgentType.QA: QAAgent(),
            AgentType.COMMUNICATOR: CommunicatorAgent(),
        }
        self.jira_client = JIRAClient()
        # Use configured intervals
        self.process_interval = config.agent_process_interval
        self.intake_interval = config.agent_intake_interval

    async def start_processing(self):
        """Start processing tickets through agent pipeline"""
        self.running = True
        logger.info(f"Starting agent orchestrator with intervals: process={self.process_interval}s, intake={self.intake_interval}s")
        
        # Validate configuration
        missing_config = config.validate_required_config()
        if missing_config:
            logger.warning(f"Missing required configuration: {missing_config}")
        
        # Start intake polling in background
        asyncio.create_task(self._intake_polling_loop())
        
        while self.running:
            try:
                await self.process_pending_tickets()
                await asyncio.sleep(self.process_interval)
            except Exception as e:
                logger.error(f"Error in agent orchestrator: {e}")
                await asyncio.sleep(5)

    async def stop_processing(self):
        """Stop processing"""
        self.running = False
        logger.info("Stopping agent orchestrator...")

    async def _intake_polling_loop(self):
        """Separate loop for intake agent to poll JIRA"""
        while self.running:
            try:
                if config.jira_base_url and config.jira_api_token:
                    await self.agents[AgentType.INTAKE].poll_and_create_tickets()
                else:
                    logger.debug("JIRA not configured, skipping intake polling")
                await asyncio.sleep(self.intake_interval)
            except Exception as e:
                logger.error(f"Error in intake polling: {e}")
                await asyncio.sleep(30)

    async def process_pending_tickets(self):
        """Process tickets that are ready for agent processing"""
        with next(get_sync_db()) as db:
            # Get tickets in different stages
            todo_tickets = db.query(Ticket).filter(
                Ticket.status == TicketStatus.TODO
            ).limit(3).all()
            
            for ticket in todo_tickets:
                try:
                    await self.process_ticket_pipeline(ticket)
                except Exception as e:
                    logger.error(f"Error processing ticket {ticket.id}: {e}")

    async def process_ticket_pipeline(self, ticket: Ticket):
        """Process a single ticket through the complete agent pipeline"""
        logger.info(f"Processing ticket {ticket.id} through pipeline")
        
        # Update ticket status to in progress and update Jira
        with next(get_sync_db()) as db:
            ticket.status = TicketStatus.IN_PROGRESS
            db.add(ticket)
            db.commit()
        
        # Update Jira status to "In Progress"
        await self._update_jira_status(ticket.jira_id, "In Progress", 
                                     f"AI Agent system has started processing this ticket.")
        
        try:
            # Step 1: Planner agent analyzes the ticket
            logger.info(f"Ticket {ticket.id}: Running planner agent")
            planner_result = await self.agents[AgentType.PLANNER].execute_with_retry(ticket)
            
            # Step 2: Developer agent generates patches
            logger.info(f"Ticket {ticket.id}: Running developer agent")
            developer_result = await self.agents[AgentType.DEVELOPER].execute_with_retry(ticket)
            
            # Step 3: QA agent tests patches
            logger.info(f"Ticket {ticket.id}: Running QA agent")
            qa_result = await self.agents[AgentType.QA].execute_with_retry(ticket)
            
            # Step 4: If QA passes, communicator creates PR
            if qa_result.get("ready_for_deployment"):
                logger.info(f"Ticket {ticket.id}: Running communicator agent")
                comm_result = await self.agents[AgentType.COMMUNICATOR].execute_with_retry(ticket)
                
                # Update ticket status to in review
                with next(get_sync_db()) as db:
                    ticket.status = TicketStatus.IN_REVIEW
                    db.add(ticket)
                    db.commit()
                
                # Update Jira status to "Needs Review" for human code review
                await self._update_jira_status(ticket.jira_id, "Needs Review", 
                                             f"AI Agent has completed processing and created a pull request. Please review the changes.")
                    
                logger.info(f"Ticket {ticket.id}: Pipeline completed successfully - PR created")
            else:
                # QA failed, mark as failed and update Jira
                with next(get_sync_db()) as db:
                    ticket.status = TicketStatus.FAILED
                    db.add(ticket)
                    db.commit()
                
                # Update Jira status to "Needs Review" for human intervention
                await self._update_jira_status(ticket.jira_id, "Needs Review", 
                                             f"AI Agent was unable to successfully process this ticket. QA testing failed. Human intervention required.")
                
                logger.warning(f"Ticket {ticket.id}: QA testing failed")
            
        except Exception as e:
            # Mark ticket as failed and update Jira
            with next(get_sync_db()) as db:
                ticket.status = TicketStatus.FAILED
                ticket.retry_count += 1
                db.add(ticket)
                db.commit()
            
            # Check if we've exceeded max retries
            if ticket.retry_count >= config.agent_max_retries:
                # Update Jira status to "Needs Review" after max retries
                await self._update_jira_status(ticket.jira_id, "Needs Review", 
                                             f"AI Agent failed to process this ticket after {config.agent_max_retries} attempts. Human intervention required. Error: {str(e)}")
                logger.error(f"Ticket {ticket.id} failed after {config.agent_max_retries} retries: {e}")
            else:
                # Will retry, keep ticket status as failed for now
                logger.error(f"Ticket {ticket.id} failed (attempt {ticket.retry_count}): {e}")
            
            raise e

    async def retry_failed_ticket(self, ticket_id: int):
        """Retry a failed ticket"""
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket and ticket.retry_count < config.agent_max_retries:
                ticket.status = TicketStatus.TODO
                ticket.retry_count += 1
                db.add(ticket)
                db.commit()
                logger.info(f"Ticket {ticket_id} queued for retry (attempt {ticket.retry_count})")
            else:
                logger.warning(f"Ticket {ticket_id} cannot be retried - max retries exceeded")

    async def _update_jira_status(self, jira_id: str, status: str, comment: str = ""):
        """Update Jira ticket status with error handling"""
        try:
            success = await self.jira_client.update_ticket_status(jira_id, status, comment)
            if success:
                logger.info(f"Updated Jira ticket {jira_id} to status '{status}'")
            else:
                logger.warning(f"Failed to update Jira ticket {jira_id} to status '{status}'")
        except Exception as e:
            logger.error(f"Error updating Jira ticket {jira_id} status: {e}")

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents with configuration details"""
        return {
            "orchestrator_running": self.running,
            "configuration": config.to_dict(),
            "intervals": {
                "process": self.process_interval,
                "intake": self.intake_interval
            },
            "agents_available": [agent_type.value for agent_type in self.agents.keys()],
            "intake_polling": self.running and bool(config.jira_base_url and config.jira_api_token),
            "jira_status_management": "enabled"
        }

