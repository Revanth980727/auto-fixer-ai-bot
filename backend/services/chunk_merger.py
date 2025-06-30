
import ast
import re
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ChunkMerger:
    """Handles merging of code chunks with proper context preservation and validation."""
    
    def __init__(self):
        self.indent_pattern = re.compile(r'^(\s*)')
        self.import_pattern = re.compile(r'^\s*(from\s+\S+\s+)?import\s+')
        self.class_pattern = re.compile(r'^\s*class\s+\w+')
        self.function_pattern = re.compile(r'^\s*def\s+\w+')
    
    def merge_chunks_intelligently(self, chunks: List[Dict[str, Any]], original_file: str, file_path: str) -> Dict[str, Any]:
        """Merge chunks with intelligent context preservation and global validation."""
        try:
            logger.info(f"🔗 Starting intelligent chunk merge for {file_path}")
            logger.info(f"  - Original file size: {len(original_file)} chars")
            logger.info(f"  - Chunks to merge: {len(chunks)}")
            
            # Parse original file structure
            original_structure = self._analyze_file_structure(original_file)
            logger.info(f"  - Original structure: {original_structure['summary']}")
            
            # Sort chunks by line number to maintain order
            sorted_chunks = sorted(chunks, key=lambda x: x.get('start_line', 0))
            
            # Apply chunks in order while preserving context
            merged_content = self._apply_chunks_with_context(
                original_file, sorted_chunks, original_structure
            )
            
            if not merged_content:
                logger.error("❌ Chunk merging failed - no content produced")
                return {"success": False, "error": "Chunk merging produced no content"}
            
            # Validate merged content structure
            validation_result = self._validate_merged_structure(
                merged_content, original_structure, file_path
            )
            
            if not validation_result["valid"]:
                logger.error(f"❌ Merged content failed validation: {validation_result['error']}")
                return {
                    "success": False, 
                    "error": f"Merged content validation failed: {validation_result['error']}",
                    "debug_info": validation_result.get("debug_info", {})
                }
            
            # Generate final patch with proper formatting
            final_patch = self._generate_validated_patch(original_file, merged_content, file_path)
            
            logger.info(f"✅ Successfully merged {len(chunks)} chunks for {file_path}")
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": final_patch,
                "validation_info": validation_result,
                "chunks_merged": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"💥 Chunk merging error for {file_path}: {e}")
            return {"success": False, "error": str(e)}
    
    def _analyze_file_structure(self, content: str) -> Dict[str, Any]:
        """Analyze the structural elements of a file."""
        lines = content.split('\n')
        structure = {
            "imports": [],
            "classes": [],
            "functions": [],
            "global_vars": [],
            "indentation_levels": set(),
            "summary": ""
        }
        
        for i, line in enumerate(lines):
            # Track indentation levels
            indent_match = self.indent_pattern.match(line)
            if indent_match:
                indent_level = len(indent_match.group(1))
                structure["indentation_levels"].add(indent_level)
            
            # Track imports
            if self.import_pattern.match(line):
                structure["imports"].append({"line": i, "content": line.strip()})
            
            # Track classes
            if self.class_pattern.match(line):
                structure["classes"].append({"line": i, "name": line.strip()})
            
            # Track functions
            if self.function_pattern.match(line):
                structure["functions"].append({"line": i, "name": line.strip()})
        
        structure["summary"] = f"{len(structure['imports'])} imports, {len(structure['classes'])} classes, {len(structure['functions'])} functions"
        return structure
    
    def _apply_chunks_with_context(self, original: str, chunks: List[Dict], structure: Dict) -> str:
        """Apply chunks while preserving file structure and context."""
        try:
            original_lines = original.split('\n')
            result_lines = original_lines.copy()
            
            # Apply chunks in reverse order to maintain line numbers
            for chunk in reversed(chunks):
                start_line = chunk.get('start_line', 0)
                end_line = chunk.get('end_line', start_line)
                new_content = chunk.get('patched_content', '')
                
                if not new_content:
                    continue
                
                # Preserve indentation context
                new_lines = self._preserve_indentation_context(
                    new_content.split('\n'), 
                    original_lines, 
                    start_line, 
                    end_line
                )
                
                # Replace the chunk
                result_lines[start_line:end_line + 1] = new_lines
                
                logger.info(f"  - Applied chunk at lines {start_line}-{end_line}")
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            logger.error(f"❌ Error applying chunks with context: {e}")
            return ""
    
    def _preserve_indentation_context(self, new_lines: List[str], original_lines: List[str], start: int, end: int) -> List[str]:
        """Preserve proper indentation based on surrounding context."""
        if start >= len(original_lines):
            return new_lines
        
        # Get the base indentation from the surrounding context
        base_indent = ""
        
        # Look at the line before the chunk
        if start > 0:
            prev_line = original_lines[start - 1]
            base_indent = self.indent_pattern.match(prev_line).group(1) if prev_line.strip() else ""
        
        # Look at the line after the chunk
        if end + 1 < len(original_lines):
            next_line = original_lines[end + 1]
            if next_line.strip():
                next_indent = self.indent_pattern.match(next_line).group(1)
                if not base_indent:
                    base_indent = next_indent
        
        # Apply consistent indentation to new lines
        adjusted_lines = []
        for line in new_lines:
            if line.strip():  # Non-empty line
                # Remove existing indentation and apply base indentation
                content = line.lstrip()
                adjusted_lines.append(base_indent + content)
            else:
                adjusted_lines.append(line)  # Keep empty lines as-is
        
        return adjusted_lines
    
    def _validate_merged_structure(self, content: str, original_structure: Dict, file_path: str) -> Dict[str, Any]:
        """Validate that the merged content maintains proper structure."""
        validation = {
            "valid": True,
            "error": None,
            "debug_info": {}
        }
        
        try:
            # Python syntax validation
            if file_path.endswith('.py'):
                try:
                    ast.parse(content)
                    validation["debug_info"]["syntax"] = "valid"
                except SyntaxError as e:
                    validation["valid"] = False
                    validation["error"] = f"Syntax error at line {e.lineno}: {e.msg}"
                    validation["debug_info"]["syntax_error"] = {
                        "line": e.lineno,
                        "message": e.msg,
                        "problematic_line": content.split('\n')[e.lineno - 1] if e.lineno <= len(content.split('\n')) else "N/A"
                    }
                    return validation
            
            # Structural validation
            new_structure = self._analyze_file_structure(content)
            
            # Check for major structural issues
            if len(new_structure["imports"]) == 0 and len(original_structure["imports"]) > 0:
                validation["valid"] = False
                validation["error"] = "All imports were lost during merge"
                return validation
            
            # Check indentation consistency
            if not self._validate_indentation_consistency(content):
                validation["valid"] = False
                validation["error"] = "Inconsistent indentation detected"
                return validation
            
            validation["debug_info"]["structure_comparison"] = {
                "original": original_structure["summary"],
                "merged": new_structure["summary"]
            }
            
            logger.info(f"✅ Merged content validation passed for {file_path}")
            return validation
            
        except Exception as e:
            validation["valid"] = False
            validation["error"] = f"Validation exception: {str(e)}"
            return validation
    
    def _validate_indentation_consistency(self, content: str) -> bool:
        """Check if indentation is consistent throughout the file."""
        lines = content.split('\n')
        indent_stack = [0]  # Stack to track indentation levels
        
        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                continue
            
            indent_match = self.indent_pattern.match(line)
            current_indent = len(indent_match.group(1)) if indent_match else 0
            
            # Check for consistent indentation increase/decrease
            if current_indent > indent_stack[-1]:
                # Indentation increased - should be by 4 spaces (or consistent amount)
                indent_stack.append(current_indent)
            elif current_indent < indent_stack[-1]:
                # Indentation decreased - should match a previous level
                while indent_stack and indent_stack[-1] > current_indent:
                    indent_stack.pop()
                if not indent_stack or indent_stack[-1] != current_indent:
                    logger.warning(f"❌ Inconsistent indentation at line {i + 1}: {current_indent} spaces")
                    return False
        
        return True
    
    def _generate_validated_patch(self, original: str, merged: str, file_path: str) -> str:
        """Generate a properly formatted unified diff patch."""
        import difflib
        
        original_lines = original.splitlines(keepends=True)
        merged_lines = merged.splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            original_lines,
            merged_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3,  # Context lines
            lineterm=""
        ))
        
        return '\n'.join(diff_lines)
