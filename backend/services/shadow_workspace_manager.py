import os
import shutil
import tempfile
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ShadowWorkspaceManager:
    """Manages isolated shadow workspaces for safe validation before merging."""
    
    def __init__(self):
        self.active_workspaces = {}
        self.cleanup_tasks = []
    
    async def create_shadow_workspace(self, file_path: str, original_content: str, patched_content: str) -> str:
        """Create an isolated shadow workspace for validation."""
        try:
            workspace_id = f"shadow_{hash(f'{file_path}_{original_content[:100]}')}"
            workspace_dir = tempfile.mkdtemp(prefix=f"shadow_validation_{workspace_id}_")
            
            logger.info(f"🏗️ Creating shadow workspace: {workspace_dir}")
            
            # Create directory structure
            file_dir = os.path.dirname(file_path)
            if file_dir:
                shadow_file_dir = os.path.join(workspace_dir, file_dir)
                os.makedirs(shadow_file_dir, exist_ok=True)
            
            # Write patched content to shadow workspace
            shadow_file_path = os.path.join(workspace_dir, file_path)
            with open(shadow_file_path, 'w', encoding='utf-8') as f:
                f.write(patched_content)
            
            # Store original content for comparison
            original_file_path = shadow_file_path + ".original"
            with open(original_file_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Track workspace
            self.active_workspaces[workspace_id] = {
                'dir': workspace_dir,
                'file_path': file_path,
                'shadow_file_path': shadow_file_path,
                'original_file_path': original_file_path,
                'created_at': asyncio.get_event_loop().time()
            }
            
            logger.info(f"✅ Shadow workspace created: {workspace_id}")
            return workspace_id
            
        except Exception as e:
            logger.error(f"❌ Error creating shadow workspace: {e}")
            raise
    
    async def validate_in_shadow(self, workspace_id: str, patch_info: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive validation in shadow workspace."""
        if workspace_id not in self.active_workspaces:
            return {
                'success': False,
                'error': 'Shadow workspace not found'
            }
        
        workspace = self.active_workspaces[workspace_id]
        
        try:
            logger.info(f"🔍 Starting shadow workspace validation: {workspace_id}")
            
            # Initialize validation orchestrator
            from services.validation_orchestrator import ValidationOrchestrator
            validator = ValidationOrchestrator()
            
            # Read patched and original content
            with open(workspace['shadow_file_path'], 'r', encoding='utf-8') as f:
                patched_content = f.read()
            
            with open(workspace['original_file_path'], 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Run comprehensive validation
            validation_summary = await validator.validate_patch(
                original_content=original_content,
                patched_content=patched_content,
                file_path=workspace['file_path'],
                patch_info=patch_info
            )
            
            validation_result = {
                'success': validation_summary.overall_success,
                'confidence': validation_summary.overall_confidence,
                'recommendation': validation_summary.recommendation,
                'issues': validation_summary.critical_issues,
                'execution_time': validation_summary.total_execution_time,
                'validator_results': [
                    {
                        'name': result.validator_name,
                        'success': result.success,
                        'confidence': result.confidence,
                        'issues': result.issues,
                        'warnings': result.warnings
                    }
                    for result in validation_summary.results
                ]
            }
            
            logger.info(f"✅ Shadow validation completed: {validation_summary.recommendation}")
            return validation_result
            
        except Exception as e:
            logger.error(f"❌ Error in shadow validation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_diff_for_approval(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Generate diff data for interactive approval."""
        if workspace_id not in self.active_workspaces:
            return None
        
        workspace = self.active_workspaces[workspace_id]
        
        try:
            # Read content
            with open(workspace['shadow_file_path'], 'r', encoding='utf-8') as f:
                patched_content = f.read()
            
            with open(workspace['original_file_path'], 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Generate diff using DiffPresenter
            from services.diff_presenter import DiffPresenter
            diff_presenter = DiffPresenter()
            
            diff_result = diff_presenter.create_interactive_diff(
                original_content=original_content,
                patched_content=patched_content,
                file_path=workspace['file_path']
            )
            
            if diff_result['success']:
                return {
                    'workspace_id': workspace_id,
                    'file_path': workspace['file_path'],
                    'diff_data': diff_result,
                    'requires_approval': diff_result['has_changes']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error generating diff for approval: {e}")
            return None
    
    async def cleanup_workspace(self, workspace_id: str) -> bool:
        """Clean up a shadow workspace."""
        if workspace_id not in self.active_workspaces:
            return False
        
        workspace = self.active_workspaces[workspace_id]
        
        try:
            if os.path.exists(workspace['dir']):
                shutil.rmtree(workspace['dir'])
                logger.info(f"🧹 Cleaned up shadow workspace: {workspace_id}")
            
            del self.active_workspaces[workspace_id]
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning up shadow workspace {workspace_id}: {e}")
            return False
    
    async def cleanup_expired_workspaces(self, max_age_seconds: int = 3600) -> int:
        """Clean up expired shadow workspaces."""
        current_time = asyncio.get_event_loop().time()
        expired_count = 0
        expired_workspaces = []
        
        for workspace_id, workspace in self.active_workspaces.items():
            if current_time - workspace['created_at'] > max_age_seconds:
                expired_workspaces.append(workspace_id)
        
        for workspace_id in expired_workspaces:
            if await self.cleanup_workspace(workspace_id):
                expired_count += 1
        
        if expired_count > 0:
            logger.info(f"🧹 Cleaned up {expired_count} expired shadow workspaces")
        
        return expired_count
    
    def get_workspace_info(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a shadow workspace."""
        if workspace_id not in self.active_workspaces:
            return None
        
        workspace = self.active_workspaces[workspace_id]
        return {
            'workspace_id': workspace_id,
            'file_path': workspace['file_path'],
            'created_at': workspace['created_at'],
            'age_seconds': asyncio.get_event_loop().time() - workspace['created_at']
        }
    
    def list_active_workspaces(self) -> List[Dict[str, Any]]:
        """List all active shadow workspaces."""
        return [
            self.get_workspace_info(workspace_id)
            for workspace_id in self.active_workspaces.keys()
        ]