
import asyncio
from typing import List
from core.models import Ticket, TicketStatus
from core.database import get_sync_db
import logging

logger = logging.getLogger(__name__)

class TicketPoller:
    def __init__(self):
        self.running = False
        self.poll_interval = 30  # seconds

    async def start_polling(self):
        """Start polling for new tickets"""
        self.running = True
        logger.info("Starting ticket polling...")
        
        while self.running:
            try:
                await self.poll_tickets()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in ticket polling: {e}")
                await asyncio.sleep(5)  # Short retry delay

    async def stop_polling(self):
        """Stop polling"""
        self.running = False
        logger.info("Stopping ticket polling...")

    async def poll_tickets(self):
        """Poll for new tickets from JIRA"""
        # Mock implementation - in reality this would connect to JIRA API
        logger.debug("Polling for new tickets...")
        
        # Here you would:
        # 1. Connect to JIRA API
        # 2. Fetch new tickets
        # 3. Create Ticket records in database
        # 4. Trigger agent processing
        
        # For now, just log that we're polling
        pass

    def create_ticket_from_jira(self, jira_data: dict) -> Ticket:
        """Create a ticket from JIRA data"""
        with next(get_sync_db()) as db:
            ticket = Ticket(
                jira_id=jira_data.get("id"),
                title=jira_data.get("title", ""),
                description=jira_data.get("description", ""),
                error_trace=jira_data.get("error_trace", ""),
                status=TicketStatus.TODO,
                priority=jira_data.get("priority", "medium")
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            return ticket
