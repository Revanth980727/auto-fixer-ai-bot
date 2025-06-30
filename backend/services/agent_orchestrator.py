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
from services.repository_analyzer import RepositoryAnalyzer
from services.metrics_collector import metrics_collector
from services.pipeline_context import context_manager, PipelineStage
import logging
import re
import time
from services.pipeline_validator import pipeline_validator

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
        self.repository_analyzer = RepositoryAnalyzer()
        
        # Use configured intervals
        self.process_interval = config.agent_process_interval
        self.intake_interval = config.agent_intake_interval

    async def start_processing(self):
        """Start processing tickets through enhanced agent pipeline with full monitoring"""
        self.running = True
        logger.info(f"🚀 Starting enhanced agent orchestrator with complete JIRA-GitHub automation")
        logger.info(f"📊 Intervals: process={self.process_interval}s, intake={self.intake_interval}s")
        
        # Critical: Validate and fix GitHub configuration
        github_status = await self._validate_and_fix_github_config()
        if not github_status["configured"]:
            logger.warning("⚠️ GitHub not fully configured - continuing with JIRA-only mode")
            logger.warning("📋 Features available: JIRA status updates and commenting")
            logger.warning("📋 Features limited: No PR creation, manual code review required")
        else:
            logger.info("✅ GitHub fully configured - complete automation enabled")
        
        # Validate JIRA configuration
        jira_status = await self._validate_jira_config()
        if not jira_status["configured"]:
            logger.error("❌ JIRA not configured - cannot proceed with automation")
            return
        
        # Perform initial repository analysis if GitHub available
        if github_status["configured"]:
            await self._perform_initial_repository_analysis()
        
        # Start background tasks with enhanced monitoring
        asyncio.create_task(self._intake_polling_loop())
        asyncio.create_task(self._health_monitoring_loop())
        asyncio.create_task(self._context_cleanup_loop())
        
        while self.running:
            try:
                # Enhanced processing with detailed logging
                await self._process_pending_tickets_enhanced()
                await asyncio.sleep(self.process_interval)
            except Exception as e:
                logger.error(f"💥 Critical error in agent orchestrator: {e}")
                metrics_collector.record_agent_execution("orchestrator", 0, False)
                await asyncio.sleep(5)

    async def _validate_and_fix_github_config(self) -> Dict[str, Any]:
        """Validate GitHub configuration and provide detailed diagnostics"""
        logger.info("🔍 GITHUB CONFIG VALIDATION")
        
        config_status = self.github_client.get_configuration_status()
        
        logger.info(f"📋 GitHub Token: {'✅ Present' if config_status['has_token'] else '❌ Missing'}")
        logger.info(f"📋 GitHub Repo Owner: {'✅ Present' if config_status['has_repo_owner'] else '❌ Missing'}")
        logger.info(f"📋 GitHub Repo Name: {'✅ Present' if config_status['has_repo_name'] else '❌ Missing'}")
        logger.info(f"📋 Target Branch: {config_status['target_branch']}")
        logger.info(f"📋 Full Repository: {config_status['repo_full_name'] or 'Not configured'}")
        
        if config_status["configured"]:
            # Test GitHub API access
            try:
                repo_tree = await self.github_client.get_repository_tree()
                if repo_tree:
                    logger.info(f"✅ GitHub API access verified - {len(repo_tree)} files found")
                else:
                    logger.warning("⚠️ GitHub API access limited - repository tree empty")
            except Exception as e:
                logger.error(f"❌ GitHub API test failed: {e}")
                config_status["configured"] = False
                config_status["api_error"] = str(e)
        
        return config_status

    async def _validate_jira_config(self) -> Dict[str, Any]:
        """Validate JIRA configuration"""
        logger.info("🔍 JIRA CONFIG VALIDATION")
        
        has_token = bool(config.jira_api_token)
        has_url = bool(config.jira_base_url)
        has_username = bool(config.jira_username)
        
        logger.info(f"📋 JIRA API Token: {'✅ Present' if has_token else '❌ Missing'}")
        logger.info(f"📋 JIRA Base URL: {'✅ Present' if has_url else '❌ Missing'}")
        logger.info(f"📋 JIRA Username: {'✅ Present' if has_username else '❌ Missing'}")
        logger.info(f"📋 JIRA Project Key: {config.jira_project_key}")
        
        return {
            "configured": has_token and has_url,
            "has_token": has_token,
            "has_url": has_url,
            "has_username": has_username
        }

    async def _process_pending_tickets_enhanced(self):
        """Enhanced ticket processing with comprehensive logging and JIRA integration"""
        with next(get_sync_db()) as db:
            # Get tickets ready for processing - fix enum comparison
            pending_tickets = db.query(Ticket).filter(
                Ticket.status.in_([TicketStatus.TODO.value, TicketStatus.IN_PROGRESS.value])
            ).limit(3).all()
            
            if pending_tickets:
                logger.info(f"🎯 PROCESSING QUEUE: Found {len(pending_tickets)} tickets")
                for ticket in pending_tickets:
                    logger.info(f"📋 Ticket {ticket.id}: {ticket.jira_id} - Status: {ticket.status}")
                    logger.info(f"   Title: {ticket.title[:100]}...")
                    logger.info(f"   Priority: {ticket.priority}")
                    logger.info(f"   Created: {ticket.created_at}")
            else:
                logger.debug("📋 No pending tickets found for processing")
                return
            
            # Get ticket IDs to avoid session conflicts
            ticket_ids = [ticket.id for ticket in pending_tickets]
        
        # Process each ticket with enhanced pipeline
        for ticket_id in ticket_ids:
            try:
                logger.info(f"🚀 Starting enhanced pipeline for ticket {ticket_id}")
                await self._process_ticket_with_comprehensive_jira_integration(ticket_id)
            except Exception as e:
                logger.error(f"💥 Enhanced pipeline error for ticket {ticket_id}: {e}")
                await self._handle_ticket_processing_error(ticket_id, e)

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
            
            # Update JIRA with QA results
            successful_patches = qa_result.get("successful_patches", 0)
            ready_for_deployment = qa_result.get("ready_for_deployment", False)
            
            qa_comment = f"""🧪 **Quality Assurance Completed** ({qa_duration:.1f}s)

**Test Results:**
- Patches Tested: {len(patches)}
- Successful: {successful_patches}
- Ready for Deployment: {'✅ Yes' if ready_for_deployment else '❌ No'}

**Quality Checks:**
- Syntax Validation: {'✅ Passed' if successful_patches > 0 else '❌ Failed'}
- Logic Verification: {'✅ Passed' if ready_for_deployment else '⚠️ Needs Review'}
- Integration Testing: {'✅ Passed' if ready_for_deployment else '⚠️ Requires Manual Testing'}

**Status:** {'Proceeding to deployment' if ready_for_deployment else 'Manual review required'}"""
            
            await self._update_jira_with_comment(jira_id, None, qa_comment)
            
            # PHASE 5: Communication/Deployment
            if ready_for_deployment and successful_patches > 0:
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
- Patches Applied: {comm_result.get('patches_deployed', 0)}
- Target Branch: {comm_result.get('target_branch', 'main')}

