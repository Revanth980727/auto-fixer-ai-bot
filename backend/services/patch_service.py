
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from services.github_client import GitHubClient
from services.fine_grained_diff import FineGrainedDiffGenerator
from services.patch_validator import PatchValidator
from core.config import config
import logging

logger = logging.getLogger(__name__)

class PatchApplicationError(Exception):
    """Custom exception for patch application errors"""
    pass

class PatchService:
    def __init__(self):
        self.github_client = GitHubClient()
        self.target_branch = config.github_target_branch
        self.diff_generator = FineGrainedDiffGenerator()
        self.validator = PatchValidator()
        self.max_safe_hunk_size = 50  # Reject patches with hunks larger than this
    
    async def apply_patches_intelligently(self, patches: List[Dict[str, Any]], ticket_id: int) -> Dict[str, Any]:
        """Apply patches with surgical precision and enhanced validation"""
        results = {
            "successful_patches": [],
            "failed_patches": [],
            "conflicts_detected": [],
            "files_modified": [],
            "target_branch": self.target_branch,
            "patch_quality_scores": [],
            "validation_failures": []
        }
        
        logger.info(f"🔧 Applying {len(patches)} surgical patches to: {self.target_branch}")
        
        # Pre-validate all patches for size and content
        validated_patches = []
        for patch in patches:
            if self._pre_validate_patch_safety(patch):
                validated_patches.append(patch)
            else:
                results["failed_patches"].append({
                    "patch": patch,
                    "error": "Patch rejected for unsafe size or content"
                })
                results["validation_failures"].append(patch.get("target_file", "unknown"))
        
        if not validated_patches:
            logger.error("❌ All patches failed pre-validation")
            return {
                **results,
                "error": "All patches failed pre-validation for safety",
                "all_patches_rejected": True
            }
        
        logger.info(f"✅ {len(validated_patches)} patches passed pre-validation")
        
        # Validate target branch exists
        if not await self._validate_target_branch():
            logger.error(f"❌ Target branch {self.target_branch} not accessible")
            return {
                **results,
                "error": f"Target branch {self.target_branch} not accessible",
                "branch_validation_failed": True
            }
        
        # Group patches by file for atomic operations
        patches_by_file = self._group_patches_by_file(validated_patches)
        
        for file_path, file_patches in patches_by_file.items():
            try:
                result = await self._apply_file_patches_surgically(
                    file_path, file_patches, self.target_branch
                )
                
                if result["success"]:
                    results["successful_patches"].extend(result["patches"])
                    if file_path not in results["files_modified"]:
                        results["files_modified"].append(file_path)
                    
                    # Track patch quality
                    if "quality_score" in result:
                        results["patch_quality_scores"].append({
                            "file": file_path,
                            "score": result["quality_score"],
                            "summary": result.get("change_summary", ""),
                            "is_surgical": result.get("is_surgical", False)
                        })
                    
                    logger.info(f"✅ Applied {len(result['patches'])} surgical patches to {file_path}")
                else:
                    results["failed_patches"].extend(result["patches"])
                    if result.get("conflict"):
                        results["conflicts_detected"].append(result["conflict"])
                    logger.warning(f"❌ Failed to apply surgical patches to {file_path}: {result.get('error')}")
                        
            except Exception as e:
                logger.error(f"Error applying surgical patches to {file_path}: {e}")
                for patch in file_patches:
                    results["failed_patches"].append({
                        "patch": patch,
                        "error": str(e)
                    })
        
        # Calculate overall quality metrics
        if results["patch_quality_scores"]:
            avg_quality = sum(p["score"] for p in results["patch_quality_scores"]) / len(results["patch_quality_scores"])
            surgical_patches = sum(1 for p in results["patch_quality_scores"] if p.get("is_surgical", False))
            results["overall_quality_score"] = avg_quality
            results["surgical_patches_count"] = surgical_patches
            logger.info(f"📊 Overall patch quality score: {avg_quality:.3f} ({surgical_patches} surgical)")
        
        logger.info(f"🎉 COMPLETED: {len(results['successful_patches'])} successful, {len(results['failed_patches'])} failed")
        return results
    
    def _pre_validate_patch_safety(self, patch: Dict[str, Any]) -> bool:
        """Pre-validate patch for safety before application"""
        try:
            patch_content = patch.get('patch_content', '')
            
            # Count changes
            add_lines = patch_content.count('\n+')
            remove_lines = patch_content.count('\n-')
            total_changes = add_lines + remove_lines
            
            # Reject massive patches
            if total_changes > self.max_safe_hunk_size * 3:
                logger.warning(f"❌ Patch rejected: {total_changes} changes exceeds safety limit")
                return False
            
            # Check for suspicious deletion patterns
            if remove_lines > 200 and add_lines < 20:
                logger.warning(f"❌ Patch rejected: Suspicious deletion pattern ({remove_lines} deletions)")
                return False
            
            # Check for required fields
            if not patch.get('patched_code'):
                logger.warning("❌ Patch rejected: Missing patched_code")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Patch safety validation error: {e}")
            return False
    
    async def _apply_file_patches_surgically(self, file_path: str, patches: List[Dict], branch_name: str) -> Dict[str, Any]:
        """Apply patches using surgical precision with enhanced validation"""
        logger.info(f"🔧 Applying {len(patches)} surgical patches to {file_path}")
        
        # Get current file content
        current_content = await self.github_client.get_file_content(file_path, branch_name)
        if current_content is None:
            logger.warning(f"⚠️ File {file_path} not found on branch {branch_name}")
            return {
                "success": False,
                "patches": patches,
                "error": f"File {file_path} not found"
            }
        
        # Pre-validate all patches
        for patch in patches:
            is_valid, error = self.validator.validate_pre_application(patch)
            if not is_valid:
                logger.error(f"❌ Pre-validation failed for {file_path}: {error}")
                return {
                    "success": False,
                    "patches": patches,
                    "error": f"Pre-validation failed: {error}"
                }
        
        # Apply patches using patched_code with surgical validation
        successful_patches = []
        final_content = current_content
        
        for patch in patches:
            try:
                # Use the patched_code directly from the AI-generated patch
                patched_code = patch.get("patched_code", "")
                if not patched_code:
                    logger.error(f"❌ No patched_code provided for {file_path}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": "No patched_code provided"
                    }
                
                # Generate fine-grained diff for analysis
                diff_result = self.diff_generator.generate_minimal_diff(
                    final_content, patched_code, file_path
                )
                
                if not diff_result["success"]:
                    logger.error(f"❌ Diff generation failed for {file_path}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": f"Diff generation failed: {diff_result.get('error')}"
                    }
                
                if not diff_result["has_changes"]:
                    logger.info(f"⚠️ No changes detected for {file_path}")
                    continue
                
                # Enhanced surgical validation
                analysis = diff_result.get("analysis", {})
                if not self._validate_surgical_quality(analysis, file_path):
                    logger.error(f"❌ Surgical quality validation failed for {file_path}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": "Surgical quality validation failed - changes too large or unsafe"
                    }
                
                # Log diff analysis with enhanced details
                logger.info(f"📊 Surgical diff analysis for {file_path}:")
                logger.info(f"  - {diff_result.get('change_summary', 'No summary')}")
                logger.info(f"  - Quality score: {analysis.get('quality_score', 'N/A')}")
                logger.info(f"  - Large hunks: {analysis.get('large_hunks', 0)}")
                
                # Enhanced post-validation with debugging
                is_valid, validation_error = self.validator.validate_post_application(patched_code, file_path)
                if not is_valid:
                    logger.error(f"❌ Post-validation failed for {file_path}: {validation_error}")
                    logger.error(f"🔍 First 500 chars of patched code: {patched_code[:500]}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": f"Post-validation failed: {validation_error}"
                    }
                
                # Update the final content and mark patch as successful
                final_content = patched_code
                successful_patches.append(patch)
                
                logger.info(f"✅ Surgical patch validation passed for {file_path}")
                
            except Exception as e:
                logger.error(f"💥 Exception processing surgical patch for {file_path}: {e}")
                return {
                    "success": False,
                    "patches": patches,
                    "error": str(e)
                }
        
        if not successful_patches:
            logger.warning(f"⚠️ No surgical patches were successfully processed for {file_path}")
            return {
                "success": False,
                "patches": patches,
                "error": "No surgical patches were successfully processed"
            }
        
        # Commit the changes
        commit_message = self._generate_surgical_commit_message(file_path, successful_patches)
        logger.info(f"🔧 Committing surgical changes to {file_path}")
        commit_success = await self.github_client.commit_file(
            file_path, final_content, commit_message, branch_name
        )
        
        if not commit_success:
            logger.error(f"❌ Failed to commit surgical changes to {branch_name} for {file_path}")
            return {
                "success": False,
                "patches": patches,
                "error": f"Failed to commit surgical changes to {branch_name}"
            }
        
        logger.info(f"✅ Successfully committed surgical patches to {file_path}")
        
        return {
            "success": True,
            "patches": successful_patches,
            "content": final_content,
            "quality_score": analysis.get("quality_score", 1.0),
            "change_summary": diff_result.get("change_summary", "Surgical changes applied"),
            "is_surgical": True
        }
    
    def _validate_surgical_quality(self, analysis: Dict[str, Any], file_path: str) -> bool:
        """Validate that changes meet surgical quality standards"""
        try:
            large_hunks = analysis.get("large_hunks", 0)
            total_changes = analysis.get("lines_added", 0) + analysis.get("lines_removed", 0)
            
            # Reject if there are large hunks (indicates massive changes)
            if large_hunks > 0:
                logger.warning(f"❌ Surgical validation failed: {large_hunks} large hunks detected")
                return False
            
            # Reject if total changes are too large
            if total_changes > self.max_safe_hunk_size * 2:
                logger.warning(f"❌ Surgical validation failed: {total_changes} total changes exceeds limit")
                return False
            
            # Validate quality score
            quality_score = analysis.get("quality_score", 0)
            if quality_score < 0.3:
                logger.warning(f"❌ Surgical validation failed: Quality score {quality_score} too low")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Surgical quality validation error: {e}")
            return False
    
    def _generate_surgical_commit_message(self, file_path: str, patches: List[Dict]) -> str:
        """Generate descriptive commit message for surgical patches"""
        if len(patches) == 1:
            patch = patches[0]
            base_message = patch.get("commit_message", f"Surgical fix applied to {file_path}")
            return f"🔧 {base_message}"
        else:
            return f"🔧 Apply {len(patches)} surgical fixes to {file_path}"
    
    # ... keep existing code (validation methods, utility functions)
    
    async def _validate_target_branch(self) -> bool:
        """Validate that the target branch exists and is accessible"""
        try:
            test_content = await self.github_client.get_file_content("README.md", self.target_branch)
            if test_content is not None:
                logger.info(f"✅ Target branch {self.target_branch} validated successfully")
                return True
            
            tree = await self.github_client.get_repository_tree(self.target_branch)
            if tree:
                logger.info(f"✅ Target branch {self.target_branch} validated via tree")
                return True
            
            logger.warning(f"⚠️ Target branch {self.target_branch} may not exist")
            return False
            
        except Exception as e:
            logger.error(f"❌ Branch validation failed: {e}")
            return False
    
    def _group_patches_by_file(self, patches: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Group patches by target file for atomic operations"""
        grouped = {}
        for patch in patches:
            file_path = patch.get("target_file", "unknown")
            if file_path not in grouped:
                grouped[file_path] = []
            grouped[file_path].append(patch)
        return grouped
    
    async def validate_repository_state(self, file_paths: List[str]) -> Dict[str, Any]:
        """Validate repository state on target branch before applying patches"""
        validation_result = {
            "valid": True,
            "missing_files": [],
            "file_states": {},
            "target_branch": self.target_branch
        }
        
        for file_path in file_paths:
            content = await self.github_client.get_file_content(file_path, self.target_branch)
            if content is None:
                validation_result["missing_files"].append(file_path)
                validation_result["valid"] = False
            else:
                validation_result["file_states"][file_path] = {
                    "exists": True,
                    "hash": hashlib.sha256(content.encode()).hexdigest(),
                    "size": len(content)
                }
        
        return validation_result
    
    def get_target_branch(self) -> str:
        """Get the configured target branch"""
        return self.target_branch
