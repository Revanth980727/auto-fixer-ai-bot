
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from typing import Dict, Any, Optional
import json
import asyncio

class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.DEVELOPER)
        self.openai_client = OpenAIClient()
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate code patches for the ticket with actual source code context"""
        self.log_execution(execution_id, "Starting code generation process with repository context")
        
        if not context:
            raise Exception("Developer agent requires context with planner analysis and source files")
        
        planner_data = context.get("planner_analysis", {})
        source_files = context.get("source_files", [])
        
        if not source_files:
            self.log_execution(execution_id, "No source files available - cannot generate patches")
            raise Exception("No source files available for patch generation")
        
        # Add processing delay for realistic timing
        await asyncio.sleep(3)
        
        # Generate patch for each available source file
        patches = []
        for file_info in source_files:
            self.log_execution(execution_id, f"Generating patch for {file_info['path']}")
            
            patch_data = await self._generate_patch(ticket, file_info, planner_data, execution_id)
            if patch_data:
                patches.append(patch_data)
                self._save_patch_attempt(ticket, execution_id, patch_data)
        
        if not patches:
            self.log_execution(execution_id, "Failed to generate any valid patches")
            raise Exception("No valid patches could be generated")
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data
        }
        
        self.log_execution(execution_id, f"Generated {len(patches)} patches successfully")
        return result
    
    async def _generate_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate a patch for a specific file with actual source code"""
        try:
            patch_prompt = f"""
You are an expert software engineer. Generate a minimal code patch to fix this bug using the provided source code:

BUG REPORT:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace}

TARGET FILE: {file_info['path']}
CURRENT SOURCE CODE:
```
{file_info['content']}
```

ROOT CAUSE: {analysis.get('root_cause', 'Unknown')}
SUGGESTED APPROACH: {analysis.get('suggested_approach', 'Standard debugging approach')}
CODE ANALYSIS: {analysis.get('code_analysis', 'No specific analysis')}

Please provide your solution in JSON format:
{{
    "patch_content": "unified diff format patch with specific line changes",
    "patched_code": "complete file content after applying the fix",
    "test_code": "unit tests specific to this fix",
    "commit_message": "descriptive commit message explaining the fix",
    "confidence_score": 0.85,
    "explanation": "detailed explanation of what was changed and why",
    "lines_changed": ["line numbers that were modified"]
}}

IMPORTANT: 
- Only modify the specific lines that fix the bug
- Ensure the patched_code is the complete file with the fix applied
- Make minimal changes to preserve existing functionality
- Include specific line numbers that were changed
"""
            
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": "You are an expert software engineer. Provide fixes in the exact JSON format requested. Focus on minimal, targeted changes."},
                {"role": "user", "content": patch_prompt}
            ])
            
            patch_data = json.loads(response)
            patch_data["target_file"] = file_info["path"]
            
            # Validate patch content
            if not patch_data.get("patch_content") or not patch_data.get("patched_code"):
                self.log_execution(execution_id, f"Invalid patch generated for {file_info['path']} - missing content")
                return None
            
            self.log_execution(execution_id, f"Patch generated for {file_info['path']} with confidence {patch_data.get('confidence_score', 0)}")
            return patch_data
            
        except (json.JSONDecodeError, Exception) as e:
            self.log_execution(execution_id, f"Error generating patch for {file_info['path']}: {e}")
            return None
    
    # ... keep existing code (_save_patch_attempt method)

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate developer context"""
        required_fields = ["planner_analysis", "source_files"]
        return all(field in context for field in required_fields) and len(context.get("source_files", [])) > 0

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate developer results"""
        patches = result.get("patches", [])
        return len(patches) > 0 and all(
            isinstance(patch, dict) and 
            "patch_content" in patch and 
            "patched_code" in patch and 
            "target_file" in patch 
            for patch in patches
        )
