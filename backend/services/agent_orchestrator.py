
import asyncio
from typing import Dict, Any
from core.models import Ticket, TicketStatus, AgentType
from core.database import get_sync_db
from agents.intake_agent import IntakeAgent
from agents.planner_agent import PlannerAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from agents.communicator_agent import CommunicatorAgent
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
        self.process_interval = 10  # seconds
        self.intake_interval = 60   # seconds

    async def start_processing(self):
        """Start processing tickets through agent pipeline"""
        self.running = True
        logger.info("Starting agent orchestrator...")
        
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
                await self.agents[AgentType.INTAKE].poll_and_create_tickets()
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
        
        # Update ticket status
        with next(get_sync_db()) as db:
            ticket.status = TicketStatus.IN_PROGRESS
            db.add(ticket)
            db.commit()
        
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
                    
                logger.info(f"Ticket {ticket.id}: Pipeline completed successfully - PR created")
            else:
                # QA failed, mark as failed
                with next(get_sync_db()) as db:
                    ticket.status = TicketStatus.FAILED
                    db.add(ticket)
                    db.commit()
                
                logger.warning(f"Ticket {ticket.id}: QA testing failed")
            
        except Exception as e:
            # Mark ticket as failed
            with next(get_sync_db()) as db:
                ticket.status = TicketStatus.FAILED
                db.add(ticket)
                db.commit()
            
            logger.error(f"Failed to process ticket {ticket.id}: {e}")
            raise e

    async def retry_failed_ticket(self, ticket_id: int):
        """Retry a failed ticket"""
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = TicketStatus.TODO
                ticket.retry_count += 1
                db.add(ticket)
                db.commit()
                logger.info(f"Ticket {ticket_id} queued for retry")

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            "orchestrator_running": self.running,
            "process_interval": self.process_interval,
            "agents_available": list(self.agents.keys()),
            "intake_polling": self.running
        }
