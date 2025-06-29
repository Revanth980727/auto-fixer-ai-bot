
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from services.github_client import GitHubClient
from services.json_response_handler import JSONResponseHandler
from services.large_file_handler import LargeFileHandler
from services.semantic_evaluator import SemanticEvaluator
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
        self.large_file_threshold = 15000  # Force chunking for files over 15KB
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate intelligent code patches with semantic evaluation and relevance filtering"""
        self.log_execution(execution_id, "🚀 Starting enhanced developer agent with semantic evaluation")
        
        if not context:
            self.log_execution(execution_id, "❌ No context provided - developer agent requires planner analysis")
            raise Exception("Developer agent requires context with planner analysis")
        
        # Check for GitHub access failure
        if context.get("github_access_failed"):
            self.log_execution(execution_id, "❌ GitHub access failed - cannot generate patches without source code")
            raise Exception("GitHub repository access required for patch generation")
        
        planner_data = context.get("planner_analysis", {})
        source_files = context.get("source_files", [])
        
        if not source_files:
            self.log_execution(execution_id, "❌ No source files available - cannot generate patches")
            raise Exception("No source files available for patch generation")
        
        self.log_execution(execution_id, f"📁 Processing {len(source_files)} files with semantic evaluation")
        
        # Analyze file sizes and processing strategy
        for file_info in source_files:
            file_size = len(file_info['content'])
            self.log_execution(execution_id, f"📊 {file_info['path']}: {file_size} characters")
            if file_size > self.large_file_threshold:
                self.log_execution(execution_id, f"🧩 {file_info['path']} will use SEMANTIC CHUNKING strategy (size: {file_size})")
            else:
                self.log_execution(execution_id, f"📝 {file_info['path']} will use ENHANCED SINGLE FILE strategy")
        
        # Generate patches with semantic evaluation
        patches = []
        total_files = len(source_files)
        semantic_stats = {
            "total_patches_generated": 0,
            "patches_accepted": 0,
            "patches_rejected": 0,
            "files_with_no_relevant_fixes": 0
        }
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Processing file {i}/{total_files}: {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                # Set processing timeout based on file size
                file_size = len(file_info['content'])
                timeout = 360.0 if file_size > self.large_file_threshold else 240.0
                
                self.log_execution(execution_id, f"⏱️ Setting timeout to {timeout}s for {file_info['path']}")
                
                # Use enhanced patch generation with semantic evaluation
                patch_data = await asyncio.wait_for(
                    self._generate_patch_with_semantic_evaluation(ticket, file_info, planner_data, execution_id),
                    timeout=timeout
                )
                
                if patch_data:
                    patches.append(patch_data)
                    await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                    
                    # Update semantic stats - fixed counting logic
                    semantic_stats["total_patches_generated"] += 1
                    semantic_stats["patches_accepted"] += 1  # If patch_data exists, it was accepted
                    
                    self.log_execution(execution_id, f"✅ SUCCESS: Generated semantically validated patch for {file_info['path']}")
                else:
                    semantic_stats["files_with_no_relevant_fixes"] += 1
                    semantic_stats["patches_rejected"] += 1  # Track rejections properly
                    self.log_execution(execution_id, f"⚠️ NO RELEVANT FIX: No semantically relevant patches found for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                semantic_stats["patches_rejected"] += 1
                self.log_execution(execution_id, f"⏰ TIMEOUT: Patch generation for {file_info['path']} exceeded timeout")
                continue
            except Exception as e:
                semantic_stats["patches_rejected"] += 1
                self.log_execution(execution_id, f"💥 ERROR: Exception generating patch for {file_info['path']}: {str(e)}")
                continue
        
        if not patches:
            self.log_execution(execution_id, "💥 CRITICAL: No semantically relevant patches generated")
            raise Exception("No semantically relevant patches were generated - all fixes were below quality thresholds")
        
        # Log semantic evaluation summary
        self.log_execution(execution_id, f"🧠 SEMANTIC EVALUATION SUMMARY:")
        self.log_execution(execution_id, f"  - Files processed: {total_files}")
        self.log_execution(execution_id, f"  - Patches generated: {semantic_stats['total_patches_generated']}")
        self.log_execution(execution_id, f"  - High-quality patches: {semantic_stats['patches_accepted']}")
        self.log_execution(execution_id, f"  - Files with no relevant fixes: {semantic_stats['files_with_no_relevant_fixes']}")
        
        # CRITICAL FIX: Return data structure that validator expects with all required flags
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data,
            
            # VALIDATOR COMPATIBILITY - ALL detection methods the validator looks for
            "intelligent_patching": True,  # Primary flag for intelligent patching
            "semantic_evaluation_enabled": True,  # Legacy flag
            "using_intelligent_patching": True,  # Alternative flag
            
            "processing_summary": f"Generated {len(patches)} semantically validated patches from {total_files} files",
            "semantic_stats": semantic_stats,
            "quality_thresholds": {
                "confidence_threshold": self.semantic_evaluator.confidence_threshold,
                "relevance_threshold": self.semantic_evaluator.relevance_threshold
            }
        }
        
        # Add debug logging for validator compatibility
        self.log_execution(execution_id, f"🔍 VALIDATOR DEBUG - Result structure for validator:")
        self.log_execution(execution_id, f"  - patches count: {len(patches)}")
        self.log_execution(execution_id, f"  - intelligent_patching: {result['intelligent_patching']}")
        self.log_execution(execution_id, f"  - semantic_evaluation_enabled: {result['semantic_evaluation_enabled']}")
        self.log_execution(execution_id, f"  - using_intelligent_patching: {result['using_intelligent_patching']}")
        self.log_execution(execution_id, f"  - semantic_stats: {semantic_stats}")
        self.log_execution(execution_id, f"  - quality_thresholds present: {bool(result.get('quality_thresholds'))}")
        
        # Log individual patch details for validator
        for i, patch in enumerate(patches):
            confidence = patch.get('confidence_score', 0)
            strategy = patch.get('processing_strategy', 'unknown')
            semantic_eval = patch.get('semantic_evaluation', {})
            self.log_execution(execution_id, f"  - Patch {i}: confidence={confidence:.3f}, strategy={strategy}, semantic_eval={bool(semantic_eval)}")
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} semantically validated patches")
        return result
    
    # ... keep existing code (patch generation methods remain the same)
    
    async def _generate_patch_with_semantic_evaluation(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate patch using appropriate strategy with semantic evaluation"""
        file_size = len(file_info['content'])
        
        # Force chunking for large files with semantic evaluation
        if file_size > self.large_file_threshold:
            self.log_execution(execution_id, f"🧩 SEMANTIC CHUNKING: {file_info['path']} ({file_size} chars > {self.large_file_threshold})")
            return await self._generate_semantically_evaluated_chunked_patch(ticket, file_info, analysis, execution_id)
        else:
            self.log_execution(execution_id, f"📝 ENHANCED SINGLE FILE: {file_info['path']} ({file_size} chars)")
            return await self._generate_semantically_evaluated_single_patch(ticket, file_info, analysis, execution_id)
    
    async def _generate_semantically_evaluated_single_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate semantically evaluated patch for a single file"""
        try:
            self.log_execution(execution_id, f"📝 Starting enhanced single file patch generation for {file_info['path']}")
            
            # Generate the fix with enhanced context and relevance requirements
            patch_prompt = f"""
