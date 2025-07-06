
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from services.github_client import GitHubClient
from services.diff_presenter import DiffPresenter
from services.patch_validator import PatchValidator
from services.shadow_workspace_manager import ShadowWorkspaceManager
from core.websocket_manager import WebSocketManager
from core.config import config
import logging
import asyncio

logger = logging.getLogger(__name__)

class PatchApplicationError(Exception):
    """Custom exception for patch application errors"""
    pass

class PatchService:
    def __init__(self):
        self.github_client = GitHubClient()
        self.target_branch = config.github_target_branch
        self.diff_presenter = DiffPresenter()
        self.validator = PatchValidator()
        self.shadow_manager = ShadowWorkspaceManager()
        self.websocket_manager = WebSocketManager()
        self.max_safe_hunk_size = 50  # Reject patches with hunks larger than this
        self.approval_cache = {}  # Cache for approval decisions
        self.execution_state = {}  # Track patch execution to prevent duplicates
    
    async def apply_patches_intelligently(self, patches: List[Dict[str, Any]], ticket_id: int) -> Dict[str, Any]:
        """Apply patches with surgical precision and enhanced validation"""
        # Check for duplicate execution
        execution_key = f"ticket_{ticket_id}_{len(patches)}"
        if execution_key in self.execution_state:
            logger.warning(f"⚠️ Preventing duplicate execution for {execution_key}")
            return self.execution_state[execution_key]
        
        results = {
            "successful_patches": [],
            "failed_patches": [],
            "conflicts_detected": [],
            "files_modified": [],
            "target_branch": self.target_branch,
            "patch_quality_scores": [],
            "validation_failures": []
        }
        
        # Mark execution as in progress
        self.execution_state[execution_key] = {"status": "in_progress", "start_time": asyncio.get_event_loop().time()}
        
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
            error_result = {
                **results,
                "error": "All patches failed pre-validation for safety",
                "all_patches_rejected": True
            }
            self.execution_state[execution_key] = error_result
            return error_result
        
        logger.info(f"✅ {len(validated_patches)} patches passed pre-validation")
        
        # Validate target branch exists
        if not await self._validate_target_branch():
            logger.error(f"❌ Target branch {self.target_branch} not accessible")
            error_result = {
                **results,
                "error": f"Target branch {self.target_branch} not accessible",
                "branch_validation_failed": True
            }
            self.execution_state[execution_key] = error_result
            return error_result
        
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
        
        # Cache successful result
        self.execution_state[execution_key] = results
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
        """Apply patches using shadow workspace validation and interactive approval flow"""
        logger.info(f"🔧 Starting shadow workspace validation for {file_path}")
        
        # Get current file content
        current_content = await self.github_client.get_file_content(file_path, branch_name)
        if current_content is None:
            logger.warning(f"⚠️ File {file_path} not found on branch {branch_name}")
            return {
                "success": False,
                "patches": patches,
                "error": f"File {file_path} not found"
            }
        
        # Process all patches and validate in shadow workspace
        successful_patches = []
        final_content = current_content
        processed_patch_ids = set()  # Prevent duplicate processing
        
        for patch in patches:
            try:
                # Check for duplicate processing
                patch_id = self._get_patch_id(patch)
                if patch_id in processed_patch_ids:
                    logger.info(f"⏭️ Skipping duplicate patch: {patch_id}")
                    continue
                processed_patch_ids.add(patch_id)
                
                # Validate patch has required fields
                if not self._validate_patch_fields(patch):
                    logger.error(f"❌ Patch validation failed for {file_path}")
                    continue
                
                # Apply patch surgically using diff content
                patch_result = await self._apply_single_patch(final_content, patch, file_path)
                if not patch_result['success']:
                    logger.error(f"❌ Patch application failed: {patch_result['error']}")
                    continue
                
                # Create shadow workspace for validation
                workspace_id = await self.shadow_manager.create_shadow_workspace(
                    file_path, final_content, patch_result['content']
                )
                logger.info(f"🏗️ Created shadow workspace: {workspace_id}")
                
                # Run validation in shadow workspace
                validation_result = await self.shadow_manager.validate_in_shadow(
                    workspace_id, patch
                )
                
                if not validation_result['success']:
                    logger.error(f"❌ Shadow validation failed for {file_path}: {validation_result.get('error')}")
                    await self.shadow_manager.cleanup_workspace(workspace_id)
                    continue
                
                logger.info(f"✅ Shadow validation passed: {validation_result['recommendation']}")
                
                # Generate diff for interactive approval
                diff_data = await self.shadow_manager.get_diff_for_approval(workspace_id)
                
                if not diff_data or not diff_data['requires_approval']:
                    logger.info(f"⚠️ No changes requiring approval for {file_path}")
                    await self.shadow_manager.cleanup_workspace(workspace_id)
                    continue
                
                # Determine approval strategy based on confidence
                approval_decision = await self._determine_approval_strategy(
                    workspace_id, diff_data, patch
                )
                
                if approval_decision == 'approved':
                    logger.info(f"✅ Patch approved for {file_path}")
                    final_content = patch_result['content']  # Apply the surgically modified content
                    successful_patches.append(patch)
                    
                    # Broadcast approval result
                    await self.websocket_manager.broadcast_approval_result(
                        workspace_id, 'approved', {
                            'file_path': file_path,
                            'timestamp': asyncio.get_event_loop().time()
                        }
                    )
                else:
                    logger.info(f"❌ Patch rejected for {file_path}: {approval_decision}")
                
                # Cleanup shadow workspace
                await self.shadow_manager.cleanup_workspace(workspace_id)
                
            except Exception as e:
                logger.error(f"💥 Exception processing patch for {file_path}: {e}")
                continue
        
        if not successful_patches:
            logger.warning(f"⚠️ No patches were approved for {file_path}")
            return {
                "success": False,
                "patches": patches,
                "error": "No patches were approved"
            }
        
        # Commit the approved changes
        commit_message = self._generate_surgical_commit_message(file_path, successful_patches)
        logger.info(f"🔧 Committing approved changes to {file_path}")
        commit_success = await self.github_client.commit_file(
            file_path, final_content, commit_message, branch_name
        )
        
        if not commit_success:
            logger.error(f"❌ Failed to commit approved changes to {branch_name} for {file_path}")
            return {
                "success": False,
                "patches": patches,
                "error": f"Failed to commit approved changes to {branch_name}"
            }
        
        logger.info(f"✅ Successfully committed approved patches to {file_path}")
        
        return {
            "success": True,
            "patches": successful_patches,
            "content": final_content,
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
    
    async def _request_interactive_approval(self, workspace_id: str, diff_data: Dict[str, Any], patch: Dict[str, Any]) -> str:
        """Request interactive approval for patch and wait for decision"""
        try:
            # Create approval request
            approval_request = {
                'workspace_id': workspace_id,
                'file_path': diff_data['file_path'],
                'diff_data': diff_data['diff_data'],
                'patch_summary': {
                    'confidence_score': patch.get('confidence_score', 0.5),
                    'patch_type': patch.get('patch_type', 'unknown'),
                    'processing_strategy': patch.get('processing_strategy', 'unknown')
                },
                'approval_options': ['approve', 'reject', 'modify'],
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Store in approval cache
            self.approval_cache[workspace_id] = {
                'status': 'pending',
                'request_time': asyncio.get_event_loop().time()
            }
            
            # Broadcast approval request via WebSocket
            await self.websocket_manager.broadcast_approval_request(
                workspace_id, approval_request
            )
            
            logger.info(f"📤 Sent interactive approval request for {diff_data['file_path']}")
            
            # Wait for approval decision (with timeout)
            timeout = 300  # 5 minutes timeout
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                if workspace_id in self.approval_cache:
                    cache_entry = self.approval_cache[workspace_id]
                    if cache_entry['status'] != 'pending':
                        decision = cache_entry['status']
                        # Clean up cache
                        del self.approval_cache[workspace_id]
                        return decision
                
                # Check every second
                await asyncio.sleep(1)
            
            # Timeout - default to reject
            logger.warning(f"⏰ Approval timeout for {diff_data['file_path']} - defaulting to reject")
            if workspace_id in self.approval_cache:
                del self.approval_cache[workspace_id]
            return 'timeout_reject'
            
        except Exception as e:
            logger.error(f"❌ Error in interactive approval: {e}")
            return 'error_reject'
    
    async def _determine_approval_strategy(self, workspace_id: str, diff_data: Dict[str, Any], patch: Dict[str, Any]) -> str:
        """Determine whether to auto-approve or request interactive approval"""
        try:
            confidence_score = patch.get('confidence_score', 0.0)
            patch_type = patch.get('patch_type', 'unknown')
            file_path = diff_data.get('file_path', 'unknown')
            
            # Auto-approve high-confidence, simple patches
            if confidence_score >= 0.9 and patch_type in ['import_fix', 'syntax_fix', 'small_change']:
                logger.info(f"🤖 Auto-approving high-confidence patch for {file_path} (confidence: {confidence_score})")
                return 'approved'
            
            # Auto-approve medium-confidence patches for specific file types
            elif confidence_score >= 0.7 and file_path.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                logger.info(f"🤖 Auto-approving medium-confidence code patch for {file_path} (confidence: {confidence_score})")
                return 'approved'
            
            # For lower confidence or complex changes, request interactive approval
            else:
                logger.info(f"👤 Requesting interactive approval for {file_path} (confidence: {confidence_score})")
                return await self._request_interactive_approval(workspace_id, diff_data, patch)
                
        except Exception as e:
            logger.error(f"❌ Error in approval strategy determination: {e}")
            # Default to interactive approval on error
            return await self._request_interactive_approval(workspace_id, diff_data, patch)
    
    def set_approval_decision(self, workspace_id: str, decision: str) -> bool:
        """Set approval decision for a workspace (called by API endpoint)"""
        if workspace_id in self.approval_cache:
            self.approval_cache[workspace_id]['status'] = decision
            self.approval_cache[workspace_id]['decision_time'] = asyncio.get_event_loop().time()
            logger.info(f"✅ Approval decision set for {workspace_id}: {decision}")
            return True
        return False
    
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
    
    def _get_patch_id(self, patch: Dict[str, Any]) -> str:
        """Generate unique ID for patch to prevent duplicates"""
        content = f"{patch.get('target_file', '')}{patch.get('patch_content', '')}{patch.get('patched_code', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _validate_patch_fields(self, patch: Dict[str, Any]) -> bool:
        """Validate patch has required fields"""
        required_fields = ["target_file", "patch_content"]
        for field in required_fields:
            if not patch.get(field):
                logger.error(f"❌ Missing required field '{field}' in patch")
                return False
        
        # Add default commit message if missing
        if not patch.get("commit_message"):
            patch["commit_message"] = f"Apply surgical fix to {patch['target_file']}"
            logger.info(f"✅ Added default commit message for {patch['target_file']}")
        
        return True
    
    async def _apply_single_patch(self, current_content: str, patch: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Apply a single patch surgically using diff content"""
        try:
            patch_content = patch.get("patch_content", "")
            if not patch_content:
                return {"success": False, "error": "No patch_content provided"}
            
            # For now, if patch_content looks like unified diff, use it
            # Otherwise fall back to patched_code (for backward compatibility)
            if patch_content.startswith("@@") or "---" in patch_content or "+++" in patch_content:
                # This is a unified diff - apply it properly
                result_content = self._apply_unified_diff(current_content, patch_content)
                if result_content is None:
                    return {"success": False, "error": "Failed to apply unified diff"}
                return {"success": True, "content": result_content}
            else:
                # Fallback: use patched_code but validate it's reasonable
                patched_code = patch.get("patched_code", "")
                if not patched_code:
                    return {"success": False, "error": "No patched_code provided"}
                
                # Safety check: patched_code should not be drastically different in size
                size_diff = abs(len(patched_code) - len(current_content))
                if size_diff > len(current_content) * 2:  # More than 200% size change
                    logger.warning(f"⚠️ Large size change detected for {file_path}: {size_diff} characters")
                
                return {"success": True, "content": patched_code}
                
        except Exception as e:
            logger.error(f"❌ Error applying patch: {e}")
            return {"success": False, "error": str(e)}
    
    def _apply_unified_diff(self, content: str, diff: str) -> Optional[str]:
        """Apply unified diff to content with proper hunk-based processing"""
        try:
            lines = content.split('\n')
            diff_lines = diff.split('\n')
            result_lines = lines.copy()
            
            i = 0
            while i < len(diff_lines):
                line = diff_lines[i]
                
                if line.startswith('@@'):
                    # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                    hunk_match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                    if not hunk_match:
                        logger.warning(f"⚠️ Invalid hunk header: {line}")
                        i += 1
                        continue
                    
                    old_start = int(hunk_match.group(1)) - 1  # Convert to 0-based
                    old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                    new_start = int(hunk_match.group(3)) - 1  # Convert to 0-based
                    
                    # Process the hunk
                    hunk_result = self._apply_hunk(result_lines, diff_lines, i + 1, old_start, old_count)
                    if hunk_result:
                        result_lines, processed_lines = hunk_result
                        i += processed_lines + 1  # Skip processed diff lines
                    else:
                        logger.error(f"❌ Failed to apply hunk starting at line {old_start + 1}")
                        return None
                else:
                    i += 1
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            logger.error(f"❌ Error applying unified diff: {e}")
            return None
    
    def _apply_hunk(self, lines: List[str], diff_lines: List[str], start_idx: int, old_start: int, old_count: int) -> Optional[Tuple[List[str], int]]:
        """Apply a single hunk to the lines"""
        try:
            result_lines = lines.copy()
            current_old_line = old_start
            processed_diff_lines = 0
            
            # Collect changes from this hunk
            removals = []
            additions = []
            
            i = start_idx
            while i < len(diff_lines):
                diff_line = diff_lines[i]
                
                if diff_line.startswith('@@'):
                    # Next hunk, stop here
                    break
                elif diff_line.startswith(' '):
                    # Context line - verify it matches
                    expected_line = diff_line[1:]
                    if current_old_line < len(result_lines) and result_lines[current_old_line] == expected_line:
                        current_old_line += 1
                    else:
                        logger.warning(f"⚠️ Context mismatch at line {current_old_line + 1}")
                elif diff_line.startswith('-'):
                    # Line to remove
                    removals.append((current_old_line, diff_line[1:]))
                    current_old_line += 1
                elif diff_line.startswith('+'):
                    # Line to add
                    additions.append((current_old_line, diff_line[1:]))
                
                processed_diff_lines += 1
                i += 1
            
            # Apply removals in reverse order to maintain line numbers
            for line_idx, expected_content in reversed(removals):
                if line_idx < len(result_lines) and result_lines[line_idx] == expected_content:
                    result_lines.pop(line_idx)
                else:
                    logger.warning(f"⚠️ Could not find expected line to remove at {line_idx + 1}: {expected_content[:50]}...")
            
            # Apply additions
            for line_idx, new_content in additions:
                # Adjust index for previous removals
                adjusted_idx = min(line_idx, len(result_lines))
                result_lines.insert(adjusted_idx, new_content)
            
            return result_lines, processed_diff_lines
            
        except Exception as e:
            logger.error(f"❌ Error applying hunk: {e}")
            return None
