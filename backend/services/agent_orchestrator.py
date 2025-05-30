
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
        
        # Log GitHub configuration status
        github_status = self.github_client.get_configuration_status()
        logger.info(f"GitHub configuration status: {github_status}")
        
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
        """Stop processing tickets"""
        self.running = False
        logger.info("Agent orchestrator stopped")

    async def _intake_polling_loop(self):
        """Background loop for intake polling"""
        while self.running:
            try:
                # Fix: Use the correct method name from IntakeAgent
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
            logger.info(f"Found {len(ticket_ids)} pending tickets to process: {ticket_ids}")
        
        # Process each ticket using its ID
        for ticket_id in ticket_ids:
            try:
                await self.process_ticket_pipeline(ticket_id)
            except Exception as e:
                logger.error(f"Error processing ticket {ticket_id}: {e}")

    async def process_ticket_pipeline(self, ticket_id: int):
        """Process a single ticket through the complete agent pipeline with proper validation"""
        logger.info(f"🎯 Starting pipeline for ticket {ticket_id}")
        
        # Update ticket status to in progress and update Jira
        jira_id = None
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return
                
            logger.info(f"📋 Ticket {ticket_id}: {ticket.title} (Status: {ticket.status})")
            
            # Only update to IN_PROGRESS if it's currently TODO
            if ticket.status == TicketStatus.TODO:
                ticket.status = TicketStatus.IN_PROGRESS
                jira_id = ticket.jira_id
                db.add(ticket)
                db.commit()
                
                logger.info(f"✅ Ticket {ticket_id} status updated to IN_PROGRESS")
                
                # Update Jira status to "In Progress"
                await self._update_jira_status(jira_id, "In Progress", 
                                             f"AI Agent system has started processing this ticket.")
            else:
                jira_id = ticket.jira_id
        
        try:
            # Get fresh ticket object for processing
            with next(get_sync_db()) as db:
                ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket:
                    logger.error(f"Ticket {ticket_id} not found during processing")
                    return
                
                # Step 1: Planner agent analyzes the ticket with repository context
                logger.info(f"🧠 STEP 1: Running planner agent for ticket {ticket_id}")
                planner_context = await self._prepare_planner_context(ticket)
                logger.info(f"📊 Planner context prepared: {len(planner_context.get('error_trace_files', []))} error trace files")
                
                planner_result = await self.agents[AgentType.PLANNER].execute_with_retry(ticket, planner_context)
                logger.info(f"✅ PLANNER COMPLETED for ticket {ticket_id}")
                logger.info(f"📋 Planner result keys: {list(planner_result.keys())}")
                
                # Validate planner results
                if not self._validate_planner_results(planner_result):
                    logger.warning(f"⚠️ Planner validation failed for ticket {ticket_id}")
                    logger.info(f"❌ Planner result validation details: {planner_result}")
                    raise Exception("Planner agent failed to identify target files or root cause")
                
                logger.info(f"✅ Planner validation passed for ticket {ticket_id}")
                
                # Step 2: Developer agent generates patches with code context
                logger.info(f"👨‍💻 STEP 2: Running developer agent for ticket {ticket_id}")
                developer_context = await self._prepare_developer_context(ticket, planner_result)
                logger.info(f"📊 Developer context prepared: {len(developer_context.get('source_files', []))} source files")
                
                developer_result = await self.agents[AgentType.DEVELOPER].execute_with_retry(ticket, developer_context)
                logger.info(f"✅ DEVELOPER COMPLETED for ticket {ticket_id}")
                logger.info(f"📋 Developer result keys: {list(developer_result.keys())}")
                
                # Validate developer results
                if not self._validate_developer_results(developer_result):
                    logger.warning(f"⚠️ Developer validation failed for ticket {ticket_id}")
                    logger.info(f"❌ Developer result validation details: {developer_result}")
                    raise Exception("Developer agent failed to generate valid patches")
                
                logger.info(f"✅ Developer validation passed for ticket {ticket_id}")
                
                # Step 3: QA agent tests patches in proper environment
                logger.info(f"🧪 STEP 3: Running QA agent for ticket {ticket_id}")
                qa_context = await self._prepare_qa_context(ticket, developer_result)
                logger.info(f"📊 QA context prepared: {len(qa_context.get('patches', []))} patches to test")
                
                qa_result = await self.agents[AgentType.QA].execute_with_retry(ticket, qa_context)
                logger.info(f"✅ QA COMPLETED for ticket {ticket_id}")
                logger.info(f"📋 QA result: ready_for_deployment={qa_result.get('ready_for_deployment')}, successful_patches={qa_result.get('successful_patches', 0)}")
            
            # Step 4: If QA passes, communicator creates PR and mark as COMPLETED
            if qa_result.get("ready_for_deployment") and qa_result.get("successful_patches", 0) > 0:
                logger.info(f"📢 STEP 4: Running communicator agent for ticket {ticket_id}")
                
                # Get fresh ticket object for communicator
                with next(get_sync_db()) as db:
                    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        comm_context = await self._prepare_communicator_context(ticket, qa_result)
                        comm_result = await self.agents[AgentType.COMMUNICATOR].execute_with_retry(ticket, comm_context)
                        logger.info(f"✅ COMMUNICATOR COMPLETED for ticket {ticket_id}")
                
                # Update ticket status to COMPLETED (successful completion)
                with next(get_sync_db()) as db:
                    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        ticket.status = TicketStatus.COMPLETED
                        db.add(ticket)
                        db.commit()
                
                # Update Jira status to "Done" for successful completion
                await self._update_jira_status(jira_id, "Done", 
                                             f"AI Agent has successfully completed processing and created a pull request. The fix is ready for deployment.")
                    
                logger.info(f"🎉 PIPELINE SUCCESS: Ticket {ticket_id} completed successfully - PR created and ticket marked as COMPLETED")
            else:
                # QA failed or no successful patches, mark as IN_REVIEW for human intervention
                logger.warning(f"⚠️ QA validation failed for ticket {ticket_id} - marking for human review")
                
                with next(get_sync_db()) as db:
                    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        ticket.status = TicketStatus.IN_REVIEW
                        db.add(ticket)
                        db.commit()
                
                # Update Jira status to "Needs Review" for human intervention
                qa_message = "QA testing failed - no patches passed validation." if qa_result.get("successful_patches", 0) == 0 else "QA testing completed but patches were not ready for deployment."
                await self._update_jira_status(jira_id, "Needs Review", 
                                             f"AI Agent processed this ticket but requires human review. {qa_message}")
                
                logger.warning(f"🔍 PIPELINE REVIEW NEEDED: Ticket {ticket_id} - {qa_message} - marked as IN_REVIEW")
            
        except Exception as e:
            logger.error(f"💥 PIPELINE ERROR for ticket {ticket_id}: {e}")
            
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
                        # Update ticket to IN_REVIEW and Jira status to "Needs Review" after max retries
                        ticket.status = TicketStatus.IN_REVIEW
                        db.add(ticket)
                        db.commit()
                        
                        await self._update_jira_status(jira_id, "Needs Review", 
                                                     f"AI Agent failed to process this ticket after {config.agent_max_retries} attempts. Human intervention required. Error: {str(e)}")
                        logger.error(f"🚫 PIPELINE FAILED: Ticket {ticket_id} failed after {config.agent_max_retries} retries - marked as IN_REVIEW: {e}")
                    else:
                        # Will retry, keep ticket status as failed for now
                        logger.warning(f"🔄 PIPELINE RETRY: Ticket {ticket_id} failed (attempt {current_retry_count}): {e}")
            
            raise e

    async def _prepare_planner_context(self, ticket: Ticket) -> Dict[str, Any]:
        """Prepare context for planner agent including repository information with fallback"""
        logger.info(f"🔍 Preparing planner context for ticket {ticket.id}")
        
        context = {
            "ticket": ticket,
            "repository_files": [],
            "error_trace_files": []
        }
        
        # Extract file paths from error trace
        if ticket.error_trace:
            file_matches = re.findall(r'File "([^"]+)"', ticket.error_trace)
            logger.info(f"📁 Found {len(file_matches)} files in error trace: {file_matches}")
            
            for file_path in file_matches:
                try:
                    file_content = await self.github_client.get_file_content(file_path)
                    if file_content:
                        context["error_trace_files"].append({
                            "path": file_path,
                            "content": file_content
                        })
                        logger.info(f"✅ Successfully fetched error trace file: {file_path}")
                    else:
                        # Add fallback synthetic context for missing files
                        context["error_trace_files"].append({
                            "path": file_path,
                            "content": self._generate_mock_file_content(file_path, ticket),
                            "is_mock": True
                        })
                        logger.info(f"🔄 Added mock content for missing file: {file_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch file {file_path}: {e}")
                    # Add fallback context even for failed fetches
                    context["error_trace_files"].append({
                        "path": file_path,
                        "content": self._generate_mock_file_content(file_path, ticket),
                        "is_mock": True
                    })
        else:
            logger.warning(f"⚠️ No error trace found for ticket {ticket.id}")
        
        logger.info(f"✅ Planner context ready: {len(context['error_trace_files'])} files prepared")
        return context

    # ... keep existing code (_prepare_developer_context, _generate_mock_file_content, _guess_main_file_from_ticket, _prepare_qa_context, _prepare_communicator_context methods)

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

    def _validate_developer_results(self, result: Dict) -> bool:
        """Validate that developer agent generated actual patches"""
        logger.info(f"🔍 Validating developer results...")
        
        if not result:
            logger.warning("❌ Developer validation failed: No result returned")
            return False
        
        patches = result.get("patches", [])
        if not patches or len(patches) == 0:
            logger.warning("❌ Developer validation failed: No patches generated")
            return False
        
        # Check that patches have required content
        for i, patch in enumerate(patches):
            if not isinstance(patch, dict):
                logger.warning(f"❌ Developer validation failed: Invalid patch at index {i}")
                return False
            required_fields = ["patch_content", "patched_code", "target_file"]
            for field in required_fields:
                if field not in patch or not patch[field]:
                    logger.warning(f"❌ Developer validation failed: Missing/empty field '{field}' in patch {i}")
                    return False
        
        logger.info(f"✅ Developer validation passed: {len(patches)} patches generated")
        return True

    # ... keep existing code (remaining methods like retry_failed_ticket, _update_jira_status, get_agent_status)