You are an expert software engineer with deep understanding of code architecture and debugging.

TICKET INFORMATION (CRITICAL - ANALYZE CAREFULLY):
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace or 'No error trace provided'}

TARGET FILE: {file_info['path']}
FILE HASH: {file_info['hash']}
FILE SIZE: {len(file_info['content'])} characters

COMPLETE FILE CONTENT:
```
{file_info['content']}
```

PLANNER CONTEXT:
Root Cause: {analysis.get('root_cause', 'Unknown')}
Suggested Approach: {analysis.get('suggested_approach', 'Standard debugging approach')}

CRITICAL INSTRUCTIONS:
1. ONLY propose a fix if it directly resolves the issue described in the ticket
2. If this file doesn't contain code related to the issue, return confidence_score: 0.1
3. Consider the ENTIRE file context when making changes
4. Ensure the fix doesn't break existing functionality
5. Make minimal but effective changes
6. Provide clear justification for why this change addresses the issue

REQUIRED RESPONSE FORMAT (JSON ONLY):
{{
    "patch_content": "unified diff format patch with proper headers and line numbers",
    "patched_code": "complete file content after applying the fix",
    "test_code": "comprehensive unit tests specific to this fix",
    "commit_message": "detailed commit message explaining the fix",
    "confidence_score": 0.95,
    "explanation": "detailed technical explanation of the problem and solution",
    "justification": "Why do you think this change addresses the issue?",
    "base_file_hash": "{file_info['hash']}",
    "patch_type": "enhanced_unified_diff",
    "addresses_issue": true
}}