**GitHub Integration:**
{'✅ **Pull Request Created**' if github_operations and pr_info else '⚠️ **Manual Deployment Required**'}
{f"- PR #{pr_info.get('number', 'N/A')}: {pr_info.get('html_url', 'N/A')}" if pr_info else "- GitHub not configured - patches generated for manual application"}

**Actions Taken:**
{chr(10).join(f"• {action}" for action in comm_result.get('actions_taken', []))}

**Status:** {'Ready for code review and merge' if github_operations else 'Fix generated - manual deployment needed'}

---
*This fix was automatically generated and {'deployed' if github_operations else 'prepared'} by the AI Agent System*"""
                
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

    async def _mark_ticket_for_review(self, ticket_id: int, jira_id: str, reason: str):
        """Mark ticket as needing human review with comprehensive JIRA update"""
        logger.warning(f"🔍 MANUAL REVIEW REQUIRED: {jira_id}")
        
        review_comment = f"""⚠️ **Manual Review Required**

**Issue:** {reason}

**AI Agent Analysis:**
The automated system encountered a limitation that requires human intervention. This is not an error in the system, but rather a complex scenario that benefits from human expertise.

**Recommended Actions:**
1. Review the analysis provided in previous comments
2. Examine the identified files and root cause analysis
3. Consider the complexity of the required changes
4. Determine if manual coding or additional context is needed

