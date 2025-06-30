from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from services.github_client import GitHubClient
from services.json_response_handler import JSONResponseHandler
from services.large_file_handler import LargeFileHandler
from services.semantic_evaluator import SemanticEvaluator
from services.minimal_change_prompter import MinimalChangePrompter
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
        self.large_file_threshold = 15000  # Force chunking for files over 15KB
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate minimal, focused code patches with semantic evaluation"""
        self.log_execution(execution_id, "🚀 Starting enhanced developer agent with minimal change approach")
        
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
        
        self.log_execution(execution_id, f"📁 Processing {len(source_files)} files with minimal change approach")
        
        # Generate minimal patches with semantic evaluation
        patches = []
        total_files = len(source_files)
        semantic_stats = {
            "total_patches_generated": 0,
            "patches_accepted": 0,
            "patches_rejected": 0,
            "files_with_no_relevant_fixes": 0,
            "minimal_changes_applied": 0
        }
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Processing file {i}/{total_files}: {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                file_size = len(file_info['content'])
                timeout = 360.0 if file_size > self.large_file_threshold else 240.0
                
                self.log_execution(execution_id, f"⏱️ Setting timeout to {timeout}s for {file_info['path']}")
                
                # Use minimal change patch generation
                patch_data = await asyncio.wait_for(
                    self._generate_minimal_patch_with_evaluation(ticket, file_info, planner_data, execution_id),
                    timeout=timeout
                )
                
                if patch_data:
                    patches.append(patch_data)
                    await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                    
                    semantic_stats["total_patches_generated"] += 1
                    semantic_stats["patches_accepted"] += 1
                    
                    # Track if this was a truly minimal change
                    lines_modified = patch_data.get("lines_modified", "unknown")
                    if isinstance(lines_modified, (int, str)) and str(lines_modified).isdigit() and int(lines_modified) <= 5:
                        semantic_stats["minimal_changes_applied"] += 1
                    
                    self.log_execution(execution_id, f"✅ SUCCESS: Generated minimal patch for {file_info['path']} ({lines_modified} lines)")
                else:
                    semantic_stats["files_with_no_relevant_fixes"] += 1
                    semantic_stats["patches_rejected"] += 1
                    self.log_execution(execution_id, f"⚠️ NO RELEVANT FIX: No minimal fixes found for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                semantic_stats["patches_rejected"] += 1
                self.log_execution(execution_id, f"⏰ TIMEOUT: Patch generation for {file_info['path']} exceeded timeout")
                continue
            except Exception as e:
                semantic_stats["patches_rejected"] += 1
                self.log_execution(execution_id, f"💥 ERROR: Exception generating patch for {file_info['path']}: {str(e)}")
                continue
        
        if not patches:
            self.log_execution(execution_id, "💥 CRITICAL: No minimal patches generated")
            raise Exception("No minimal patches were generated - all fixes were below quality thresholds")
        
        # Log minimal change summary
        self.log_execution(execution_id, f"🔧 MINIMAL CHANGE SUMMARY:")
        self.log_execution(execution_id, f"  - Files processed: {total_files}")
        self.log_execution(execution_id, f"  - Patches generated: {semantic_stats['total_patches_generated']}")
        self.log_execution(execution_id, f"  - Truly minimal changes: {semantic_stats['minimal_changes_applied']}")
        self.log_execution(execution_id, f"  - Files with no relevant fixes: {semantic_stats['files_with_no_relevant_fixes']}")
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data,
            
            # Validator compatibility flags
            "intelligent_patching": True,
            "semantic_evaluation_enabled": True,
            "using_intelligent_patching": True,
            "minimal_change_approach": True,  # New flag for minimal changes
            
            "processing_summary": f"Generated {len(patches)} minimal patches from {total_files} files",
            "semantic_stats": semantic_stats,
            "quality_thresholds": {
                "confidence_threshold": self.semantic_evaluator.confidence_threshold,
                "relevance_threshold": self.semantic_evaluator.relevance_threshold
            }
        }
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} minimal patches")
        return result
    
    async def _generate_minimal_patch_with_evaluation(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch using appropriate strategy with semantic evaluation"""
        file_size = len(file_info['content'])
        
        if file_size > self.large_file_threshold:
            self.log_execution(execution_id, f"🧩 CHUNKED MINIMAL: {file_info['path']} ({file_size} chars)")
            return await self._generate_minimal_chunked_patch(ticket, file_info, analysis, execution_id)
        else:
            self.log_execution(execution_id, f"📝 MINIMAL SINGLE FILE: {file_info['path']} ({file_size} chars)")
            return await self._generate_minimal_single_patch(ticket, file_info, analysis, execution_id)
    
    async def _generate_minimal_single_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch for a single file using focused prompts"""
        try:
            self.log_execution(execution_id, f"📝 Starting minimal single file patch for {file_info['path']}")
            
            # Use minimal change prompter
            patch_prompt = self.minimal_prompter.create_minimal_patch_prompt(ticket, file_info, analysis)
            
            self.log_execution(execution_id, f"🤖 Sending minimal change request for {file_info['path']}")
            
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": "You are an expert at making minimal, surgical code fixes. Only change what is absolutely necessary to fix the issue. Generate only valid JSON responses."},
                {"role": "user", "content": patch_prompt}
            ], model="gpt-4.1-2025-04-14")
            
            # Parse response
            patch_data, error = self.json_handler.clean_and_parse_json(response)
            
            if patch_data is None:
                self.log_execution(execution_id, f"❌ JSON parsing failed for {file_info['path']}: {error}")
                return None
            
            # Validate patch data
            is_valid, validation_error = self.json_handler.validate_patch_json(patch_data)
            if not is_valid:
                self.log_execution(execution_id, f"❌ Patch validation failed for {file_info['path']}: {validation_error}")
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
                self.log_execution(execution_id, f"❌ Minimal patch rejected for {file_info['path']}: {reason}")
                return None
            
            # Ensure all required fields are present
            patch_data.update({
                "target_file": file_info["path"],
                "file_size": len(file_info["content"]),
                "processing_strategy": "minimal_single_file",
                "semantic_evaluation": evaluation,
                "selection_reason": reason,
                "confidence_score": patch_data.get("confidence_score", 0.95)
            })
            
            confidence = patch_data.get('confidence_score', 0)
            relevance = evaluation.get('relevance_score', 0)
            lines_modified = patch_data.get('lines_modified', 'unknown')
            
            self.log_execution(execution_id, f"🎯 Minimal patch accepted for {file_info['path']} - Confidence: {confidence:.3f}, Relevance: {relevance:.3f}, Lines: {lines_modified}")
            return patch_data
            
        except Exception as e:
            self.log_execution(execution_id, f"💥 Minimal single file error for {file_info['path']}: {str(e)}")
            return None
    
    async def _generate_minimal_chunked_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate minimal patch using chunking strategy for large files"""
        try:
            self.log_execution(execution_id, f"🧩 Starting minimal chunked processing for {file_info['path']}")
            
            chunks = self.file_handler.create_file_chunks(file_info['content'], file_info['path'])
            self.log_execution(execution_id, f"📦 Created {len(chunks)} chunks for minimal processing")
            
            chunk_patches = []
            for chunk in chunks:
                chunk_num = chunk['chunk_id'] + 1
                total_chunks = len(chunks)
                
                self.log_execution(execution_id, f"🔧 Processing chunk {chunk_num}/{total_chunks} with minimal approach")
                
                # Use minimal change prompter for chunks
                chunk_prompt = self.minimal_prompter.create_chunked_minimal_prompt(ticket, chunk, file_info)
                
                try:
                    response = await self.openai_client.complete_chat([
                        {"role": "system", "content": "You are analyzing code chunks for minimal fixes. Only suggest changes if they're absolutely necessary and directly address the issue."},
                        {"role": "user", "content": chunk_prompt}
                    ], model="gpt-4.1-2025-04-14")
                    
                    chunk_data, error = self.json_handler.clean_and_parse_json(response)
                    
                    if chunk_data and chunk_data.get('confidence_score', 0) > 0.3:
                        chunk_patches.append(chunk_data)
                        self.log_execution(execution_id, f"✅ Minimal chunk {chunk_num} processed")
                    else:
                        self.log_execution(execution_id, f"⚠️ Chunk {chunk_num} had low confidence - no minimal changes")
                        
                except Exception as e:
                    self.log_execution(execution_id, f"💥 Error processing minimal chunk {chunk_num}: {e}")
                    continue
            
            if not chunk_patches:
                self.log_execution(execution_id, f"❌ No minimal chunk patches for {file_info['path']}")
                return None
            
            self.log_execution(execution_id, f"🔗 Combining {len(chunk_patches)} minimal chunk patches")
            combined_patch = await self.file_handler.combine_chunk_patches(chunk_patches, file_info, ticket)
            
            if combined_patch:
                combined_patch.update({
                    "processing_strategy": "minimal_chunked",
                    "target_file": file_info["path"],
                    "file_size": len(file_info["content"])
                })
                
                if "confidence_score" not in combined_patch:
                    avg_confidence = sum(p.get('confidence_score', 0) for p in chunk_patches) / len(chunk_patches)
                    combined_patch["confidence_score"] = avg_confidence
                
                self.log_execution(execution_id, f"✅ Successfully combined minimal chunk patches for {file_info['path']}")
                return combined_patch
            else:
                self.log_execution(execution_id, f"❌ Failed to combine minimal chunk patches for {file_info['path']}")
                return None
                
        except Exception as e:
            self.log_execution(execution_id, f"💥 Minimal chunked processing error for {file_info['path']}: {e}")
            return None

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
                patch_type=patch_data.get("patch_type", "minimal_unified_diff"),
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
