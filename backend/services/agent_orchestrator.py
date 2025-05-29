
import asyncio
from typing import Dict, Any
from core.models import Ticket, TicketStatus, AgentType
from core.database import get_sync_db
from agents.planner_agent import PlannerAgent
from agents.developer_agent import DeveloperAgent
import logging

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self):
        self.running = False
        self.agents = {
            AgentType.PLANNER: PlannerAgent(),
            AgentType.DEVELOPER: DeveloperAgent(),
        }
        self.process_interval = 10  # seconds

    async def start_processing(self):
        """Start processing tickets through agent pipeline"""
        self.running = True
        logger.info("Starting agent orchestrator...")
        
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

    async def process_pending_tickets(self):
        """Process tickets that are ready for agent processing"""
        with next(get_sync_db()) as db:
            # Get tickets that need processing
            pending_tickets = db.query(Ticket).filter(
                Ticket.status == TicketStatus.TODO
            ).limit(5).all()
            
            for ticket in pending_tickets:
                try:
                    await self.process_ticket(ticket)
                except Exception as e:
                    logger.error(f"Error processing ticket {ticket.id}: {e}")

    async def process_ticket(self, ticket: Ticket):
        """Process a single ticket through the agent pipeline"""
        logger.info(f"Processing ticket {ticket.id}")
        
        # Update ticket status
        with next(get_sync_db()) as db:
            ticket.status = TicketStatus.IN_PROGRESS
            db.add(ticket)
            db.commit()
        
        try:
            # Step 1: Planner agent analyzes the ticket
            planner_result = await self.agents[AgentType.PLANNER].execute_with_retry(ticket)
            
            # Step 2: Developer agent generates patches
            developer_result = await self.agents[AgentType.DEVELOPER].execute_with_retry(ticket)
            
            # Update ticket status to completed
            with next(get_sync_db()) as db:
                ticket.status = TicketStatus.COMPLETED
                db.add(ticket)
                db.commit()
                
            logger.info(f"Successfully processed ticket {ticket.id}")
            
        except Exception as e:
            # Mark ticket as failed
            with next(get_sync_db()) as db:
                ticket.status = TicketStatus.FAILED
                db.add(ticket)
                db.commit()
            
            logger.error(f"Failed to process ticket {ticket.id}: {e}")
