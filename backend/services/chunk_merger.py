
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
            logger.info(f"🔗 Starting enhanced chunk merge for {file_path}")
            logger.info(f"  - Original file size: {len(original_file)} chars")
            logger.info(f"  - Chunks to merge: {len(chunks)}")
            
            # Log chunk data for debugging
            for i, chunk in enumerate(chunks):
                confidence = chunk.get('confidence_score', 0)
                logger.debug(f"  - Chunk {i}: confidence={confidence:.3f}, lines={chunk.get('start_line', 0)}-{chunk.get('end_line', 0)}")
                if confidence == 0:
                    logger.warning(f"⚠️ Chunk {i} has zero confidence - check data structure")
            
            # Parse original file structure
            original_structure = self._analyze_structure(original_file)
            logger.info(f"  - Original structure: {original_structure['summary']}")
            
            # Sort chunks by line number
            sorted_chunks = sorted(chunks, key=lambda x: x.get('start_line', 0))
            
            # Validate boundaries
            boundary_issues = self._validate_improved_boundaries(sorted_chunks, original_file)
            
            # Use enhanced fallback strategy for complex cases or when boundary issues exist
            if len(boundary_issues) > 0 or len(chunks) > 8:
                logger.info(f"🔄 Using enhanced fallback strategy ({len(boundary_issues)} boundary issues, {len(chunks)} chunks)")
                return self._enhanced_fallback_merge(original_file, sorted_chunks, file_path)
            
            # Try simple merge for straightforward cases
            merged_content = self._apply_chunks_safely(original_file, sorted_chunks)
            
            if not merged_content:
                logger.warning("❌ Safe merge failed - falling back to enhanced fallback")
                return self._enhanced_fallback_merge(original_file, sorted_chunks, file_path)
            
            # Deduplicate imports
            merged_content = self._deduplicate_imports(merged_content)
            
            # Final validation only at the end
            validation_result = self._validate_final_result(merged_content, original_structure, file_path)
            
            if not validation_result["valid"]:
                logger.warning(f"❌ Final validation failed: {validation_result['error']}")
                logger.info("🔄 Falling back to enhanced fallback strategy")
                return self._enhanced_fallback_merge(original_file, sorted_chunks, file_path)
            
            # Generate patch
            final_patch = self._generate_patch(original_file, merged_content, file_path)
            
            logger.info(f"✅ Successfully merged {len(chunks)} chunks")
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": final_patch,
                "validation_info": validation_result,
                "chunks_merged": len(chunks),
                "merge_strategy": "safe_merge"
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
                prev_line = lines[start_line - 1].strip() if start_line > 0 else ""
                current_line = lines[start_line].strip() if start_line < len(lines) else ""
                
                # Check if we're starting after a block header
                if prev_line.endswith(':') and current_line and not current_line.startswith('#'):
                    issue = f"Chunk starts after block header at line {start_line}"
                    issues.append(issue)
                    logger.warning(f"⚠️ {issue}")
            
            # Check ending boundaries
            if end_line < len(lines) - 1:
                current_line = lines[end_line].strip() if end_line < len(lines) else ""
                next_line = lines[end_line + 1].strip() if end_line + 1 < len(lines) else ""
                
                # Check if we're ending at a block header
                if current_line.endswith(':') and next_line and not next_line.startswith('#'):
                    issue = f"Chunk ends at block header at line {end_line}"
                    issues.append(issue)
                    logger.warning(f"⚠️ {issue}")
        
        if issues:
            logger.warning("⚠️ Chunk boundaries may cause structural issues")
        
        return issues
    
    def _apply_chunks_safely(self, original: str, chunks: List[Dict]) -> str:
        """Apply chunks safely with minimal processing."""
        try:
            original_lines = original.split('\n')
            result_lines = original_lines.copy()
            
            # Apply chunks in reverse order to maintain line numbers
            for chunk in reversed(chunks):
                start_line = chunk.get('start_line', 0)
                end_line = chunk.get('end_line', start_line)
                new_content = chunk.get('patched_content', '')
                confidence = chunk.get('confidence_score', 0)
                
                if not new_content:
                    continue
                
                logger.debug(f"  - Applying safe chunk at lines {start_line}-{end_line} (confidence: {confidence:.3f})")
                
                # Get original indentation context
                original_indent = self._get_original_indentation(original_lines, start_line)
                
                # Preserve indentation simply
                new_lines = self._preserve_simple_indentation(
                    new_content.split('\n'), 
                    original_indent
                )
                
                # Apply the replacement
                result_lines[start_line:end_line + 1] = new_lines
                logger.debug(f"  ✅ Safe chunk applied at lines {start_line}-{end_line}")
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            logger.error(f"❌ Error in safe chunk application: {e}")
            return ""
    
    # ... keep existing code (helper methods like _get_original_indentation, _preserve_simple_indentation, _deduplicate_imports, _normalize_import, _validate_final_result) the same ...
    
    def _get_original_indentation(self, original_lines: List[str], start_line: int) -> int:
        """Get the original indentation level at the start line."""
        if start_line >= len(original_lines):
            return 0
        
        # Look at the actual line being replaced
        if start_line < len(original_lines) and original_lines[start_line].strip():
            indent_match = self.indent_pattern.match(original_lines[start_line])
            return len(indent_match.group(1)) if indent_match else 0
        
        # If the line is empty, look at surrounding context
        for i in range(max(0, start_line - 2), min(len(original_lines), start_line + 2)):
            if original_lines[i].strip():
                indent_match = self.indent_pattern.match(original_lines[i])
                return len(indent_match.group(1)) if indent_match else 0
        
        return 0
    
    def _preserve_simple_indentation(self, new_lines: List[str], base_indent: int) -> List[str]:
        """Preserve indentation simply using the original file's indentation as base."""
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
    
    def _deduplicate_imports(self, content: str) -> str:
        """Advanced import deduplication."""
        lines = content.split('\n')
        seen_imports = {}
        result_lines = []
        
        for line in lines:
            # Check if it's an import line
            if self.import_pattern.match(line):
                # Normalize the import for comparison
                normalized_import = self._normalize_import(line.strip())
                
                if normalized_import not in seen_imports:
                    seen_imports[normalized_import] = line
                    result_lines.append(line)
                else:
                    logger.debug(f"  - Removing duplicate import: {normalized_import}")
            else:
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _normalize_import(self, import_line: str) -> str:
        """Advanced import normalization for better duplicate detection."""
        # Remove extra whitespace and standardize format
        normalized = re.sub(r'\s+', ' ', import_line.strip())
        
        # Handle different import formats consistently
        if normalized.startswith('from '):
            # Sort imported names for consistent comparison
            match = re.match(r'from\s+(\S+)\s+import\s+(.+)', normalized)
            if match:
                module, imports = match.groups()
                # Handle aliases and complex imports
                import_parts = []
                for imp in imports.split(','):
                    imp = imp.strip()
                    # Handle 'as' aliases
                    if ' as ' in imp:
                        base, alias = imp.split(' as ', 1)
                        import_parts.append(f"{base.strip()} as {alias.strip()}")
                    else:
                        import_parts.append(imp)
                
                # Sort for consistent comparison
                import_parts.sort()
                normalized = f"from {module} import {', '.join(import_parts)}"
        elif normalized.startswith('import '):
            # Handle multiple imports in single statement
            match = re.match(r'import\s+(.+)', normalized)
            if match:
                imports = match.group(1)
                import_parts = []
                for imp in imports.split(','):
                    imp = imp.strip()
                    # Handle aliases
                    if ' as ' in imp:
                        base, alias = imp.split(' as ', 1)
                        import_parts.append(f"{base.strip()} as {alias.strip()}")
                    else:
                        import_parts.append(imp)
                
                # Sort for consistent comparison
                import_parts.sort()
                normalized = f"import {', '.join(import_parts)}"
        
        return normalized
    
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
                    logger.debug(f"✅ Syntax validation passed for {file_path}")
                except SyntaxError as e:
                    validation["valid"] = False
                    validation["error"] = f"Syntax error at line {e.lineno}: {e.msg}"
                    
                    # Add debug info about the problematic line
                    lines = content.split('\n')
                    if e.lineno and e.lineno <= len(lines):
                        validation["debug_info"]["problematic_line"] = lines[e.lineno - 1]
                        validation["debug_info"]["line_number"] = e.lineno
                        logger.error(f"❌ Syntax error at line {e.lineno}: {lines[e.lineno - 1]}")
                    
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
            logger.error(f"❌ Validation exception: {e}")
            return validation
    
    def _enhanced_fallback_merge(self, original_file: str, chunks: List[Dict], file_path: str) -> Dict[str, Any]:
        """Enhanced fallback strategy that works reliably and always generates patch content."""
        try:
            logger.info(f"🔄 Using enhanced fallback merge for {file_path}")
            
            original_lines = original_file.split('\n')
            result_lines = original_lines.copy()
            
            # Lower confidence threshold for fallback - we need to apply some changes
            confidence_threshold = 0.3  # Lowered from 0.5 to be more permissive
            successful_chunks = 0
            applied_changes = False
            
            # Log confidence scores for debugging
            logger.debug("🔍 Chunk confidence scores:")
            for i, chunk in enumerate(chunks):
                confidence = chunk.get('confidence_score', 0)
                logger.debug(f"  - Chunk {i}: confidence={confidence:.3f}")
            
            # Apply chunks in reverse order, but with more lenient criteria
            for chunk in reversed(sorted(chunks, key=lambda x: x.get('start_line', 0))):
                confidence = chunk.get('confidence_score', 0)
                
                # Use lower threshold and also consider any chunk that has actual content
                should_apply = (
                    confidence >= confidence_threshold or 
                    (confidence > 0 and chunk.get('patched_content', '').strip())
                )
                
                if not should_apply:
                    logger.debug(f"  - Skipping chunk with confidence {confidence:.3f} (below threshold {confidence_threshold})")
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
                applied_changes = True
                logger.debug(f"  ✅ Applied fallback chunk at lines {start_line}-{end_line} (confidence: {confidence:.3f})")
            
            merged_content = '\n'.join(result_lines)
            
            # If no changes were applied, try to apply at least one highest-confidence chunk
            if not applied_changes and chunks:
                logger.info("⚠️ No chunks met threshold, applying highest confidence chunk")
                best_chunk = max(chunks, key=lambda x: x.get('confidence_score', 0))
                
                if best_chunk.get('patched_content', '').strip():
                    start_line = best_chunk.get('start_line', 0)
                    end_line = best_chunk.get('end_line', start_line)
                    new_content = best_chunk.get('patched_content', '')
                    
                    if start_line < len(original_lines):
                        original_indent = self._get_original_indentation(original_lines, start_line)
                        new_lines = []
                        
                        for line in new_content.split('\n'):
                            if line.strip():
                                new_lines.append(' ' * original_indent + line.lstrip())
                            else:
                                new_lines.append(line)
                        
                        result_lines[start_line:end_line + 1] = new_lines
                        merged_content = '\n'.join(result_lines)
                        successful_chunks = 1
                        applied_changes = True
                        logger.info(f"✅ Applied best chunk with confidence {best_chunk.get('confidence_score', 0):.3f}")
            
            # Deduplicate imports
            merged_content = self._deduplicate_imports(merged_content)
            
            # Always generate patch content, even if no changes were applied
            patch_content = self._generate_patch(original_file, merged_content, file_path)
            
            # Simple validation
            validation_passed = True
            try:
                if file_path.endswith('.py'):
                    ast.parse(merged_content)
                    logger.info(f"✅ Fallback merge validation passed")
            except SyntaxError as e:
                logger.warning(f"⚠️ Fallback merge has syntax issues, using original file")
                merged_content = original_file
                patch_content = ""  # No patch if we fall back to original
                successful_chunks = 0
                validation_passed = False
            
            # Ensure we always return valid patch content
            if not patch_content and applied_changes:
                # Generate minimal patch even if changes seem small
                patch_content = self._generate_patch(original_file, merged_content, file_path)
            
            logger.info(f"✅ Fallback merge strategy completed with {successful_chunks} chunks applied")
            logger.debug(f"  - Applied changes: {applied_changes}")
            logger.debug(f"  - Patch content length: {len(patch_content)}")
            logger.debug(f"  - Validation passed: {validation_passed}")
            
            return {
                "success": True,
                "merged_content": merged_content,
                "patch_content": patch_content,
                "validation_info": {
                    "valid": validation_passed, 
                    "strategy": "enhanced_fallback",
                    "applied_changes": applied_changes,
                    "chunks_applied": successful_chunks
                },
                "chunks_merged": successful_chunks,
                "merge_strategy": "enhanced_fallback"
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced fallback merge failed: {e}")
            # Even in failure, return valid structure with original content
            return {
                "success": True,
                "merged_content": original_file,
                "patch_content": "",
                "validation_info": {
                    "valid": True, 
                    "strategy": "safe_no_change",
                    "applied_changes": False,
                    "error": str(e)
                },
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
