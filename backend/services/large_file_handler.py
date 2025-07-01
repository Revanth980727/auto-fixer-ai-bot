
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from services.chunk_merger import ChunkMerger
import logging

logger = logging.getLogger(__name__)

class LargeFileHandler:
    """Handle large files by breaking them into manageable chunks with intelligent merging."""
    
    def __init__(self):
        self.chunk_size = 3000  # Reduced for better context
        self.overlap_size = 200  # Overlap between chunks
        self.chunk_merger = ChunkMerger()
    
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
    
    async def combine_chunk_patches(self, chunk_patches: List[Dict[str, Any]], file_info: Dict, ticket: Any) -> Optional[Dict[str, Any]]:
        """Combine chunk patches using intelligent merging with global validation."""
        try:
            logger.info(f"🔗 Combining {len(chunk_patches)} chunk patches for {file_info['path']}")
            
            # Log chunk patch data for debugging
            for i, patch in enumerate(chunk_patches):
                confidence = patch.get('confidence_score', 0)
                logger.debug(f"  - Chunk {i}: confidence={confidence:.3f}, lines={patch.get('start_line', 0)}-{patch.get('end_line', 0)}")
            
            # Prepare chunks for merging - using consistent field names
            chunks_for_merge = []
            for patch in chunk_patches:
                chunk_data = {
                    'start_line': patch.get('start_line', 0),
                    'end_line': patch.get('end_line', 0),
                    'patched_content': patch.get('patched_code', ''),
                    'confidence_score': patch.get('confidence_score', 0)  # Fixed: use consistent field name
                }
                chunks_for_merge.append(chunk_data)
                
                # Add validation warning for low confidence
                if chunk_data['confidence_score'] == 0:
                    logger.warning(f"⚠️ Chunk at lines {chunk_data['start_line']}-{chunk_data['end_line']} has zero confidence")
            
            # Log data structure before merging
            logger.debug(f"🔍 Prepared {len(chunks_for_merge)} chunks for merging")
            
            # Use the chunk merger for intelligent combination
            merge_result = self.chunk_merger.merge_chunks_intelligently(
                chunks_for_merge, 
                file_info['content'], 
                file_info['path']
            )
            
            if not merge_result["success"]:
                logger.error(f"❌ Chunk merging failed: {merge_result.get('error', 'Unknown error')}")
                return None
            
            # Calculate combined confidence
            total_confidence = sum(p.get('confidence_score', 0) for p in chunk_patches)
            avg_confidence = total_confidence / len(chunk_patches) if chunk_patches else 0
            
            # Create the final combined patch
            combined_patch = {
                'patch_content': merge_result['patch_content'],
                'patched_code': merge_result['merged_content'],
                'confidence_score': avg_confidence,
                'commit_message': f"Apply {len(chunk_patches)} intelligent fixes to {file_info['path']}",
                'explanation': f"Combined {len(chunk_patches)} chunk patches with structural validation",
                'patch_type': 'intelligent_chunked_merge',
                'chunks_merged': len(chunk_patches),
                'validation_info': merge_result.get('validation_info', {}),
                'addresses_issue': True
            }
            
            logger.info(f"✅ Successfully combined chunk patches with confidence {avg_confidence:.3f}")
            return combined_patch
            
        except Exception as e:
            logger.error(f"💥 Error combining chunk patches: {e}")
            return None
