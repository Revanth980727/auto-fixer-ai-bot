
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class LargeFileHandler:
    """Handler for processing large files with chunking and incremental patching"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.chunk_size_limit = 15000  # characters
        self.context_overlap = 500     # characters overlap between chunks
    
    def should_chunk_file(self, file_content: str) -> bool:
        """Determine if file should be processed in chunks"""
        return len(file_content) > self.chunk_size_limit
    
    def create_file_chunks(self, file_content: str, file_path: str) -> List[Dict[str, Any]]:
        """Create overlapping chunks of large files"""
        if not self.should_chunk_file(file_content):
            return [{
                "content": file_content,
                "start_line": 1,
                "end_line": len(file_content.splitlines()),
                "chunk_id": 0,
                "is_single_chunk": True
            }]
        
        lines = file_content.splitlines(keepends=True)
        chunks = []
        chunk_id = 0
        
        # Calculate lines per chunk
        total_chars = len(file_content)
        chars_per_chunk = self.chunk_size_limit
        lines_per_chunk = max(50, int(len(lines) * chars_per_chunk / total_chars))
        
        start_line = 0
        while start_line < len(lines):
            end_line = min(start_line + lines_per_chunk, len(lines))
            
            # Add overlap from previous chunk
            chunk_start = max(0, start_line - self.context_overlap // 20)
            chunk_content = ''.join(lines[chunk_start:end_line])
            
            chunks.append({
                "content": chunk_content,
                "start_line": start_line + 1,  # 1-based line numbers
                "end_line": end_line,
                "chunk_id": chunk_id,
                "is_single_chunk": False,
                "overlap_start": chunk_start,
                "total_chunks": 0  # Will be filled later
            })
            
            start_line = end_line - self.context_overlap // 20
            chunk_id += 1
        
        # Update total chunks count
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)
        
        logger.info(f"Created {len(chunks)} chunks for {file_path}")
        return chunks
    
    def create_chunk_context(self, chunk: Dict[str, Any], file_info: Dict[str, Any], ticket) -> str:
        """Create focused context for a specific chunk"""
        return f"""
CHUNK ANALYSIS CONTEXT:
File: {file_info['path']}
Chunk {chunk['chunk_id'] + 1}/{chunk['total_chunks']}
Lines {chunk['start_line']}-{chunk['end_line']}
Content Length: {len(chunk['content'])} characters

ISSUE TO FIX:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace or 'No error trace provided'}

CHUNK CONTENT:
```
{chunk['content']}
```

INSTRUCTIONS:
Focus on this specific section of the file. If the issue is not in this chunk, 
return confidence_score: 0.1 and explanation stating this chunk doesn't contain the issue.
If you find the issue, provide a targeted fix for just this section.
"""
    
    def combine_chunk_patches(self, chunk_patches: List[Dict[str, Any]], file_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Combine multiple chunk patches into a single file patch"""
        # Filter patches with reasonable confidence
        valid_patches = [p for p in chunk_patches if p.get('confidence_score', 0) > 0.5]
        
        if not valid_patches:
            logger.warning(f"No valid chunk patches found for {file_info['path']}")
            return None
        
        # If only one valid patch, return it
        if len(valid_patches) == 1:
            return valid_patches[0]
        
        # Combine multiple patches
        combined_patch_content = []
        combined_explanation = []
        combined_confidence = sum(p.get('confidence_score', 0) for p in valid_patches) / len(valid_patches)
        
        # Sort patches by line number
        valid_patches.sort(key=lambda p: p.get('start_line', 0))
        
        for patch in valid_patches:
            combined_patch_content.append(patch.get('patch_content', ''))
            combined_explanation.append(f"Chunk {patch.get('chunk_id', 'N/A')}: {patch.get('explanation', '')}")
        
        # Reconstruct full file content with all patches applied
        # This is a simplified version - in practice, you'd need more sophisticated merging
        patched_code = file_info['content']
        for patch in valid_patches:
            if patch.get('patched_code'):
                # Apply each chunk's changes (simplified)
                patched_code = patch.get('patched_code')
        
        return {
            "patch_content": "\n\n".join(combined_patch_content),
            "patched_code": patched_code,
            "test_code": valid_patches[0].get('test_code', ''),
            "commit_message": f"Combined fix for {file_info['path']} ({len(valid_patches)} sections)",
            "confidence_score": min(combined_confidence, 0.95),
            "explanation": "\n\n".join(combined_explanation),
            "target_file": file_info['path'],
            "base_file_hash": file_info['hash'],
            "patch_type": "combined_chunks",
            "chunks_processed": len(valid_patches)
        }
