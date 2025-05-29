
import asyncio
from agents.intake_agent import IntakeAgent
import logging

logger = logging.getLogger(__name__)

class TicketPoller:
    def __init__(self):
        self.running = False
        self.poll_interval = 60  # seconds - poll JIRA every minute
        self.intake_agent = IntakeAgent()

    async def start_polling(self):
        """Start polling for new tickets"""
        self.running = True
        logger.info("Starting ticket polling...")
        
        while self.running:
            try:
                await self.intake_agent.poll_and_create_tickets()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in ticket polling: {e}")
                await asyncio.sleep(30)  # Shorter retry delay

    async def stop_polling(self):
        """Stop polling"""
        self.running = False
        logger.info("Stopping ticket polling...")
