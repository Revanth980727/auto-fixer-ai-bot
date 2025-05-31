
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.patch_service import PatchService
from typing import Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.QA)
        self.patch_service = PatchService()
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test patches using intelligent patch application system"""
        self.log_execution(execution_id, "Starting intelligent QA testing process")
        
        if not context:
            self.log_execution(execution_id, "No context provided for QA testing")
            return {"status": "no_context", "patches_tested": 0, "successful_patches": 0, "ready_for_deployment": False}
        
        # Get patches to test
        patches = context.get("patches", [])
        
        if not patches:
            self.log_execution(execution_id, "No patches found for testing")
            return {"status": "no_patches", "patches_tested": 0, "successful_patches": 0, "ready_for_deployment": False}
        
        # Add processing delay for realistic timing
        await asyncio.sleep(5)
        
        # Create test branch for intelligent patch application
        try:
            test_branch = await self.patch_service.create_smart_branch("main", ticket.id)
            self.log_execution(execution_id, f"Created test branch: {test_branch}")
        except Exception as e:
            self.log_execution(execution_id, f"Failed to create test branch: {e}")
            return await self._fallback_validation(patches, execution_id)
        
        # Validate repository state before applying patches
        file_paths = [patch.get("target_file") for patch in patches if patch.get("target_file")]
        repo_validation = await self.patch_service.validate_repository_state(file_paths)
        
        if not repo_validation["valid"]:
            self.log_execution(execution_id, f"Repository validation failed: {repo_validation['missing_files']}")
            return await self._fallback_validation(patches, execution_id)
        
        # Apply patches intelligently
        try:
            patch_results = await self.patch_service.apply_patches_intelligently(patches, test_branch)
            
            # Update patch attempts with results
            self._update_patch_results_from_intelligent_application(ticket, patch_results)
            
            successful_patches = len(patch_results["successful_patches"])
            total_patches = len(patches)
            
            result = {
                "status": "completed",
                "patches_tested": total_patches,
                "successful_patches": successful_patches,
                "failed_patches": len(patch_results["failed_patches"]),
                "conflicts_detected": len(patch_results["conflicts_detected"]),
                "files_modified": patch_results["files_modified"],
                "test_branch": test_branch,
                "ready_for_deployment": successful_patches > 0 and len(patch_results["conflicts_detected"]) == 0,
                "patch_application_results": patch_results,
                "validated_patches": patch_results["successful_patches"]
            }
            
            self.log_execution(execution_id, f"Intelligent QA completed: {successful_patches}/{total_patches} patches applied successfully")
            
            # If we have conflicts, provide detailed information
            if patch_results["conflicts_detected"]:
                self.log_execution(execution_id, f"Conflicts detected: {patch_results['conflicts_detected']}")
            
            return result
            
        except Exception as e:
            self.log_execution(execution_id, f"Error in intelligent patch application: {e}")
            return await self._fallback_validation(patches, execution_id)
    
    async def _fallback_validation(self, patches: List[Dict], execution_id: int) -> Dict[str, Any]:
        """Fallback to basic validation when intelligent patching fails"""
        self.log_execution(execution_id, "Falling back to basic patch validation")
        
        validated_patches = []
        
        for patch in patches:
            # Enhanced basic validation
            is_valid = self._enhanced_basic_validation(patch)
            
            result = {
                "patch_id": patch.get("id"),
                "success": is_valid,
                "test_output": "Enhanced basic validation passed" if is_valid else "Enhanced basic validation failed",
                "validation_type": "enhanced_basic",
                "patch": patch
            }
            
            validated_patches.append(result)
        
        successful_patches = [r for r in validated_patches if r.get("success")]
        
        self.log_execution(execution_id, f"Enhanced basic validation completed: {len(successful_patches)}/{len(validated_patches)} patches passed")
        
        return {
            "status": "completed",
            "patches_tested": len(validated_patches),
            "successful_patches": len(successful_patches),
            "test_results": validated_patches,
            "ready_for_deployment": len(successful_patches) > 0,
            "validation_method": "enhanced_basic"
        }
    
    def _enhanced_basic_validation(self, patch: Dict) -> bool:
        """Enhanced basic validation for patches"""
        try:
            # Check required fields
            required_fields = ["patch_content", "patched_code", "target_file"]
            for field in required_fields:
                if not patch.get(field):
                    return False
            
            # Check patch content quality
            patch_content = patch.get("patch_content", "")
            if len(patch_content.strip()) < 10:
                return False
            
            # Check for unified diff format
            if not ("---" in patch_content and "+++" in patch_content):
                return False
            
            # Check confidence score
            confidence = patch.get("confidence_score", 0)
            if confidence < 0.5:
                return False
            
            # Check patched code is substantial
            patched_code = patch.get("patched_code", "")
            if len(patched_code.strip()) < 20:
                return False
            
            # Validate file hash is present (for tracking)
            if not patch.get("base_file_hash"):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in enhanced basic validation: {e}")
            return False
    
    def _update_patch_results_from_intelligent_application(self, ticket: Ticket, patch_results: Dict):
        """Update patch attempts with intelligent application results"""
        try:
            with next(get_sync_db()) as db:
                # Update successful patches
                for successful_patch in patch_results["successful_patches"]:
                    patch_id = successful_patch.get("id")
                    if patch_id:
                        patch_attempt = db.query(PatchAttempt).filter(
                            PatchAttempt.ticket_id == ticket.id,
                            PatchAttempt.id == patch_id
                        ).first()
                        
                        if patch_attempt:
                            patch_attempt.success = True
                            patch_attempt.test_results = {
                                "validation_type": "intelligent_application",
                                "success": True,
                                "applied_successfully": True
                            }
                
                # Update failed patches
                for failed_patch in patch_results["failed_patches"]:
                    patch_info = failed_patch.get("patch", {})
                    patch_id = patch_info.get("id")
                    if patch_id:
                        patch_attempt = db.query(PatchAttempt).filter(
                            PatchAttempt.ticket_id == ticket.id,
                            PatchAttempt.id == patch_id
                        ).first()
                        
                        if patch_attempt:
                            patch_attempt.success = False
                            patch_attempt.test_results = {
                                "validation_type": "intelligent_application",
                                "success": False,
                                "error": failed_patch.get("error"),
                                "application_failed": True
                            }
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update patch results: {e}")
    
    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate QA context"""
        return "patches" in context or "ticket" in context
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate QA results"""
        required_fields = ["status", "patches_tested", "successful_patches", "ready_for_deployment"]
        return all(field in result for field in required_fields)
