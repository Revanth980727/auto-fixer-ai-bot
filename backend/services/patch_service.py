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
        """Apply patches to the configured target branch with intelligent conflict detection"""
        results = {
            "successful_patches": [],
            "failed_patches": [],
            "conflicts_detected": [],
            "files_modified": [],
            "target_branch": self.target_branch
        }
        
        logger.info(f"🔧 Applying {len(patches)} patches to branch: {self.target_branch}")
        
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
                
                if result["success"]:
                    results["successful_patches"].extend(result["patches"])
                    if file_path not in results["files_modified"]:
                        results["files_modified"].append(file_path)
                else:
                    results["failed_patches"].extend(result["patches"])
                    if result.get("conflict"):
                        results["conflicts_detected"].append(result["conflict"])
                        
            except Exception as e:
                logger.error(f"Error applying patches to {file_path}: {e}")
                for patch in file_patches:
                    results["failed_patches"].append({
                        "patch": patch,
                        "error": str(e)
                    })
        
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
                result = self._apply_unified_diff(modified_content, patch.get("patch_content", ""))
                
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
        validation_result = self._validate_patched_content(modified_content, file_path)
        if not validation_result["valid"]:
            return {
                "success": False,
                "patches": patches,
                "error": f"Validation failed: {validation_result['error']}"
            }
        
        # Commit the changes to target branch
        commit_message = self._generate_commit_message(file_path, successful_patches)
        commit_success = await self.github_client.commit_file(
            file_path, modified_content, commit_message, branch_name
        )
        
        if not commit_success:
            return {
                "success": False,
                "patches": patches,
                "error": f"Failed to commit changes to {branch_name}"
            }
        
        return {
            "success": True,
            "patches": successful_patches,
            "content": modified_content
        }
    
    def _apply_unified_diff(self, original_content: str, patch_content: str) -> Dict[str, Any]:
        """Apply a unified diff patch to content"""
        if not patch_content or not patch_content.strip():
            return {"success": False, "error": "Empty patch content"}
        
        try:
            # Parse the unified diff format
            lines = original_content.splitlines(keepends=True)
            patch_lines = patch_content.splitlines()
            
            # Simple unified diff parser
            current_line = 0
            modified_lines = lines.copy()
            
            for patch_line in patch_lines:
                if patch_line.startswith('@@'):
                    # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                    match = re.match(r'@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@', patch_line)
                    if match:
                        old_start = int(match.group(1)) - 1  # Convert to 0-based indexing
                        current_line = old_start
                elif patch_line.startswith('-'):
                    # Remove line
                    if current_line < len(modified_lines):
                        del modified_lines[current_line]
                elif patch_line.startswith('+'):
                    # Add line
                    new_line = patch_line[1:] + '\n'
                    modified_lines.insert(current_line, new_line)
                    current_line += 1
                elif patch_line.startswith(' '):
                    # Context line - advance pointer
                    current_line += 1
            
            return {
                "success": True,
                "content": ''.join(modified_lines)
            }
            
        except Exception as e:
            logger.error(f"Error applying unified diff: {e}")
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
            # Basic validation - check for common syntax issues
            if not content.strip():
                return {"valid": False, "error": "File content is empty"}
            
            # Python file validation
            if file_path.endswith('.py'):
                try:
                    compile(content, file_path, 'exec')
                except SyntaxError as e:
                    return {"valid": False, "error": f"Python syntax error: {e}"}
            
            # JSON file validation
            elif file_path.endswith('.json'):
                import json
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    return {"valid": False, "error": f"JSON syntax error: {e}"}
            
            return {"valid": True}
            
        except Exception as e:
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
        """Create a branch with intelligent naming"""
        branch_name = f"ai-fix-ticket-{ticket_id}-{hashlib.md5(str(ticket_id).encode()).hexdigest()[:8]}"
        
        success = await self.github_client.create_branch(branch_name, base_branch)
        if success:
            logger.info(f"Created smart branch: {branch_name}")
            return branch_name
        else:
            raise PatchApplicationError(f"Failed to create branch: {branch_name}")
    
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
