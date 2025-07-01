
import ast
import json
import re
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class PatchValidator:
    """Validate patches before and after application with comprehensive checks."""
    
    def __init__(self):
        self.syntax_checkers = {
            '.py': self._validate_python_syntax,
            '.json': self._validate_json_syntax,
            '.js': self._validate_javascript_syntax,
            '.ts': self._validate_typescript_syntax
        }
    
    def validate_pre_application(self, patch_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate patch data before application."""
        try:
            # Check required fields
            required_fields = ['patch_content', 'target_file']
            for field in required_fields:
                if field not in patch_data:
                    return False, f"Missing required field: {field}"
            
            # Validate patch content format
            patch_content = patch_data.get('patch_content', '')
            if not self._is_valid_unified_diff(patch_content):
                return False, "Invalid unified diff format"
            
            # Validate confidence score
            confidence = patch_data.get('confidence_score', 0)
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                return False, "Invalid confidence score (must be 0-1)"
            
            logger.info(f"Pre-application validation passed for {patch_data.get('target_file')}")
            return True, None
            
        except Exception as e:
            return False, f"Pre-application validation error: {e}"
    
    def validate_post_application(self, content: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate content after patch application."""
        try:
            # Basic content validation
            if not content.strip():
                return False, "File content is empty after patch application"
            
            # File extension specific validation
            file_ext = self._get_file_extension(file_path)
            if file_ext in self.syntax_checkers:
                is_valid, error = self.syntax_checkers[file_ext](content, file_path)
                if not is_valid:
                    return False, f"Syntax validation failed: {error}"
            
            # Check for common patch application issues
            issues = self._detect_patch_artifacts(content)
            if issues:
                return False, f"Patch artifacts detected: {', '.join(issues)}"
            
            logger.info(f"Post-application validation passed for {file_path}")
            return True, None
            
        except Exception as e:
            return False, f"Post-application validation error: {e}"
    
    def _is_valid_unified_diff(self, patch_content: str) -> bool:
        """Check if patch content is a valid unified diff."""
        if not patch_content.strip():
            return False
        
        lines = patch_content.split('\n')
        
        # Check for diff headers
        has_from_file = any(line.startswith('--- ') for line in lines)
        has_to_file = any(line.startswith('+++ ') for line in lines)
        has_hunk_header = any(line.startswith('@@') for line in lines)
        
        return has_from_file and has_to_file and has_hunk_header
    
    def _validate_python_syntax(self, content: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax."""
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, f"Python syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Python validation error: {e}"
    
    def _validate_json_syntax(self, content: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate JSON syntax."""
        try:
            json.loads(content)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSON syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"JSON validation error: {e}"
    
    def _validate_javascript_syntax(self, content: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """Basic JavaScript syntax validation."""
        # Basic checks for common syntax issues
        issues = []
        
        # Check for unmatched braces
        brace_count = content.count('{') - content.count('}')
        if brace_count != 0:
            issues.append(f"Unmatched braces ({brace_count})")
        
        # Check for unmatched parentheses
        paren_count = content.count('(') - content.count(')')
        if paren_count != 0:
            issues.append(f"Unmatched parentheses ({paren_count})")
        
        if issues:
            return False, '; '.join(issues)
        
        return True, None
    
    def _validate_typescript_syntax(self, content: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """Basic TypeScript syntax validation."""
        # Use JavaScript validation as a baseline
        return self._validate_javascript_syntax(content, file_path)
    
    def _detect_patch_artifacts(self, content: str) -> List[str]:
        """Detect common patch application artifacts with improved duplicate detection."""
        issues = []
        
        # Check for conflict markers
        conflict_markers = ['<<<<<<<', '=======', '>>>>>>>']
        for marker in conflict_markers:
            if marker in content:
                issues.append(f"Conflict marker found: {marker}")
        
        # Improved duplicate imports detection
        import_issues = self._detect_duplicate_imports(content)
        if import_issues:
            issues.extend(import_issues)
        
        # Check for malformed diff headers in content
        if '--- a/' in content or '+++ b/' in content:
            issues.append("Diff headers found in file content")
        
        return issues
    
    def _detect_duplicate_imports(self, content: str) -> List[str]:
        """Detect duplicate import statements with more sophisticated logic."""
        lines = content.split('\n')
        import_statements = []
        issues = []
        
        # Extract import statements
        for line_num, line in enumerate(lines, 1):
            stripped_line = line.strip()
            if (stripped_line.startswith('import ') or 
                stripped_line.startswith('from ') and ' import ' in stripped_line):
                import_statements.append({
                    'line': line_num,
                    'content': stripped_line,
                    'normalized': self._normalize_import(stripped_line)
                })
        
        # Check for duplicates
        seen_imports = set()
        for import_stmt in import_statements:
            normalized = import_stmt['normalized']
            if normalized in seen_imports:
                logger.debug(f"Duplicate import detected at line {import_stmt['line']}: {import_stmt['content']}")
                issues.append("Duplicate import statements detected")
                break
            else:
                seen_imports.add(normalized)
        
        return issues
    
    def _normalize_import(self, import_line: str) -> str:
        """Normalize import statement for comparison."""
        # Remove extra whitespace and standardize format
        normalized = re.sub(r'\s+', ' ', import_line.strip())
        
        # Handle different import formats consistently
        if normalized.startswith('from '):
            # Sort imported names for consistent comparison
            match = re.match(r'from\s+(\S+)\s+import\s+(.+)', normalized)
            if match:
                module, imports = match.groups()
                # Sort individual imports
                import_list = [imp.strip() for imp in imports.split(',')]
                import_list.sort()
                normalized = f"from {module} import {', '.join(import_list)}"
        
        return normalized
    
    def _get_file_extension(self, file_path: str) -> str:
        """Get file extension from path."""
        parts = file_path.split('.')
        return f'.{parts[-1]}' if len(parts) > 1 else ''