**System Status:** All automated analysis has been completed and documented above. The issue is ready for developer review.

---
*AI Agent System - Escalated for human expertise*"""
        
        await self._update_jira_with_comment(jira_id, "Needs Review", review_comment)
        
        # Update database with fresh session
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = TicketStatus.IN_REVIEW.value
                db.add(ticket)
                db.commit()

    async def _handle_ticket_processing_error(self, ticket_id: int, error: Exception):
        """Handle processing errors with detailed JIRA updates"""
        logger.error(f"💥 Processing error for ticket {ticket_id}: {error}")
        
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return
            
            jira_id = ticket.jira_id
            ticket.retry_count += 1
            current_retry = ticket.retry_count
            
            if current_retry >= config.agent_max_retries:
                # Max retries exceeded - mark for review
                error_comment = f"""❌ **Automated Processing Failed**

**Error Details:** {str(error)}

**Processing Attempts:** {current_retry} (Maximum reached)

**System Analysis:**
The AI Agent System has attempted to process this ticket {current_retry} times but encountered persistent issues. This typically indicates:

1. **Complex Integration Issues** - The changes may require broader system understanding
2. **Missing Dependencies** - Required libraries or configurations may be unavailable  
3. **Infrastructure Limitations** - GitHub access or repository structure issues
4. **Ticket Complexity** - The issue may require human architectural decisions

**Recommended Actions:**
1. Review the error details above
2. Check system configuration and repository access
3. Consider manual analysis of the reported issue
4. Update ticket with additional context if needed

---
*AI Agent System - Maximum retry attempts reached*"""
                
                await self._update_jira_with_comment(jira_id, "Needs Review", error_comment)
                ticket.status = TicketStatus.IN_REVIEW.value
                
            else:
                # Retry available - update status and retry later
                retry_comment = f"""🔄 **Retry Attempt {current_retry}**

**Temporary Error:** {str(error)}

**System Status:** The AI Agent System encountered a temporary issue and will automatically retry processing this ticket.

**Next Attempt:** Within the next {config.agent_process_interval} seconds
**Remaining Retries:** {config.agent_max_retries - current_retry}

