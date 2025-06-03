
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
        self.large_file_threshold = 15000  # Force chunking for files over 15KB
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate intelligent code patches with forced chunking for large files"""
        self.log_execution(execution_id, "🚀 Starting enhanced developer agent with forced large file chunking")
        
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
        
        self.log_execution(execution_id, f"📁 Processing {len(source_files)} files with enhanced large file handling")
        
        # Analyze file sizes and processing strategy
        for file_info in source_files:
            file_size = len(file_info['content'])
            self.log_execution(execution_id, f"📊 {file_info['path']}: {file_size} characters")
            if file_size > self.large_file_threshold:
                self.log_execution(execution_id, f"🧩 {file_info['path']} will use CHUNKING strategy (size: {file_size})")
            else:
                self.log_execution(execution_id, f"📝 {file_info['path']} will use SINGLE FILE strategy")
        
        # Generate patches with enforced strategies
        patches = []
        total_files = len(source_files)
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Processing file {i}/{total_files}: {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                # Set processing timeout based on file size
                file_size = len(file_info['content'])
                timeout = 300.0 if file_size > self.large_file_threshold else 180.0
                
                self.log_execution(execution_id, f"⏱️ Setting timeout to {timeout}s for {file_info['path']}")
                
                # Use enhanced patch generation with strict timeout
                patch_data = await asyncio.wait_for(
                    self._generate_patch_with_strategy(ticket, file_info, planner_data, execution_id),
                    timeout=timeout
                )
                
                if patch_data:
                    patches.append(patch_data)
                    await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                    self.log_execution(execution_id, f"✅ SUCCESS: Generated patch for {file_info['path']}")
                else:
                    self.log_execution(execution_id, f"❌ FAILED: Could not generate valid patch for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                self.log_execution(execution_id, f"⏰ TIMEOUT: Patch generation for {file_info['path']} exceeded timeout")
                continue
            except Exception as e:
                self.log_execution(execution_id, f"💥 ERROR: Exception generating patch for {file_info['path']}: {str(e)}")
                continue
        
        if not patches:
            self.log_execution(execution_id, "💥 CRITICAL: Failed to generate any valid patches")
            raise Exception("No valid patches could be generated - all strategies failed")
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data,
            "enhanced_processing": True,
            "large_file_handling": True,
            "processing_summary": f"Successfully processed {len(patches)}/{total_files} files"
        }
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} patches successfully")
        return result
    
    async def _generate_patch_with_strategy(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate patch using appropriate strategy based on file size"""
        file_size = len(file_info['content'])
        
        # Force chunking for large files
        if file_size > self.large_file_threshold:
            self.log_execution(execution_id, f"🧩 FORCED CHUNKING: {file_info['path']} ({file_size} chars > {self.large_file_threshold})")
            return await self._generate_chunked_patch(ticket, file_info, analysis, execution_id)
        else:
            self.log_execution(execution_id, f"📝 SINGLE FILE: {file_info['path']} ({file_size} chars)")
            return await self._generate_single_file_patch(ticket, file_info, analysis, execution_id)
    
    async def _generate_single_file_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate patch for a single file with enhanced monitoring"""
        try:
            self.log_execution(execution_id, f"📝 Starting single file patch generation for {file_info['path']}")
            
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
            
            # Use GPT-4o for better analysis with reduced timeout
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": "You are an expert software engineer specializing in precise code fixes. Generate only valid JSON responses with proper unified diff patches."},
                {"role": "user", "content": patch_prompt}
            ], model="gpt-4o")
            
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
            
            # Add metadata
            patch_data["target_file"] = file_info["path"]
            patch_data["file_size"] = len(file_info["content"])
            patch_data["processing_strategy"] = "single_file"
            
            confidence = patch_data.get('confidence_score', 0)
            self.log_execution(execution_id, f"🎯 Single file patch generated for {file_info['path']} with confidence {confidence}")
            return patch_data
            
        except Exception as e:
            self.log_execution(execution_id, f"💥 Single file generation error for {file_info['path']}: {str(e)}")
            return None
    
    async def _generate_chunked_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate patch using chunking strategy for large files"""
        try:
            self.log_execution(execution_id, f"🧩 Starting chunked processing for {file_info['path']}")
            
            # Create file chunks
            chunks = self.file_handler.create_file_chunks(file_info['content'], file_info['path'])
            self.log_execution(execution_id, f"📦 Created {len(chunks)} chunks for {file_info['path']}")
            
            # Process each chunk with progress tracking
            chunk_patches = []
            for chunk in chunks:
                chunk_num = chunk['chunk_id'] + 1
                total_chunks = len(chunks)
                
                self.log_execution(execution_id, f"🔧 Processing chunk {chunk_num}/{total_chunks} for {file_info['path']}")
                self.log_execution(execution_id, f"📋 Chunk {chunk_num}: lines {chunk['start_line']}-{chunk['end_line']}")
                
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
                    self.log_execution(execution_id, f"🤖 Sending chunk {chunk_num} request")
                    
                    response = await self.openai_client.complete_chat([
                        {"role": "system", "content": "You are an expert software engineer analyzing code chunks. Generate only valid JSON responses."},
                        {"role": "user", "content": chunk_prompt}
                    ], model="gpt-4o")
                    
                    self.log_execution(execution_id, f"📨 Chunk {chunk_num} response received")
                    
                    # Parse chunk response
                    chunk_data, error = self.json_handler.clean_and_parse_json(response)
                    
                    if chunk_data and chunk_data.get('confidence_score', 0) > 0.3:
                        chunk_patches.append(chunk_data)
                        self.log_execution(execution_id, f"✅ Chunk {chunk_num} processed successfully (confidence: {chunk_data.get('confidence_score', 0)})")
                    else:
                        self.log_execution(execution_id, f"⚠️ Chunk {chunk_num} had low confidence or failed parsing")
                        
                except Exception as e:
                    self.log_execution(execution_id, f"💥 Error processing chunk {chunk_num}: {e}")
                    continue
            
            # Combine chunk patches
            if not chunk_patches:
                self.log_execution(execution_id, f"❌ No valid chunk patches for {file_info['path']}")
                return None
            
            self.log_execution(execution_id, f"🔗 Combining {len(chunk_patches)} chunk patches for {file_info['path']}")
            combined_patch = self.file_handler.combine_chunk_patches(chunk_patches, file_info)
            
            if combined_patch:
                self.log_execution(execution_id, f"✅ Successfully combined chunk patches for {file_info['path']}")
                combined_patch["processing_strategy"] = "chunked"
                combined_patch["chunks_processed"] = len(chunk_patches)
                return combined_patch
            else:
                self.log_execution(execution_id, f"❌ Failed to combine chunk patches for {file_info['path']}")
                return None
                
        except Exception as e:
            self.log_execution(execution_id, f"💥 Chunked processing error for {file_info['path']}: {e}")
            return None

    # ... keep existing code (_save_patch_attempt_safely method)
