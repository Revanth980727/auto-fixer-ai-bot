
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
        """Generate intelligent code patches with file state tracking"""
        self.log_execution(execution_id, "Starting intelligent code generation process")
        
        if not context:
            self.log_execution(execution_id, "No context provided - developer agent requires planner analysis")
            raise Exception("Developer agent requires context with planner analysis")
        
        # Check for GitHub access failure
        if context.get("github_access_failed"):
            self.log_execution(execution_id, "GitHub access failed - cannot generate patches without source code")
            raise Exception("GitHub repository access required for patch generation")
        
        planner_data = context.get("planner_analysis", {})
        source_files = context.get("source_files", [])
        
        if not source_files:
            self.log_execution(execution_id, "No source files available - cannot generate patches")
            raise Exception("No source files available for patch generation")
        
        self.log_execution(execution_id, f"Processing {len(source_files)} source files for intelligent patch generation")
        self.log_execution(execution_id, f"DEBUG: Planner data keys: {list(planner_data.keys())}")
        self.log_execution(execution_id, f"DEBUG: Source files: {[f['path'] for f in source_files]}")
        
        # Add processing delay for realistic timing
        await asyncio.sleep(3)
        
        # Generate intelligent patches for each source file
        patches = []
        for file_info in source_files:
            self.log_execution(execution_id, f"Generating intelligent patch for {file_info['path']}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            patch_data = await self._generate_intelligent_patch(ticket, file_info, planner_data, execution_id)
            if patch_data:
                patches.append(patch_data)
                self._save_patch_attempt(ticket, execution_id, patch_data)
                self.log_execution(execution_id, f"SUCCESS: Generated valid patch for {file_info['path']}")
            else:
                self.log_execution(execution_id, f"FAILED: Could not generate valid patch for {file_info['path']}")
        
        if not patches:
            self.log_execution(execution_id, "CRITICAL: Failed to generate any valid patches for any file")
            raise Exception("No valid patches could be generated")
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data,
            "intelligent_patching": True
        }
        
        self.log_execution(execution_id, f"COMPLETED: Generated {len(patches)} intelligent patches successfully")
        return result
    
    async def _generate_intelligent_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate an intelligent patch with proper diff format and validation"""
        try:
            self.log_execution(execution_id, f"DEBUG: Starting patch generation for {file_info['path']}")
            self.log_execution(execution_id, f"DEBUG: File content length: {len(file_info['content'])} characters")
            self.log_execution(execution_id, f"DEBUG: Analysis root cause: {analysis.get('root_cause', 'Not provided')}")
            
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
{file_info['content']}
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

Please provide your solution in JSON format:
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

CRITICAL: The patch_content must be a valid unified diff that can be applied with git apply or patch command.
"""
            
            self.log_execution(execution_id, f"DEBUG: Sending patch generation request to OpenAI for {file_info['path']}")
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": "You are an expert software engineer. Generate precise unified diff patches that can be applied automatically. Focus on minimal, targeted changes."},
                {"role": "user", "content": patch_prompt}
            ])
            
            self.log_execution(execution_id, f"DEBUG: OpenAI response received for {file_info['path']}, length: {len(response)} characters")
            self.log_execution(execution_id, f"DEBUG: OpenAI response preview: {response[:200]}...")
            
            try:
                patch_data = json.loads(response)
                self.log_execution(execution_id, f"DEBUG: Successfully parsed JSON response for {file_info['path']}")
                self.log_execution(execution_id, f"DEBUG: Patch data keys: {list(patch_data.keys())}")
            except json.JSONDecodeError as e:
                self.log_execution(execution_id, f"ERROR: JSON parsing failed for {file_info['path']}: {e}")
                self.log_execution(execution_id, f"ERROR: Raw OpenAI response: {response}")
                return None
            
            patch_data["target_file"] = file_info["path"]
            patch_data["file_size"] = len(file_info["content"])
            
            # Validate patch format and content
            self.log_execution(execution_id, f"DEBUG: Starting patch validation for {file_info['path']}")
            validation_result = self._validate_patch_format(patch_data, file_info)
            if not validation_result["valid"]:
                self.log_execution(execution_id, f"ERROR: Patch validation failed for {file_info['path']}: {validation_result['error']}")
                self.log_execution(execution_id, f"ERROR: Invalid patch content preview: {patch_data.get('patch_content', 'No patch content')[:200]}...")
                return None
            
            self.log_execution(execution_id, f"DEBUG: Patch validation passed for {file_info['path']}")
            
            # Test patch application locally
            self.log_execution(execution_id, f"DEBUG: Starting patch application test for {file_info['path']}")
            if not self._test_patch_application(patch_data, file_info):
                self.log_execution(execution_id, f"ERROR: Patch application test failed for {file_info['path']}")
                return None
            
            self.log_execution(execution_id, f"DEBUG: Patch application test passed for {file_info['path']}")
            
            confidence = patch_data.get('confidence_score', 0)
            self.log_execution(execution_id, f"SUCCESS: Intelligent patch generated for {file_info['path']} with confidence {confidence}")
            return patch_data
            
        except Exception as e:
            self.log_execution(execution_id, f"ERROR: Exception in patch generation for {file_info['path']}: {str(e)}")
            self.log_execution(execution_id, f"ERROR: Exception type: {type(e).__name__}")
            import traceback
            self.log_execution(execution_id, f"ERROR: Full traceback: {traceback.format_exc()}")
            return None
    
    def _validate_patch_format(self, patch_data: Dict, file_info: Dict) -> Dict[str, Any]:
        """Validate that the patch is in proper unified diff format"""
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
            
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation exception: {str(e)}"}
    
    def _test_patch_application(self, patch_data: Dict, file_info: Dict) -> bool:
        """Test patch application locally to ensure it works"""
        try:
            import tempfile
            import subprocess
            import os
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write original file
                original_file = os.path.join(temp_dir, "original.py")
                with open(original_file, "w") as f:
                    f.write(file_info["content"])
                
                # Write patch file
                patch_file = os.path.join(temp_dir, "fix.patch")
                with open(patch_file, "w") as f:
                    f.write(patch_data["patch_content"])
                
                # Test patch application
                result = subprocess.run([
                    "patch", "-s", original_file, patch_file
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.warning(f"Patch test failed: {result.stderr}")
                    return False
                
                # Read patched content and compare with expected
                with open(original_file, "r") as f:
                    patched_content = f.read()
                
                expected_content = patch_data.get("patched_code", "")
                if patched_content.strip() != expected_content.strip():
                    logger.warning("Patched content doesn't match expected result")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error testing patch application: {e}")
            return False
    
    def _save_patch_attempt(self, ticket: Ticket, execution_id: int, patch_data: Dict[str, Any]):
        """Save enhanced patch attempt to database"""
        try:
            with next(get_sync_db()) as db:
                patch_attempt = PatchAttempt(
                    ticket_id=ticket.id,
                    agent_execution_id=execution_id,
                    target_file=patch_data.get("target_file"),
                    patch_content=patch_data.get("patch_content"),
                    confidence_score=patch_data.get("confidence_score", 0.0),
                    base_file_hash=patch_data.get("base_file_hash"),
                    patch_type=patch_data.get("patch_type", "unified_diff"),
                    test_code=patch_data.get("test_code"),
                    patched_code=patch_data.get("patched_code")
                )
                db.add(patch_attempt)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to save enhanced patch attempt: {e}")

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate developer context"""
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
        """Validate enhanced developer results"""
        patches = result.get("patches", [])
        return len(patches) > 0 and all(
            isinstance(patch, dict) and 
            "patch_content" in patch and 
            "patched_code" in patch and 
            "target_file" in patch and
            "base_file_hash" in patch
            for patch in patches
        )
