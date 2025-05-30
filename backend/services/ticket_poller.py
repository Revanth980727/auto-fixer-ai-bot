
import asyncio
from agents.intake_agent import IntakeAgent
from core.config import config
import logging
import os

logger = logging.getLogger(__name__)

class TicketPoller:
    def __init__(self):
        self.running = False
        # Use configured poll interval
        self.poll_interval = config.agent_poll_interval
        self.intake_agent = IntakeAgent()
        
        # Debug logging for initialization
        logger.info(f"TicketPoller initialized with poll_interval: {self.poll_interval}s")
        logger.info(f"Jira config loaded - Base URL: {config.jira_base_url}")
        logger.info(f"Jira config loaded - Project Key: {config.jira_project_key}")
        logger.info(f"Jira config loaded - Username: {config.jira_username}")
        logger.info(f"Jira config loaded - API Token present: {'Yes' if config.jira_api_token else 'No'}")
        if config.jira_api_token:
            logger.info(f"Jira API Token length: {len(config.jira_api_token)} chars")

    async def start_polling(self):
        """Start polling for new tickets"""
        logger.info("=== TICKET POLLER START_POLLING CALLED ===")
        self.running = True
        logger.info(f"Starting ticket polling with interval: {self.poll_interval}s")
        
        # Debug environment variables
        logger.info(f"Environment JIRA_BASE_URL: {os.getenv('JIRA_BASE_URL')}")
        logger.info(f"Environment JIRA_API_TOKEN present: {'Yes' if os.getenv('JIRA_API_TOKEN') else 'No'}")
        logger.info(f"Environment JIRA_PROJECT_KEY: {os.getenv('JIRA_PROJECT_KEY')}")
        logger.info(f"Environment AGENT_POLL_INTERVAL: {os.getenv('AGENT_POLL_INTERVAL')}")
        
        # Validate JIRA configuration
        if not config.jira_base_url or not config.jira_api_token:
            logger.warning("JIRA configuration incomplete - polling will be skipped")
            logger.warning(f"Missing: jira_base_url={bool(config.jira_base_url)}, jira_api_token={bool(config.jira_api_token)}")
        else:
            logger.info("JIRA configuration validated successfully")
        
        poll_count = 0
        while self.running:
            try:
                poll_count += 1
                logger.info(f"=== POLL CYCLE {poll_count} STARTING ===")
                
                if config.jira_base_url and config.jira_api_token:
                    logger.info("Calling intake_agent.poll_and_create_tickets()")
                    await self.intake_agent.poll_and_create_tickets()
                    logger.info("Completed intake_agent.poll_and_create_tickets()")
                else:
                    logger.debug("JIRA not configured, skipping poll")
                
                logger.info(f"Poll cycle {poll_count} completed, sleeping for {self.poll_interval}s")
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in ticket polling cycle {poll_count}: {e}")
                logger.exception("Full error traceback:")
                await asyncio.sleep(30)  # Shorter retry delay

    async def stop_polling(self):
        """Stop polling"""
        self.running = False
        logger.info("Stopping ticket polling...")
