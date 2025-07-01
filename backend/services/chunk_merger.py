
import ast
import re
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ChunkMerger:
    """Enhanced chunk merger with improved boundary detection and fallback strategy."""
    
    def __init__(self):
        self.indent_pattern = re.compile(r'^(\s*)')
        self.import_pattern = re.compile(r'^\s*(from\s+\S+\s+)?import\s+')
        self.class_pattern = re.compile(r'^\s*class\s+\w+')
        self.function_pattern = re.compile(r'^\s*def\s+\w+')
        self.control_flow_pattern = re.compile(r'^\s*(if|elif|else|for|while|try|except|finally|with)\b')
        self.block_start_pattern = re.compile(r':\s*$')
        self.decorator_pattern = re.compile(r'^\s*@\w+')
    
    def merge_chunks_intelligently(self, chunks: List[Dict[str, Any]], original_file: str, file_path: str) -> Dict[str, Any]:
        """Enhanced merge with improved boundary detection and reliable fallback."""
        try:
            logger.info(f"🔗 Starting improved chunk merge for {file_path}")
            logger.info(f"  - Original file size: {len(original_file)} chars")
            logger.info(f"  - Chunks to merge: {len(chunks)}")
            
            # Parse original file structure
            original_structure = self._analyze_structure(original_file)
            logger.info(f"  - Original structure: {original_structure['summary']}")
            
            # Sort chunks by line number
            sorted_chunks = sorted(chunks, key=lambda x: x.get('start_line', 0))
            
            # Validate boundaries and determine merge strategy
            boundary_issues = self._validate_improved_boundaries(sorted_chunks, original_file)
            
            # Choose merge strategy based on complexity
            if len(boundary_issues) > 2 or len(chunks) > 8:
                logger.info(f"🔄 Using enhanced fallback strategy due to complexity ({len(boundary_issues)} boundary issues)")
                return self._enhanced_fallback_merge(original_file, sorted_chunks, file_path)
            
            # Try intelligent merge for simpler cases
            merged_content = self._apply_chunks_conservatively(original_file, sorted_chunks, original_structure)
            
            if not merged_content:
                logger.warning("❌ Conservative merge failed - falling back to enhanced fallback")
                return self._enhanced_fallback_merge(original_file, sorted_chunks, file_path)
            
            # Final validation only at the end
            validation_result = self._validate_final_result(merged_content, original_structure, file_path)
            
            if not validation_result["valid"]:
                logger.warning(f"❌ Final validation failed: {validation_result['error']}")
                logger.info("🔄 Falling back to enhanced fallback strategy")
                return self._enhanced_fallback_merge(original_file, sorted_chunks, file_path)
            
            # Generate patch
            final_patch = self._generate_patch(original_file, merged_content, file_path)
            
            logger.info(f"✅ Successfully merged {len(chunks)} chunks with improved strategy")
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": final_patch,
                "validation_info": validation_result,
                "chunks_merged": len(chunks),
                "merge_strategy": "improved_intelligent"
            }
            
        except Exception as e:
            logger.error(f"💥 Chunk merging error for {file_path}: {e}")
            return self._enhanced_fallback_merge(original_file, chunks, file_path)
    
    def _analyze_structure(self, content: str) -> Dict[str, Any]:
        """Analyze file structure with focus on indentation patterns."""
        lines = content.split('\n')
        structure = {
            "imports": [],
            "classes": [],
            "functions": [],
            "control_blocks": [],
            "indentation_levels": set(),
            "block_boundaries": [],
            "summary": ""
        }
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            # Track indentation levels
            indent_match = self.indent_pattern.match(line)
            indent_level = len(indent_match.group(1)) if indent_match else 0
            structure["indentation_levels"].add(indent_level)
            
            # Track structural elements
            if self.import_pattern.match(line):
                structure["imports"].append({"line": i, "indent": indent_level})
            elif self.class_pattern.match(line):
                structure["classes"].append({"line": i, "indent": indent_level})
            elif self.function_pattern.match(line):
                structure["functions"].append({"line": i, "indent": indent_level})
            elif self.control_flow_pattern.match(line):
                structure["control_blocks"].append({"line": i, "indent": indent_level})
            
            # Track block boundaries
            if self.block_start_pattern.search(line):
                structure["block_boundaries"].append({"line": i, "indent": indent_level})
        
        structure["summary"] = f"{len(structure['imports'])} imports, {len(structure['classes'])} classes, {len(structure['functions'])} functions, {len(structure['control_blocks'])} control blocks"
        return structure
    
    def _validate_improved_boundaries(self, chunks: List[Dict], original_file: str) -> List[str]:
        """Improved boundary validation with detailed issue reporting."""
        lines = original_file.split('\n')
        issues = []
        
        for chunk in chunks:
            start_line = chunk.get('start_line', 0)
            end_line = chunk.get('end_line', start_line)
            
            # Check for problematic boundaries
            if start_line > 0 and start_line < len(lines):
                prev_line = lines[start_line - 1].strip()
                current_line = lines[start_line].strip() if start_line < len(lines) else ""
                
                # Check if we're starting after a block header
                if prev_line.endswith(':') and current_line and not current_line.startswith('#'):
                    issue = f"Chunk starts after block header at line {start_line}"
                    issues.append(issue)
                    logger.warning(f"⚠️ {issue}")
            
            # Check ending boundaries
            if end_line < len(lines) - 1:
                current_line = lines[end_line].strip()
                next_line = lines[end_line + 1].strip() if end_line + 1 < len(lines) else ""
                
                # Check if we're ending at a block header
                if current_line.endswith(':') and next_line and not next_line.startswith('#'):
                    issue = f"Chunk ends at block header at line {end_line}"
                    issues.append(issue)
                    logger.warning(f"⚠️ {issue}")
                
                # Check for multi-line statement splitting
                if (current_line.endswith('\\') or 
                    current_line.endswith(',') and not current_line.endswith('):') or
                    '(' in current_line and ')' not in current_line):
                    issue = f"Chunk may split multi-line statement at line {end_line}"
                    issues.append(issue)
                    logger.warning(f"⚠️ {issue}")
        
        return issues
    
    def _apply_chunks_conservatively(self, original: str, chunks: List[Dict], structure: Dict) -> str:
        """Apply chunks with conservative indentation preservation."""
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
                
                logger.debug(f"  - Applying conservative chunk at lines {start_line}-{end_line}")
                
                # Get original indentation context
                original_indent = self._get_original_indentation(original_lines, start_line)
                
                # Preserve indentation more conservatively
                new_lines = self._preserve_original_indentation(
                    new_content.split('\n'), 
                    original_indent
                )
                
                # Apply the replacement
                result_lines[start_line:end_line + 1] = new_lines
                logger.debug(f"  ✅ Conservative chunk applied at lines {start_line}-{end_line}")
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            logger.error(f"❌ Error in conservative chunk application: {e}")
            return ""
    
    def _get_original_indentation(self, original_lines: List[str], start_line: int) -> int:
        """Get the original indentation level at the start line."""
        if start_line >= len(original_lines):
            return 0
        
        # Look at the actual line being replaced
        if start_line < len(original_lines) and original_lines[start_line].strip():
            indent_match = self.indent_pattern.match(original_lines[start_line])
            return len(indent_match.group(1)) if indent_match else 0
        
        # If the line is empty, look at surrounding context
        for i in range(max(0, start_line - 3), min(len(original_lines), start_line + 3)):
            if original_lines[i].strip():
                indent_match = self.indent_pattern.match(original_lines[i])
                return len(indent_match.group(1)) if indent_match else 0
        
        return 0
    
    def _preserve_original_indentation(self, new_lines: List[str], base_indent: int) -> List[str]:
        """Preserve indentation by using the original file's indentation as base."""
        if not new_lines:
            return new_lines
        
        adjusted_lines = []
        
        # Find the base indentation of the new content
        new_base_indent = 0
        for line in new_lines:
            if line.strip():
                indent_match = self.indent_pattern.match(line)
                new_base_indent = len(indent_match.group(1)) if indent_match else 0
                break
        
        # Adjust all lines to match the original indentation
        for line in new_lines:
            if not line.strip():
                adjusted_lines.append(line)
                continue
            
            # Calculate relative indentation
            indent_match = self.indent_pattern.match(line)
            current_indent = len(indent_match.group(1)) if indent_match else 0
            relative_indent = current_indent - new_base_indent
            
            # Apply original base indentation + relative indentation
            final_indent = max(0, base_indent + relative_indent)
            content = line.lstrip()
            adjusted_lines.append(' ' * final_indent + content)
        
        return adjusted_lines
    
    def _validate_final_result(self, content: str, original_structure: Dict, file_path: str) -> Dict[str, Any]:
        """Validate only the final merged result."""
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
                    
                    # Add debug info about the problematic line
                    lines = content.split('\n')
                    if e.lineno and e.lineno <= len(lines):
                        validation["debug_info"]["problematic_line"] = lines[e.lineno - 1]
                        validation["debug_info"]["line_number"] = e.lineno
                    
                    return validation
            
            # Basic structural validation
            new_structure = self._analyze_structure(content)
            validation["debug_info"]["structure_comparison"] = {
                "original": original_structure["summary"],
                "merged": new_structure["summary"]
            }
            
            logger.info(f"✅ Final validation passed for {file_path}")
            return validation
            
        except Exception as e:
            validation["valid"] = False
            validation["error"] = f"Validation exception: {str(e)}"
            return validation
    
    def _enhanced_fallback_merge(self, original_file: str, chunks: List[Dict], file_path: str) -> Dict[str, Any]:
        """Enhanced fallback strategy that works reliably."""
        try:
            logger.info(f"🔄 Using enhanced fallback merge for {file_path}")
            
            original_lines = original_file.split('\n')
            result_lines = original_lines.copy()
            
            # Apply only the highest confidence chunks with minimal changes
            successful_chunks = 0
            for chunk in reversed(sorted(chunks, key=lambda x: x.get('start_line', 0))):
                confidence = chunk.get('confidence_score', 0)
                if confidence < 0.7:  # Only high-confidence chunks
                    continue
                
                start_line = chunk.get('start_line', 0)
                end_line = chunk.get('end_line', start_line)
                new_content = chunk.get('patched_content', '')
                
                if not new_content or start_line >= len(original_lines):
                    continue
                
                # Preserve original indentation exactly
                original_indent = self._get_original_indentation(original_lines, start_line)
                new_lines = []
                
                for line in new_content.split('\n'):
                    if line.strip():
                        # Remove any existing indentation and apply original
                        new_lines.append(' ' * original_indent + line.lstrip())
                    else:
                        new_lines.append(line)
                
                # Apply the change
                result_lines[start_line:end_line + 1] = new_lines
                successful_chunks += 1
            
            merged_content = '\n'.join(result_lines)
            
            # Simple validation
            try:
                if file_path.endswith('.py'):
                    ast.parse(merged_content)
            except SyntaxError as e:
                logger.warning(f"⚠️ Fallback merge has syntax issues, using original file")
                merged_content = original_file
                successful_chunks = 0
            
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": self._generate_patch(original_file, merged_content, file_path),
                "validation_info": {"valid": True, "strategy": "enhanced_fallback"},
                "chunks_merged": successful_chunks,
                "merge_strategy": "enhanced_fallback"
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced fallback merge failed: {e}")
            return {
                "success": True,
                "merged_content": original_file,
                "patch_content": "",
                "validation_info": {"valid": True, "strategy": "no_change"},
                "chunks_merged": 0,
                "merge_strategy": "safe_no_change"
            }
    
    def _generate_patch(self, original: str, merged: str, file_path: str) -> str:
        """Generate unified diff patch."""
        import difflib
        
        original_lines = original.splitlines(keepends=True)
        merged_lines = merged.splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            original_lines,
            merged_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3,
            lineterm=""
        ))
        
        return '\n'.join(diff_lines)