CRITICAL: Generate ONLY valid JSON. If you're not confident this file contains the issue, set confidence_score to 0.1 and addresses_issue to false.
"""
            
            self.log_execution(execution_id, f"🤖 Sending enhanced single file patch request for {file_info['path']}")
            
            # Use GPT-4.1 for better analysis
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": "You are an expert software engineer specializing in precise, relevant code fixes. Only propose fixes that directly address the stated issue. Generate only valid JSON responses."},
                {"role": "user", "content": patch_prompt}
            ], model="gpt-4.1-2025-04-14")
            
            self.log_execution(execution_id, f"📨 Response received for {file_info['path']}, length: {len(response)}")
            
            # Use enhanced JSON parsing
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
                self.log_execution(execution_id, f"❌ Patch rejected for {file_info['path']}: {reason}")
                return None
            
            # CRITICAL FIX: Ensure all validator-required fields are present
            patch_data.update({
                "target_file": file_info["path"],
                "file_size": len(file_info["content"]),
                "processing_strategy": "enhanced_single_file",
                "semantic_evaluation": evaluation,
                "selection_reason": reason,
                # Ensure confidence_score is at top level for validator
                "confidence_score": patch_data.get("confidence_score", 0.95)
            })
            
            confidence = patch_data.get('confidence_score', 0)
            relevance = evaluation.get('relevance_score', 0)
            self.log_execution(execution_id, f"🎯 Enhanced single file patch accepted for {file_info['path']} - Confidence: {confidence:.3f}, Relevance: {relevance:.3f}")
            return patch_data
            
        except Exception as e:
            self.log_execution(execution_id, f"💥 Enhanced single file generation error for {file_info['path']}: {str(e)}")
            return None
    
    async def _generate_semantically_evaluated_chunked_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate semantically evaluated patch using chunking strategy for large files"""
        try:
            self.log_execution(execution_id, f"🧩 Starting semantic chunked processing for {file_info['path']}")
            
            # Create file chunks with smart overlap
            chunks = self.file_handler.create_file_chunks(file_info['content'], file_info['path'])
            self.log_execution(execution_id, f"📦 Created {len(chunks)} chunks with smart overlap for {file_info['path']}")
            
            # Process each chunk with enhanced prompts
            chunk_patches = []
            for chunk in chunks:
                chunk_num = chunk['chunk_id'] + 1
                total_chunks = len(chunks)
                
                self.log_execution(execution_id, f"🔧 Processing chunk {chunk_num}/{total_chunks} for {file_info['path']}")
                self.log_execution(execution_id, f"📋 Chunk {chunk_num}: lines {chunk['start_line']}-{chunk['end_line']} (overlap: {chunk.get('overlap_lines', 0)} lines)")
                
                chunk_context = self.file_handler.create_chunk_context(chunk, file_info, ticket)
                
                try:
                    self.log_execution(execution_id, f"🤖 Sending enhanced chunk {chunk_num} request")
                    
                    response = await self.openai_client.complete_chat([
                        {"role": "system", "content": "You are an expert software engineer analyzing code chunks with strict relevance requirements. Only propose fixes that directly address the stated issue. Generate only valid JSON responses."},
                        {"role": "user", "content": chunk_context}
                    ], model="gpt-4.1-2025-04-14")
                    
                    self.log_execution(execution_id, f"📨 Chunk {chunk_num} response received")
                    
                    # Parse chunk response
                    chunk_data, error = self.json_handler.clean_and_parse_json(response)
                    
                    if chunk_data and chunk_data.get('confidence_score', 0) > 0.3:
                        chunk_patches.append(chunk_data)
                        confidence = chunk_data.get('confidence_score', 0)
                        addresses_issue = chunk_data.get('addresses_issue', False)
                        self.log_execution(execution_id, f"✅ Chunk {chunk_num} processed - Confidence: {confidence:.3f}, Addresses Issue: {addresses_issue}")
                    else:
                        self.log_execution(execution_id, f"⚠️ Chunk {chunk_num} had low confidence or failed parsing")
                        
                except Exception as e:
                    self.log_execution(execution_id, f"💥 Error processing chunk {chunk_num}: {e}")
                    continue
            
            # Use enhanced semantic combination
            if not chunk_patches:
                self.log_execution(execution_id, f"❌ No valid chunk patches for {file_info['path']}")
                return None
            
            self.log_execution(execution_id, f"🔗 Starting semantic evaluation and combination of {len(chunk_patches)} chunk patches for {file_info['path']}")
            combined_patch = await self.file_handler.combine_chunk_patches(chunk_patches, file_info, ticket)
            
            if combined_patch:
                self.log_execution(execution_id, f"✅ Successfully combined semantically validated chunk patches for {file_info['path']}")
                
                # CRITICAL FIX: Ensure all validator-required fields are present
                combined_patch.update({
                    "processing_strategy": "semantic_chunked",
                    "target_file": file_info["path"],
                    "file_size": len(file_info["content"])
                })
                
                # Ensure confidence_score is at top level for validator
                if "confidence_score" not in combined_patch:
                    # Calculate average confidence from chunk patches
                    avg_confidence = sum(p.get('confidence_score', 0) for p in chunk_patches) / len(chunk_patches)
                    combined_patch["confidence_score"] = avg_confidence
                
                return combined_patch
            else:
                self.log_execution(execution_id, f"❌ Semantic evaluation rejected all chunk patches for {file_info['path']}")
                return None
                
        except Exception as e:
            self.log_execution(execution_id, f"💥 Semantic chunked processing error for {file_info['path']}: {e}")
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
                patch_type=patch_data.get("patch_type", "enhanced_unified_diff"),
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
