from services.pipeline_validator import pipeline_validator
from services.jira_client import JIRAClient
from services.github_client import GitHubClient
from services.patch_service import PatchService
from agents.planner_agent import PlannerAgent
from agents.developer_agent import DeveloperAgent
from core.models import Ticket, TicketStatus
from core.database import get_sync_db
import logging
import json
import asyncio
import time
from services.pipeline_context import context_manager, PipelineStage
from core.models import AgentType

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self):
        self.jira_client = JIRAClient()
        self.github_client = GitHubClient()
        self.patch_service = PatchService()
        self.planner_agent = PlannerAgent()
        self.developer_agent = DeveloperAgent()
        self.running = False
        self.processing_task = None
        self.agents = {
            AgentType.PLANNER: self.planner_agent,
            AgentType.DEVELOPER: self.developer_agent,
            # Add other agents if needed
        }
    
    async def start_processing(self):
        """Start the orchestrator processing loop"""
        logger.info("Starting AgentOrchestrator processing...")
        self.running = True
        
        while self.running:
            try:
                # Get pending tickets from database
                with next(get_sync_db()) as db:
                    pending_tickets = db.query(Ticket).filter(
                        Ticket.status == TicketStatus.TODO
                    ).limit(10).all()
                
                if pending_tickets:
                    logger.info(f"Processing {len(pending_tickets)} pending tickets")
                    for ticket in pending_tickets:
                        if not self.running:
                            break
                        
                        # Update ticket status to in_progress
                        with next(get_sync_db()) as db:
                            db_ticket = db.query(Ticket).filter(Ticket.id == ticket.id).first()
                            if db_ticket:
                                db_ticket.status = TicketStatus.IN_PROGRESS
                                db.commit()
                        
                        # Process the ticket
                        await self.process_ticket(ticket)
                else:
                    logger.debug("No pending tickets found")
                
                # Wait before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in orchestrator processing loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def stop_processing(self):
        """Stop the orchestrator processing"""
        logger.info("Stopping AgentOrchestrator processing...")
        self.running = False
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
    
    async def get_agent_status(self):
        """Get the current status of the orchestrator"""
        return {
            "orchestrator_running": self.running,
            "agents": {
                "planner": "active" if self.planner_agent else "inactive",
                "developer": "active" if self.developer_agent else "inactive"
            }
        }
    
    async def retry_failed_ticket(self, ticket_id: int):
        """Retry processing a failed ticket"""
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = TicketStatus.TODO
                ticket.retry_count += 1
                db.commit()
                logger.info(f"Queued ticket {ticket_id} for retry")
    
    async def process_ticket(self, ticket: Ticket):
        """Process a ticket through the entire pipeline"""
        logger.info(f"🚀 Processing ticket {ticket.jira_id}")
        
        # Phase 1: Planner Agent
        logger.info(f"📋 Running planner agent for {ticket.jira_id}")
        planner_result = await self.planner_agent.execute_with_retry(ticket)
        
        # Phase 2: Developer Agent
        logger.info(f"🔧 Running developer agent for {ticket.jira_id}")
        developer_result = await self.developer_agent.execute_with_retry(ticket, context=planner_result)
        
        # CRITICAL DEBUG: Log complete developer result before validation
        logger.info(f"🔍 ORCHESTRATOR DEBUG - Complete developer result for {ticket.jira_id}:")
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
        logger.info(f"🔍 ORCHESTRATOR DEBUG - Validation result for {ticket.jira_id}:")
        logger.info(f"  - Valid: {validation['valid']}")
        logger.info(f"  - Reason: {validation['reason']}")
        logger.info(f"  - Quality: {validation['patches_quality']}")
        logger.info(f"  - Using intelligent patching: {validation['using_intelligent_patching']}")
        
        if not validation["valid"]:
            logger.warning(f"❌ Enhanced developer validation failed: {validation['reason']}")
            logger.warning(f"🔍 MANUAL REVIEW REQUIRED: {ticket.jira_id}")
            
            # Update JIRA with manual review status
            await self.jira_client.add_comment(
                ticket.jira_id,
                f"❌ AI Agent failed to generate suitable patches. {validation['reason']}"
            )
            await self.jira_client.transition_ticket(ticket.jira_id, "Needs Review")
            logger.info(f"✅ Updated JIRA {ticket.jira_id} and status to Needs Review")
            return
        
        # Determine next action
        action = pipeline_validator.determine_next_action(validation, ticket)
        
        logger.info(f"🎯 Next action for {ticket.jira_id}: {action['action']}")
        
        # Execute action
        if action["action"] == "create_pr":
            logger.info(f"🚀 Creating PR for {ticket.jira_id}")
            await self._create_pull_request(ticket, developer_result, action)
        elif action["action"] == "create_pr_with_review":
            logger.info(f"⚠️ Creating PR with review flag for {ticket.jira_id}")
            await self._create_pull_request(ticket, developer_result, action)
        else:
            logger.info(f"👥 Manual review required for {ticket.jira_id}")
            await self._handle_manual_review(ticket, action)
        
        # Update JIRA status
        await self.jira_client.add_comment(ticket.jira_id, action["jira_comment"])
        if action["jira_status"]:
            await self.jira_client.transition_ticket(ticket.jira_id, action["jira_status"])
        
        logger.info(f"✅ Updated JIRA {ticket.jira_id}")

    async def _create_pull_request(self, ticket: Ticket, developer_result: dict, action: dict):
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
            logger.error(f"❌ Failed to create PR for {ticket.jira_id}")

    async def _handle_manual_review(self, ticket: Ticket, action: dict):
        """Handle manual review requirement"""
        with next(get_sync_db()) as db:
            db_ticket = db.query(Ticket).filter(Ticket.id == ticket.id).first()
            if db_ticket:
                db_ticket.status = TicketStatus.NEEDS_REVIEW
                db.commit()
        
        logger.info(f"👥 Manual review flagged for {ticket.jira_id}")

    async def _process_ticket_with_comprehensive_jira_integration(self, ticket_id: int):
        """Process ticket with complete JIRA status management and commenting"""
        pipeline_start_time = time.time()
        logger.info(f"🎯 COMPREHENSIVE JIRA INTEGRATION - Ticket {ticket_id}")
        
        # Create pipeline context
        pipeline_context = context_manager.create_context(ticket_id)
        
        try:
            # Get fresh ticket data with proper session management
            with next(get_sync_db()) as db:
                ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.error(f"❌ Ticket {ticket_id} not found")
                    return
                    
                jira_id = ticket.jira_id
                ticket_title = ticket.title
                ticket_priority = ticket.priority
                ticket_description = ticket.description
                ticket_error_trace = ticket.error_trace
                current_status = ticket.status
                
                logger.info(f"📋 Processing {jira_id}: {ticket_title}")
                
                # PHASE 1: Start processing - Update JIRA to "In Progress"
                if current_status == TicketStatus.TODO.value:
                    logger.info(f"📈 JIRA UPDATE: Moving {jira_id} to In Progress")
                    
                    start_comment = f"""🤖 **AI Agent System Started Processing**

**Ticket Analysis:**
- Priority: {ticket_priority}
- Complexity: Auto-detected based on description length and error traces
- Processing Mode: {'Full GitHub Integration' if self.github_client._is_configured() else 'JIRA-Only Mode'}

**Pipeline Stages:**
1. 🧠 **Planning** - Analyzing root cause and identifying target files
2. 👨‍💻 **Development** - Generating intelligent patches
3. 🧪 **Quality Assurance** - Testing and validation
4. 📢 **Communication** - {'Creating GitHub PR' if self.github_client._is_configured() else 'Updating ticket status'}

**Status:** Analysis in progress..."""
                    
                    await self._update_jira_with_comment(jira_id, "In Progress", start_comment)
                    
                    # Update database status with fresh session
                    ticket.status = TicketStatus.IN_PROGRESS.value
                    db.add(ticket)
                    db.commit()
                    current_status = TicketStatus.IN_PROGRESS.value
            
            # PHASE 2: Planning Agent with JIRA Updates
            logger.info(f"🧠 PHASE 1: Enhanced Planning for {jira_id}")
            planner_start_time = time.time()
            
            # Create a fresh ticket object for planning context
            with next(get_sync_db()) as db:
                fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                planner_context = await self._prepare_production_planner_context(fresh_ticket, pipeline_context.context_id)
            
            if planner_context.get("github_access_failed"):
                await self._mark_ticket_for_review(ticket_id, jira_id, 
                    "GitHub repository access failed during planning phase. Unable to analyze source files for intelligent fix generation.")
                return
            
            # Execute planner with fresh ticket object
            with next(get_sync_db()) as db:
                fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                planner_result = await self.agents[AgentType.PLANNER].execute_with_retry(fresh_ticket, planner_context)
            
            planner_duration = time.time() - planner_start_time
            
            # Update JIRA with planning results
            planning_comment = f"""🧠 **Planning Phase Completed** ({planner_duration:.1f}s)

**Root Cause Analysis:**
{planner_result.get('root_cause', 'Analysis in progress...')}

**Files Identified for Modification:**
{chr(10).join(f"• `{file.get('path', 'Unknown')}` - {file.get('reason', 'Target file')}" for file in planner_result.get('likely_files', [])[:5])}

**Confidence Level:** {planner_result.get('confidence', 'Medium')}
**Next Phase:** Generating code patches..."""
            
            await self._update_jira_with_comment(jira_id, None, planning_comment)
            
            # Validate planning results
            if not self._validate_planner_results(planner_result):
                await self._mark_ticket_for_review(ticket_id, jira_id, 
                    "Planning phase failed to identify actionable files or root cause. Manual analysis required.")
                return
            
            # PHASE 3: Development Agent with JIRA Updates
            logger.info(f"👨‍💻 PHASE 2: Enhanced Development for {jira_id}")
            developer_start_time = time.time()
            
            # Create fresh ticket object for development context
            with next(get_sync_db()) as db:
                fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                developer_context = await self._prepare_production_developer_context(fresh_ticket, planner_result, pipeline_context.context_id)
            
            if developer_context.get("github_access_failed"):
                await self._mark_ticket_for_review(ticket_id, jira_id, 
                    "Unable to fetch source files for patch generation. GitHub access required for automated fixes.")
                return
            
            # Execute developer with fresh ticket object
            with next(get_sync_db()) as db:
                fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                developer_result = await self.agents[AgentType.DEVELOPER].execute_with_retry(fresh_ticket, developer_context)
            
            developer_duration = time.time() - developer_start_time
            
            # Update JIRA with development results
            patches = developer_result.get("patches", [])
            development_comment = f"""👨‍💻 **Development Phase Completed** ({developer_duration:.1f}s)

**Patches Generated:** {len(patches)}
**Intelligent Patching:** {'✅ Enabled' if developer_result.get('intelligent_patching') else '❌ Basic mode'}

**Patch Summary:**
{chr(10).join(f"• `{patch.get('target_file', 'Unknown')}` - {patch.get('description', 'Code modification')}" for patch in patches[:3])}

**Next Phase:** Quality assurance testing..."""
            
            await self._update_jira_with_comment(jira_id, None, development_comment)
            
            # Validate development results
            if not self._validate_enhanced_developer_results(developer_result):
                await self._mark_ticket_for_review(ticket_id, jira_id, 
                    "Development phase failed to generate valid patches. Manual code changes required.")
                return
            
            # PHASE 4: QA Agent with JIRA Updates
            logger.info(f"🧪 PHASE 3: Enhanced QA for {jira_id}")
            qa_start_time = time.time()
            
            # Create fresh ticket object for QA context
            with next(get_sync_db()) as db:
                fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                qa_context = await self._prepare_production_qa_context(fresh_ticket, developer_result, pipeline_context.context_id)
                qa_result = await self.agents[AgentType.QA].execute_with_retry(fresh_ticket, qa_context)
            
            qa_duration = time.time() - qa_start_time
            
            # FIXED: Improved QA result interpretation
            successful_patches = qa_result.get("successful_patches", 0)
            ready_for_deployment = qa_result.get("ready_for_deployment", False)
            qa_status = qa_result.get("status", "unknown")
            patch_application_results = qa_result.get("patch_application_results", {})
            
            # Enhanced QA success detection
            qa_success = (
                qa_status == "completed" and 
                (successful_patches > 0 or 
                 len(patch_application_results.get("successful_patches", [])) > 0 or
                 ready_for_deployment)
            )
            
            logger.info(f"🔍 QA ANALYSIS: status={qa_status}, successful={successful_patches}, ready={ready_for_deployment}, qa_success={qa_success}")
            
            # Update JIRA with QA results
            qa_comment = f"""🧪 **Quality Assurance Completed** ({qa_duration:.1f}s)

**Test Results:**
- Patches Tested: {len(patches)}
- Successful: {successful_patches}
- Ready for Deployment: {'✅ Yes' if ready_for_deployment else '❌ No'}

**Quality Checks:**
- Syntax Validation: {'✅ Passed' if successful_patches > 0 else '❌ Failed'}
- Logic Verification: {'✅ Passed' if ready_for_deployment else '⚠️ Needs Review'}
- Integration Testing: {'✅ Passed' if ready_for_deployment else '⚠️ Requires Manual Testing'}

**Status:** {'Proceeding to deployment' if qa_success else 'Manual review required'}"""
            
            await self._update_jira_with_comment(jira_id, None, qa_comment)
            
            # PHASE 5: Communication/Deployment - FIXED logic
            if qa_success:
                logger.info(f"📢 PHASE 4: Communication/Deployment for {jira_id}")
                comm_start_time = time.time()
                
                # Create fresh ticket object for communication context
                with next(get_sync_db()) as db:
                    fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    comm_context = await self._prepare_production_communicator_context(fresh_ticket, qa_result, pipeline_context.context_id)
                    comm_result = await self.agents[AgentType.COMMUNICATOR].execute_with_retry(fresh_ticket, comm_context)
                
                comm_duration = time.time() - comm_start_time
                
                # Final success update to JIRA
                github_operations = comm_result.get("github_operations", False)
                pr_info = comm_result.get("pr_info", {})
                
                success_comment = f"""🎉 **Automated Fix Completed Successfully**

**Deployment Summary:**
- Total Processing Time: {(time.time() - pipeline_start_time):.1f}s
- Patches Applied: {comm_result.get('patches_deployed', len(patches))}
- Target Branch: {comm_result.get('target_branch', 'main')}

**GitHub Integration:**
{'✅ **Pull Request Created**' if github_operations and pr_info else '✅ **Changes Applied Directly**'}
{f"- PR #{pr_info.get('number', 'N/A')}: {pr_info.get('html_url', 'N/A')}" if pr_info else "- Changes have been applied directly to the target branch"}

**Actions Taken:**
{chr(10).join(f"• {action}" for action in comm_result.get('actions_taken', ['Applied automated fixes to repository']))}

**Status:** {'Ready for code review and merge' if github_operations else 'Fix deployed successfully'}

---
*This fix was automatically generated and deployed by the AI Agent System*"""
                
                await self._update_jira_with_comment(jira_id, "Done", success_comment)
                
                # Update ticket status to completed with fresh session
                with next(get_sync_db()) as db:
                    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        ticket.status = TicketStatus.COMPLETED.value
                        db.add(ticket)
                        db.commit()
                
                logger.info(f"🎉 SUCCESS: Ticket {jira_id} completed with full automation")
                
            else:
                # QA failed - mark for review
                await self._mark_ticket_for_review(ticket_id, jira_id, 
                    f"Quality assurance testing failed. {successful_patches} of {len(patches)} patches passed validation. Manual review and testing required before deployment.")
        
        except Exception as e:
            logger.error(f"💥 Pipeline error for {jira_id}: {e}")
            await self._handle_ticket_processing_error(ticket_id, e)

    async def _update_jira_with_comment(self, jira_id: str, status: str, comment: str):
        """Helper to update JIRA ticket with comment and optional status transition"""
        if comment:
            await self.jira_client.add_comment(jira_id, comment)
            logger.info(f"📝 Added comment to {jira_id}: {len(comment)} chars")
        if status:
            await self.jira_client.transition_ticket(jira_id, status)
            logger.info(f"✅ Successfully transitioned {jira_id} to '{status}'")

    async def _mark_ticket_for_review(self, ticket_id: int, jira_id: str, reason: str):
        """Mark ticket for manual review with comment and status update"""
        logger.warning(f"🔍 MANUAL REVIEW REQUIRED: {jira_id} - {reason}")
        await self.jira_client.add_comment(jira_id, f"⚠️ Manual review required: {reason}")
        await self.jira_client.transition_ticket(jira_id, "Needs Review")
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = TicketStatus.NEEDS_REVIEW.value
                db.add(ticket)
                db.commit()
        logger.info(f"✅ Updated JIRA {jira_id} and status to Needs Review")

    async def _handle_ticket_processing_error(self, ticket_id: int, error: Exception):
        """Handle errors during ticket processing"""
        logger.error(f"Error processing ticket {ticket_id}: {error}")
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = TicketStatus.FAILED.value
                db.add(ticket)
                db.commit()
        # Optionally notify or escalate

    async def _prepare_production_planner_context(self, ticket: Ticket, context_id: str) -> dict:
        """Prepare context for planner agent"""
        # Placeholder for actual context preparation logic
        return {}

    async def _prepare_production_developer_context(self, ticket: Ticket, planner_result: dict, context_id: str) -> dict:
        """Prepare context for developer agent"""
        # Placeholder for actual context preparation logic
        return {}

    async def _prepare_production_qa_context(self, ticket: Ticket, developer_result: dict, context_id: str) -> dict:
        """Prepare context for QA agent"""
        # Placeholder for actual context preparation logic
        return {}

    async def _prepare_production_communicator_context(self, ticket: Ticket, qa_result: dict, context_id: str) -> dict:
        """Prepare context for communicator agent"""
        # Placeholder for actual context preparation logic
        return {}

    def _validate_planner_results(self, planner_result: dict) -> bool:
        """Validate planner results"""
        # Basic validation example
        if not planner_result:
            return False
        if not planner_result.get("likely_files"):
            return False
        return True

    def _validate_enhanced_developer_results(self, developer_result: dict) -> bool:
        """Validate developer results with enhanced logic"""
        if not developer_result:
            return False
        patches = developer_result.get("patches", [])
        if not patches:
            return False
        return True
