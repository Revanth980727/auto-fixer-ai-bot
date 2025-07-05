from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from services.github_client import GitHubClient
from services.json_response_handler import JSONResponseHandler
from services.semantic_evaluator import SemanticEvaluator
from services.semantic_patcher import SemanticPatcher
from .developer_agent_helpers import create_semantic_patch_prompt
from services.patch_validator import PatchValidator
from typing import Dict, Any, Optional
import json
import asyncio
import logging
import hashlib

logger = logging.getLogger(__name__)

class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.DEVELOPER)
        self.openai_client = OpenAIClient()
        self.github_client = GitHubClient()
        self.json_handler = JSONResponseHandler()
        self.semantic_evaluator = SemanticEvaluator()
        self.semantic_patcher = SemanticPatcher()
        self.patch_validator = PatchValidator()
        self.max_hunk_size = 30  # Stricter size limit
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate minimal, focused code patches with enhanced validation"""
        self.log_execution(execution_id, "🚀 Starting minimal change developer agent")
        
        if not context:
            self.log_execution(execution_id, "❌ No context provided - developer agent requires planner analysis")
            raise Exception("Developer agent requires context with planner analysis")
        
        if context.get("github_access_failed"):
            self.log_execution(execution_id, "❌ GitHub access failed - cannot generate patches without source code")
            raise Exception("GitHub repository access required for patch generation")
        
        planner_data = context.get("planner_analysis", {})
        source_files = context.get("source_files", [])
        
        if not source_files:
            self.log_execution(execution_id, "❌ No source files available - cannot generate patches")
            raise Exception("No source files available for patch generation")
        
        self.log_execution(execution_id, f"📁 Processing {len(source_files)} files with minimal change strategy")
        
        # Generate minimal patches with validation orchestrator integration
        patches = []
        total_files = len(source_files)
        processing_stats = {
            "total_patches_generated": 0,
            "patches_accepted": 0,
            "patches_rejected": 0,
            "patches_rejected_for_size": 0,
            "files_with_no_relevant_fixes": 0,
            "truly_minimal_changes": 0,
            "validation_rejections": 0
        }
        
        # Initialize validation orchestrator
        from services.validation_orchestrator import ValidationOrchestrator
        validator = ValidationOrchestrator()
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Processing file {i}/{total_files}: {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                file_size = len(file_info['content'])
                timeout = 300.0  # Reduced timeout for focused changes
                
                self.log_execution(execution_id, f"⏱️ Setting timeout to {timeout}s for minimal changes")
                
                # Use direct semantic processing - no chunking
                patch_data = await asyncio.wait_for(
                    self._generate_semantic_patch(ticket, file_info, planner_data, execution_id),
                    timeout=timeout
                )
                
                if patch_data:
                    # Validate patch with validation orchestrator
                    validation_passed = await self._validate_with_orchestrator(
                        patch_data, file_info, validator, execution_id
                    )
                    
                    if validation_passed and self._validate_patch_size(patch_data, execution_id):
                        patches.append(patch_data)
                        await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                        
                        processing_stats["total_patches_generated"] += 1
                        processing_stats["patches_accepted"] += 1
                        
                        # Track minimal changes
                        lines_modified = patch_data.get("lines_modified", 0)
                        if isinstance(lines_modified, (int, str)) and str(lines_modified).isdigit() and int(lines_modified) <= 10:
                            processing_stats["truly_minimal_changes"] += 1
                        
                        self.log_execution(execution_id, f"✅ Accepted minimal patch for {file_info['path']} ({lines_modified} lines)")
                    elif not validation_passed:
                        processing_stats["validation_rejections"] += 1
                        self.log_execution(execution_id, f"❌ Rejected patch for {file_info['path']} - validation failed")
                    else:
                        processing_stats["patches_rejected_for_size"] += 1
                        self.log_execution(execution_id, f"❌ Rejected patch for {file_info['path']} - too large")
                else:
                    processing_stats["files_with_no_relevant_fixes"] += 1
                    processing_stats["patches_rejected"] += 1
                    self.log_execution(execution_id, f"⚠️ No minimal fixes found for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                processing_stats["patches_rejected"] += 1
                self.log_execution(execution_id, f"⏰ TIMEOUT: Minimal patch generation for {file_info['path']} exceeded timeout")
                continue
            except Exception as e:
                processing_stats["patches_rejected"] += 1
                self.log_execution(execution_id, f"💥 ERROR: Exception generating minimal patch for {file_info['path']}: {str(e)}")
                continue
        
        if not patches:
            self.log_execution(execution_id, "💥 CRITICAL: No minimal patches generated")
            raise Exception("No minimal patches were generated - all fixes were rejected for being too large or irrelevant")
        
        # Log minimal change summary
        self.log_execution(execution_id, f"🔧 MINIMAL CHANGE SUMMARY:")
        self.log_execution(execution_id, f"  - Files processed: {total_files}")
        self.log_execution(execution_id, f"  - Patches generated: {processing_stats['total_patches_generated']}")
        self.log_execution(execution_id, f"  - Truly minimal changes: {processing_stats['truly_minimal_changes']}")
        self.log_execution(execution_id, f"  - Rejected for size: {processing_stats['patches_rejected_for_size']}")
        self.log_execution(execution_id, f"  - Files with no relevant fixes: {processing_stats['files_with_no_relevant_fixes']}")
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data,
            
            # Enhanced validation flags
            "minimal_change_approach": True,
            "size_validation_enabled": True,
            "enhanced_prompting": True,
            
            "processing_summary": f"Generated {len(patches)} minimal patches from {total_files} files",
            "processing_stats": processing_stats,
            "validation_thresholds": {
                "max_hunk_size": self.max_hunk_size,
                "confidence_threshold": self.semantic_evaluator.confidence_threshold
            }
        }
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} minimal patches")
        return result
    
    async def _generate_semantic_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate semantic patch using AST-based targeting - no chunking logic"""
        file_size = len(file_info['content'])
        self.log_execution(execution_id, f"🎯 SEMANTIC PROCESSING: {file_info['path']} ({file_size} chars)")
        return await self._generate_minimal_single_patch(ticket, file_info, analysis, execution_id)
    
    async def _generate_minimal_single_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch for a single file with strict size limits"""
        try:
            self.log_execution(execution_id, f"📝 Starting surgical patch generation for {file_info['path']}")
            
            # Use semantic approach for targeted fixes
            targets = self.semantic_patcher.identify_target_nodes(
                file_info['content'], 
                f"{ticket.description} {ticket.error_trace or ''}"
            )
            
            if not targets:
                self.log_execution(execution_id, f"⚠️ No semantic targets found for {file_info['path']}")
                return None
            
            # Generate patch for primary target
            patch_prompt = create_semantic_patch_prompt(ticket, file_info, targets[0])
            
            # Enhanced system prompt for minimal changes with strict JSON requirements
            system_prompt = f"""You are an expert at making SURGICAL code fixes. Your goal is to modify the ABSOLUTE MINIMUM necessary to fix the issue.

