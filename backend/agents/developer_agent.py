from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from services.github_client import GitHubClient
from services.json_response_handler import JSONResponseHandler
from services.large_file_handler import LargeFileHandler
from services.semantic_evaluator import SemanticEvaluator
from services.minimal_change_prompter import MinimalChangePrompter
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
        self.file_handler = LargeFileHandler()
        self.semantic_evaluator = SemanticEvaluator()
        self.minimal_prompter = MinimalChangePrompter()
        self.patch_validator = PatchValidator()
        self.large_file_threshold = 12000  # Reduced threshold for better chunking
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
        
        # Generate minimal patches with enhanced validation
        patches = []
        total_files = len(source_files)
        processing_stats = {
            "total_patches_generated": 0,
            "patches_accepted": 0,
            "patches_rejected": 0,
            "patches_rejected_for_size": 0,
            "files_with_no_relevant_fixes": 0,
            "truly_minimal_changes": 0
        }
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Processing file {i}/{total_files}: {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                file_size = len(file_info['content'])
                timeout = 300.0  # Reduced timeout for focused changes
                
                self.log_execution(execution_id, f"⏱️ Setting timeout to {timeout}s for minimal changes")
                
                # Use minimal change patch generation with enhanced validation
                patch_data = await asyncio.wait_for(
                    self._generate_minimal_patch_with_validation(ticket, file_info, planner_data, execution_id),
                    timeout=timeout
                )
                
                if patch_data:
                    # Validate patch size before accepting
                    if self._validate_patch_size(patch_data, execution_id):
                        patches.append(patch_data)
                        await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                        
                        processing_stats["total_patches_generated"] += 1
                        processing_stats["patches_accepted"] += 1
                        
                        # Track minimal changes
                        lines_modified = patch_data.get("lines_modified", 0)
                        if isinstance(lines_modified, (int, str)) and str(lines_modified).isdigit() and int(lines_modified) <= 10:
                            processing_stats["truly_minimal_changes"] += 1
                        
                        self.log_execution(execution_id, f"✅ Accepted minimal patch for {file_info['path']} ({lines_modified} lines)")
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
    
    async def _generate_minimal_patch_with_validation(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch with size validation"""
        file_size = len(file_info['content'])
        
        if file_size > self.large_file_threshold:
            self.log_execution(execution_id, f"🧩 CHUNKED MINIMAL: {file_info['path']} ({file_size} chars)")
            return await self._generate_minimal_chunked_patch(ticket, file_info, analysis, execution_id)
        else:
            self.log_execution(execution_id, f"📝 MINIMAL SINGLE FILE: {file_info['path']} ({file_size} chars)")
            return await self._generate_minimal_single_patch(ticket, file_info, analysis, execution_id)
    
    async def _generate_minimal_single_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch for a single file with strict size limits"""
        try:
            self.log_execution(execution_id, f"📝 Starting surgical patch generation for {file_info['path']}")
            
            # Use minimal change prompter with enhanced instructions
            patch_prompt = self.minimal_prompter.create_minimal_patch_prompt(ticket, file_info, analysis)
            
            # Enhanced system prompt for minimal changes
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

Generate only valid JSON responses with minimal unified diffs."""
            
            self.log_execution(execution_id, f"🤖 Sending surgical change request for {file_info['path']}")
            
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": patch_prompt}
            ], model="gpt-4o-mini")
            
            # Parse response
            patch_data, error = self.json_handler.clean_and_parse_json(response)
            
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
    
    async def _generate_minimal_chunked_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch using improved chunking strategy with intelligent merging."""
        try:
            self.log_execution(execution_id, f"🧩 Starting intelligent chunked processing for {file_info['path']}")
            
            # Create logical chunks with better boundaries
            chunks = self.file_handler.create_file_chunks(file_info['content'], file_info['path'])
            self.log_execution(execution_id, f"📦 Created {len(chunks)} logical chunks for intelligent processing")
            
            chunk_patches = []
            high_confidence_chunks = 0
            
            for chunk in chunks:
                chunk_num = chunk['chunk_id'] + 1
                total_chunks = len(chunks)
                
                self.log_execution(execution_id, f"🔧 Processing logical chunk {chunk_num}/{total_chunks}")
                
                # Use enhanced prompting for chunks
                chunk_prompt = self.minimal_prompter.create_chunked_minimal_prompt(ticket, chunk, file_info)
                
                # Enhanced system prompt for chunk processing
                system_prompt = """You are analyzing a logical code chunk for minimal fixes. 

CRITICAL REQUIREMENTS:
- Only suggest changes if this chunk contains the actual issue
- Maintain proper indentation and code structure
- Preserve imports and class/function boundaries
- Keep changes minimal and focused
- If this chunk doesn't relate to the issue, return confidence_score: 0.1

Generate only valid JSON responses."""
                
                try:
                    response = await self.openai_client.complete_chat([
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk_prompt}
                    ], model="gpt-4o-mini")
                    
                    chunk_data, error = self.json_handler.clean_and_parse_json(response)
                    
                    if chunk_data and chunk_data.get('confidence_score', 0) > 0.3:
                        # Enhanced chunk validation
                        if self._validate_chunk_patch(chunk_data, chunk, execution_id):
                            # Add chunk context information
                            chunk_data.update({
                                'start_line': chunk['start_line'],
                                'end_line': chunk['end_line'],
                                'chunk_id': chunk['chunk_id']
                            })
                            chunk_patches.append(chunk_data)
                            
                            if chunk_data.get('confidence_score', 0) > 0.7:
                                high_confidence_chunks += 1
                            
                            self.log_execution(execution_id, f"✅ Logical chunk {chunk_num} processed successfully (confidence: {chunk_data.get('confidence_score', 0):.3f})")
                        else:
                            self.log_execution(execution_id, f"❌ Chunk {chunk_num} failed validation")
                    else:
                        self.log_execution(execution_id, f"⚠️ Chunk {chunk_num} had low confidence - skipping")
                        
                except Exception as e:
                    self.log_execution(execution_id, f"💥 Error processing chunk {chunk_num}: {e}")
                    continue
            
            if not chunk_patches:
                self.log_execution(execution_id, f"❌ No valid chunk patches for {file_info['path']}")
                return None
            
            self.log_execution(execution_id, f"🔗 Combining {len(chunk_patches)} chunk patches with intelligent merging")
            self.log_execution(execution_id, f"  - High confidence chunks: {high_confidence_chunks}")
            
            # Use the improved chunk combination with intelligent merging
            combined_patch = await self.file_handler.combine_chunk_patches(chunk_patches, file_info, ticket)
            
            if combined_patch:
                # Add metadata for surgical processing
                combined_patch.update({
                    "processing_strategy": "intelligent_chunked",
                    "target_file": file_info["path"],
                    "file_size": len(file_info["content"]),
                    "base_file_hash": file_info["hash"],
                    "high_confidence_chunks": high_confidence_chunks,
                    "total_chunks_processed": len(chunk_patches)
                })
                
                # Final comprehensive validation
                if self._validate_combined_patch(combined_patch, execution_id):
                    self.log_execution(execution_id, f"✅ Successfully created and validated intelligent chunked patch for {file_info['path']}")
                    return combined_patch
                else:
                    self.log_execution(execution_id, f"❌ Combined patch failed final validation: {file_info['path']}")
                    return None
            else:
                self.log_execution(execution_id, f"❌ Failed to intelligently combine chunk patches for {file_info['path']}")
                return None
                
        except Exception as e:
            self.log_execution(execution_id, f"💥 Intelligent chunked processing error for {file_info['path']}: {e}")
            return None
    
    def _validate_chunk_patch(self, chunk_data: Dict[str, Any], chunk: Dict, execution_id: int) -> bool:
        """Enhanced validation for individual chunk patches."""
        try:
            # Check for required fields
            if not chunk_data.get('patched_code'):
                self.log_execution(execution_id, f"❌ Chunk patch missing patched_code")
                return False
            
            # Validate chunk patch size
            patched_code = chunk_data.get('patched_code', '')
            original_lines = chunk['content'].count('\n')
            patched_lines = patched_code.count('\n')
            
            # Allow reasonable growth but prevent massive expansion
            if patched_lines > original_lines * 2 and patched_lines > 100:
                self.log_execution(execution_id, f"❌ Chunk patch too large: {patched_lines} lines vs {original_lines} original")
                return False
            
            # Check for structural integrity
            if not self._validate_chunk_structure(patched_code, chunk):
                self.log_execution(execution_id, f"❌ Chunk patch failed structural validation")
                return False
            
            return True
            
        except Exception as e:
            self.log_execution(execution_id, f"❌ Chunk patch validation error: {e}")
            return False
    
    def _validate_chunk_structure(self, patched_code: str, chunk: Dict) -> bool:
        """Validate that chunk structure is maintained."""
        try:
            original_lines = chunk['content'].split('\n')
            patched_lines = patched_code.split('\n')
            
            # Check for major structural elements preservation
            original_classes = len([l for l in original_lines if l.strip().startswith('class ')])
            patched_classes = len([l for l in patched_lines if l.strip().startswith('class ')])
            
            original_functions = len([l for l in original_lines if l.strip().startswith('def ')])
            patched_functions = len([l for l in patched_lines if l.strip().startswith('def ')])
            
            # Allow some flexibility but prevent major structural changes
            if abs(original_classes - patched_classes) > 1 or abs(original_functions - patched_functions) > 2:
                logger.warning(f"❌ Major structural changes detected in chunk")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Chunk structure validation error: {e}")
            return False
    
    def _validate_combined_patch(self, combined_patch: Dict[str, Any], execution_id: int) -> bool:
        """Final validation for combined patches."""
        try:
            # Check validation info from merger
            validation_info = combined_patch.get('validation_info', {})
            if not validation_info.get('valid', False):
                self.log_execution(execution_id, f"❌ Combined patch failed merger validation: {validation_info.get('error', 'Unknown error')}")
                return False
            
            # Additional patch size validation
            if not self._validate_patch_size(combined_patch, execution_id):
                return False
            
            # Check confidence threshold
            confidence = combined_patch.get('confidence_score', 0)
            if confidence < 0.4:
                self.log_execution(execution_id, f"❌ Combined patch confidence too low: {confidence}")
                return False
            
            return True
            
        except Exception as e:
            self.log_execution(execution_id, f"❌ Combined patch validation error: {e}")
            return False
    
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
