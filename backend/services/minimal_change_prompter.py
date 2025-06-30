
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MinimalChangePrompter:
    """Generate prompts that encourage minimal, focused code changes."""
    
    def __init__(self):
        self.base_instructions = """
CRITICAL PATCHING INSTRUCTIONS:
- Make ONLY the minimal changes necessary to fix the issue
- Preserve original code structure and formatting
- Do NOT rewrite entire functions unless they are fundamentally broken
- Focus on surgical fixes: change specific lines, not whole blocks
- Maintain existing imports, comments, and code organization
- If adding new functionality, add it in the least disruptive way possible
"""
    
    def create_minimal_patch_prompt(self, ticket: Any, file_info: Dict, analysis: Dict) -> str:
        """Create a prompt that encourages minimal changes."""
        
        file_size = len(file_info['content'])
        change_scope = self._determine_change_scope(ticket, file_info, analysis)
        
        prompt = f"""
You are an expert software engineer specializing in MINIMAL, SURGICAL code fixes.

{self.base_instructions}

TICKET INFORMATION:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace or 'No error trace provided'}

TARGET FILE: {file_info['path']}
FILE SIZE: {file_size} characters
CHANGE SCOPE: {change_scope}

COMPLETE FILE CONTENT:
```
{file_info['content']}
```

ANALYSIS CONTEXT:
Root Cause: {analysis.get('root_cause', 'Unknown')}
Suggested Approach: {analysis.get('suggested_approach', 'Minimal fix approach')}

SPECIFIC INSTRUCTIONS FOR THIS FIX:
{self._get_scope_specific_instructions(change_scope)}

REQUIRED RESPONSE FORMAT (JSON ONLY):
{{
    "patch_content": "unified diff with MINIMAL changes - only modify necessary lines",
    "patched_code": "complete file content after applying the minimal fix",
    "test_code": "focused unit tests for the specific change",
    "commit_message": "concise commit message describing the minimal change",
    "confidence_score": 0.95,
    "explanation": "technical explanation focusing on what was changed and why",
    "change_scope": "{change_scope}",
    "lines_modified": "approximate number of lines changed",
    "base_file_hash": "{file_info['hash']}",
    "patch_type": "minimal_unified_diff",
    "addresses_issue": true
}}

CRITICAL: Generate a patch that modifies the FEWEST POSSIBLE LINES while still fixing the issue.
If you're not confident this file contains the issue, set confidence_score to 0.1.
"""
        return prompt
    
    def _determine_change_scope(self, ticket: Any, file_info: Dict, analysis: Dict) -> str:
        """Determine the appropriate scope of changes based on the issue."""
        
        # Analyze the error trace and description for scope hints
        error_keywords = ['typo', 'variable', 'import', 'syntax', 'missing', 'undefined']
        rewrite_keywords = ['refactor', 'redesign', 'architecture', 'complete', 'rewrite']
        
        issue_text = f"{ticket.title} {ticket.description} {ticket.error_trace or ''}".lower()
        
        if any(keyword in issue_text for keyword in error_keywords):
            return "MINIMAL_FIX"
        elif any(keyword in issue_text for keyword in rewrite_keywords):
            return "TARGETED_REWRITE"
        elif len(file_info['content']) < 5000:
            return "SMALL_FILE_EDIT"
        else:
            return "FOCUSED_CHANGE"
    
    def _get_scope_specific_instructions(self, scope: str) -> str:
        """Get specific instructions based on the change scope."""
        
        instructions = {
            "MINIMAL_FIX": """
- Fix ONLY the specific error mentioned
- Change 1-3 lines maximum if possible
- Do NOT modify surrounding code
- Preserve all existing functionality
""",
            "TARGETED_REWRITE": """
- Rewrite only the specific function/method that's broken
- Keep the same function signature and interface
- Preserve surrounding code exactly as-is
- Make the rewrite as small as possible while being correct
""",
            "SMALL_FILE_EDIT": """
- Since this is a small file, you can make broader changes if needed
- Still prefer minimal changes when possible
- Ensure the entire file remains cohesive
""",
            "FOCUSED_CHANGE": """
- Identify the specific section that needs changes
- Make surgical modifications to that section only
- Leave all other parts of the file untouched
- Use the smallest possible diff
"""
        }
        
        return instructions.get(scope, instructions["FOCUSED_CHANGE"])
    
    def create_chunked_minimal_prompt(self, ticket: Any, chunk: Dict, file_info: Dict) -> str:
        """Create a minimal change prompt for file chunks."""
        
        prompt = f"""
You are analyzing a CHUNK of a larger file for minimal fixes.

{self.base_instructions}

TICKET: {ticket.title}
DESCRIPTION: {ticket.description}

CHUNK CONTEXT:
- File: {file_info['path']}
- Chunk: Lines {chunk['start_line']}-{chunk['end_line']}
- This is chunk {chunk['chunk_id'] + 1} of {chunk.get('total_chunks', 'unknown')}

CHUNK CONTENT:
```
{chunk['content']}
```

INSTRUCTIONS FOR CHUNK ANALYSIS:
- Only suggest changes if this chunk contains the actual problem
- If this chunk doesn't relate to the issue, return confidence_score: 0.1
- Make the smallest possible changes to fix the issue
- Consider context from surrounding chunks

RESPONSE FORMAT (JSON):
{{
    "patch_content": "minimal unified diff for this chunk only",
    "patched_code": "complete chunk content with minimal changes",
    "confidence_score": 0.95,
    "explanation": "why this chunk needs changes",
    "addresses_issue": true,
    "chunk_id": {chunk['chunk_id']},
    "lines_affected": "list of line numbers changed"
}}

Only propose changes if you're confident this chunk contains the issue.
"""
        return prompt