CRITICAL CONSTRAINTS:
- Never modify more than {self.max_hunk_size} lines unless absolutely critical
- Preserve ALL existing imports, class definitions, and function signatures
- Fix ONLY the specific error mentioned in the ticket
- Do NOT refactor, reorganize, or "improve" code beyond fixing the issue
- If the issue requires a large change, break it into the smallest possible modification

FORBIDDEN ACTIONS:
- Rewriting entire functions unless they are completely broken
- Adding new imports unless essential for the fix  
- Changing code style or formatting
- Modifying unrelated code sections
- Creating wholesale replacements

RESPONSE FORMAT REQUIREMENTS:
- Return ONLY valid JSON, no markdown formatting or explanations
- Use MINIMAL patch_content (unified diff format, only changed lines)
- Keep patched_code brief - show only the modified section, not entire files
- NEVER include full file content in responses
- Focus on the specific lines that need to change

JSON RESPONSE REQUIREMENTS:
You MUST respond with ONLY a valid JSON object containing these exact fields:
{{
  "patch_content": "unified diff format patch - MINIMAL, only changed lines",
  "patched_code": "ONLY the modified section/function, NOT the entire file", 
  "explanation": "one sentence explanation of the fix",
  "confidence_score": 0.95,
  "lines_modified": 1,
  "commit_message": "fix: brief commit message"
}}

