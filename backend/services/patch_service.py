import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from services.github_client import GitHubClient
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
    
    async def apply_patches_intelligently(self, patches: List[Dict[str, Any]], ticket_id: int) -> Dict[str, Any]:
        """Apply patches directly to the configured target branch with intelligent conflict detection"""
        results = {
            "successful_patches": [],
            "failed_patches": [],
            "conflicts_detected": [],
            "files_modified": [],
            "target_branch": self.target_branch
        }
        
        logger.info(f"🔧 Applying {len(patches)} patches directly to target branch: {self.target_branch}")
        
        # Validate target branch exists
        if not await self._validate_target_branch():
            logger.error(f"❌ Target branch {self.target_branch} does not exist or is not accessible")
            return {
                **results,
                "error": f"Target branch {self.target_branch} not accessible",
                "branch_validation_failed": True
            }
        
        # Group patches by file for atomic operations
        patches_by_file = self._group_patches_by_file(patches)
        
        for file_path, file_patches in patches_by_file.items():
            try:
                result = await self._apply_file_patches(file_path, file_patches, self.target_branch)
                
                logger.info(f"🔍 File patch result for {file_path}: success={result['success']}, patches_count={len(result.get('patches', []))}")
                
                if result["success"]:
                    results["successful_patches"].extend(result["patches"])
                    if file_path not in results["files_modified"]:
                        results["files_modified"].append(file_path)
                    logger.info(f"✅ Added {len(result['patches'])} successful patches for {file_path}")
                else:
                    results["failed_patches"].extend(result["patches"])
                    if result.get("conflict"):
                        results["conflicts_detected"].append(result["conflict"])
                    logger.warning(f"❌ Added {len(result['patches'])} failed patches for {file_path}")
                        
            except Exception as e:
                logger.error(f"Error applying patches to {file_path}: {e}")
                for patch in file_patches:
                    results["failed_patches"].append({
                        "patch": patch,
                        "error": str(e)
                    })
        
        logger.info(f"🔍 FINAL PATCH RESULTS: {len(results['successful_patches'])} successful, {len(results['failed_patches'])} failed, {len(results['conflicts_detected'])} conflicts")
        return results
    
    async def _validate_target_branch(self) -> bool:
        """Validate that the target branch exists and is accessible"""
        try:
            # Try to get a file from the target branch
            test_content = await self.github_client.get_file_content("README.md", self.target_branch)
            if test_content is not None:
                logger.info(f"✅ Target branch {self.target_branch} validated successfully")
                return True
            
            # If README.md doesn't exist, try to get repository tree
            tree = await self.github_client.get_repository_tree(self.target_branch)
            if tree:
                logger.info(f"✅ Target branch {self.target_branch} validated via tree")
                return True
            
            logger.warning(f"⚠️ Target branch {self.target_branch} may not exist")
            return False
            
        except Exception as e:
            logger.error(f"❌ Branch validation failed: {e}")
            return False
    
    async def _apply_file_patches(self, file_path: str, patches: List[Dict], branch_name: str) -> Dict[str, Any]:
        """Apply multiple patches to a single file with enhanced validation"""
        logger.info(f"🔧 Applying {len(patches)} patches to {file_path} on branch {branch_name}")
        
        # Get current file content and SHA
        current_content = await self.github_client.get_file_content(file_path, branch_name)
        if current_content is None:
            logger.warning(f"⚠️ File {file_path} not found on branch {branch_name}")
            return {
                "success": False,
                "patches": patches,
                "error": f"File {file_path} not found on branch {branch_name}"
            }
        
        # Calculate current file hash
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()
        
        # Check if any patch expects a different base version
        conflicts = self._detect_version_conflicts(patches, current_content, current_hash)
        if conflicts:
            return {
                "success": False,
                "patches": patches,
                "conflict": {
                    "file": file_path,
                    "type": "version_mismatch",
                    "details": conflicts
                }
            }
        
        # Apply patches sequentially with validation
        modified_content = current_content
        successful_patches = []
        
        for patch in patches:
            try:
                # Apply individual patch
                patch_content = patch.get("patch_content", "")
                logger.info(f"🔍 Applying patch to {file_path}:")
                logger.info(f"   Patch content length: {len(patch_content)}")
                logger.info(f"   Patch content preview: {patch_content[:200]}...")
                
                # Validate patch content
                if not patch_content or not patch_content.strip():
                    logger.error(f"❌ Patch content is empty for {file_path}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": "Patch content is empty"
                    }
                
                # Check for proper unified diff format
                if "--- " not in patch_content or "+++ " not in patch_content:
                    logger.error(f"❌ Patch content is not in unified diff format for {file_path}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": "Patch content is not in unified diff format"
                    }
                
                # Check for hunk headers
                if "@@" not in patch_content:
                    logger.error(f"❌ Patch content missing hunk headers for {file_path}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": "Patch content missing hunk headers"
                    }
                
                logger.info(f"✅ Patch content validation passed for {file_path}")
                
                result = self._apply_unified_diff(modified_content, patch_content)
                
                if result["success"]:
                    modified_content = result["content"]
                    successful_patches.append(patch)
                    logger.info(f"✅ Successfully applied patch to {file_path}")
                else:
                    logger.warning(f"❌ Failed to apply patch to {file_path}: {result['error']}")
                    return {
                        "success": False,
                        "patches": patches,
                        "error": result["error"]
                    }
                    
            except Exception as e:
                logger.error(f"💥 Exception applying patch to {file_path}: {e}")
                return {
                    "success": False,
                    "patches": patches,
                    "error": str(e)
                }
        
        # Validate the final result
        logger.info(f"🔍 Validating patched content for {file_path}")
        validation_result = self._validate_patched_content(modified_content, file_path)
        if not validation_result["valid"]:
            logger.error(f"❌ Content validation failed for {file_path}: {validation_result['error']}")
            return {
                "success": False,
                "patches": patches,
                "error": f"Validation failed: {validation_result['error']}"
            }
        
        logger.info(f"✅ Content validation passed for {file_path}")
        
        # Commit the changes to target branch
        commit_message = self._generate_commit_message(file_path, successful_patches)
        logger.info(f"🔧 Committing {len(successful_patches)} patches to {file_path} with message: {commit_message}")
        commit_success = await self.github_client.commit_file(
            file_path, modified_content, commit_message, branch_name
        )
        
        if not commit_success:
            logger.error(f"❌ Failed to commit changes to {branch_name} for {file_path}")
            return {
                "success": False,
                "patches": patches,
                "error": f"Failed to commit changes to {branch_name}"
            }
        
        logger.info(f"✅ Successfully committed {len(successful_patches)} patches to {file_path}")
        logger.info(f"🔍 Returning successful patches: {len(successful_patches)} patches")
        
        return {
            "success": True,
            "patches": successful_patches,
            "content": modified_content
        }
    
    def _apply_unified_diff(self, original_content: str, patch_content: str) -> Dict[str, Any]:
        """Apply a unified diff patch to content with proper parsing"""
        if not patch_content or not patch_content.strip():
            return {"success": False, "error": "Empty patch content"}
        
        try:
            logger.info(f"🔍 Applying unified diff patch")
            logger.info(f"   Original content length: {len(original_content)}")
            logger.info(f"   Patch content length: {len(patch_content)}")
            
            # Split content into lines for easier manipulation
            original_lines = original_content.splitlines(keepends=True)
            patch_lines = patch_content.splitlines()
            
            # Parse the unified diff format properly
            modified_lines = original_lines.copy()
            current_line = 0
            in_hunk = False
            hunk_start = 0
            hunk_old_count = 0
            hunk_new_count = 0
            
            for patch_line in patch_lines:
                # Skip git diff header lines (--- a/file, +++ b/file)
                if patch_line.startswith('--- ') or patch_line.startswith('+++ '):
                    logger.info(f"   Skipping git header: {patch_line}")
                    continue
                
                if patch_line.startswith('@@'):
                    # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                    match = re.match(r'@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@', patch_line)
                    if match:
                        old_start = int(match.group(1)) - 1  # Convert to 0-based indexing
                        hunk_old_count = int(match.group(2)) if match.group(2) else 1
                        new_start = int(match.group(3)) - 1  # Convert to 0-based indexing
                        hunk_new_count = int(match.group(4)) if match.group(4) else 1
                        
                        current_line = old_start
                        in_hunk = True
                        hunk_start = old_start
                        
                        logger.info(f"   Processing hunk: old_start={old_start}, old_count={hunk_old_count}, new_start={new_start}, new_count={hunk_new_count}")
                        continue
                
                if not in_hunk:
                    continue
                
                if patch_line.startswith(' '):
                    # Context line - verify it matches and advance
                    if current_line < len(modified_lines):
                        expected_line = modified_lines[current_line].rstrip('\n')
                        if expected_line != patch_line[1:]:
                            logger.error(f"❌ Context line mismatch at line {current_line}")
                            logger.error(f"   Expected: {expected_line}")
                            logger.error(f"   Found: {patch_line[1:]}")
                            return {"success": False, "error": f"Context line mismatch at line {current_line}"}
                    current_line += 1
                    
                elif patch_line.startswith('-'):
                    # Remove line
                    if current_line < len(modified_lines):
                        removed_line = modified_lines[current_line].rstrip('\n')
                        del modified_lines[current_line]
                        logger.info(f"   Removed line {current_line}: {removed_line}")
                    else:
                        logger.error(f"❌ Cannot remove line {current_line} - beyond file bounds")
                        return {"success": False, "error": f"Cannot remove line {current_line} - beyond file bounds"}
                        
                elif patch_line.startswith('+'):
                    # Add line - but skip if it's a git header line
                    if patch_line.startswith('+++ '):
                        logger.info(f"   Skipping git header in content: {patch_line}")
                        continue
                    
                    new_line = patch_line[1:] + '\n'
                    modified_lines.insert(current_line, new_line)
                    current_line += 1
                    logger.info(f"   Added line at position {current_line-1}: {new_line.rstrip()}")
            
            result_content = ''.join(modified_lines)
            logger.info(f"✅ Successfully applied unified diff patch")
            logger.info(f"   Result content length: {len(result_content)}")
            
            return {
                "success": True,
                "content": result_content
            }
            
        except Exception as e:
            logger.error(f"❌ Error applying unified diff: {e}")
            return {"success": False, "error": str(e)}
    
    def _detect_version_conflicts(self, patches: List[Dict], current_content: str, current_hash: str) -> List[Dict]:
        """Detect if patches are based on different file versions"""
        conflicts = []
        
        for patch in patches:
            expected_hash = patch.get("base_file_hash")
            if expected_hash and expected_hash != current_hash:
                conflicts.append({
                    "patch_id": patch.get("id"),
                    "expected_hash": expected_hash,
                    "current_hash": current_hash,
                    "target_file": patch.get("target_file")
                })
        
        return conflicts
    
    def _validate_patched_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """Validate that patched content is syntactically correct"""
        try:
            logger.info(f"🔍 Starting content validation for {file_path}")
            
            # Basic validation - check for common syntax issues
            if not content.strip():
                logger.error(f"❌ Content validation failed: File content is empty")
                return {"valid": False, "error": "File content is empty"}
            
            logger.info(f"✅ Basic content validation passed for {file_path}")
            
            # Python file validation
            if file_path.endswith('.py'):
                logger.info(f"🔍 Running Python syntax validation for {file_path}")
                try:
                    compile(content, file_path, 'exec')
                    logger.info(f"✅ Python syntax validation passed for {file_path}")
                except SyntaxError as e:
                    logger.error(f"❌ Python syntax validation failed for {file_path}: {e}")
                    return {"valid": False, "error": f"Python syntax error: {e}"}
            
            # JSON file validation
            elif file_path.endswith('.json'):
                logger.info(f"🔍 Running JSON syntax validation for {file_path}")
                import json
                try:
                    json.loads(content)
                    logger.info(f"✅ JSON syntax validation passed for {file_path}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON syntax validation failed for {file_path}: {e}")
                    return {"valid": False, "error": f"JSON syntax error: {e}"}
            
            logger.info(f"✅ All content validation passed for {file_path}")
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"❌ Unexpected error in content validation for {file_path}: {e}")
            return {"valid": False, "error": str(e)}
    
    def _group_patches_by_file(self, patches: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Group patches by target file for atomic operations"""
        grouped = {}
        for patch in patches:
            file_path = patch.get("target_file", "unknown")
            if file_path not in grouped:
                grouped[file_path] = []
            grouped[file_path].append(patch)
        return grouped
    
    def _generate_commit_message(self, file_path: str, patches: List[Dict]) -> str:
        """Generate descriptive commit message for patches"""
        if len(patches) == 1:
            patch = patches[0]
            return patch.get("commit_message", f"Fix applied to {file_path}")
        else:
            return f"Apply {len(patches)} fixes to {file_path}"
    
    async def create_smart_branch(self, base_branch: str, ticket_id: int) -> str:
        """Create a branch with intelligent naming - deprecated, use target branch directly"""
        logger.warning("⚠️ create_smart_branch is deprecated - using target branch directly")
        return self.target_branch
    
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
