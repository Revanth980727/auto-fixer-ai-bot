
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt, GitHubPR
from core.database import get_sync_db
from services.github_client import GitHubClient
from services.jira_client import JIRAClient
from services.patch_service import PatchService
from core.config import config
from typing import Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class CommunicatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.COMMUNICATOR)
        self.github_client = GitHubClient()
        self.jira_client = JIRAClient()
        self.patch_service = PatchService()
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Apply patches to target branch and update JIRA ticket"""
        self.log_execution(execution_id, f"Starting communication process with target branch: {config.github_target_branch}")
        
        # Get successful patches
        successful_patches = self._get_successful_patches(ticket)
        
        if not successful_patches:
            self.log_execution(execution_id, "No successful patches to deploy")
            return {"status": "no_patches", "actions_taken": []}
        
        # Add processing delay for realistic timing
        await asyncio.sleep(2)
        
        actions_taken = []
        
        # Only proceed with GitHub operations if configured
        if not self.github_client._is_configured():
            self.log_execution(execution_id, "GitHub not configured - updating JIRA only")
            
            # Update JIRA with results
            jira_updated = await self._update_jira_with_results(ticket, successful_patches)
            if jira_updated:
                actions_taken.append("Updated JIRA with patch information")
            
            return {
                "status": "completed",
                "actions_taken": actions_taken,
                "patches_deployed": len(successful_patches),
                "github_operations": False,
                "target_branch": config.github_target_branch
            }
        
        try:
            # Apply patches directly to target branch
            self.log_execution(execution_id, f"Applying {len(successful_patches)} patches to {config.github_target_branch}")
            
            # Convert PatchAttempt objects to dictionaries for patch service
            patch_dicts = []
            for patch in successful_patches:
                patch_dict = {
                    "id": patch.id,
                    "target_file": patch.target_file,
                    "patch_content": patch.patch_content,
                    "patched_code": patch.patched_code,
                    "base_file_hash": patch.base_file_hash,
                    "commit_message": patch.commit_message or f"Fix for ticket {ticket.jira_id}"
                }
                patch_dicts.append(patch_dict)
            
            # Apply patches using patch service
            apply_result = await self.patch_service.apply_patches_intelligently(patch_dicts, ticket.id)
            
            if apply_result["successful_patches"]:
                self.log_execution(execution_id, f"Successfully applied {len(apply_result['successful_patches'])} patches")
                actions_taken.append(f"Applied {len(apply_result['successful_patches'])} patches to {config.github_target_branch}")
                
                for file_path in apply_result["files_modified"]:
                    actions_taken.append(f"Modified {file_path}")
            
            if apply_result["failed_patches"]:
                self.log_execution(execution_id, f"Failed to apply {len(apply_result['failed_patches'])} patches")
                actions_taken.append(f"Failed to apply {len(apply_result['failed_patches'])} patches")
            
            # Update JIRA ticket with results
            jira_updated = await self._update_jira_ticket_with_branch_info(ticket, apply_result)
            if jira_updated:
                actions_taken.append("Updated JIRA ticket with deployment info")
                
        except Exception as e:
            self.log_execution(execution_id, f"Error in communication process: {e}")
            return {
                "status": "error", 
                "error": str(e), 
                "actions_taken": actions_taken,
                "target_branch": config.github_target_branch
            }
        
        result = {
            "status": "completed",
            "actions_taken": actions_taken,
            "patches_deployed": len(successful_patches),
            "target_branch": config.github_target_branch,
            "github_operations": True,
            "apply_result": apply_result
        }
        
        self.log_execution(execution_id, f"Communication completed: {len(actions_taken)} actions taken on {config.github_target_branch}")
        return result
    
    def _get_successful_patches(self, ticket: Ticket) -> list:
        """Get patches that passed QA testing"""
        with next(get_sync_db()) as db:
            return db.query(PatchAttempt).filter(
                PatchAttempt.ticket_id == ticket.id,
                PatchAttempt.success == True
            ).all()
    
    async def _update_jira_ticket_with_branch_info(self, ticket: Ticket, apply_result: Dict) -> bool:
        """Update JIRA ticket with branch deployment information"""
        successful_count = len(apply_result["successful_patches"])
        failed_count = len(apply_result["failed_patches"])
        files_modified = apply_result["files_modified"]
        
        comment = f"""
Automated fix has been applied to branch: {config.github_target_branch}

**Deployment Summary**:
- Successfully applied: {successful_count} patches
- Failed to apply: {failed_count} patches
- Files modified: {len(files_modified)}

**Modified Files**:
{chr(10).join(f"- {file}" for file in files_modified)}

**Branch**: {config.github_target_branch}
**Status**: {'Deployed successfully' if successful_count > 0 else 'Deployment failed'}

This fix was automatically generated and applied by the AI Agent System.
"""
        
        if successful_count > 0:
            status = "In Review"
        else:
            status = "To Do"  # Reset if deployment failed
        
        return await self.jira_client.update_ticket_status(
            jira_id=ticket.jira_id,
            status=status,
            comment=comment
        )
    
    async def _update_jira_with_results(self, ticket: Ticket, patches: list) -> bool:
        """Update JIRA with patch results when GitHub is not configured"""
        comment = f"""
Automated patches have been generated for this ticket.

**Patch Summary**:
- Total patches generated: {len(patches)}
- Average confidence: {sum(p.confidence_score for p in patches) / len(patches):.2f}

**Note**: GitHub integration is not configured, so patches were not automatically deployed.
Manual review and application of patches may be required.

This analysis was performed by the AI Agent System.
"""
        
        return await self.jira_client.update_ticket_status(
            jira_id=ticket.jira_id,
            status="Analysis Complete",
            comment=comment
        )
    
    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate communicator context"""
        return True  # Communicator can work with minimal context
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate communicator results"""
        required_fields = ["status", "actions_taken", "patches_deployed", "target_branch"]
        return all(field in result for field in required_fields)
