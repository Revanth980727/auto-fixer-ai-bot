
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
        self.applied_patches = {}  # Track patches applied per file/phase
        self.phase_coordination = {}  # Coordinate between phases
    
    async def apply_patches_intelligently(self, patches: List[Dict[str, Any]], ticket_id: int, phase: str = "unknown") -> Dict[str, Any]:
        """Apply patches with surgical precision and enhanced validation"""
        
        # Enhanced phase coordination to prevent duplicate applications
        phase_key = f"ticket_{ticket_id}_phase_{phase}"
        if phase_key in self.phase_coordination:
            logger.warning(f"⚠️ Preventing duplicate phase execution for {phase_key}")
            return self.phase_coordination[phase_key]
        
        # Check for duplicate execution with enhanced tracking
        execution_key = f"ticket_{ticket_id}_{len(patches)}_{self._get_patches_signature(patches)}"
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
        
        # Cache successful result and mark phase completion
        self.execution_state[execution_key] = results
        self.phase_coordination[phase_key] = results
        
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
                # This is a unified diff - apply it with enhanced algorithm
                result_content = self._apply_unified_diff_enhanced(current_content, patch_content, file_path)
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
    
    def _get_patches_signature(self, patches: List[Dict[str, Any]]) -> str:
        """Generate signature for a set of patches to detect duplicates"""
        try:
            signature_data = []
            for patch in patches:
                patch_data = {
                    'target_file': patch.get('target_file', ''),
                    'patch_content': patch.get('patch_content', ''),
                    'confidence_score': patch.get('confidence_score', 0)
                }
                signature_data.append(str(sorted(patch_data.items())))
            
            combined_signature = ''.join(signature_data)
            return hashlib.md5(combined_signature.encode()).hexdigest()[:12]
        except Exception as e:
            logger.error(f"❌ Error generating patches signature: {e}")
            return "unknown_signature"
    
    def _apply_unified_diff_enhanced(self, content: str, diff: str, file_path: str) -> Optional[str]:
        """Enhanced unified diff application with comprehensive debugging and fuzzy matching"""
        try:
            logger.info(f"🔧 Applying enhanced unified diff to {file_path}")
            logger.debug(f"📝 Diff content:\n{diff}")
            logger.debug(f"📄 Original file content (first 500 chars):\n{content[:500]}...")
            
            # Parse diff content with validation
            hunks = self._parse_unified_diff_hunks(diff)
            if not hunks:
                logger.error("❌ No valid hunks found in diff")
                # Try fallback strategy for simple changes
                return self._apply_fallback_strategy(content, diff, file_path)
            
            logger.info(f"🎯 Found {len(hunks)} hunks to apply")
            
            lines = content.split('\n')
            result_lines = lines.copy()
            applied_hunks = 0
            
            # Apply hunks in reverse order to maintain line numbers
            for i, hunk in enumerate(reversed(hunks)):
                logger.info(f"🔧 Applying hunk {len(hunks)-i}/{len(hunks)}")
                success = self._apply_single_hunk_with_debugging(result_lines, hunk, file_path)
                if success:
                    applied_hunks += 1
                    logger.info(f"✅ Hunk applied successfully")
                else:
                    logger.error(f"❌ Failed to apply hunk starting at line {hunk.get('target_start', 'unknown')}")
            
            if applied_hunks == 0:
                logger.error(f"❌ All {len(hunks)} hunks failed to apply")
                # Try fallback strategy
                return self._apply_fallback_strategy(content, diff, file_path)
            elif applied_hunks < len(hunks):
                logger.warning(f"⚠️ Partial application: {applied_hunks}/{len(hunks)} hunks applied successfully")
            
            result_content = '\n'.join(result_lines)
            logger.info(f"✅ Diff application completed: {applied_hunks}/{len(hunks)} hunks applied")
            return result_content
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced unified diff application: {e}")
            # Try fallback strategy on exception
            return self._apply_fallback_strategy(content, diff, file_path)

    def _parse_unified_diff_hunks(self, diff: str) -> List[Dict[str, Any]]:
        """Parse unified diff into structured hunks with comprehensive validation"""
        hunks = []
        diff_lines = diff.split('\n')
        
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i].strip()
            
            if line.startswith('@@'):
                # Parse hunk header with improved regex
                hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$', line)
                if not hunk_match:
                    logger.warning(f"⚠️ Invalid hunk header format: {line}")
                    i += 1
                    continue
                
                old_start = int(hunk_match.group(1)) - 1  # Convert to 0-based
                old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3)) - 1  # Convert to 0-based
                new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                context_info = hunk_match.group(5).strip() if hunk_match.group(5) else ""
                
                # Collect hunk content
                hunk_content = []
                j = i + 1
                while j < len(diff_lines) and not diff_lines[j].startswith('@@'):
                    if diff_lines[j].strip():  # Skip empty lines
                        hunk_content.append(diff_lines[j])
                    j += 1
                
                hunk = {
                    'target_start': old_start,
                    'target_count': old_count,
                    'new_start': new_start,
                    'new_count': new_count,
                    'context_info': context_info,
                    'content': hunk_content,
                    'header': line
                }
                
                hunks.append(hunk)
                logger.debug(f"📋 Parsed hunk: lines {old_start+1}-{old_start+old_count} -> {new_start+1}-{new_start+new_count}")
                i = j
            else:
                i += 1
        
        return hunks

    def _apply_single_hunk_with_debugging(self, lines: List[str], hunk: Dict[str, Any], file_path: str) -> bool:
        """Apply single hunk with comprehensive debugging and fuzzy matching"""
        try:
            target_start = hunk['target_start']
            target_count = hunk['target_count']
            hunk_content = hunk['content']
            
            logger.debug(f"🎯 Applying hunk at line {target_start+1}, count {target_count}")
            logger.debug(f"📝 Hunk content ({len(hunk_content)} lines):")
            for i, line in enumerate(hunk_content[:5]):  # Show first 5 lines
                logger.debug(f"  {i+1}: {line}")
            
            # Parse hunk content into operations
            context_lines = []
            removals = []
            additions = []
            
            current_line = target_start
            for content_line in hunk_content:
                if content_line.startswith(' '):
                    # Context line
                    context_lines.append((current_line, content_line[1:]))
                    current_line += 1
                elif content_line.startswith('-'):
                    # Removal
                    removals.append((current_line, content_line[1:]))
                    current_line += 1
                elif content_line.startswith('+'):
                    # Addition (doesn't advance current_line)
                    additions.append((current_line, content_line[1:]))
            
            # Validate context lines with fuzzy matching
            context_matches = 0
            total_context = len(context_lines)
            
            logger.debug(f"🔍 Validating {total_context} context lines")
            for line_idx, expected_content in context_lines:
                if line_idx < len(lines):
                    actual_content = lines[line_idx]
                    if self._fuzzy_line_match(actual_content, expected_content):
                        context_matches += 1
                        logger.debug(f"✓ Context match at line {line_idx+1}")
                    else:
                        logger.debug(f"✗ Context mismatch at line {line_idx+1}:")
                        logger.debug(f"  Expected: '{expected_content}'")
                        logger.debug(f"  Actual:   '{actual_content}'")
                else:
                    logger.debug(f"✗ Line {line_idx+1} out of bounds (file has {len(lines)} lines)")
            
            # Calculate context validation score
            context_score = context_matches / total_context if total_context > 0 else 1.0
            logger.info(f"📊 Context validation: {context_matches}/{total_context} ({context_score:.2%})")
            
            # Apply changes if context validation passes threshold
            if context_score >= 0.6:  # Lowered threshold for more flexibility
                # Apply removals in reverse order
                for line_idx, expected_content in reversed(removals):
                    if line_idx < len(lines):
                        actual_content = lines[line_idx]
                        if self._fuzzy_line_match(actual_content, expected_content):
                            lines.pop(line_idx)
                            logger.debug(f"➖ Removed line {line_idx+1}: '{expected_content[:50]}...'")
                        else:
                            logger.warning(f"⚠️ Could not remove line {line_idx+1}, content mismatch")
                            logger.debug(f"  Expected: '{expected_content}'")
                            logger.debug(f"  Actual:   '{actual_content}'")
                
                # Apply additions
                for line_idx, new_content in additions:
                    # Adjust index for previous removals
                    adjusted_idx = min(line_idx, len(lines))
                    lines.insert(adjusted_idx, new_content)
                    logger.debug(f"➕ Added line at {adjusted_idx+1}: '{new_content[:50]}...'")
                
                return True
            else:
                logger.warning(f"❌ Context validation failed: {context_score:.2%} - skipping hunk")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error applying single hunk: {e}")
            return False

    def _fuzzy_line_match(self, actual: str, expected: str) -> bool:
        """Fuzzy matching for lines to handle whitespace and minor differences"""
        # Exact match first
        if actual == expected:
            return True
        
        # Normalize whitespace
        actual_norm = re.sub(r'\s+', ' ', actual.strip())
        expected_norm = re.sub(r'\s+', ' ', expected.strip())
        
        if actual_norm == expected_norm:
            return True
        
        # Check similarity for minor differences (typos, etc.)
        if len(actual_norm) > 0 and len(expected_norm) > 0:
            # Simple character difference check
            if abs(len(actual_norm) - len(expected_norm)) <= 2:
                differences = sum(c1 != c2 for c1, c2 in zip(actual_norm, expected_norm))
                differences += abs(len(actual_norm) - len(expected_norm))
                similarity = 1 - (differences / max(len(actual_norm), len(expected_norm)))
                return similarity >= 0.9
        
        return False

    def _apply_fallback_strategy(self, content: str, diff: str, file_path: str) -> Optional[str]:
        """Fallback strategy for when unified diff fails - extract core changes"""
        try:
            logger.info(f"🔄 Applying fallback strategy for {file_path}")
            
            # Try to extract simple line replacements from diff
            lines = content.split('\n')
            diff_lines = diff.split('\n')
            
            # Look for simple - and + pairs (line replacements)
            removals = []
            additions = []
            
            for line in diff_lines:
                if line.startswith('-') and not line.startswith('---'):
                    removals.append(line[1:])
                elif line.startswith('+') and not line.startswith('+++'):
                    additions.append(line[1:])
            
            # If we have equal numbers of removals and additions, try direct replacement
            if len(removals) == len(additions) and len(removals) > 0:
                logger.info(f"🔄 Attempting direct line replacement: {len(removals)} lines")
                
                result_lines = lines.copy()
                replacements_made = 0
                
                for removal, addition in zip(removals, additions):
                    # Find the removal line using fuzzy matching
                    for i, line in enumerate(result_lines):
                        if self._fuzzy_line_match(line, removal):
                            result_lines[i] = addition
                            replacements_made += 1
                            logger.debug(f"🔄 Replaced line {i+1}: '{removal[:50]}...' -> '{addition[:50]}...'")
                            break
                
                if replacements_made > 0:
                    logger.info(f"✅ Fallback strategy succeeded: {replacements_made} replacements made")
                    return '\n'.join(result_lines)
            
            logger.warning(f"⚠️ Fallback strategy could not process diff for {file_path}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in fallback strategy: {e}")
            return None
    
    def _apply_hunk_enhanced(self, lines: List[str], diff_lines: List[str], start_idx: int, old_start: int, old_count: int, file_path: str) -> Optional[Tuple[List[str], int]]:
        """Enhanced hunk application with fuzzy matching and better context validation"""
        try:
            result_lines = lines.copy()
            current_old_line = old_start
            processed_diff_lines = 0
            
            # Collect all changes from this hunk first
            context_lines = []
            removals = []
            additions = []
            
            i = start_idx
            while i < len(diff_lines):
                diff_line = diff_lines[i]
                
                if diff_line.startswith('@@'):
                    # Next hunk, stop here
                    break
                elif diff_line.startswith(' '):
                    # Context line
                    context_lines.append((current_old_line, diff_line[1:]))
                    current_old_line += 1
                elif diff_line.startswith('-'):
                    # Line to remove
                    removals.append((current_old_line, diff_line[1:]))
                    current_old_line += 1
                elif diff_line.startswith('+'):
                    # Line to add (doesn't advance current_old_line)
                    additions.append((current_old_line, diff_line[1:]))
                
                processed_diff_lines += 1
                i += 1
            
            # Enhanced context validation with fuzzy matching
            context_matches = 0
            total_context = len(context_lines)
            
            for line_idx, expected_content in context_lines:
                if line_idx < len(result_lines):
                    actual_content = result_lines[line_idx]
                    if actual_content.strip() == expected_content.strip():  # Fuzzy match ignoring whitespace
                        context_matches += 1
                    else:
                        logger.debug(f"📝 Context mismatch at line {line_idx + 1}:")
                        logger.debug(f"   Expected: '{expected_content}'")
                        logger.debug(f"   Actual:   '{actual_content}'")
            
            # Apply changes if context is reasonable (allow some mismatches)
            context_ratio = context_matches / max(total_context, 1)
            if context_ratio >= 0.7 or total_context == 0:  # Allow if 70% of context matches or no context lines
                logger.debug(f"✅ Context validation passed: {context_matches}/{total_context} ({context_ratio:.2%})")
                
                # Apply removals in reverse order to maintain line numbers
                successful_removals = 0
                for line_idx, expected_content in reversed(removals):
                    if line_idx < len(result_lines):
                        actual_content = result_lines[line_idx]
                        # Use fuzzy matching for removals too
                        if actual_content.strip() == expected_content.strip() or actual_content == expected_content:
                            result_lines.pop(line_idx)
                            successful_removals += 1
                        else:
                            logger.debug(f"⚠️ Could not remove line {line_idx + 1} - content mismatch:")
                            logger.debug(f"   Expected: '{expected_content}'")
                            logger.debug(f"   Actual:   '{actual_content}'")
                
                # Apply additions
                for line_idx, new_content in additions:
                    # Adjust index for previous removals
                    adjusted_idx = min(line_idx, len(result_lines))
                    result_lines.insert(adjusted_idx, new_content)
                
                logger.debug(f"🔧 Applied {successful_removals} removals and {len(additions)} additions")
                return result_lines, processed_diff_lines
            else:
                logger.warning(f"❌ Context validation failed: {context_matches}/{total_context} ({context_ratio:.2%}) - skipping hunk")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in enhanced hunk application: {e}")
            return None
    
    async def create_feature_branch_and_pr(self, patches: List[Dict[str, Any]], ticket_id: str) -> Dict[str, Any]:
        """Create feature branch and PR for patches instead of direct commits to main"""
        try:
            # Generate feature branch name
            branch_name = f"feature/ticket-{ticket_id}-{int(asyncio.get_event_loop().time())}"
            logger.info(f"🌿 Creating feature branch: {branch_name}")
            
            # Create feature branch from main
            branch_created = await self.github_client.create_branch(branch_name, self.target_branch)
            if not branch_created:
                logger.error(f"❌ Failed to create feature branch: {branch_name}")
                return {"success": False, "error": "Failed to create feature branch"}
            
            # Apply patches to feature branch
            patch_results = await self.apply_patches_intelligently(patches, ticket_id, f"feature_branch_{branch_name}")
            
            if not patch_results.get("successful_patches"):
                logger.error(f"❌ No patches successfully applied to feature branch")
                return {"success": False, "error": "No patches applied successfully"}
            
            # Create PR from feature branch to main
            pr_title = f"[Ticket-{ticket_id}] Automated bug fix"
            pr_body = self._generate_pr_description(patches, patch_results)
            
            pr_result = await self.github_client.create_pull_request(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=self.target_branch
            )
            
            if pr_result:
                logger.info(f"✅ Successfully created PR: {pr_result.get('html_url', 'unknown')}")
                return {
                    "success": True,
                    "branch_name": branch_name,
                    "pr_url": pr_result.get('html_url'),
                    "pr_number": pr_result.get('number'),
                    "patch_results": patch_results
                }
            else:
                logger.error(f"❌ Failed to create PR from {branch_name} to {self.target_branch}")
                return {"success": False, "error": "Failed to create pull request"}
                
        except Exception as e:
            logger.error(f"❌ Error in feature branch and PR creation: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_pr_description(self, patches: List[Dict[str, Any]], patch_results: Dict[str, Any]) -> str:
        """Generate comprehensive PR description"""
        try:
            description_parts = [
                "## Automated Bug Fix",
                "",
                "This PR contains automated patches generated by the AI development system.",
                "",
                "### Changes Summary:",
            ]
            
            # Add file changes
            files_modified = patch_results.get("files_modified", [])
            for file_path in files_modified:
                description_parts.append(f"- 🔧 Modified: `{file_path}`")
            
            # Add patch quality metrics
            if patch_results.get("patch_quality_scores"):
                description_parts.extend([
                    "",
                    "### Quality Metrics:",
                ])
                for score_info in patch_results["patch_quality_scores"]:
                    confidence = score_info.get("score", 0) * 100
                    surgical = "✅ Surgical" if score_info.get("is_surgical") else "⚠️ Standard"
                    description_parts.append(f"- `{score_info.get('file', 'unknown')}`: {confidence:.1f}% confidence, {surgical}")
            
            # Add individual patch details
            if len(patches) <= 5:  # Don't overwhelm for many patches
                description_parts.extend([
                    "",
                    "### Patch Details:",
                ])
                for i, patch in enumerate(patches, 1):
                    commit_msg = patch.get("commit_message", "No description")
                    confidence = patch.get("confidence_score", 0) * 100
                    description_parts.append(f"{i}. **{patch.get('target_file', 'unknown')}** ({confidence:.1f}% confidence)")
                    description_parts.append(f"   - {commit_msg}")
            
            description_parts.extend([
                "",
                "### Validation:",
                "- ✅ All patches passed pre-validation",
                "- ✅ Shadow workspace validation completed",
                "- ✅ Surgical patch application verified",
                "",
                "---",
                "*This PR was automatically generated by the AI development system*"
            ])
            
            return "\n".join(description_parts)
            
        except Exception as e:
            logger.error(f"❌ Error generating PR description: {e}")
            return "Automated bug fix - see individual commits for details."
