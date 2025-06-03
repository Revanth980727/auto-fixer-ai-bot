
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from services.github_client import GitHubClient
from services.json_response_handler import JSONResponseHandler
from services.large_file_handler import LargeFileHandler
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
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate intelligent code patches with enhanced error handling and resilient processing"""
        self.log_execution(execution_id, "🚀 Starting enhanced intelligent code generation with resilient processing")
        
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
        
        self.log_execution(execution_id, f"📁 Processing {len(source_files)} intelligently selected files")
        self.log_execution(execution_id, f"🎯 Files selected: {[f['path'] for f in source_files]}")
        self.log_execution(execution_id, f"🔍 Total code size: {sum(len(f['content']) for f in source_files)} characters")
        
        # Generate intelligent patches with enhanced resilience
        patches = []
        total_files = len(source_files)
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Generating resilient patch {i}/{total_files} for {file_info['path']}")
            self.log_execution(execution_id, f"📊 File size: {len(file_info['content'])} characters")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                # Use resilient patch generation with fallback strategies
                patch_data = await asyncio.wait_for(
                    self._generate_resilient_patch(ticket, file_info, planner_data, execution_id),
                    timeout=300.0  # 5 minute timeout for complex analysis
                )
                
                if patch_data:
                    patches.append(patch_data)
                    # Save patch with enhanced error handling
                    await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                    self.log_execution(execution_id, f"✅ SUCCESS: Generated resilient patch for {file_info['path']}")
                else:
                    self.log_execution(execution_id, f"❌ FAILED: Could not generate valid patch for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                self.log_execution(execution_id, f"⏰ TIMEOUT: Patch generation for {file_info['path']} exceeded 5 minutes")
                continue
            except Exception as e:
                self.log_execution(execution_id, f"💥 ERROR: Exception generating patch for {file_info['path']}: {str(e)}")
                continue
        
        if not patches:
            self.log_execution(execution_id, "💥 CRITICAL: Failed to generate any valid patches for any file")
            raise Exception("No valid patches could be generated - check OpenAI API connectivity and file analysis")
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data,
            "resilient_processing": True,
            "large_file_support": True,
            "processing_time_info": f"Processed {len(patches)}/{total_files} files successfully with resilient handling"
        }
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} resilient patches successfully")
        return result
    
    async def _generate_resilient_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate a patch with multiple fallback strategies for large files"""
        try:
            self.log_execution(execution_id, f"🔄 Starting resilient patch generation for {file_info['path']}")
            
            # Strategy 1: Try full file processing for smaller files
            if not self.file_handler.should_chunk_file(file_info['content']):
                self.log_execution(execution_id, f"📝 Processing {file_info['path']} as single file")
                return await self._generate_single_file_patch(ticket, file_info, analysis, execution_id)
            
            # Strategy 2: Use chunked processing for large files
            self.log_execution(execution_id, f"🧩 Processing {file_info['path']} with chunking strategy")
            return await self._generate_chunked_patch(ticket, file_info, analysis, execution_id)
            
        except Exception as e:
            self.log_execution(execution_id, f"💥 All strategies failed for {file_info['path']}: {e}")
            return None
    
    async def _generate_single_file_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate patch for a single file with enhanced JSON handling"""
        try:
            # Generate the fix with enhanced context
            patch_prompt = f"""
You are an expert software engineer with deep understanding of code architecture and debugging.

TICKET INFORMATION:
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

REQUIREMENTS FOR FIX:
1. Generate a PRECISE UNIFIED DIFF PATCH that fixes the specific issue
2. Consider the ENTIRE file context when making changes
3. Ensure the fix doesn't break existing functionality
4. Make minimal but effective changes

RESPONSE FORMAT (JSON ONLY):
{{
    "patch_content": "unified diff format patch with proper headers and line numbers",
    "patched_code": "complete file content after applying the fix",
    "test_code": "comprehensive unit tests specific to this fix",
    "commit_message": "detailed commit message explaining the fix",
    "confidence_score": 0.95,
    "explanation": "detailed technical explanation of the problem and solution",
    "base_file_hash": "{file_info['hash']}",
    "patch_type": "unified_diff"
}}