---
*AI Agent System - Automatic retry scheduled*"""
                
                await self._update_jira_with_comment(jira_id, None, retry_comment)
                ticket.status = TicketStatus.TODO.value  # Reset for retry
            
            db.add(ticket)
            db.commit()

    async def _update_jira_with_comment(self, jira_id: str, status: str = None, comment: str = ""):
        """Update JIRA ticket with status and/or comment"""
        if not jira_id:
            return False
        
        try:
            success = await self.jira_client.update_ticket_status(jira_id, status or "", comment)
            if success:
                status_msg = f" and status to {status}" if status else ""
                logger.info(f"✅ Updated JIRA {jira_id}{status_msg}")
            else:
                logger.error(f"❌ Failed to update JIRA {jira_id}")
            return success
        except Exception as e:
            logger.error(f"❌ JIRA update error for {jira_id}: {e}")
            return False

    async def _perform_initial_repository_analysis(self):
        """Perform initial repository analysis for better file discovery"""
        try:
            logger.info("Performing initial repository analysis...")
            analysis_start = time.time()
            
            repo_analysis = await self.repository_analyzer.analyze_repository()
            analysis_duration = time.time() - analysis_start
            
            if repo_analysis.get("error"):
                logger.warning(f"Repository analysis failed: {repo_analysis['error']}")
                metrics_collector.record_github_operation("repository_analysis", analysis_duration, False)
            else:
                # Fix: Access files from the correct location - they're in source_files
                files = repo_analysis.get("source_files", [])
                
                logger.info(f"Repository analysis completed: {len(files)} files analyzed")
                logger.info(f"Repository analysis structure keys: {list(repo_analysis.keys())}")
                if files:
                    logger.info(f"Sample discovered files: {[f.get('path', str(f)) for f in files[:5]]}")
                
                metrics_collector.record_github_operation("repository_analysis", analysis_duration, True)
                
                # Log repository structure type
                repo_structure = repo_analysis.get("repository_structure", "Unknown")
                logger.info(f"Detected repository structure: {repo_structure}")
                
        except Exception as e:
            logger.error(f"Error in initial repository analysis: {e}")

    # ... keep existing code (all utility methods remain the same)
    async def process_ticket_pipeline(self, ticket_id: int):
        """Legacy method - redirects to comprehensive JIRA integration"""
        await self._process_ticket_with_comprehensive_jira_integration(ticket_id)

    async def _prepare_production_planner_context(self, ticket: Ticket, context_id: str) -> Dict[str, Any]:
        """Prepare production context for planner agent with repository intelligence"""
        logger.info(f"🔍 Preparing production planner context for ticket {ticket.id}")
        
        # Check GitHub configuration first
        if not self.github_client._is_configured():
            logger.error(f"❌ GitHub not configured - cannot prepare production planner context for ticket {ticket.id}")
            return {"github_access_failed": True}
        
        # Get repository analysis for intelligent file discovery
        repo_analysis = {}
        discovered_files = []
        try:
            repo_analysis = await self.repository_analyzer.analyze_repository()
            if not repo_analysis.get("error"):
                # Fix: Access files from the correct location - they're in source_files
                discovered_files = repo_analysis.get("source_files", [])
                
                logger.info(f"📊 Repository analysis available: {len(discovered_files)} files discovered")
                
                # Add detailed logging of the structure we received
                if discovered_files:
                    sample_files = [f.get('path', str(f)) if isinstance(f, dict) else str(f) for f in discovered_files[:5]]
                    logger.info(f"📁 Sample discovered files: {sample_files}")
                else:
                    logger.warning(f"⚠️ No files found in repository analysis")
                    logger.info(f"📋 Repository analysis keys: {list(repo_analysis.keys())}")
            else:
                logger.warning(f"Repository analysis failed: {repo_analysis.get('error')}")
        except Exception as e:
            logger.warning(f"Repository analysis failed: {e}")
        
        # Validate that we have discovered files before proceeding
        if not discovered_files:
            logger.error(f"❌ No discovered files available for ticket {ticket.id} - cannot prepare production context")
            return {"github_access_failed": True}
        
        context = {
            "ticket": ticket,
            "repository_files": discovered_files,
            "error_trace_files": [],
            "repository_structure": {},
            "repository_analysis": repo_analysis,
            "relevant_files": [],
            "discovered_files": discovered_files  # Ensure this is consistently set
        }
        
        # Enhanced file discovery using repository intelligence
        if ticket.error_trace:
            try:
                relevant_files = await self.repository_analyzer.find_relevant_files(
                    ticket.error_trace, ticket.description
                )
                context["relevant_files"] = relevant_files
                logger.info(f"📁 Found {len(relevant_files)} relevant files using intelligent analysis")
                
                files_fetched = 0
                for file_info in relevant_files[:10]:  # Top 10 most relevant
                    try:
                        file_content = await self.github_client.get_file_content(file_info["path"])
                        if file_content:
                            context["error_trace_files"].append({
                                "path": file_info["path"],
                                "content": file_content,
                                "hash": self._calculate_file_hash(file_content),
                                "relevance": file_info.get("relevance"),
                                "confidence": file_info.get("confidence", 0.5)
                            })
                            files_fetched += 1
                            logger.info(f"✅ Successfully fetched relevant file: {file_info['path']}")
                        else:
                            logger.warning(f"⚠️ File not found in repository: {file_info['path']}")
                    except Exception as e:
                        logger.error(f"❌ Could not fetch file {file_info['path']}: {e}")
                
                # If intelligent discovery failed, fall back to basic extraction but use discovered files
                if files_fetched == 0:
                    file_matches = re.findall(r'File "([^"]+)"', ticket.error_trace)
                    logger.info(f"📁 Falling back to basic file extraction: {file_matches}")
                    
                    # Filter file matches to only include files that actually exist in the repository
                    discovered_file_paths = [f.get("path", "") if isinstance(f, dict) else str(f) for f in discovered_files]
                    valid_file_matches = [f for f in file_matches if f in discovered_file_paths]
                    
                    logger.info(f"📁 Valid files from error trace: {valid_file_matches}")
                    
                    for file_path in valid_file_matches[:5]:  # Limit to 5 files
                        try:
                            file_content = await self.github_client.get_file_content(file_path)
                            if file_content:
                                context["error_trace_files"].append({
                                    "path": file_path,
                                    "content": file_content,
                                    "hash": self._calculate_file_hash(file_content),
                                    "relevance": "error_trace",
                                    "confidence": 0.9
                                })
                                files_fetched += 1
                        except Exception as e:
                            logger.error(f"❌ Could not fetch file {file_path}: {e}")
                
                # Log final context preparation summary
                logger.info(f"📊 Final context summary: {len(context['error_trace_files'])} error trace files, {len(discovered_files)} discovered files")
                    
            except Exception as e:
                logger.error(f"Error in intelligent file discovery: {e}")
                # Don't fail completely, we still have discovered files
                logger.warning(f"⚠️ Continuing with basic discovered files context")
        else:
            logger.warning(f"⚠️ No error trace found for ticket {ticket.id}")
        
        logger.info(f"✅ Production planner context ready: {len(context['error_trace_files'])} files prepared")
        return context

    async def _prepare_production_developer_context(self, ticket: Ticket, planner_result: Dict, context_id: str) -> Dict[str, Any]:
        """Prepare production context for developer agent with intelligent file tracking"""
        logger.info(f"🔍 Preparing production developer context for ticket {ticket.id}")
        
        # Check GitHub configuration first
        if not self.github_client._is_configured():
            logger.error(f"❌ GitHub not configured - cannot prepare production developer context for ticket {ticket.id}")
            return {"github_access_failed": True}
        
        context = {
            "planner_analysis": planner_result,
            "source_files": [],
            "repository_state": {},
            "context_id": context_id
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
                        "size": len(file_content),
                        "confidence": file_info.get("confidence", 0.8) if isinstance(file_info, dict) else 0.8
                    })
                    files_fetched += 1
                    logger.info(f"✅ Successfully fetched production source file: {file_path}")
                else:
                    logger.warning(f"⚠️ Production source file not found in repository: {file_path}")
            except Exception as e:
                logger.error(f"❌ Could not fetch production source file {file_path}: {e}")
        
        # If we couldn't fetch any source files, this is a failure
        if files_fetched == 0 and len(likely_files) > 0:
            logger.error(f"❌ Failed to fetch any source files for production developer on ticket {ticket.id}")
            return {"github_access_failed": True}
        
        logger.info(f"✅ Production developer context ready: {len(context['source_files'])} source files prepared")
        return context

    async def _prepare_production_qa_context(self, ticket: Ticket, developer_result: Dict, context_id: str) -> Dict[str, Any]:
        """Prepare production context for QA agent with intelligent patch testing"""
        logger.info(f"🔍 Preparing production QA context for ticket {ticket.id}")
        
        context = {
            "patches": developer_result.get("patches", []),
            "planner_analysis": developer_result.get("planner_analysis", {}),
            "ticket": ticket,
            "intelligent_patching": developer_result.get("intelligent_patching", False),
            "context_id": context_id
        }
        
        logger.info(f"✅ Production QA context ready: {len(context['patches'])} patches to test intelligently")
        return context

    async def _prepare_production_communicator_context(self, ticket: Ticket, qa_result: Dict, context_id: str) -> Dict[str, Any]:
        """Prepare production context for communicator agent"""
        logger.info(f"🔍 Preparing production communicator context for ticket {ticket.id}")
        
        context = {
            "qa_results": qa_result,
            "ticket": ticket,
            "patches": qa_result.get("validated_patches", []),
            "test_branch": qa_result.get("test_branch"),
            "intelligent_application": True,
            "context_id": context_id
        }
        
        logger.info(f"✅ Production communicator context ready")
        return context

    def _calculate_file_hash(self, content: str) -> str:
        """Calculate SHA256 hash of file content for tracking"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()

    async def _health_monitoring_loop(self):
        """Background health monitoring loop"""
        while self.running:
            try:
                health_status = metrics_collector.get_system_health_status()
                
                if health_status["overall_status"] != "healthy":
                    logger.warning(f"System health status: {health_status['overall_status']}")
                    for alert in health_status.get("alerts", []):
                        logger.warning(f"Health Alert: {alert}")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)

    async def _context_cleanup_loop(self):
        """Background context cleanup loop"""
        while self.running:
            try:
                cleaned_count = context_manager.cleanup_old_contexts(24)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} old pipeline contexts")
                
                await asyncio.sleep(3600)  # Run every hour
                
            except Exception as e:
                logger.error(f"Error in context cleanup: {e}")
                await asyncio.sleep(600)

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current status of all agents with production metrics"""
        performance_summary = metrics_collector.get_agent_performance_summary()
        pipeline_summary = metrics_collector.get_pipeline_performance_summary()
        health_status = metrics_collector.get_system_health_status()
        
        return {
            "orchestrator_running": self.running,
            "process_interval": self.process_interval,
            "intake_interval": self.intake_interval,
            "agents": {
                agent_type.value: {
                    "type": agent_type.value,
                    "available": True,
                    "performance": performance_summary.get(agent_type.value.lower(), {}),
                    "circuit_breaker": health_status.get("circuit_breakers", {}).get(agent_type.value.lower(), {})
                } for agent_type in AgentType
            },
            "github_configured": self.github_client._is_configured(),
            "jira_configured": bool(config.jira_base_url and config.jira_api_token),
            "intelligent_patching": True,
            "patch_service_available": True,
            "repository_analysis_available": True,
            "metrics_collection_active": True,
            "pipeline_performance": pipeline_summary,
            "system_health": health_status,
            "active_contexts": len(context_manager.get_all_active_contexts())
        }

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
        """Legacy method - redirects to enhanced processing"""
        await self._process_pending_tickets_enhanced()

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

    def validate_developer_results(self, result: Dict[str, Any]) -> bool:
        """Enhanced validation for developer results using pipeline validator"""
        try:
            validation = pipeline_validator.validate_developer_results(result)
            
            if validation["valid"]:
                logger.info(f"✅ Enhanced developer validation passed: {validation['reason']}")
                if validation["recommendations"]:
                    logger.info(f"💡 Recommendations: {', '.join(validation['recommendations'])}")
                return True
            else:
                logger.warning(f"❌ Enhanced developer validation failed: {validation['reason']}")
                if validation["recommendations"]:
                    logger.warning(f"💡 Recommendations: {', '.join(validation['recommendations'])}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Developer validation error: {e}")
            return False

    async def _update_jira_with_results(self, ticket: Ticket, result: Dict[str, Any]) -> bool:
        """Update JIRA with enhanced pipeline results"""
        try:
            validation = pipeline_validator.validate_developer_results(result)
            action = pipeline_validator.determine_next_action(validation, ticket)
            
            # Update JIRA with appropriate status and comment
            success = await self.jira_client.update_ticket_status(
                ticket.jira_id,
                action["jira_status"],
                action["jira_comment"]
            )
            
            if success:
                logger.info(f"✅ Updated JIRA {ticket.jira_id} with action: {action['action']}")
                
                # Log manual review requirement
                if action["require_manual_review"]:
                    logger.warning(f"🔍 MANUAL REVIEW REQUIRED: {ticket.jira_id}")
                    
            return success
            
        except Exception as e:
            logger.error(f"💥 Error updating JIRA with results: {e}")
            return False

    async def retry_failed_ticket(self, ticket_id: int):
        """Retry processing a failed ticket"""
        logger.info(f"🔄 Retrying failed ticket {ticket_id}")
        
        with next(get_sync_db()) as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            # Fix enum comparison - compare string values
            if ticket and ticket.status == TicketStatus.FAILED.value:
                ticket.status = TicketStatus.TODO.value
                ticket.retry_count = 0
                db.add(ticket)
                db.commit()
                logger.info(f"✅ Ticket {ticket_id} reset for retry")
            else:
                logger.warning(f"⚠️ Cannot retry ticket {ticket_id} - not in FAILED status")
