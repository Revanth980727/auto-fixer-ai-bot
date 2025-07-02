
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from services.semantic_file_handler import SemanticFileHandler
import logging

logger = logging.getLogger(__name__)

class LargeFileHandler:
    """Handle large files by breaking them into manageable chunks with intelligent merging."""
    
    def __init__(self):
        self.chunk_size = 3000  # Reduced for better context
        self.overlap_size = 200  # Overlap between chunks
        self.semantic_handler = SemanticFileHandler()
    
    def create_file_chunks(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Create overlapping chunks that preserve code structure."""
        lines = content.split('\n')
        chunks = []
        
        if len(content) <= self.chunk_size:
            return [{
                'chunk_id': 0,
                'start_line': 0,
                'end_line': len(lines) - 1,
                'content': content,
                'file_path': file_path,
                'total_chunks': 1
            }]
        
        # Create chunks with structural boundaries
        chunk_boundaries = self._find_logical_boundaries(lines)
        
        for i, (start, end) in enumerate(chunk_boundaries):
            chunk_content = '\n'.join(lines[start:end + 1])
            chunks.append({
                'chunk_id': i,
                'start_line': start,
                'end_line': end,
                'content': chunk_content,
                'file_path': file_path,
                'total_chunks': len(chunk_boundaries)
            })
        
        logger.info(f"📦 Created {len(chunks)} logical chunks for {file_path}")
        return chunks
    
    def _find_logical_boundaries(self, lines: List[str]) -> List[Tuple[int, int]]:
        """Find logical boundaries for chunks (classes, functions, etc.)."""
        boundaries = []
        current_start = 0
        current_size = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            current_size += len(line) + 1  # +1 for newline
            
            # Check if we've reached a logical boundary
            is_boundary = (
                self._is_class_definition(line) or
                self._is_function_definition(line) or
                current_size >= self.chunk_size
            )
            
            if is_boundary and current_start < i:
                boundaries.append((current_start, i - 1))
                current_start = max(0, i - self.overlap_size // 50)  # Small overlap
                current_size = 0
            
            i += 1
        
        # Add the final chunk
        if current_start < len(lines):
            boundaries.append((current_start, len(lines) - 1))
        
        return boundaries
    
    def _is_class_definition(self, line: str) -> bool:
        """Check if line is a class definition."""
        return bool(re.match(r'^\s*class\s+\w+', line))
    
    def _is_function_definition(self, line: str) -> bool:
        """Check if line is a function definition."""
        return bool(re.match(r'^\s*def\s+\w+', line))
    
    def combine_chunk_patches(self, chunk_patches: List[Dict[str, Any]], file_info: Dict, ticket: Any) -> Optional[Dict[str, Any]]:
        """DEPRECATED: Chunk merging removed - use semantic approach only."""
        logger.error("❌ DEPRECATED: combine_chunk_patches called - chunk merging is disabled")
        logger.error("📍 Use SemanticPatcher.identify_target_nodes() instead for AST-based processing")
        raise NotImplementedError("Chunk merging has been removed. Use semantic processing instead.")
