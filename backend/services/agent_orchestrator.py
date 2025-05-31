
import asyncio
from typing import Dict, Any, List
from core.models import Ticket, TicketStatus, AgentType
from core.database import get_sync_db
from core.config import config
from agents.intake_agent import IntakeAgent
from agents.planner_agent import PlannerAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from agents.communicator_agent import CommunicatorAgent
from services.jira_client import JIRAClient
from services.github_client import GitHubClient
from services.patch_service import PatchService
import logging
import re

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
        self.github_client = GitHubClient()
        self.patch_service = PatchService()
        # Use configured intervals
        self.process_interval = config.agent_process_interval
        self.intake_interval = config.agent_intake_interval

    async def start_processing(self):
        """Start processing tickets through enhanced agent pipeline"""
        self.running = True
        logger.info(f"Starting enhanced agent orchestrator with intervals: process={self.process_interval}s, intake={self.intake_interval}s")
        
        # Validate configuration
        missing_config = config.validate_required_config()
        if missing_config:
            logger.warning(f"Missing required configuration: {missing_config}")
        
        # Check GitHub configuration - this is now a hard requirement
        github_status = self.github_client.get_configuration_status()
        logger.info(f"GitHub configuration status: {github_status}")
        
        if not github_status.get("configured"):
            logger.error("GitHub is not properly configured - enhanced agent processing requires GitHub access")
            logger.error("Please configure GITHUB_TOKEN, GITHUB_REPO_OWNER, and GITHUB_REPO_NAME")
            return
        
        # Start intake polling in background
        asyncio.create_task(self._intake_polling_loop())
        
        while self.running:
            try:
                await self.process_pending_tickets()
                await asyncio.sleep(self.process_interval)
            except Exception as e:
                logger.error(f"Error in enhanced agent orchestrator: {e}")
                await asyncio.sleep(5)

    # ... keep existing code (stop_processing, _intake_polling_loop, process_pending_tickets methods)

    async def process_ticket_pipeline(self, ticket_id: int):
        """Process a single ticket through the enhanced agent pipeline"""
        logger.info(f"🎯 Starting enhanced pipeline for ticket {ticket_id}")
        
        # Update ticket status to in progress and update Jira
        jira_id = None
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                logger.error(f"❌ Ticket {ticket_id} not found")
                return
                
            logger.info(f"📋 Ticket {ticket_id}: {ticket.title} (Status: {ticket.status})")
            
            # Only update to IN_PROGRESS if it's currently TODO
            if ticket.status == TicketStatus.TODO:
                ticket.status = TicketStatus.IN_PROGRESS
                jira_id = ticket.jira_id
                db.add(ticket)
                db.commit()
                
                logger.info(f"✅ Ticket {ticket_id} status updated to IN_PROGRESS")
                
                # Update Jira status - using proper method
                await self._update_jira_status(jira_id, "In Progress", 
                                             f"Enhanced AI Agent system has started processing this ticket with intelligent patching.")
            else:
                jira_id = ticket.jira_id
        
        try:
            # Get fresh ticket object for processing
            with next(get_sync_db()) as db:
                ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.error(f"❌ Ticket {ticket_id} not found during processing")
                    return
                
                # Step 1: Enhanced Planner agent with repository discovery
                logger.info(f"🧠 STEP 1: Running enhanced planner agent for ticket {ticket_id}")
                planner_context = await self._prepare_enhanced_planner_context(ticket)
                
                # Check if planner context is valid (no GitHub access issues)
                if not planner_context or planner_context.get("github_access_failed"):
                    logger.warning(f"⚠️ GitHub access failed for ticket {ticket_id} - marking for human intervention")
                    await self._mark_ticket_for_review(ticket_id, jira_id, 
                        "GitHub repository access failed. Unable to fetch source files for enhanced analysis. Please verify GitHub configuration and retry manually.")
                    return
                
                logger.info(f"📊 Enhanced planner context prepared: {len(planner_context.get('error_trace_files', []))} error trace files")
                
                planner_result = await self.agents[AgentType.PLANNER].execute_with_retry(ticket, planner_context)
                logger.info(f"✅ ENHANCED PLANNER COMPLETED for ticket {ticket_id}")
                logger.info(f"📋 Planner result keys: {list(planner_result.keys())}")
                
                # Validate planner results
                if not self._validate_planner_results(planner_result):
                    logger.warning(f"⚠️ Enhanced planner validation failed for ticket {ticket_id}")
                    await self._mark_ticket_for_review(ticket_id, jira_id, 
                        "Enhanced planner agent failed to identify target files or root cause. Manual analysis required.")
                    return
                
                logger.info(f"✅ Enhanced planner validation passed for ticket {ticket_id}")
                
                # Step 2: Enhanced Developer agent with intelligent patch generation
                logger.info(f"👨‍💻 STEP 2: Running enhanced developer agent for ticket {ticket_id}")
                developer_context = await self._prepare_enhanced_developer_context(ticket, planner_result)
                
                # Check if developer context is valid
                if not developer_context or developer_context.get("github_access_failed"):
                    logger.warning(f"⚠️ GitHub access failed during enhanced developer context preparation for ticket {ticket_id}")
                    await self._mark_ticket_for_review(ticket_id, jira_id, 
                        "Unable to fetch source files for intelligent patch generation. GitHub repository access required.")
                    return
                
                logger.info(f"📊 Enhanced developer context prepared: {len(developer_context.get('source_files', []))} source files")
                
                developer_result = await self.agents[AgentType.DEVELOPER].execute_with_retry(ticket, developer_context)
                logger.info(f"✅ ENHANCED DEVELOPER COMPLETED for ticket {ticket_id}")
                logger.info(f"📋 Developer result keys: {list(developer_result.keys())}")
                
                # Validate enhanced developer results
                if not self._validate_enhanced_developer_results(developer_result):
                    logger.warning(f"⚠️ Enhanced developer validation failed for ticket {ticket_id}")
                    await self._mark_ticket_for_review(ticket_id, jira_id, 
                        "Enhanced developer agent failed to generate valid intelligent patches. Manual code changes required.")
                    return
                
                logger.info(f"✅ Enhanced developer validation passed for ticket {ticket_id}")
                
                # Step 3: Enhanced QA agent with intelligent patch testing
                logger.info(f"🧪 STEP 3: Running enhanced QA agent for ticket {ticket_id}")
                qa_context = await self._prepare_enhanced_qa_context(ticket, developer_result)
                logger.info(f"📊 Enhanced QA context prepared: {len(qa_context.get('patches', []))} patches to test intelligently")
                
                qa_result = await self.agents[AgentType.QA].execute_with_retry(ticket, qa_context)
                logger.info(f"✅ ENHANCED QA COMPLETED for ticket {ticket_id}")
                logger.info(f"📋 QA result: ready_for_deployment={qa_result.get('ready_for_deployment')}, successful_patches={qa_result.get('successful_patches', 0)}")
            
            # Step 4: If enhanced QA passes, communicator creates PR
            if qa_result.get("ready_for_deployment") and qa_result.get("successful_patches", 0) > 0:
                logger.info(f"📢 STEP 4: Running enhanced communicator agent for ticket {ticket_id}")
                
                # Get fresh ticket object for communicator
                with next(get_sync_db()) as db:
                    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        comm_context = await self._prepare_enhanced_communicator_context(ticket, qa_result)
                        comm_result = await self.agents[AgentType.COMMUNICATOR].execute_with_retry(ticket, comm_context)
                        logger.info(f"✅ ENHANCED COMMUNICATOR COMPLETED for ticket {ticket_id}")
                
                # Update ticket status to COMPLETED
                with next(get_sync_db()) as db:
                    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        ticket.status = TicketStatus.COMPLETED
                        db.add(ticket)
                        db.commit()
                
                # Update Jira status to "Done"
                await self._update_jira_status(jira_id, "Done", 
                                             f"Enhanced AI Agent has successfully completed processing with intelligent patch application and created a pull request. The fix is ready for deployment.")
                    
                logger.info(f"🎉 ENHANCED PIPELINE SUCCESS: Ticket {ticket_id} completed successfully with intelligent patching")
            else:
                # Enhanced QA failed, mark for review
                logger.warning(f"⚠️ Enhanced QA validation failed for ticket {ticket_id} - marking for human review")
                
                qa_message = "Enhanced QA testing failed - no patches passed intelligent validation." if qa_result.get("successful_patches", 0) == 0 else "Enhanced QA testing completed but patches were not ready for deployment due to conflicts or validation issues."
                await self._mark_ticket_for_review(ticket_id, jira_id, qa_message)
                
                logger.warning(f"🔍 ENHANCED PIPELINE REVIEW NEEDED: Ticket {ticket_id} - {qa_message}")
            
        except Exception as e:
            logger.error(f"💥 ENHANCED PIPELINE ERROR for ticket {ticket_id}: {e}")
            
            # Mark ticket as failed and update Jira
            with next(get_sync_db()) as db:
                ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                if ticket:
                    ticket.status = TicketStatus.FAILED
                    ticket.retry_count += 1
                    current_retry_count = ticket.retry_count
                    db.add(ticket)
                    db.commit()
                    
                    # Check if we've exceeded max retries
                    if current_retry_count >= config.agent_max_retries:
                        await self._mark_ticket_for_review(ticket_id, jira_id, 
                            f"Enhanced AI Agent failed to process this ticket after {config.agent_max_retries} attempts. Error: {str(e)}")
                        logger.error(f"🚫 ENHANCED PIPELINE FAILED: Ticket {ticket_id} failed after {config.agent_max_retries} retries")
                    else:
                        logger.warning(f"🔄 ENHANCED PIPELINE RETRY: Ticket {ticket_id} failed (attempt {current_retry_count}): {e}")
            
            raise e

    async def _prepare_enhanced_planner_context(self, ticket: Ticket) -> Dict[str, Any]:
        """Prepare enhanced context for planner agent with repository discovery"""
        logger.info(f"🔍 Preparing enhanced planner context for ticket {ticket.id}")
        
        # Check GitHub configuration first
        if not self.github_client._is_configured():
            logger.error(f"❌ GitHub not configured - cannot prepare enhanced planner context for ticket {ticket.id}")
            return {"github_access_failed": True}
        
        context = {
            "ticket": ticket,
            "repository_files": [],
            "error_trace_files": [],
            "repository_structure": {}
        }
        
        # Enhanced file discovery from error trace
        if ticket.error_trace:
            file_matches = re.findall(r'File "([^"]+)"', ticket.error_trace)
            logger.info(f"📁 Found {len(file_matches)} files in error trace: {file_matches}")
            
            files_fetched = 0
            for file_path in file_matches:
                try:
                    file_content = await self.github_client.get_file_content(file_path)
                    if file_content:
                        context["error_trace_files"].append({
                            "path": file_path,
                            "content": file_content,
                            "hash": self._calculate_file_hash(file_content)
                        })
                        files_fetched += 1
                        logger.info(f"✅ Successfully fetched error trace file: {file_path}")
                    else:
                        logger.warning(f"⚠️ File not found in repository: {file_path}")
                except Exception as e:
                    logger.error(f"❌ Could not fetch file {file_path}: {e}")
            
            # If we couldn't fetch any files, this is a failure
            if files_fetched == 0 and len(file_matches) > 0:
                logger.error(f"❌ Failed to fetch any source files for enhanced planner on ticket {ticket.id}")
                return {"github_access_failed": True}
        else:
            logger.warning(f"⚠️ No error trace found for ticket {ticket.id}")
        
        logger.info(f"✅ Enhanced planner context ready: {len(context['error_trace_files'])} files prepared")
        return context

    async def _prepare_enhanced_developer_context(self, ticket: Ticket, planner_result: Dict) -> Dict[str, Any]:
        """Prepare enhanced context for developer agent with intelligent file tracking"""
        logger.info(f"🔍 Preparing enhanced developer context for ticket {ticket.id}")
        
        # Check GitHub configuration first
        if not self.github_client._is_configured():
            logger.error(f"❌ GitHub not configured - cannot prepare enhanced developer context for ticket {ticket.id}")
            return {"github_access_failed": True}
        
        context = {
            "planner_analysis": planner_result,
            "source_files": [],
            "repository_state": {}
        }
        
        # Get likely files from planner analysis with enhanced tracking
        likely_files = planner_result.get("likely_files", [])
        
        files_fetched = 0
        for file_info in likely_files:
            file_path = file_info.get("path") if isinstance(file_info, dict) else str(file_info)
            
            try:
                file_content = await self.github_client.get_file_content(file_path)
                if file_content:
                    context["source_files"].append({
                        "path": file_path,
                        "content": file_content,
                        "hash": self._calculate_file_hash(file_content),
                        "priority": file_info.get("priority", "medium") if isinstance(file_info, dict) else "medium",
                        "size": len(file_content)
                    })
                    files_fetched += 1
                    logger.info(f"✅ Successfully fetched enhanced source file: {file_path}")
                else:
                    logger.warning(f"⚠️ Enhanced source file not found in repository: {file_path}")
            except Exception as e:
                logger.error(f"❌ Could not fetch enhanced source file {file_path}: {e}")
        
        # If we couldn't fetch any source files, this is a failure
        if files_fetched == 0 and len(likely_files) > 0:
            logger.error(f"❌ Failed to fetch any source files for enhanced developer on ticket {ticket.id}")
            return {"github_access_failed": True}
        
        logger.info(f"✅ Enhanced developer context ready: {len(context['source_files'])} source files prepared")
        return context

    async def _prepare_enhanced_qa_context(self, ticket: Ticket, developer_result: Dict) -> Dict[str, Any]:
        """Prepare enhanced context for QA agent with intelligent patch testing"""
        logger.info(f"🔍 Preparing enhanced QA context for ticket {ticket.id}")
        
        context = {
            "patches": developer_result.get("patches", []),
            "planner_analysis": developer_result.get("planner_analysis", {}),
            "ticket": ticket,
            "intelligent_patching": developer_result.get("intelligent_patching", False)
        }
        
        logger.info(f"✅ Enhanced QA context ready: {len(context['patches'])} patches to test intelligently")
        return context

    async def _prepare_enhanced_communicator_context(self, ticket: Ticket, qa_result: Dict) -> Dict[str, Any]:
        """Prepare enhanced context for communicator agent"""
        logger.info(f"🔍 Preparing enhanced communicator context for ticket {ticket.id}")
        
        context = {
            "qa_results": qa_result,
            "ticket": ticket,
            "patches": qa_result.get("validated_patches", []),
            "test_branch": qa_result.get("test_branch"),
            "intelligent_application": True
        }
        
        logger.info(f"✅ Enhanced communicator context ready")
        return context

    def _calculate_file_hash(self, content: str) -> str:
        """Calculate SHA256 hash of file content for tracking"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()

    # ... keep existing code (mark_ticket_for_review, validate_planner_results methods)

    def _validate_enhanced_developer_results(self, result: Dict) -> bool:
        """Validate that enhanced developer agent generated intelligent patches"""
        logger.info(f"🔍 Validating enhanced developer results...")
        
        if not result:
            logger.warning("❌ Enhanced developer validation failed: No result returned")
            return False
        
        patches = result.get("patches", [])
        if not patches or len(patches) == 0:
            logger.warning("❌ Enhanced developer validation failed: No patches generated")
            return False
        
        # Check that patches have enhanced content with file tracking
        for i, patch in enumerate(patches):
            if not isinstance(patch, dict):
                logger.warning(f"❌ Enhanced developer validation failed: Invalid patch at index {i}")
                return False
            required_fields = ["patch_content", "patched_code", "target_file", "base_file_hash"]
            for field in required_fields:
                if field not in patch or not patch[field]:
                    logger.warning(f"❌ Enhanced developer validation failed: Missing/empty field '{field}' in patch {i}")
                    return False
        
        # Check for intelligent patching flag
        if not result.get("intelligent_patching"):
            logger.warning("❌ Enhanced developer validation failed: Not using intelligent patching")
            return False
        
        logger.info(f"✅ Enhanced developer validation passed: {len(patches)} intelligent patches generated")
        return True

    # ... keep existing code (retry_failed_ticket, _update_jira_status, get_agent_status methods)

    async def stop_processing(self):
        """Stop processing tickets"""
        self.running = False
        logger.info("Enhanced agent orchestrator stopped")

    async def _intake_polling_loop(self):
        """Background loop for intake polling"""
        while self.running:
            try:
                await self.agents[AgentType.INTAKE].poll_and_create_tickets()
                await asyncio.sleep(self.intake_interval)
            except Exception as e:
                logger.error(f"Error in intake polling: {e}")
                await asyncio.sleep(10)

    async def process_pending_tickets(self):
        """Process tickets that are ready for agent processing"""
        with next(get_sync_db()) as db:
            # Get tickets in TODO or IN_PROGRESS status (to resume interrupted tickets)
            pending_tickets = db.query(Ticket).filter(
                Ticket.status.in_([TicketStatus.TODO, TicketStatus.IN_PROGRESS])
            ).limit(3).all()
            
            # Get ticket IDs to avoid session conflicts
            ticket_ids = [ticket.id for ticket in pending_tickets]
            
        if ticket_ids:
            logger.info(f"🎯 Found {len(ticket_ids)} pending tickets to process: {ticket_ids}")
        
        # Process each ticket using its ID
        for ticket_id in ticket_ids:
            try:
                await self.process_ticket_pipeline(ticket_id)
            except Exception as e:
                logger.error(f"💥 Error processing ticket {ticket_id}: {e}")

    async def _mark_ticket_for_review(self, ticket_id: int, jira_id: str, reason: str):
        """Mark ticket as needing human review and update Jira"""
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = TicketStatus.IN_REVIEW
                db.add(ticket)
                db.commit()
        
        # Update Jira status to "Needs Review"
        await self._update_jira_status(jira_id, "Needs Review", 
                                     f"Enhanced AI Agent requires human intervention. {reason}")
        
        logger.warning(f"🔍 Ticket {ticket_id} marked for human review: {reason}")

    def _validate_planner_results(self, result: Dict) -> bool:
        """Validate that planner agent produced meaningful results"""
        logger.info(f"🔍 Validating planner results...")
        
        if not result:
            logger.warning("❌ Planner validation failed: No result returned")
            return False
        
        # Check for required fields
        required_fields = ["root_cause", "likely_files"]
        for field in required_fields:
            if field not in result:
                logger.warning(f"❌ Planner validation failed: Missing field '{field}'")
                return False
        
        # Check that we have at least one likely file
        likely_files = result.get("likely_files", [])
        if not likely_files or len(likely_files) == 0:
            logger.warning("❌ Planner validation failed: No likely files identified")
            return False
        
        # Check that files have required structure
        for i, file_info in enumerate(likely_files):
            if not isinstance(file_info, dict) or "path" not in file_info:
                logger.warning(f"❌ Planner validation failed: Invalid file info at index {i}")
                return False
        
        logger.info(f"✅ Planner validation passed: {len(likely_files)} files identified")
        return True

    async def retry_failed_ticket(self, ticket_id: int):
        """Retry processing a failed ticket"""
        logger.info(f"🔄 Retrying failed ticket {ticket_id}")
        
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket and ticket.status == TicketStatus.FAILED:
                ticket.status = TicketStatus.TODO
                ticket.retry_count = 0
                db.add(ticket)
                db.commit()
                logger.info(f"✅ Ticket {ticket_id} reset for retry")
            else:
                logger.warning(f"⚠️ Cannot retry ticket {ticket_id} - not in FAILED status")

    async def _update_jira_status(self, jira_id: str, status: str, comment: str):
        """Update JIRA ticket status and add comment"""
        try:
            if jira_id:
                # Update ticket status with comment using the correct method
                await self.jira_client.update_ticket_status(jira_id, status, comment)
                logger.info(f"✅ Updated JIRA {jira_id} status to {status}")
        except Exception as e:
            logger.error(f"❌ Failed to update JIRA {jira_id}: {e}")

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current status of all agents"""
        return {
            "orchestrator_running": self.running,
            "process_interval": self.process_interval,
            "intake_interval": self.intake_interval,
            "agents": {
                agent_type.value: {
                    "type": agent_type.value,
                    "available": True
                } for agent_type in AgentType
            },
            "github_configured": self.github_client._is_configured(),
            "jira_configured": bool(config.jira_base_url and config.jira_api_token),
            "intelligent_patching": True,
            "patch_service_available": True
        }