CRITICAL: 
- patched_code should contain ONLY the modified function/class/section, NOT the entire file
- patch_content should be a minimal unified diff showing only what changed
- Keep responses under 2000 characters total
- Do not include any text before or after the JSON. The JSON must be valid and parseable."""
            
            self.log_execution(execution_id, f"🤖 Sending surgical change request for {file_info['path']}")
            
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": patch_prompt}
            ], model="gpt-4o-mini", force_json=True)
            
            # Parse response
            patch_data, error = self.json_handler.clean_and_parse_json(response, file_info['path'])
            
            if patch_data is None:
                self.log_execution(execution_id, f"❌ JSON parsing failed for {file_info['path']}: {error}")
                return None
            
            # Validate patch data structure
            is_valid, validation_error = self.json_handler.validate_patch_json(patch_data)
            if not is_valid:
                self.log_execution(execution_id, f"❌ Patch validation failed for {file_info['path']}: {validation_error}")
                return None
            
            # Pre-validate patch content
            pre_valid, pre_error = self.patch_validator.validate_pre_application(patch_data)
            if not pre_valid:
                self.log_execution(execution_id, f"❌ Pre-application validation failed for {file_info['path']}: {pre_error}")
                return None
            
            # Perform semantic evaluation
            jira_context = {
                'title': ticket.title,
                'description': ticket.description,
                'error_trace': ticket.error_trace or ''
            }
            
            evaluation = await self.semantic_evaluator.evaluate_patch_relevance(patch_data, jira_context)
            should_accept, reason = self.semantic_evaluator.should_accept_patch(patch_data, evaluation)
            
            if not should_accept:
                self.log_execution(execution_id, f"❌ Semantic evaluation rejected patch for {file_info['path']}: {reason}")
                return None
            
            # Ensure all required fields are present
            patch_data.update({
                "target_file": file_info["path"],
                "file_size": len(file_info["content"]),
                "processing_strategy": "surgical_single_file",
                "semantic_evaluation": evaluation,
                "selection_reason": reason,
                "confidence_score": patch_data.get("confidence_score", 0.95),
                "base_file_hash": file_info["hash"]
            })
            
            confidence = patch_data.get('confidence_score', 0)
            relevance = evaluation.get('relevance_score', 0)
            lines_modified = patch_data.get('lines_modified', 'unknown')
            
            self.log_execution(execution_id, f"🎯 Surgical patch accepted for {file_info['path']} - Confidence: {confidence:.3f}, Relevance: {relevance:.3f}, Lines: {lines_modified}")
            return patch_data
            
        except Exception as e:
            self.log_execution(execution_id, f"💥 Surgical patch error for {file_info['path']}: {str(e)}")
            return None
    
    def _validate_patch_size(self, patch_data: Dict[str, Any], execution_id: int) -> bool:
        """Validate that patch size is reasonable for minimal changes"""
        try:
            patch_content = patch_data.get('patch_content', '')
            
            # Count actual changes (not context lines)
            add_lines = patch_content.count('\n+')
            remove_lines = patch_content.count('\n-')
            total_changes = add_lines + remove_lines
            
            # Check for massive hunks
            if total_changes > self.max_hunk_size * 2:  # Allow some flexibility
                self.log_execution(execution_id, f"❌ Patch rejected: {total_changes} changes exceeds limit of {self.max_hunk_size * 2}")
                return False
            
            # Check for suspicious patterns
            if remove_lines > 100 and add_lines < 10:
                self.log_execution(execution_id, f"❌ Patch rejected: Suspicious deletion pattern ({remove_lines} deletions, {add_lines} additions)")
                return False
            
            # Validate patched code syntax if Python
            target_file = patch_data.get('target_file', '')
            if target_file.endswith('.py'):
                patched_code = patch_data.get('patched_code', '')
                if patched_code:
                    post_valid, post_error = self.patch_validator.validate_post_application(patched_code, target_file)
                    if not post_valid:
                        self.log_execution(execution_id, f"❌ Patch rejected: Post-validation failed - {post_error}")
                        return False
            
            self.log_execution(execution_id, f"✅ Patch size validation passed: {total_changes} changes")
            return True
            
        except Exception as e:
            self.log_execution(execution_id, f"❌ Patch size validation error: {e}")
            return False
    
    
    async def _validate_with_orchestrator(self, patch_data: Dict[str, Any], file_info: Dict, 
                                        validator, execution_id: int) -> bool:
        """Validate patch using validation orchestrator."""
        try:
            original_content = file_info.get('content', '')
            patched_content = patch_data.get('patched_code', '')
            file_path = file_info.get('path', '')
            
            # Run comprehensive validation
            validation_summary = await validator.validate_patch(
                original_content=original_content,
                patched_content=patched_content,
                file_path=file_path,
                patch_info=patch_data
            )
            
            # Check validation results
            if validation_summary.overall_success and validation_summary.overall_confidence > 0.6:
                self.log_execution(execution_id, f"✅ Validation passed for {file_path} - confidence: {validation_summary.overall_confidence:.2f}")
                # Store validation info in patch data
                patch_data['validation_summary'] = {
                    'confidence': validation_summary.overall_confidence,
                    'recommendation': validation_summary.recommendation,
                    'execution_time': validation_summary.total_execution_time
                }
                return True
            else:
                self.log_execution(execution_id, f"❌ Validation failed for {file_path} - {validation_summary.recommendation}")
                return False
                
        except Exception as e:
            self.log_execution(execution_id, f"❌ Validation orchestrator error: {e}")
            return False  # Fail safely
    
    
    async def _save_patch_attempt_safely(self, ticket: Ticket, execution_id: int, patch_data: Dict[str, Any]):
        """Save patch attempt to database with proper error handling"""
        try:
            db = next(get_sync_db())
            patch_attempt = PatchAttempt(
                ticket_id=ticket.id,
                execution_id=execution_id,
                target_file=patch_data.get("target_file", "unknown"),
                patch_content=patch_data.get("patch_content", ""),
                patched_code=patch_data.get("patched_code", ""),
                test_code=patch_data.get("test_code", ""),
                commit_message=patch_data.get("commit_message", ""),
                confidence_score=patch_data.get("confidence_score", 0.0),
                base_file_hash=patch_data.get("base_file_hash", ""),
                patch_type=patch_data.get("patch_type", "surgical_unified_diff"),
                test_results=json.dumps(patch_data.get("semantic_evaluation", {})),
                success=True
            )
            db.add(patch_attempt)
            db.commit()
            logger.info(f"✅ Successfully saved patch attempt for {patch_data.get('target_file', 'unknown')}")
        except Exception as e:
            logger.error(f"❌ Failed to save patch attempt: {e}")
        finally:
            if 'db' in locals():
                db.close()
