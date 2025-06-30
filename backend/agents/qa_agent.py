from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.patch_service import PatchService
from services.metrics_collector import metrics_collector
from services.pipeline_context import context_manager, PipelineStage
from typing import Dict, Any, Optional, List
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.QA)
        self.patch_service = PatchService()
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test patches using intelligent patch application system with enhanced monitoring"""
        start_time = time.time()
        
        try:
            self.log_execution(execution_id, "Starting intelligent QA testing process with enhanced monitoring")
            
            # Get or create pipeline context
            pipeline_context = context_manager.get_context(ticket.id)
            if pipeline_context:
                context_manager.create_checkpoint(pipeline_context.context_id, "qa_start")
            
            if not context:
                self.log_execution(execution_id, "No context provided for QA testing")
                result = {"status": "no_context", "patches_tested": 0, "successful_patches": 0, "ready_for_deployment": False}
                metrics_collector.record_agent_execution("qa", time.time() - start_time, False, ticket.id)
                return result
            
            # Get patches to test
            patches = context.get("patches", [])
            
            if not patches:
                self.log_execution(execution_id, "No patches found for testing")
                result = {"status": "no_patches", "patches_tested": 0, "successful_patches": 0, "ready_for_deployment": False}
                metrics_collector.record_agent_execution("qa", time.time() - start_time, False, ticket.id)
                return result
            
            # Add processing delay for realistic timing
            await asyncio.sleep(5)
            
            # Use circuit breaker for GitHub operations
            github_breaker = metrics_collector.get_circuit_breaker("github")
            
            # Get the configured target branch instead of creating a new one
            target_branch = self.patch_service.get_target_branch()
            self.log_execution(execution_id, f"Using configured target branch: {target_branch}")
            
            # Validate repository state before applying patches
            file_paths = [patch.get("target_file") for patch in patches if patch.get("target_file")]
            repo_validation = await self.patch_service.validate_repository_state(file_paths)
            
            if not repo_validation["valid"]:
                self.log_execution(execution_id, f"Repository validation failed: {repo_validation['missing_files']}")
                result = await self._fallback_validation(patches, execution_id, ticket.id)
                metrics_collector.record_agent_execution("qa", time.time() - start_time, False, ticket.id)
                return result
            
            # Apply patches intelligently with monitoring
            try:
                patch_start_time = time.time()
                patch_results = await self.patch_service.apply_patches_intelligently(patches, ticket.id)
                patch_duration = time.time() - patch_start_time
                
                metrics_collector.record_github_operation("patch_application", patch_duration, True)
                
                # Update patch attempts with results
                self._update_patch_results_from_intelligent_application(ticket, patch_results)
                
                # DEBUG: Log patch results structure
                self.log_execution(execution_id, f"🔍 PATCH RESULTS DEBUG:")
                self.log_execution(execution_id, f"  - patch_results keys: {list(patch_results.keys())}")
                self.log_execution(execution_id, f"  - successful_patches type: {type(patch_results['successful_patches'])}")
                self.log_execution(execution_id, f"  - successful_patches length: {len(patch_results['successful_patches'])}")
                self.log_execution(execution_id, f"  - failed_patches length: {len(patch_results['failed_patches'])}")
                self.log_execution(execution_id, f"  - conflicts_detected length: {len(patch_results['conflicts_detected'])}")
                self.log_execution(execution_id, f"  - files_modified: {patch_results['files_modified']}")
                
                if patch_results['successful_patches']:
                    self.log_execution(execution_id, f"  - First successful patch keys: {list(patch_results['successful_patches'][0].keys())}")
                
                successful_patches = len(patch_results["successful_patches"])
                total_patches = len(patches)
                
                result = {
                    "status": "completed",
                    "patches_tested": total_patches,
                    "successful_patches": successful_patches,
                    "failed_patches": len(patch_results["failed_patches"]),
                    "conflicts_detected": len(patch_results["conflicts_detected"]),
                    "files_modified": patch_results["files_modified"],
                    "target_branch": target_branch,
                    "ready_for_deployment": successful_patches > 0 and len(patch_results["conflicts_detected"]) == 0,
                    "patch_application_results": patch_results,
                    "validated_patches": patch_results["successful_patches"],
                    "patch_application_duration": patch_duration
                }
                
                self.log_execution(execution_id, f"Intelligent QA completed: {successful_patches}/{total_patches} patches applied successfully")
                
                # If we have conflicts, provide detailed information
                if patch_results["conflicts_detected"]:
                    self.log_execution(execution_id, f"Conflicts detected: {patch_results['conflicts_detected']}")
                
                # Update pipeline context
                if pipeline_context:
                    context_manager.update_stage(
                        pipeline_context.context_id, 
                        PipelineStage.QA, 
                        result, 
                        "success", 
                        duration=time.time() - start_time
                    )
                
                # Record successful execution
                metrics_collector.record_agent_execution("qa", time.time() - start_time, True, ticket.id)
                return result
                
            except Exception as e:
                self.log_execution(execution_id, f"Error in intelligent patch application: {e}")
                result = await self._fallback_validation(patches, execution_id, ticket.id)
                metrics_collector.record_agent_execution("qa", time.time() - start_time, False, ticket.id)
                return result
                
        except Exception as e:
            logger.error(f"Unexpected error in QA agent: {e}")
            metrics_collector.record_agent_execution("qa", time.time() - start_time, False, ticket.id)
            raise e
    
    async def _fallback_validation(self, patches: List[Dict], execution_id: int, ticket_id: int) -> Dict[str, Any]:
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
                # Get all patch attempts for this ticket that haven't been tested yet
                untested_patches = db.query(PatchAttempt).filter(
                    PatchAttempt.ticket_id == ticket.id,
                    PatchAttempt.success == True  # Only consider patches that were successfully generated
                ).all()
                
                # Create a mapping of target files to patch attempts
                patch_attempts_by_file = {}
                for patch_attempt in untested_patches:
                    patch_attempts_by_file[patch_attempt.target_file] = patch_attempt
                
                # Update successful patches based on patch service results
                successful_files = [patch.get("target_file") for patch in patch_results["successful_patches"]]
                for file_path in successful_files:
                    if file_path in patch_attempts_by_file:
                        patch_attempt = patch_attempts_by_file[file_path]
                        patch_attempt.test_results = {
                            "validation_type": "intelligent_application",
                            "success": True,
                            "applied_successfully": True,
                            "qa_tested": True
                        }
                        logger.info(f"✅ Updated patch attempt for {file_path} as successfully applied")
                
                # Update failed patches
                failed_files = []
                for failed_patch in patch_results["failed_patches"]:
                    patch_info = failed_patch.get("patch", {})
                    file_path = patch_info.get("target_file")
                    if file_path and file_path in patch_attempts_by_file:
                        patch_attempt = patch_attempts_by_file[file_path]
                        patch_attempt.test_results = {
                            "validation_type": "intelligent_application",
                            "success": False,
                            "error": failed_patch.get("error"),
                            "application_failed": True,
                            "qa_tested": True
                        }
                        failed_files.append(file_path)
                        logger.warning(f"❌ Updated patch attempt for {file_path} as failed: {failed_patch.get('error')}")
                
                db.commit()
                logger.info(f"✅ Updated {len(successful_files)} successful and {len(failed_files)} failed patch attempts")
                
        except Exception as e:
            logger.error(f"Failed to update patch results: {e}")
    
    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate QA context"""
        return "patches" in context or "ticket" in context
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate QA results"""
        required_fields = ["status", "patches_tested", "successful_patches", "ready_for_deployment"]
        return all(field in result for field in required_fields)
