
import ast
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from core.analysis_config import processing_config, file_type_config

logger = logging.getLogger(__name__)

class CodePreprocessor:
    """Preprocesses code files for semantic analysis by removing noise and chunking intelligently"""
    
    def __init__(self):
        self.max_chunk_tokens = processing_config.max_chunk_tokens
        self.overlap_tokens = processing_config.overlap_tokens
    
    def preprocess_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Main preprocessing pipeline that cleans and chunks code"""
        try:
            # Determine file type and apply appropriate preprocessing
            file_ext = file_path.split('.')[-1].lower()
            language = file_type_config.get_language_for_extension(file_ext)
            
            if language == 'python':
                return self._preprocess_python(content)
            elif language == 'javascript':
                return self._preprocess_javascript(content)
            else:
                return self._preprocess_generic(content)
                
        except Exception as e:
            logger.warning(f"Failed to preprocess {file_path}: {e}")
            return self._preprocess_generic(content)
    
    def _preprocess_python(self, content: str) -> Dict[str, Any]:
        """Preprocess Python files using AST parsing"""
        try:
            tree = ast.parse(content)
            
            # Extract meaningful code blocks
            code_blocks = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    # Get function/class signature and docstring
                    lines = content.split('\n')
                    start_line = node.lineno - 1
                    
                    # Find the end of the function/class
                    end_line = start_line + 1
                    if hasattr(node, 'body') and node.body:
                        end_line = node.body[-1].end_lineno if hasattr(node.body[-1], 'end_lineno') else start_line + 10
                    
                    block_content = '\n'.join(lines[start_line:min(end_line, len(lines))])
                    
                    # Clean the block
                    cleaned_block = self._clean_python_block(block_content)
                    if cleaned_block.strip():
                        code_blocks.append({
                            'type': type(node).__name__,
                            'name': node.name,
                            'content': cleaned_block,
                            'line_start': start_line + 1
                        })
            
            # If no blocks found, fall back to generic preprocessing
            if not code_blocks:
                return self._preprocess_generic(content)
            
            # Create chunks from code blocks
            chunks = self._create_chunks_from_blocks(code_blocks)
            
            return {
                'preprocessed_size': sum(len(chunk['content']) for chunk in chunks),
                'original_size': len(content),
                'chunks': chunks,
                'compression_ratio': 1 - (sum(len(chunk['content']) for chunk in chunks) / len(content)) if len(content) > 0 else 0
            }
            
        except SyntaxError:
            logger.warning("Failed to parse Python file with AST, falling back to generic preprocessing")
            return self._preprocess_generic(content)
    
    def _preprocess_javascript(self, content: str) -> Dict[str, Any]:
        """Preprocess JavaScript/TypeScript files using regex patterns"""
        # Get comment patterns for JavaScript
        comment_patterns = file_type_config.comment_patterns.get('javascript', {})
        
        # Remove comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove import/export statements (keep only the function/class names)
        content = re.sub(r'^\s*import\s+.*?;?\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*export\s+.*?;?\s*$', '', content, flags=re.MULTILINE)
        
        # Extract function and class definitions
        functions = re.findall(r'(function\s+\w+\s*\([^)]*\)\s*\{[^}]*\})', content, re.DOTALL)
        classes = re.findall(r'(class\s+\w+\s*(?:extends\s+\w+)?\s*\{[^}]*\})', content, re.DOTALL)
        arrow_functions = re.findall(r'(const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*\{[^}]*\})', content, re.DOTALL)
        
        # Combine all extracted blocks
        all_blocks = functions + classes + arrow_functions
        
        if not all_blocks:
            return self._preprocess_generic(content)
        
        # Create chunks
        chunks = []
        for i, block in enumerate(all_blocks):
            clean_block = self._clean_generic_block(block)
            if clean_block.strip():
                chunks.append({
                    'type': 'function/class',
                    'content': clean_block,
                    'index': i
                })
        
        return {
            'preprocessed_size': sum(len(chunk['content']) for chunk in chunks),
            'original_size': len(content),
            'chunks': chunks,
            'compression_ratio': 1 - (sum(len(chunk['content']) for chunk in chunks) / len(content)) if len(content) > 0 else 0
        }
    
    def _preprocess_generic(self, content: str) -> Dict[str, Any]:
        """Generic preprocessing for any file type"""
        # Remove empty lines and excessive whitespace
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('//'):
                cleaned_lines.append(line.rstrip())
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # Split into chunks by approximate token count
        chunks = self._split_by_tokens(cleaned_content)
        
        return {
            'preprocessed_size': len(cleaned_content),
            'original_size': len(content),
            'chunks': chunks,
            'compression_ratio': 1 - (len(cleaned_content) / len(content)) if len(content) > 0 else 0
        }
    
    def _clean_python_block(self, block: str) -> str:
        """Clean a Python code block by removing docstrings and comments"""
        lines = block.split('\n')
        cleaned_lines = []
        in_docstring = False
        docstring_char = None
        
        for line in lines:
            stripped = line.strip()
            
            # Handle docstrings
            if '"""' in stripped or "'''" in stripped:
                if not in_docstring:
                    docstring_char = '"""' if '"""' in stripped else "'''"
                    in_docstring = True
                    continue
                elif docstring_char in stripped:
                    in_docstring = False
                    continue
            
            if in_docstring:
                continue
            
            # Remove comments but keep the line structure
            if '#' in stripped and not stripped.startswith('#'):
                line = line[:line.find('#')].rstrip()
            elif stripped.startswith('#'):
                continue
            
            if line.strip():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _clean_generic_block(self, block: str) -> str:
        """Generic block cleaning"""
        lines = block.split('\n')
        cleaned_lines = [line.rstrip() for line in lines if line.strip()]
        return '\n'.join(cleaned_lines)
    
    def _create_chunks_from_blocks(self, code_blocks: List[Dict]) -> List[Dict]:
        """Create overlapping chunks from code blocks"""
        chunks = []
        current_chunk = ""
        current_blocks = []
        
        # Use configured token estimation
        chars_per_token = processing_config.chars_per_token
        max_chars = self.max_chunk_tokens * chars_per_token
        
        for block in code_blocks:
            block_content = f"# {block['type']}: {block['name']}\n{block['content']}\n\n"
            
            # If adding this block would exceed chunk size, save current chunk
            if len(current_chunk + block_content) > max_chars:
                if current_chunk:
                    chunks.append({
                        'content': current_chunk.strip(),
                        'blocks': current_blocks.copy(),
                        'type': 'code_chunk'
                    })
                
                # Start new chunk with overlap from previous chunk
                if current_blocks:
                    # Include last block for overlap
                    last_block = current_blocks[-1]
                    current_chunk = f"# {last_block['type']}: {last_block['name']}\n{last_block['content']}\n\n"
                    current_blocks = [last_block]
                else:
                    current_chunk = ""
                    current_blocks = []
            
            current_chunk += block_content
            current_blocks.append(block)
        
        # Add the final chunk
        if current_chunk:
            chunks.append({
                'content': current_chunk.strip(),
                'blocks': current_blocks,
                'type': 'code_chunk'
            })
        
        return chunks
    
    def _split_by_tokens(self, content: str, max_tokens: int = None) -> List[Dict]:
        """Split content into token-based chunks with overlap"""
        if max_tokens is None:
            max_tokens = self.max_chunk_tokens
        
        # Use configured token estimation
        chars_per_token = processing_config.chars_per_token
        max_chars = max_tokens * chars_per_token
        overlap_chars = self.overlap_tokens * chars_per_token
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + max_chars, len(content))
            
            # Try to break at word boundaries
            if end < len(content):
                # Look for line break near the end
                last_newline = content.rfind('\n', start, end)
                if last_newline > start + max_chars * 0.7:  # At least 70% of target size
                    end = last_newline
            
            chunk_content = content[start:end].strip()
            if chunk_content:
                chunks.append({
                    'content': chunk_content,
                    'start_pos': start,
                    'end_pos': end,
                    'type': 'text_chunk'
                })
            
            # Move start position with overlap
            start = max(start + max_chars - overlap_chars, end)
            if start >= len(content):
                break
        
        return chunks
