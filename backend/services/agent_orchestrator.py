
from services.pipeline_validator import pipeline_validator
from services.jira_client import JiraClient
from services.github_client import GitHubClient
from services.patch_service import PatchService
from agents.planner_agent import PlannerAgent
from agents.developer_agent import DeveloperAgent
from core.models import Ticket, TicketStatus
from core.database import get_sync_db
import logging
import json

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self):
        self.jira_client = JiraClient()
        self.github_client = GitHubClient()
        self.patch_service = PatchService()
        self.planner_agent = PlannerAgent()
        self.developer_agent = DeveloperAgent()
    
    async def process_ticket(self, ticket: Ticket):
        """Process a ticket through the entire pipeline"""
        logger.info(f"🚀 Processing ticket {ticket.jira_key}")
        
        # Phase 1: Planner Agent
        logger.info(f"📋 Running planner agent for {ticket.jira_key}")
        planner_result = await self.planner_agent.execute_with_retry(ticket)
        
        # Phase 2: Developer Agent
        logger.info(f"🔧 Running developer agent for {ticket.jira_key}")
        developer_result = await self.developer_agent.execute_with_retry(ticket, context=planner_result)
        
        # CRITICAL DEBUG: Log complete developer result before validation
        logger.info(f"🔍 ORCHESTRATOR DEBUG - Complete developer result for {ticket.jira_key}:")
        logger.info(f"  - Result keys: {list(developer_result.keys())}")
        logger.info(f"  - intelligent_patching: {developer_result.get('intelligent_patching')}")
        logger.info(f"  - semantic_evaluation_enabled: {developer_result.get('semantic_evaluation_enabled')}")
        logger.info(f"  - using_intelligent_patching: {developer_result.get('using_intelligent_patching')}")
        logger.info(f"  - patches count: {len(developer_result.get('patches', []))}")
        logger.info(f"  - semantic_stats: {developer_result.get('semantic_stats')}")
        logger.info(f"  - quality_thresholds: {developer_result.get('quality_thresholds')}")
        
        # Log individual patch details
        patches = developer_result.get('patches', [])
        for i, patch in enumerate(patches):
            logger.info(f"  - Patch {i}: confidence={patch.get('confidence_score', 0):.3f}, strategy={patch.get('processing_strategy', 'unknown')}")
        
        # Phase 3: Validate Results
        logger.info(f"🔍 Validating enhanced developer results...")
        validation = pipeline_validator.validate_developer_results(developer_result)
        
        # CRITICAL DEBUG: Log validation results
        logger.info(f"🔍 ORCHESTRATOR DEBUG - Validation result for {ticket.jira_key}:")
        logger.info(f"  - Valid: {validation['valid']}")
        logger.info(f"  - Reason: {validation['reason']}")
        logger.info(f"  - Quality: {validation['patches_quality']}")
        logger.info(f"  - Using intelligent patching: {validation['using_intelligent_patching']}")
        
        if not validation["valid"]:
            logger.warning(f"❌ Enhanced developer validation failed: {validation['reason']}")
            logger.warning(f"🔍 MANUAL REVIEW REQUIRED: {ticket.jira_key}")
            
            # Update JIRA with manual review status
            await self.jira_client.add_comment(
                ticket.jira_key,
                f"❌ AI Agent failed to generate suitable patches. {validation['reason']}"
            )
            await self.jira_client.transition_ticket(ticket.jira_key, "Needs Review")
            logger.info(f"✅ Updated JIRA {ticket.jira_key} and status to Needs Review")
            return
        
        # Determine next action
        action = pipeline_validator.determine_next_action(validation, ticket)
        
        logger.info(f"🎯 Next action for {ticket.jira_key}: {action['action']}")
        
        # Execute action
        if action["action"] == "create_pr":
            logger.info(f"🚀 Creating PR for {ticket.jira_key}")
            await self._create_pull_request(ticket, developer_result, action)
        elif action["action"] == "create_pr_with_review":
            logger.info(f"⚠️ Creating PR with review flag for {ticket.jira_key}")
            await self._create_pull_request(ticket, developer_result, action)
        else:
            logger.info(f"👥 Manual review required for {ticket.jira_key}")
            await self._handle_manual_review(ticket, action)
        
        # Update JIRA status
        await self.jira_client.add_comment(ticket.jira_key, action["jira_comment"])
        if action["jira_status"]:
            await self.jira_client.transition_ticket(ticket.jira_key, action["jira_status"])
        
        logger.info(f"✅ Updated JIRA {ticket.jira_key}")
    
    async def _create_pull_request(self, ticket: Ticket, developer_result: Dict, action: Dict):
        """Create a pull request with the generated patches"""
        patches = developer_result.get("patches", [])
        
        # Create PR with patch service
        pr_url = await self.patch_service.create_pull_request(
            ticket=ticket,
            patches=patches,
            require_manual_review=action.get("require_manual_review", False)
        )
        
        if pr_url:
            logger.info(f"✅ Created PR: {pr_url}")
            # Update ticket status
            with next(get_sync_db()) as db:
                db_ticket = db.query(Ticket).filter(Ticket.id == ticket.id).first()
                if db_ticket:
                    db_ticket.status = TicketStatus.IN_REVIEW
                    db_ticket.github_pr_url = pr_url
                    db.commit()
        else:
            logger.error(f"❌ Failed to create PR for {ticket.jira_key}")
    
    async def _handle_manual_review(self, ticket: Ticket, action: Dict):
        """Handle manual review requirement"""
        with next(get_sync_db()) as db:
            db_ticket = db.query(Ticket).filter(Ticket.id == ticket.id).first()
            if db_ticket:
                db_ticket.status = TicketStatus.NEEDS_REVIEW
                db.commit()
        
        logger.info(f"👥 Manual review flagged for {ticket.jira_key}")
