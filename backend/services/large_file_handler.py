
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from services.chunk_merger import ChunkMerger
from services.semantic_file_handler import SemanticFileHandler
import logging

logger = logging.getLogger(__name__)

class LargeFileHandler:
    """Handle large files by breaking them into manageable chunks with intelligent merging."""
    
    def __init__(self):
        self.chunk_size = 3000  # Reduced for better context
        self.overlap_size = 200  # Overlap between chunks
        self.chunk_merger = ChunkMerger()
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
    
    async def combine_chunk_patches(self, chunk_patches: List[Dict[str, Any]], file_info: Dict, ticket: Any) -> Optional[Dict[str, Any]]:
        """Process using semantic approach only - chunk merging deprecated."""
        try:
            # Use semantic approach as the primary and only method
            logger.info(f"🎯 Using semantic processing for {file_info['path']} (chunk merging deprecated)")
            
            # Import semantic patcher for large file handling
            from services.semantic_patcher import SemanticPatcher
            semantic_patcher = SemanticPatcher()
            
            # Use semantic patcher with AST subdivision for large files
            targets = semantic_patcher.identify_target_nodes(
                file_info['content'], 
                ticket.description + " " + (ticket.error_trace or ""),
                max_file_size=self.chunk_size
            )
            
            if not targets:
                logger.warning(f"⚠️ No semantic targets found for {file_info['path']}")
                return None
            
            # Generate semantic patches for top targets
            semantic_patches = []
            for target in targets[:3]:  # Process top 3 targets
                patch_info = semantic_patcher.generate_surgical_fix(
                    target, 
                    ticket.description, 
                    file_info['path']
                )
                if patch_info:
                    semantic_patches.append(patch_info)
            
            if not semantic_patches:
                logger.warning(f"⚠️ No semantic patches generated for {file_info['path']}")
                return None
            
            # Apply the best semantic patch
            best_patch = max(semantic_patches, key=lambda x: x.get('confidence_score', 0))
            
            # Apply surgical patch
            apply_result = semantic_patcher.apply_surgical_patch(
                file_info['content'],
                best_patch,
                best_patch.get('original_content', '')
            )
            
            if not apply_result.get('success'):
                logger.error(f"❌ Semantic patch application failed: {apply_result.get('error')}")
                return None
            
            # Create the final semantic patch result
            semantic_result = {
                'patch_content': apply_result['patch_diff'],
                'patched_code': apply_result['patched_content'],
                'confidence_score': best_patch.get('confidence_score', 0.8),
                'commit_message': f"Semantic fix for {file_info['path']}",
                'explanation': f"Applied semantic patch to {best_patch.get('target_name', 'target')}",
                'patch_type': 'semantic_ast_based',
                'targets_processed': len(targets),
                'lines_changed': apply_result.get('lines_changed', 0),
                'addresses_issue': True
            }
            
            logger.info(f"✅ Semantic processing successful for {file_info['path']}")
            return semantic_result
            
        except Exception as e:
            logger.error(f"❌ Error in semantic processing: {e}")
            return None
