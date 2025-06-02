
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from services.github_client import GitHubClient
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
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate intelligent code patches with enhanced error handling and timeouts"""
        self.log_execution(execution_id, "🚀 Starting enhanced intelligent code generation process")
        
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
        
        self.log_execution(execution_id, f"📁 Processing {len(source_files)} source files for intelligent patch generation")
        self.log_execution(execution_id, f"🔍 DEBUG: Planner data keys: {list(planner_data.keys())}")
        self.log_execution(execution_id, f"📂 DEBUG: Source files: {[f['path'] for f in source_files]}")
        
        # Generate intelligent patches for each source file with progress tracking
        patches = []
        total_files = len(source_files)
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Generating patch {i}/{total_files} for {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                # Use timeout for patch generation
                patch_data = await asyncio.wait_for(
                    self._generate_intelligent_patch(ticket, file_info, planner_data, execution_id),
                    timeout=120.0  # 2 minute timeout per file
                )
                
                if patch_data:
                    patches.append(patch_data)
                    # Save patch with enhanced error handling
                    await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                    self.log_execution(execution_id, f"✅ SUCCESS: Generated valid patch for {file_info['path']}")
                else:
                    self.log_execution(execution_id, f"❌ FAILED: Could not generate valid patch for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                self.log_execution(execution_id, f"⏰ TIMEOUT: Patch generation for {file_info['path']} exceeded 2 minutes")
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
            "intelligent_patching": True,
            "processing_time_info": f"Processed {len(patches)}/{total_files} files successfully"
        }
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} intelligent patches successfully")
        return result
    
    async def _generate_intelligent_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate an intelligent patch with timeout handling and enhanced validation"""
        try:
            self.log_execution(execution_id, f"🔄 DEBUG: Starting patch generation for {file_info['path']}")
            self.log_execution(execution_id, f"📏 DEBUG: File content length: {len(file_info['content'])} characters")
            self.log_execution(execution_id, f"🔍 DEBUG: Analysis root cause: {analysis.get('root_cause', 'Not provided')}")
            
            # Enhanced prompt with clearer instructions
            patch_prompt = f"""
You are an expert software engineer. Generate a PRECISE UNIFIED DIFF PATCH to fix this bug.

BUG REPORT:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace}

TARGET FILE: {file_info['path']}
FILE HASH: {file_info['hash']}
CURRENT SOURCE CODE:
```
{file_info['content'][:5000]}  # Truncate very long files
```

ANALYSIS:
Root Cause: {analysis.get('root_cause', 'Unknown')}
Suggested Approach: {analysis.get('suggested_approach', 'Standard debugging approach')}
Code Analysis: {analysis.get('code_analysis', 'No specific analysis')}

REQUIREMENTS:
1. Generate a UNIFIED DIFF PATCH in standard format (use --- and +++ headers)
2. Only modify the specific lines that fix the bug
3. Preserve all existing functionality
4. Make minimal, targeted changes
5. RESPOND ONLY WITH VALID JSON - no additional text before or after

JSON RESPONSE FORMAT:
{{
    "patch_content": "unified diff format patch with proper headers and line numbers",
    "patched_code": "complete file content after applying the fix",
    "test_code": "unit tests specific to this fix",
    "commit_message": "descriptive commit message explaining the fix",
    "confidence_score": 0.85,
    "explanation": "detailed explanation of what was changed and why",
    "lines_changed": ["specific line numbers that were modified"],
    "base_file_hash": "{file_info['hash']}",
    "patch_type": "unified_diff"
}}

CRITICAL: Response must be valid JSON only. The patch_content must be a valid unified diff.
"""
            
            self.log_execution(execution_id, f"🤖 DEBUG: Sending patch generation request to OpenAI for {file_info['path']}")
            
            # Use timeout for OpenAI request
            response = await asyncio.wait_for(
                self.openai_client.complete_chat([
                    {"role": "system", "content": "You are an expert software engineer. Generate precise unified diff patches in JSON format only. No additional text."},
                    {"role": "user", "content": patch_prompt}
                ], model="gpt-4o"),  # Use more powerful model for better results
                timeout=60.0  # 1 minute timeout for OpenAI
            )
            
            self.log_execution(execution_id, f"📨 DEBUG: OpenAI response received for {file_info['path']}, length: {len(response)} characters")
            
            # Clean response and parse JSON
            try:
                # Remove any markdown code blocks or extra text
                response = response.strip()
                if response.startswith('```json'):
                    response = response[7:]
                if response.endswith('```'):
                    response = response[:-3]
                response = response.strip()
                
                patch_data = json.loads(response)
                self.log_execution(execution_id, f"✅ DEBUG: Successfully parsed JSON response for {file_info['path']}")
                self.log_execution(execution_id, f"🔑 DEBUG: Patch data keys: {list(patch_data.keys())}")
            except json.JSONDecodeError as e:
                self.log_execution(execution_id, f"❌ ERROR: JSON parsing failed for {file_info['path']}: {e}")
                self.log_execution(execution_id, f"📄 ERROR: Raw OpenAI response: {response[:500]}...")
                return None
            
            patch_data["target_file"] = file_info["path"]
            patch_data["file_size"] = len(file_info["content"])
            
            # Validate patch format and content
            self.log_execution(execution_id, f"✔️ DEBUG: Starting patch validation for {file_info['path']}")
            validation_result = self._validate_patch_format(patch_data, file_info)
            if not validation_result["valid"]:
                self.log_execution(execution_id, f"❌ ERROR: Patch validation failed for {file_info['path']}: {validation_result['error']}")
                return None
            
            self.log_execution(execution_id, f"✅ DEBUG: Patch validation passed for {file_info['path']}")
            
            confidence = patch_data.get('confidence_score', 0)
            self.log_execution(execution_id, f"🎯 SUCCESS: Intelligent patch generated for {file_info['path']} with confidence {confidence}")
            return patch_data
            
        except asyncio.TimeoutError:
            self.log_execution(execution_id, f"⏰ ERROR: OpenAI request timeout for {file_info['path']}")
            return None
        except Exception as e:
            self.log_execution(execution_id, f"💥 ERROR: Exception in patch generation for {file_info['path']}: {str(e)}")
            import traceback
            self.log_execution(execution_id, f"📋 ERROR: Full traceback: {traceback.format_exc()}")
            return None
    
    def _validate_patch_format(self, patch_data: Dict, file_info: Dict) -> Dict[str, Any]:
        """Enhanced validation that the patch is in proper unified diff format"""
        try:
            patch_content = patch_data.get("patch_content", "")
            
            if not patch_content:
                return {"valid": False, "error": "Empty patch content"}
            
            # Check for unified diff headers
            if not ("---" in patch_content and "+++" in patch_content):
                return {"valid": False, "error": "Missing unified diff headers (--- and +++)"}
            
            # Check for hunk headers
            if "@@" not in patch_content:
                return {"valid": False, "error": "Missing hunk headers (@@)"}
            
            # Validate required fields
            required_fields = ["patched_code", "base_file_hash", "target_file"]
            for field in required_fields:
                if not patch_data.get(field):
                    return {"valid": False, "error": f"Missing required field: {field}"}
            
            # Validate confidence score
            confidence = patch_data.get("confidence_score", 0)
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                return {"valid": False, "error": "Invalid confidence score (must be 0-1)"}
            
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation exception: {str(e)}"}
    
    async def _save_patch_attempt_safely(self, ticket: Ticket, execution_id: int, patch_data: Dict[str, Any]):
        """Save patch attempt with enhanced error handling and proper field mapping"""
        try:
            with next(get_sync_db()) as db:
                patch_attempt = PatchAttempt(
                    ticket_id=ticket.id,
                    execution_id=execution_id,  # Fixed field name
                    target_file=patch_data.get("target_file"),
                    patch_content=patch_data.get("patch_content"),
                    patched_code=patch_data.get("patched_code"),
                    test_code=patch_data.get("test_code"),
                    commit_message=patch_data.get("commit_message"),
                    confidence_score=patch_data.get("confidence_score", 0.0),
                    base_file_hash=patch_data.get("base_file_hash"),
                    patch_type=patch_data.get("patch_type", "unified_diff"),
                    success=True  # Mark as successful since it passed validation
                )
                db.add(patch_attempt)
                db.commit()
                logger.info(f"Successfully saved patch attempt for execution {execution_id}")
        except Exception as e:
            logger.error(f"Failed to save patch attempt for execution {execution_id}: {e}")
            # Don't raise exception here to avoid failing the entire process

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Enhanced context validation"""
        if not context:
            return False
        
        # Check for GitHub access failure
        if context.get("github_access_failed"):
            return False
        
        # Require planner analysis and source files
        if "planner_analysis" not in context:
            return False
        
        if "source_files" not in context or not context["source_files"]:
            return False
        
        return True

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Enhanced developer results validation"""
        patches = result.get("patches", [])
        return len(patches) > 0 and all(
            isinstance(patch, dict) and 
            "patch_content" in patch and 
            "patched_code" in patch and 
            "target_file" in patch and
            "base_file_hash" in patch
            for patch in patches
        )
