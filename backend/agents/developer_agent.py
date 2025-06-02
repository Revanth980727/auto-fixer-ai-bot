
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
        """Generate intelligent code patches with enhanced error handling and full file context"""
        self.log_execution(execution_id, "🚀 Starting enhanced intelligent code generation with full context")
        
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
        
        # Generate intelligent patches with full file context
        patches = []
        total_files = len(source_files)
        
        for i, file_info in enumerate(source_files, 1):
            self.log_execution(execution_id, f"🔧 Generating enhanced patch {i}/{total_files} for {file_info['path']}")
            self.log_execution(execution_id, f"📊 File relevance score: {file_info.get('relevance_score', 'N/A')}")
            
            # Add file state tracking
            file_hash = hashlib.sha256(file_info['content'].encode()).hexdigest()
            file_info['hash'] = file_hash
            
            try:
                # Use enhanced patch generation with full context
                patch_data = await asyncio.wait_for(
                    self._generate_enhanced_patch(ticket, file_info, planner_data, execution_id),
                    timeout=180.0  # 3 minute timeout for complex analysis
                )
                
                if patch_data:
                    patches.append(patch_data)
                    # Save patch with enhanced error handling
                    await self._save_patch_attempt_safely(ticket, execution_id, patch_data)
                    self.log_execution(execution_id, f"✅ SUCCESS: Generated enhanced patch for {file_info['path']}")
                else:
                    self.log_execution(execution_id, f"❌ FAILED: Could not generate valid patch for {file_info['path']}")
                    
            except asyncio.TimeoutError:
                self.log_execution(execution_id, f"⏰ TIMEOUT: Patch generation for {file_info['path']} exceeded 3 minutes")
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
            "enhanced_context": True,
            "processing_time_info": f"Processed {len(patches)}/{total_files} files successfully with full context"
        }
        
        self.log_execution(execution_id, f"🎉 COMPLETED: Generated {len(patches)} enhanced patches successfully")
        return result
    
    async def _generate_enhanced_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Dict[str, Any]:
        """Generate an enhanced patch with full file context and multi-step analysis"""
        try:
            self.log_execution(execution_id, f"🔄 Starting enhanced patch generation for {file_info['path']}")
            self.log_execution(execution_id, f"📏 Full file content: {len(file_info['content'])} characters")
            
            # Step 1: Analyze the problem with full context
            analysis_result = await self._analyze_problem_context(ticket, file_info, analysis, execution_id)
            
            if not analysis_result:
                self.log_execution(execution_id, f"❌ Problem analysis failed for {file_info['path']}")
                return None
            
            # Step 2: Generate the fix with enhanced context
            patch_prompt = f"""
You are an expert software engineer with deep understanding of code architecture and debugging.

TICKET INFORMATION:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace or 'No error trace provided'}

TARGET FILE: {file_info['path']}
FILE HASH: {file_info['hash']}
FILE SIZE: {len(file_info['content'])} characters
RELEVANCE SCORE: {file_info.get('relevance_score', 'N/A')}

COMPLETE FILE CONTENT:
```
{file_info['content']}
```

PROBLEM ANALYSIS:
{analysis_result}

PLANNER CONTEXT:
Root Cause: {analysis.get('root_cause', 'Unknown')}
Suggested Approach: {analysis.get('suggested_approach', 'Standard debugging approach')}
Code Analysis: {analysis.get('code_analysis', 'No specific analysis')}

REQUIREMENTS FOR FIX:
1. Generate a PRECISE UNIFIED DIFF PATCH that fixes the specific issue
2. Consider the ENTIRE file context when making changes
3. Ensure the fix doesn't break existing functionality
4. Make minimal but effective changes
5. Provide comprehensive testing suggestions
6. Include proper error handling if relevant

RESPONSE FORMAT (JSON ONLY):
{{
    "patch_content": "unified diff format patch with proper headers and line numbers",
    "patched_code": "complete file content after applying the fix",
    "test_code": "comprehensive unit tests specific to this fix",
    "commit_message": "detailed commit message explaining the fix",
    "confidence_score": 0.95,
    "explanation": "detailed technical explanation of the problem and solution",
    "lines_changed": ["specific line numbers that were modified"],
    "base_file_hash": "{file_info['hash']}",
    "patch_type": "unified_diff",
    "impact_analysis": "analysis of potential side effects",
    "validation_steps": ["steps to verify the fix works correctly"]
}}

CRITICAL: Generate ONLY valid JSON. The patch must be a proper unified diff that can be applied.
"""
            
            self.log_execution(execution_id, f"🤖 Sending enhanced patch generation request for {file_info['path']}")
            
            # Use GPT-4o for better analysis with longer context
            response = await asyncio.wait_for(
                self.openai_client.complete_chat([
                    {"role": "system", "content": "You are an expert software engineer specializing in precise code fixes. Generate only valid JSON responses with proper unified diff patches."},
                    {"role": "user", "content": patch_prompt}
                ], model="gpt-4o"),  # Use most powerful model
                timeout=120.0  # 2 minute timeout for complex analysis
            )
            
            self.log_execution(execution_id, f"📨 Enhanced response received for {file_info['path']}, length: {len(response)}")
            
            # Parse and validate response
            try:
                # Clean response
                response = response.strip()
                if response.startswith('```json'):
                    response = response[7:]
                if response.endswith('```'):
                    response = response[:-3]
                response = response.strip()
                
                patch_data = json.loads(response)
                self.log_execution(execution_id, f"✅ Successfully parsed enhanced JSON for {file_info['path']}")
                
            except json.JSONDecodeError as e:
                self.log_execution(execution_id, f"❌ JSON parsing failed for {file_info['path']}: {e}")
                return None
            
            # Add metadata
            patch_data["target_file"] = file_info["path"]
            patch_data["file_size"] = len(file_info["content"])
            patch_data["enhanced_generation"] = True
            
            # Enhanced validation
            validation_result = self._validate_enhanced_patch(patch_data, file_info)
            if not validation_result["valid"]:
                self.log_execution(execution_id, f"❌ Enhanced validation failed for {file_info['path']}: {validation_result['error']}")
                return None
            
            confidence = patch_data.get('confidence_score', 0)
            self.log_execution(execution_id, f"🎯 Enhanced patch generated for {file_info['path']} with confidence {confidence}")
            return patch_data
            
        except asyncio.TimeoutError:
            self.log_execution(execution_id, f"⏰ Enhanced generation timeout for {file_info['path']}")
            return None
        except Exception as e:
            self.log_execution(execution_id, f"💥 Enhanced generation error for {file_info['path']}: {str(e)}")
            return None
    
    async def _analyze_problem_context(self, ticket: Ticket, file_info: Dict, analysis: Dict, execution_id: int) -> Optional[str]:
        """Analyze the problem with full file context first"""
        try:
            analysis_prompt = f"""
Analyze this code file in the context of the reported bug. Provide a detailed technical analysis.

BUG REPORT:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace or 'No error trace'}

FILE TO ANALYZE: {file_info['path']}
COMPLETE CODE:
```
{file_info['content']}
```

Provide a detailed analysis focusing on:
1. Where exactly the bug might be located in this file
2. What the root cause appears to be
3. How this file relates to the error described
4. What specific lines or functions need attention
5. Any dependencies or side effects to consider

Respond with a clear technical analysis in plain text (not JSON).
"""
            
            analysis_response = await asyncio.wait_for(
                self.openai_client.complete_chat([
                    {"role": "system", "content": "You are a senior software engineer performing detailed code analysis for debugging."},
                    {"role": "user", "content": analysis_prompt}
                ], model="gpt-4o"),
                timeout=60.0
            )
            
            self.log_execution(execution_id, f"🔍 Problem analysis completed for {file_info['path']}")
            return analysis_response.strip()
            
        except Exception as e:
            self.log_execution(execution_id, f"⚠️ Problem analysis failed for {file_info['path']}: {e}")
            return None
    
    def _validate_enhanced_patch(self, patch_data: Dict, file_info: Dict) -> Dict[str, Any]:
        """Enhanced validation for patches with additional checks"""
        try:
            # Basic validation
            basic_validation = self._validate_patch_format(patch_data, file_info)
            if not basic_validation["valid"]:
                return basic_validation
            
            # Additional enhanced validations
            patch_content = patch_data.get("patch_content", "")
            patched_code = patch_data.get("patched_code", "")
            
            # Check if patched code is significantly different
            original_lines = set(file_info['content'].splitlines())
            patched_lines = set(patched_code.splitlines())
            
            if len(patched_lines.symmetric_difference(original_lines)) == 0:
                return {"valid": False, "error": "Patch appears to make no changes"}
            
            # Check confidence score
            confidence = patch_data.get("confidence_score", 0)
            if confidence < 0.7:
                return {"valid": False, "error": f"Confidence score too low: {confidence}"}
            
            # Validate explanation exists
            if not patch_data.get("explanation"):
                return {"valid": False, "error": "Missing explanation field"}
            
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": f"Enhanced validation exception: {str(e)}"}
    
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
            required_fields = ["patched_code", "base_file_hash", "target_file", "explanation"]
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
    
    # ... keep existing code (_save_patch_attempt_safely, _validate_context, _validate_result methods)