CRITICAL: Generate ONLY valid JSON. The patch must be a proper unified diff that can be applied.
"""
            
            self.log_execution(execution_id, f"🤖 Sending single file patch request for {file_info['path']}")
            
            # Use GPT-4o for better analysis with timeout
            response = await asyncio.wait_for(
                self.openai_client.complete_chat([
                    {"role": "system", "content": "You are an expert software engineer specializing in precise code fixes. Generate only valid JSON responses with proper unified diff patches."},
                    {"role": "user", "content": patch_prompt}
                ], model="gpt-4o"),
                timeout=180.0
            )
            
            self.log_execution(execution_id, f"📨 Response received for {file_info['path']}, length: {len(response)}")
            
            # Use enhanced JSON parsing
            patch_data, error = self.json_handler.clean_and_parse_json(response)
            
            if patch_data is None:
                self.log_execution(execution_id, f"❌ JSON parsing failed for {file_info['path']}: {error}")
                return None
            
            self.log_execution(execution_id, f"✅ Successfully parsed JSON for {file_info['path']}")
            
            # Validate patch data
            is_valid, validation_error = self.json_handler.validate_patch_json(patch_data)
            if not is_valid:
                self.log_execution(execution_id, f"❌ Patch validation failed for {file_info['path']}: {validation_error}")
                return None
            
            # Add metadata
            patch_data["target_file"] = file_info["path"]
            patch_data["file_size"] = len(file_info["content"])
            patch_data["processing_strategy"] = "single_file"
            
            confidence = patch_data.get('confidence_score', 0)
            self.log_execution(execution_id, f"🎯 Single file patch generated for {file_info['path']} with confidence {confidence}")
            return patch_data
            
        except asyncio.TimeoutError:
            self.log_execution(execution_id, f"⏰ Single file generation timeout for {file_info['path']}")
            return None
        except Exception as e:
            self.log_execution(execution_id, f"💥 Single file generation error for {file_info['path']}: {str(e)}")
            return None
    
    async def _generate_chunked_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate patch using chunking strategy for large files"""
        try:
            # Create file chunks
            chunks = self.file_handler.create_file_chunks(file_info['content'], file_info['path'])
            self.log_execution(execution_id, f"🧩 Created {len(chunks)} chunks for {file_info['path']}")
            
            # Process each chunk
            chunk_patches = []
            for chunk in chunks:
                self.log_execution(execution_id, f"🔧 Processing chunk {chunk['chunk_id'] + 1}/{len(chunks)} for {file_info['path']}")
                
                chunk_context = self.file_handler.create_chunk_context(chunk, file_info, ticket)
                
                chunk_prompt = f"""
{chunk_context}

RESPONSE FORMAT (JSON ONLY):
{{
    "patch_content": "unified diff patch for this chunk only",
    "patched_code": "this chunk content after applying the fix",
    "confidence_score": 0.95,
    "explanation": "explanation of changes made in this chunk",
    "chunk_id": {chunk['chunk_id']},
    "start_line": {chunk['start_line']},
    "end_line": {chunk['end_line']}
}}

Generate ONLY valid JSON.
"""
                
                try:
                    response = await asyncio.wait_for(
                        self.openai_client.complete_chat([
                            {"role": "system", "content": "You are an expert software engineer analyzing code chunks. Generate only valid JSON responses."},
                            {"role": "user", "content": chunk_prompt}
                        ], model="gpt-4o"),
                        timeout=120.0
                    )
                    
                    # Parse chunk response
                    chunk_data, error = self.json_handler.clean_and_parse_json(response)
                    
                    if chunk_data and chunk_data.get('confidence_score', 0) > 0.3:
                        chunk_patches.append(chunk_data)
                        self.log_execution(execution_id, f"✅ Processed chunk {chunk['chunk_id'] + 1} successfully")
                    else:
                        self.log_execution(execution_id, f"⚠️ Chunk {chunk['chunk_id'] + 1} had low confidence or failed parsing")
                        
                except asyncio.TimeoutError:
                    self.log_execution(execution_id, f"⏰ Chunk {chunk['chunk_id'] + 1} processing timeout")
                    continue
                except Exception as e:
                    self.log_execution(execution_id, f"💥 Error processing chunk {chunk['chunk_id'] + 1}: {e}")
                    continue
            
            # Combine chunk patches
            if not chunk_patches:
                self.log_execution(execution_id, f"❌ No valid chunk patches for {file_info['path']}")
                return None
            
            combined_patch = self.file_handler.combine_chunk_patches(chunk_patches, file_info)
            
            if combined_patch:
                self.log_execution(execution_id, f"✅ Successfully combined {len(chunk_patches)} chunk patches for {file_info['path']}")
                combined_patch["processing_strategy"] = "chunked"
                return combined_patch
            else:
                self.log_execution(execution_id, f"❌ Failed to combine chunk patches for {file_info['path']}")
                return None
                
        except Exception as e:
            self.log_execution(execution_id, f"💥 Chunked processing error for {file_info['path']}: {e}")
            return None
    
    # ... keep existing code (_save_patch_attempt_safely method)
    async def _save_patch_attempt_safely(self, ticket: Ticket, execution_id: int, patch_data: Dict[str, Any]):
        """Safely save patch attempt with error handling"""
        try:
            with get_sync_db() as db:
                patch_attempt = PatchAttempt(
                    ticket_id=ticket.id,
                    patch_content=patch_data.get("patch_content", ""),
                    patched_code=patch_data.get("patched_code", ""),
                    test_code=patch_data.get("test_code", ""),
                    commit_message=patch_data.get("commit_message", ""),
                    confidence_score=patch_data.get("confidence_score", 0.0),
                    success=True
                )
                db.add(patch_attempt)
                db.commit()
                self.log_execution(execution_id, f"💾 Saved patch attempt for {patch_data.get('target_file', 'unknown file')}")
        except Exception as e:
            self.log_execution(execution_id, f"⚠️ Failed to save patch attempt: {e}")
