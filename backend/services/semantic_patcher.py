import ast
import re
import difflib
from typing import Dict, Any, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)

class SemanticPatcher:
    """AST-based semantic patcher for targeted code fixes."""
    
    def __init__(self):
        self.function_pattern = re.compile(r'^\s*def\s+(\w+)')
        self.class_pattern = re.compile(r'^\s*class\s+(\w+)')
        self.import_pattern = re.compile(r'^\s*(from\s+\S+\s+)?import\s+')
        
    def identify_target_nodes(self, content: str, issue_description: str) -> List[Dict[str, Any]]:
        """Identify specific AST nodes that need fixes based on issue description."""
        try:
            tree = ast.parse(content)
            lines = content.split('\n')
            targets = []
            
            # Extract keywords from issue description for targeting
            issue_keywords = self._extract_issue_keywords(issue_description)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    target_info = self._analyze_node_relevance(node, lines, issue_keywords)
                    if target_info:
                        targets.append(target_info)
            
            # Sort by relevance score
            targets.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            logger.info(f"🎯 Identified {len(targets)} target nodes for semantic patching")
            return targets[:5]  # Return top 5 most relevant targets
            
        except SyntaxError as e:
            logger.warning(f"⚠️ AST parsing failed, falling back to line-based analysis: {e}")
            return self._fallback_line_analysis(content, issue_description)
        
    def _extract_issue_keywords(self, issue_description: str) -> List[str]:
        """Extract relevant keywords from issue description."""
        # Common error patterns and keywords
        keywords = []
        
        # Function/method names
        function_matches = re.findall(r'\b(\w+)\(\)', issue_description)
        keywords.extend(function_matches)
        
        # Variable names
        var_matches = re.findall(r'\b[a-z_]\w*\b', issue_description.lower())
        keywords.extend(var_matches)
        
        # Error-related keywords
        error_keywords = ['error', 'bug', 'fail', 'exception', 'issue', 'problem']
        for keyword in error_keywords:
            if keyword in issue_description.lower():
                keywords.append(keyword)
        
        return list(set(keywords))
    
    def _analyze_node_relevance(self, node: ast.AST, lines: List[str], keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Analyze how relevant a node is to the issue."""
        if not hasattr(node, 'lineno'):
            return None
            
        start_line = node.lineno - 1  # Convert to 0-based
        end_line = getattr(node, 'end_lineno', start_line) - 1 if hasattr(node, 'end_lineno') else start_line
        
        # Get node content
        if end_line >= len(lines):
            end_line = len(lines) - 1
            
        node_content = '\n'.join(lines[start_line:end_line + 1])
        node_name = getattr(node, 'name', 'unknown')
        
        # Calculate relevance score
        relevance_score = 0
        
        # Check if node name matches keywords
        if node_name.lower() in [k.lower() for k in keywords]:
            relevance_score += 10
            
        # Check if node content contains keywords
        for keyword in keywords:
            if keyword.lower() in node_content.lower():
                relevance_score += 2
                
        # Prefer functions over classes for targeted fixes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            relevance_score += 1
            
        if relevance_score > 0:
            return {
                'node_type': type(node).__name__,
                'name': node_name,
                'start_line': start_line,
                'end_line': end_line,
                'content': node_content,
                'relevance_score': relevance_score,
                'context_lines': max(0, start_line - 2),  # Include 2 lines before for context
                'context_end': min(len(lines), end_line + 3)  # Include 2 lines after for context
            }
        
        return None
    
    def _fallback_line_analysis(self, content: str, issue_description: str) -> List[Dict[str, Any]]:
        """Fallback to line-based analysis when AST parsing fails."""
        lines = content.split('\n')
        keywords = self._extract_issue_keywords(issue_description)
        targets = []
        
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword.lower() in line.lower():
                    # Find function/class boundaries around this line
                    start_line, end_line = self._find_logical_boundaries(lines, i)
                    
                    targets.append({
                        'node_type': 'LineMatch',
                        'name': f'line_{i+1}',
                        'start_line': start_line,
                        'end_line': end_line,
                        'content': '\n'.join(lines[start_line:end_line + 1]),
                        'relevance_score': 5,
                        'context_lines': max(0, start_line - 2),
                        'context_end': min(len(lines), end_line + 3)
                    })
                    break
        
        return targets[:3]  # Limit fallback results
    
    def _find_logical_boundaries(self, lines: List[str], target_line: int) -> Tuple[int, int]:
        """Find logical boundaries around a target line."""
        start_line = target_line
        end_line = target_line
        
        # Look backwards for function/class definition
        for i in range(target_line, -1, -1):
            if self.function_pattern.match(lines[i]) or self.class_pattern.match(lines[i]):
                start_line = i
                break
        
        # Look forwards for next definition or end of current block
        current_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
        for i in range(start_line + 1, len(lines)):
            line = lines[i]
            if line.strip():  # Non-empty line
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= current_indent and (self.function_pattern.match(line) or self.class_pattern.match(line)):
                    end_line = i - 1
                    break
                end_line = i
        
        return start_line, end_line
    
    def generate_surgical_fix(self, target: Dict[str, Any], issue_description: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Generate a minimal surgical fix for a specific target."""
        try:
            # Create focused prompt for minimal fix
            prompt = self._create_surgical_prompt(target, issue_description, file_path)
            
            # For now, return the structure - this would integrate with OpenAI client
            return {
                'target_name': target['name'],
                'start_line': target['start_line'],
                'end_line': target['end_line'],
                'fix_type': 'surgical_patch',
                'prompt': prompt,
                'confidence_score': 0.8,  # Base confidence for surgical fixes
                'original_content': target['content']
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating surgical fix: {e}")
            return None
    
    def _create_surgical_prompt(self, target: Dict[str, Any], issue_description: str, file_path: str) -> str:
        """Create a focused prompt for surgical code fixing."""
        return f"""Fix the specific issue in this {target['node_type']} '{target['name']}' from {file_path}.

Issue: {issue_description}

Current code (lines {target['start_line'] + 1}-{target['end_line'] + 1}):
```python
{target['content']}
```

Provide ONLY the corrected lines that need to change. Do not include unchanged lines or explanations.
Focus on the minimal fix needed to resolve the issue."""

    def apply_surgical_patch(self, content: str, patch_info: Dict[str, Any], fixed_content: str) -> Dict[str, Any]:
        """Apply a surgical patch to specific lines."""
        try:
            lines = content.split('\n')
            start_line = patch_info['start_line']
            end_line = patch_info['end_line']
            
            # Validate boundaries
            if start_line >= len(lines) or end_line >= len(lines):
                return {
                    'success': False,
                    'error': 'Invalid line boundaries'
                }
            
            # Preserve indentation from original
            original_indent = self._get_base_indentation(lines[start_line])
            fixed_lines = self._adjust_indentation(fixed_content.split('\n'), original_indent)
            
            # Apply the surgical replacement
            result_lines = lines.copy()
            result_lines[start_line:end_line + 1] = fixed_lines
            
            # Validate syntax if Python file
            merged_content = '\n'.join(result_lines)
            if patch_info.get('file_path', '').endswith('.py'):
                try:
                    ast.parse(merged_content)
                except SyntaxError as e:
                    return {
                        'success': False,
                        'error': f'Syntax error after patch: {e}'
                    }
            
            # Generate patch diff
            patch_diff = self._generate_diff(content, merged_content, patch_info.get('file_path', ''))
            
            return {
                'success': True,
                'patched_content': merged_content,
                'patch_diff': patch_diff,
                'lines_changed': len(fixed_lines),
                'target_name': patch_info.get('target_name', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"❌ Error applying surgical patch: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_base_indentation(self, line: str) -> int:
        """Get the base indentation level of a line."""
        return len(line) - len(line.lstrip())
    
    def _adjust_indentation(self, lines: List[str], base_indent: int) -> List[str]:
        """Adjust indentation of lines to match base indentation."""
        if not lines or not lines[0].strip():
            return lines
            
        # Find the indentation of the first non-empty line
        first_indent = 0
        for line in lines:
            if line.strip():
                first_indent = len(line) - len(line.lstrip())
                break
        
        # Adjust all lines
        adjusted_lines = []
        for line in lines:
            if not line.strip():
                adjusted_lines.append(line)
            else:
                current_indent = len(line) - len(line.lstrip())
                relative_indent = current_indent - first_indent
                new_indent = base_indent + relative_indent
                adjusted_lines.append(' ' * max(0, new_indent) + line.lstrip())
        
        return adjusted_lines
    
    def _generate_diff(self, original: str, patched: str, file_path: str) -> str:
        """Generate unified diff for the patch."""
        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            original_lines,
            patched_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3,
            lineterm=""
        ))
        
        return '\n'.join(diff_lines)