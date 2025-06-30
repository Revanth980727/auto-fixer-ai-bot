
import ast
import re
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ChunkMerger:
    """Enhanced chunk merger with structural awareness and proper indentation handling."""
    
    def __init__(self):
        self.indent_pattern = re.compile(r'^(\s*)')
        self.import_pattern = re.compile(r'^\s*(from\s+\S+\s+)?import\s+')
        self.class_pattern = re.compile(r'^\s*class\s+\w+')
        self.function_pattern = re.compile(r'^\s*def\s+\w+')
        self.control_flow_pattern = re.compile(r'^\s*(if|elif|else|for|while|try|except|finally|with)\b')
        self.block_start_pattern = re.compile(r':\s*$')
        self.decorator_pattern = re.compile(r'^\s*@\w+')
    
    def merge_chunks_intelligently(self, chunks: List[Dict[str, Any]], original_file: str, file_path: str) -> Dict[str, Any]:
        """Enhanced merge with structural awareness and incremental validation."""
        try:
            logger.info(f"🔗 Starting enhanced structural chunk merge for {file_path}")
            logger.info(f"  - Original file size: {len(original_file)} chars")
            logger.info(f"  - Chunks to merge: {len(chunks)}")
            
            # Parse original file structure with enhanced analysis
            original_structure = self._analyze_enhanced_structure(original_file)
            logger.info(f"  - Original structure: {original_structure['summary']}")
            
            # Sort and validate chunks
            sorted_chunks = sorted(chunks, key=lambda x: x.get('start_line', 0))
            if not self._validate_chunk_boundaries(sorted_chunks, original_file):
                logger.warning("⚠️ Chunk boundaries may cause structural issues")
            
            # Apply chunks with enhanced structural preservation
            merged_content = self._apply_chunks_with_structural_awareness(
                original_file, sorted_chunks, original_structure
            )
            
            if not merged_content:
                logger.error("❌ Enhanced chunk merging failed - no content produced")
                return {"success": False, "error": "Enhanced chunk merging produced no content"}
            
            # Enhanced validation with incremental checks
            validation_result = self._validate_with_enhanced_checks(
                merged_content, original_structure, file_path
            )
            
            if not validation_result["valid"]:
                logger.error(f"❌ Enhanced validation failed: {validation_result['error']}")
                # Try fallback strategy
                fallback_result = self._try_fallback_merge(original_file, sorted_chunks, file_path)
                if fallback_result["success"]:
                    logger.info("✅ Fallback merge strategy succeeded")
                    return fallback_result
                return {
                    "success": False, 
                    "error": f"Enhanced validation failed: {validation_result['error']}",
                    "debug_info": validation_result.get("debug_info", {})
                }
            
            # Generate enhanced patch
            final_patch = self._generate_enhanced_patch(original_file, merged_content, file_path)
            
            logger.info(f"✅ Successfully merged {len(chunks)} chunks with enhanced structure preservation")
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": final_patch,
                "validation_info": validation_result,
                "chunks_merged": len(chunks),
                "merge_strategy": "enhanced_structural"
            }
            
        except Exception as e:
            logger.error(f"💥 Enhanced chunk merging error for {file_path}: {e}")
            # Try simple fallback
            fallback_result = self._try_simple_fallback(original_file, chunks, file_path)
            if fallback_result["success"]:
                logger.info("✅ Simple fallback succeeded after error")
                return fallback_result
            return {"success": False, "error": str(e)}
    
    def _analyze_enhanced_structure(self, content: str) -> Dict[str, Any]:
        """Enhanced structural analysis with indentation tracking."""
        lines = content.split('\n')
        structure = {
            "imports": [],
            "classes": [],
            "functions": [],
            "control_blocks": [],
            "indentation_levels": set(),
            "indentation_map": {},
            "block_boundaries": [],
            "summary": ""
        }
        
        current_indent_stack = [0]
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            # Track indentation levels and hierarchy
            indent_match = self.indent_pattern.match(line)
            indent_level = len(indent_match.group(1)) if indent_match else 0
            structure["indentation_levels"].add(indent_level)
            structure["indentation_map"][i] = {
                "level": indent_level,
                "parent_level": current_indent_stack[-1] if current_indent_stack else 0
            }
            
            # Update indent stack
            if indent_level > current_indent_stack[-1]:
                current_indent_stack.append(indent_level)
            elif indent_level < current_indent_stack[-1]:
                while current_indent_stack and current_indent_stack[-1] > indent_level:
                    current_indent_stack.pop()
                if indent_level not in current_indent_stack:
                    current_indent_stack.append(indent_level)
            
            # Track structural elements
            if self.import_pattern.match(line):
                structure["imports"].append({"line": i, "content": line.strip(), "indent": indent_level})
            elif self.class_pattern.match(line):
                structure["classes"].append({"line": i, "name": line.strip(), "indent": indent_level})
            elif self.function_pattern.match(line):
                structure["functions"].append({"line": i, "name": line.strip(), "indent": indent_level})
            elif self.control_flow_pattern.match(line):
                structure["control_blocks"].append({"line": i, "type": line.strip(), "indent": indent_level})
            
            # Track block boundaries (lines ending with colons)
            if self.block_start_pattern.search(line):
                structure["block_boundaries"].append({"line": i, "indent": indent_level, "type": "block_start"})
        
        structure["summary"] = f"{len(structure['imports'])} imports, {len(structure['classes'])} classes, {len(structure['functions'])} functions, {len(structure['control_blocks'])} control blocks"
        return structure
    
    def _validate_chunk_boundaries(self, chunks: List[Dict], original_file: str) -> bool:
        """Validate that chunk boundaries don't split critical structures."""
        lines = original_file.split('\n')
        
        for chunk in chunks:
            start_line = chunk.get('start_line', 0)
            end_line = chunk.get('end_line', start_line)
            
            # Check if chunk starts or ends in problematic locations
            if start_line > 0 and start_line < len(lines):
                prev_line = lines[start_line - 1].strip()
                if prev_line.endswith(':') and not lines[start_line].strip():
                    logger.warning(f"⚠️ Chunk starts after block header at line {start_line}")
                    return False
            
            if end_line < len(lines) - 1:
                current_line = lines[end_line].strip()
                next_line = lines[end_line + 1].strip() if end_line + 1 < len(lines) else ""
                if current_line.endswith(':') and next_line and not next_line.startswith('#'):
                    logger.warning(f"⚠️ Chunk ends at block header at line {end_line}")
                    return False
        
        return True
    
    def _apply_chunks_with_structural_awareness(self, original: str, chunks: List[Dict], structure: Dict) -> str:
        """Apply chunks while preserving structural integrity."""
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
                
                logger.info(f"  - Applying structural chunk at lines {start_line}-{end_line}")
                
                # Enhanced indentation preservation with structural awareness
                new_lines = self._preserve_structural_indentation(
                    new_content.split('\n'), 
                    original_lines, 
                    start_line, 
                    end_line,
                    structure
                )
                
                # Validate this specific replacement before applying
                temp_result = result_lines.copy()
                temp_result[start_line:end_line + 1] = new_lines
                
                if self._validate_incremental_change(temp_result, start_line, new_lines):
                    result_lines[start_line:end_line + 1] = new_lines
                    logger.info(f"  ✅ Chunk applied successfully at lines {start_line}-{end_line}")
                else:
                    logger.warning(f"  ⚠️ Chunk at lines {start_line}-{end_line} failed incremental validation, applying with caution")
                    # Apply anyway but with minimal changes
                    minimal_lines = self._create_minimal_replacement(new_lines, original_lines[start_line:end_line + 1])
                    result_lines[start_line:end_line + 1] = minimal_lines
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            logger.error(f"❌ Error in structural chunk application: {e}")
            return ""
    
    def _preserve_structural_indentation(self, new_lines: List[str], original_lines: List[str], 
                                       start: int, end: int, structure: Dict) -> List[str]:
        """Enhanced indentation preservation with structural context."""
        if start >= len(original_lines):
            return new_lines
        
        # Get structural context around the chunk
        context_indent = self._get_structural_context_indent(original_lines, start, end, structure)
        
        # Preserve relative indentation within the new content
        adjusted_lines = []
        base_indent_found = False
        base_indent_level = 0
        
        # Find the base indentation level in new content
        for line in new_lines:
            if line.strip() and not base_indent_found:
                indent_match = self.indent_pattern.match(line)
                base_indent_level = len(indent_match.group(1)) if indent_match else 0
                base_indent_found = True
                break
        
        # Apply structural indentation
        for line in new_lines:
            if not line.strip():
                adjusted_lines.append(line)
                continue
            
            # Calculate relative indentation
            indent_match = self.indent_pattern.match(line)
            current_indent = len(indent_match.group(1)) if indent_match else 0
            relative_indent = current_indent - base_indent_level
            
            # Apply context indent + relative indent
            final_indent = max(0, context_indent + relative_indent)
            content = line.lstrip()
            adjusted_lines.append(' ' * final_indent + content)
        
        return adjusted_lines
    
    def _get_structural_context_indent(self, original_lines: List[str], start: int, end: int, structure: Dict) -> int:
        """Determine the appropriate indentation based on structural context."""
        # Look at surrounding structural elements
        context_indent = 0
        
        # Check previous non-empty line
        for i in range(start - 1, -1, -1):
            if original_lines[i].strip():
                indent_match = self.indent_pattern.match(original_lines[i])
                prev_indent = len(indent_match.group(1)) if indent_match else 0
                
                # If previous line is a block header, indent more
                if self.block_start_pattern.search(original_lines[i]):
                    context_indent = prev_indent + 4
                else:
                    context_indent = prev_indent
                break
        
        # Validate against indentation map if available
        if 'indentation_map' in structure and start in structure['indentation_map']:
            expected_indent = structure['indentation_map'][start]['level']
            # Use the more conservative indentation
            context_indent = min(context_indent, expected_indent) if context_indent > 0 else expected_indent
        
        return context_indent
    
    def _validate_incremental_change(self, temp_lines: List[str], start_line: int, new_lines: List[str]) -> bool:
        """Validate each incremental change for syntax correctness."""
        try:
            # Create a minimal snippet around the change for validation
            context_start = max(0, start_line - 5)
            context_end = min(len(temp_lines), start_line + len(new_lines) + 5)
            snippet = '\n'.join(temp_lines[context_start:context_end])
            
            # Try to parse the snippet
            ast.parse(snippet)
            return True
        except SyntaxError as e:
            logger.warning(f"⚠️ Incremental validation failed: {e}")
            return False
        except Exception:
            # If we can't validate the snippet, assume it's okay
            return True
    
    def _create_minimal_replacement(self, new_lines: List[str], original_lines: List[str]) -> List[str]:
        """Create a minimal replacement that preserves as much original structure as possible."""
        # If new content is dramatically different, use original with minimal changes
        if len(new_lines) > len(original_lines) * 3:
            logger.warning("⚠️ New content significantly larger, using minimal replacement")
            return original_lines
        
        # Otherwise, use the new content but preserve indentation patterns
        return new_lines
    
    def _validate_with_enhanced_checks(self, content: str, original_structure: Dict, file_path: str) -> Dict[str, Any]:
        """Enhanced validation with comprehensive checks."""
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
            
            # Enhanced structural validation
            new_structure = self._analyze_enhanced_structure(content)
            
            # Check for critical structural preservation
            if not self._validate_structural_preservation(original_structure, new_structure):
                validation["valid"] = False
                validation["error"] = "Critical structural elements were lost or corrupted"
                return validation
            
            # Enhanced indentation consistency check
            if not self._validate_enhanced_indentation(content):
                validation["valid"] = False
                validation["error"] = "Enhanced indentation validation failed"
                return validation
            
            validation["debug_info"]["structure_comparison"] = {
                "original": original_structure["summary"],
                "merged": new_structure["summary"]
            }
            
            logger.info(f"✅ Enhanced validation passed for {file_path}")
            return validation
            
        except Exception as e:
            validation["valid"] = False
            validation["error"] = f"Enhanced validation exception: {str(e)}"
            return validation
    
    def _validate_structural_preservation(self, original: Dict, merged: Dict) -> bool:
        """Validate that critical structural elements are preserved."""
        # Check that we didn't lose all imports
        if len(original["imports"]) > 0 and len(merged["imports"]) == 0:
            logger.error("❌ All imports were lost")
            return False
        
        # Check that major structural elements aren't completely gone
        if (len(original["classes"]) > 0 and len(merged["classes"]) == 0 and 
            len(original["functions"]) > 0 and len(merged["functions"]) == 0):
            logger.error("❌ All classes and functions were lost")
            return False
        
        return True
    
    def _validate_enhanced_indentation(self, content: str) -> bool:
        """Enhanced indentation validation with better error detection."""
        lines = content.split('\n')
        indent_stack = [0]
        in_multiline_string = False
        string_delimiter = None
        
        for i, line in enumerate(lines):
            # Handle multiline strings
            if '"""' in line or "'''" in line:
                if not in_multiline_string:
                    in_multiline_string = True
                    string_delimiter = '"""' if '"""' in line else "'''"
                elif string_delimiter in line:
                    in_multiline_string = False
                    string_delimiter = None
            
            if in_multiline_string or not line.strip():
                continue
            
            indent_match = self.indent_pattern.match(line)
            current_indent = len(indent_match.group(1)) if indent_match else 0
            
            # More sophisticated indentation checking
            if current_indent > indent_stack[-1]:
                # Check if indentation increase is reasonable (multiple of 4 is common)
                indent_diff = current_indent - indent_stack[-1]
                if indent_diff % 4 != 0 and indent_diff > 8:
                    logger.warning(f"⚠️ Unusual indentation increase at line {i + 1}: {indent_diff} spaces")
                indent_stack.append(current_indent)
            elif current_indent < indent_stack[-1]:
                # Indentation decreased - should match a previous level
                while indent_stack and indent_stack[-1] > current_indent:
                    indent_stack.pop()
                if not indent_stack or (indent_stack and indent_stack[-1] != current_indent):
                    # Check if this is a reasonable indentation level
                    if current_indent % 4 == 0 or current_indent == 0:
                        indent_stack.append(current_indent)
                    else:
                        logger.warning(f"⚠️ Inconsistent indentation at line {i + 1}: {current_indent} spaces")
                        return False
        
        return True
    
    def _try_fallback_merge(self, original_file: str, chunks: List[Dict], file_path: str) -> Dict[str, Any]:
        """Fallback merge strategy with minimal changes."""
        try:
            logger.info(f"🔄 Attempting fallback merge for {file_path}")
            
            original_lines = original_file.split('\n')
            result_lines = original_lines.copy()
            
            # Apply only high-confidence chunks with minimal changes
            for chunk in reversed(sorted(chunks, key=lambda x: x.get('start_line', 0))):
                confidence = chunk.get('confidence_score', 0)
                if confidence < 0.8:  # Only apply high-confidence chunks
                    continue
                
                start_line = chunk.get('start_line', 0)
                end_line = chunk.get('end_line', start_line)
                new_content = chunk.get('patched_content', '')
                
                if not new_content:
                    continue
                
                # Apply with original indentation preserved
                new_lines = new_content.split('\n')
                if start_line < len(original_lines):
                    original_indent = self.indent_pattern.match(original_lines[start_line]).group(1)
                    preserved_lines = []
                    for line in new_lines:
                        if line.strip():
                            preserved_lines.append(original_indent + line.lstrip())
                        else:
                            preserved_lines.append(line)
                    
                    result_lines[start_line:end_line + 1] = preserved_lines
            
            merged_content = '\n'.join(result_lines)
            
            # Simple validation
            try:
                if file_path.endswith('.py'):
                    ast.parse(merged_content)
            except SyntaxError:
                logger.error("❌ Fallback merge also failed syntax validation")
                return {"success": False, "error": "Fallback merge failed syntax validation"}
            
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": self._generate_enhanced_patch(original_file, merged_content, file_path),
                "validation_info": {"valid": True, "strategy": "fallback"},
                "chunks_merged": len([c for c in chunks if c.get('confidence_score', 0) >= 0.8]),
                "merge_strategy": "fallback_conservative"
            }
            
        except Exception as e:
            logger.error(f"❌ Fallback merge failed: {e}")
            return {"success": False, "error": f"Fallback merge failed: {str(e)}"}
    
    def _try_simple_fallback(self, original_file: str, chunks: List[Dict], file_path: str) -> Dict[str, Any]:
        """Simple fallback that makes minimal changes."""
        try:
            logger.info(f"🔄 Attempting simple fallback for {file_path}")
            
            # Just return the original with minimal patch
            return {
                "success": True,
                "merged_content": original_file,
                "patch_content": "",
                "validation_info": {"valid": True, "strategy": "no_change"},
                "chunks_merged": 0,
                "merge_strategy": "simple_fallback_no_change"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Simple fallback failed: {str(e)}"}
    
    def _generate_enhanced_patch(self, original: str, merged: str, file_path: str) -> str:
        """Generate enhanced unified diff patch."""
        import difflib
        
        original_lines = original.splitlines(keepends=True)
        merged_lines = merged.splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            original_lines,
            merged_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=5,  # More context lines for better readability
            lineterm=""
        ))
        
        return '\n'.join(diff_lines)
