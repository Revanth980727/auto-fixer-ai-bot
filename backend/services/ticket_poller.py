
import asyncio
from agents.intake_agent import IntakeAgent
from core.config import config
import logging

logger = logging.getLogger(__name__)

class TicketPoller:
    def __init__(self):
        self.running = False
        # Use configured poll interval
        self.poll_interval = config.agent_poll_interval
        self.intake_agent = IntakeAgent()

    async def start_polling(self):
        """Start polling for new tickets"""
        self.running = True
        logger.info(f"Starting ticket polling with interval: {self.poll_interval}s")
        
        # Validate JIRA configuration
        if not config.jira_base_url or not config.jira_api_token:
            logger.warning("JIRA configuration incomplete - polling will be skipped")
        
        while self.running:
            try:
                if config.jira_base_url and config.jira_api_token:
                    await self.intake_agent.poll_and_create_tickets()
                else:
                    logger.debug("JIRA not configured, skipping poll")
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in ticket polling: {e}")
                await asyncio.sleep(30)  # Shorter retry delay

    async def stop_polling(self):
        """Stop polling"""
        self.running = False
        logger.info("Stopping ticket polling...")
