from typing import Dict, Any

def create_semantic_patch_prompt(ticket: Any, file_info: Dict, target: Dict) -> str:
    """Create a semantic patch prompt for targeted fixes."""
    return f"""
You are an expert at making SURGICAL code fixes using AST-based targeting.

TARGET INFORMATION:
- File: {file_info['path']}
- Target: {target.get('name', 'Unknown')}
- Type: {target.get('type', 'Unknown')}
- Line: {target.get('line_number', 'Unknown')}

ISSUE TO FIX:
Title: {ticket.title}
Description: {ticket.description}
Error: {ticket.error_trace or 'No error trace'}

TARGET CODE CONTEXT:
```
{target.get('content', 'No content')}
```

FULL FILE CONTENT:
```
{file_info['content']}
```

INSTRUCTIONS:
- Fix ONLY the specific issue in the identified target
- Make minimal changes preserving structure
- Generate valid JSON with patch_content and patched_code

REQUIRED JSON FORMAT:
{{
    "patch_content": "unified diff with minimal changes",
    "patched_code": "complete file after fix",
    "confidence_score": 0.95,
    "explanation": "what was changed and why",
    "lines_modified": "number of lines changed",
    "addresses_issue": true
}}
"""

def create_semantic_chunk_prompt(ticket: Any, chunk: Dict, file_info: Dict) -> str:
    """Create a semantic chunk prompt."""
    return f"""
You are analyzing a code chunk for semantic fixes.

CHUNK INFO:
- File: {file_info['path']}
- Lines: {chunk['start_line']}-{chunk['end_line']}
- Chunk {chunk['chunk_id'] + 1} of {chunk.get('total_chunks', 'unknown')}

ISSUE: {ticket.title}
DESCRIPTION: {ticket.description}

CHUNK CONTENT:
```
{chunk['content']}
```

INSTRUCTIONS:
- Only fix if this chunk contains the actual issue
- Return confidence_score: 0.1 if not relevant
- Make minimal changes if relevant

REQUIRED JSON FORMAT:
{{
    "patch_content": "minimal diff for this chunk",
    "patched_code": "chunk content with fixes",
    "confidence_score": 0.95,
    "explanation": "why this chunk needs changes",
    "addresses_issue": true,
    "chunk_id": {chunk['chunk_id']}
}}
"""