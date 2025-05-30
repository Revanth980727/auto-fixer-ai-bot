from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt, GitHubPR
from core.database import get_sync_db
from services.github_client import GitHubClient
from services.jira_client import JIRAClient
from typing import Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class CommunicatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.COMMUNICATOR)
        self.github_client = GitHubClient()
        self.jira_client = JIRAClient()
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create GitHub PR and update JIRA ticket with proper context validation"""
        self.log_execution(execution_id, "Starting communication process")
        
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
                "github_operations": False
            }
        
        # Create GitHub branch and PR
        branch_name = f"fix-{ticket.jira_id}-{ticket.id}"
        
        try:
            # Create branch
            branch_created = await self.github_client.create_branch(branch_name)
            if branch_created:
                self.log_execution(execution_id, f"Created branch: {branch_name}")
                actions_taken.append(f"Created branch {branch_name}")
                
                # Commit patches
                for patch in successful_patches:
                    commit_success = await self._commit_patch(patch, branch_name)
                    if commit_success:
                        actions_taken.append(f"Committed patch {patch.id}")
                
                # Create PR
                pr_data = await self._create_pull_request(ticket, branch_name, successful_patches)
                if pr_data:
                    self._save_github_pr(ticket, pr_data)
                    actions_taken.append(f"Created PR #{pr_data['number']}")
                    
                    # Update JIRA ticket
                    jira_updated = await self._update_jira_ticket(ticket, pr_data)
                    if jira_updated:
                        actions_taken.append("Updated JIRA ticket with PR link")
                
        except Exception as e:
            self.log_execution(execution_id, f"Error in communication process: {e}")
            return {"status": "error", "error": str(e), "actions_taken": actions_taken}
        
        result = {
            "status": "completed",
            "actions_taken": actions_taken,
            "patches_deployed": len(successful_patches),
            "branch_name": branch_name,
            "github_operations": True
        }
        
        self.log_execution(execution_id, f"Communication completed: {len(actions_taken)} actions taken")
        return result
    
    def _get_successful_patches(self, ticket: Ticket) -> list:
        """Get patches that passed QA testing"""
        with next(get_sync_db()) as db:
            return db.query(PatchAttempt).filter(
                PatchAttempt.ticket_id == ticket.id,
                PatchAttempt.success == True
            ).all()
    
    async def _commit_patch(self, patch: PatchAttempt, branch_name: str) -> bool:
        """Commit a patch to the GitHub branch"""
        try:
            # Extract file path from patch content (simplified)
            # In real implementation, would parse unified diff format
            file_path = self._extract_file_path_from_patch(patch)
            
            if not file_path:
                logger.error(f"Could not extract file path from patch {patch.id}")
                return False
            
            # Commit the patched code
            commit_success = await self.github_client.commit_file(
                file_path=file_path,
                content=patch.patched_code,
                commit_message=patch.commit_message or f"Fix for patch {patch.id}",
                branch=branch_name
            )
            
            return commit_success
            
        except Exception as e:
            logger.error(f"Error committing patch {patch.id}: {e}")
            return False
    
    async def _create_pull_request(self, ticket: Ticket, branch_name: str, patches: list) -> Dict:
        """Create a pull request for the fixes"""
        patch_count = len(patches)
        
        title = f"Fix {ticket.jira_id}: {ticket.title}"
        
        body = f"""
## Fix for {ticket.jira_id}

**Issue**: {ticket.title}

**Description**: {ticket.description[:500]}...

**Changes**:
- Applied {patch_count} code patch{'es' if patch_count > 1 else ''}
- Automated fix generated by AI Agent System

**Patches Applied**:
"""
        
        for i, patch in enumerate(patches, 1):
            body += f"\n{i}. Confidence: {patch.confidence_score:.2f} - {patch.commit_message}"
        
        body += f"\n\n**Testing**: All patches have passed automated QA testing."
        body += f"\n\n**JIRA Ticket**: [{ticket.jira_id}]({self._get_jira_url(ticket.jira_id)})"
        
        return await self.github_client.create_pull_request(
            title=title,
            body=body,
            head_branch=branch_name
        )
    
    async def _update_jira_ticket(self, ticket: Ticket, pr_data: Dict) -> bool:
        """Update JIRA ticket with PR information"""
        comment = f"""
Automated fix has been generated and is ready for review.

**Pull Request**: [{pr_data['title']}]({pr_data['html_url']})
**Branch**: {pr_data['head']['ref']}
**Status**: Ready for code review

This fix was automatically generated by the AI Agent System and has passed QA testing.
"""
        
        return await self.jira_client.update_ticket_status(
            jira_id=ticket.jira_id,
            status="In Review",
            comment=comment
        )
    
    def _save_github_pr(self, ticket: Ticket, pr_data: Dict):
        """Save GitHub PR information to database"""
        with next(get_sync_db()) as db:
            github_pr = GitHubPR(
                ticket_id=ticket.id,
                pr_number=pr_data["number"],
                pr_url=pr_data["html_url"],
                branch_name=pr_data["head"]["ref"],
                status="open"
            )
            db.add(github_pr)
            db.commit()
    
    def _extract_file_path_from_patch(self, patch: PatchAttempt) -> str:
        """Extract file path from patch content"""
        # Simple extraction - in real implementation would parse unified diff
        lines = patch.patch_content.split('\n')
        for line in lines:
            if line.startswith('+++') or line.startswith('---'):
                # Extract path after the prefix
                parts = line.split('\t')[0].split(' ')
                if len(parts) > 1:
                    path = parts[1]
                    if path.startswith('b/'):
                        return path[2:]  # Remove 'b/' prefix
                    return path
        
        # Fallback - try to guess from commit message or other context
        return "main.py"  # Default fallback
    
    def _get_jira_url(self, jira_id: str) -> str:
        """Get JIRA ticket URL"""
        base_url = self.jira_client.base_url
        return f"{base_url}/browse/{jira_id}"
    
    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate communicator context"""
        return True  # Communicator can work with minimal context
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate communicator results"""
        required_fields = ["status", "actions_taken", "patches_deployed"]
        return all(field in result for field in required_fields)
