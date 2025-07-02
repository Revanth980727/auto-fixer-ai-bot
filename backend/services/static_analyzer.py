import ast
import os
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Dependency:
    """Represents a dependency between code elements."""
    source: str  # source file/function
    target: str  # target file/function
    dependency_type: str  # 'import', 'call', 'inheritance', 'attribute'
    line_number: int
    confidence: float

@dataclass
class CodeMetrics:
    """Code quality and complexity metrics."""
    file_path: str
    lines_of_code: int
    cyclomatic_complexity: int
    function_count: int
    class_count: int
    import_count: int
    code_smells: List[str]
    maintainability_index: float

class StaticAnalyzer:
    """Static analysis for dependency tracking and code quality assessment."""
    
    def __init__(self):
        self.dependency_graph: Dict[str, List[Dependency]] = {}
        self.reverse_dependencies: Dict[str, List[Dependency]] = {}
        self.code_metrics: Dict[str, CodeMetrics] = {}
        self.call_graph: Dict[str, Set[str]] = {}
        
    def analyze_repository(self, repository_files: List[Dict[str, Any]]) -> None:
        """Perform comprehensive static analysis of repository."""
        try:
            logger.info(f"🔬 Performing static analysis on {len(repository_files)} files")
            
            self._reset_analysis()
            
            # First pass: Extract all symbols and basic metrics
            for file_info in repository_files:
                if self._is_analyzable_file(file_info.get('path', '')):
                    self._analyze_file_metrics(file_info)
            
            # Second pass: Build dependency graphs
            for file_info in repository_files:
                if self._is_analyzable_file(file_info.get('path', '')):
                    self._analyze_dependencies(file_info)
            
            # Third pass: Build call graph
            self._build_call_graph()
            
            logger.info(f"✅ Static analysis complete: {len(self.code_metrics)} files analyzed")
            
        except Exception as e:
            logger.error(f"❌ Error in static analysis: {e}")
    
    def _reset_analysis(self) -> None:
        """Reset analysis data structures."""
        self.dependency_graph.clear()
        self.reverse_dependencies.clear()
        self.code_metrics.clear()
        self.call_graph.clear()
    
    def _is_analyzable_file(self, file_path: str) -> bool:
        """Check if file should be analyzed."""
        analyzable_extensions = ['.py', '.js', '.ts', '.tsx', '.jsx']
        return any(file_path.endswith(ext) for ext in analyzable_extensions)
    
    def _analyze_file_metrics(self, file_info: Dict[str, Any]) -> None:
        """Analyze code metrics for a file."""
        try:
            content = file_info.get('content', '')
            file_path = file_info.get('path', '')
            
            if not content:
                return
                
            if file_path.endswith('.py'):
                metrics = self._analyze_python_metrics(content, file_path)
            else:
                metrics = self._analyze_generic_metrics(content, file_path)
            
            self.code_metrics[file_path] = metrics
            
        except Exception as e:
            logger.error(f"❌ Error analyzing metrics for {file_path}: {e}")
    
    def _analyze_python_metrics(self, content: str, file_path: str) -> CodeMetrics:
        """Analyze Python-specific metrics."""
        lines = content.split('\n')
        loc = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        
        try:
            tree = ast.parse(content)
            
            # Count functions and classes
            function_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
            class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            import_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
            
            # Calculate cyclomatic complexity
            complexity = self._calculate_cyclomatic_complexity(tree)
            
            # Detect code smells
            code_smells = self._detect_python_code_smells(tree, lines)
            
            # Calculate maintainability index (simplified)
            maintainability = self._calculate_maintainability_index(loc, complexity, len(code_smells))
            
        except SyntaxError:
            function_count = class_count = import_count = complexity = 0
            code_smells = ['syntax_error']
            maintainability = 0.0
        
        return CodeMetrics(
            file_path=file_path,
            lines_of_code=loc,
            cyclomatic_complexity=complexity,
            function_count=function_count,
            class_count=class_count,
            import_count=import_count,
            code_smells=code_smells,
            maintainability_index=maintainability
        )
    
    def _analyze_generic_metrics(self, content: str, file_path: str) -> CodeMetrics:
        """Analyze generic code metrics for non-Python files."""
        lines = content.split('\n')
        loc = len([line for line in lines if line.strip()])
        
        # Simple metrics for non-Python files
        function_count = content.count('function ') + content.count('=>')
        class_count = content.count('class ')
        import_count = content.count('import ') + content.count('require(')
        
        return CodeMetrics(
            file_path=file_path,
            lines_of_code=loc,
            cyclomatic_complexity=1,  # Simplified
            function_count=function_count,
            class_count=class_count,
            import_count=import_count,
            code_smells=[],
            maintainability_index=0.7  # Default for non-Python
        )
    
    def _calculate_cyclomatic_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity for Python code."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            # Add complexity for control flow statements
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity += 1
        
        return complexity
    
    def _detect_python_code_smells(self, tree: ast.AST, lines: List[str]) -> List[str]:
        """Detect code smells in Python code."""
        smells = []
        
        # Long functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_length = getattr(node, 'end_lineno', node.lineno) - node.lineno
                if func_length > 50:
                    smells.append(f'long_function_{node.name}')
        
        # Too many parameters
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.args.args) > 5:
                    smells.append(f'too_many_params_{node.name}')
        
        # Deep nesting
        max_nesting = self._calculate_max_nesting(tree)
        if max_nesting > 4:
            smells.append('deep_nesting')
        
        # Long lines
        for i, line in enumerate(lines):
            if len(line) > 120:
                smells.append(f'long_line_{i+1}')
                break  # Only report first occurrence
        
        return smells
    
    def _calculate_max_nesting(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth."""
        def get_nesting_depth(node, current_depth=0):
            max_depth = current_depth
            
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                    child_depth = get_nesting_depth(child, current_depth + 1)
                    max_depth = max(max_depth, child_depth)
                else:
                    child_depth = get_nesting_depth(child, current_depth)
                    max_depth = max(max_depth, child_depth)
            
            return max_depth
        
        return get_nesting_depth(tree)
    
    def _calculate_maintainability_index(self, loc: int, complexity: int, smells_count: int) -> float:
        """Calculate maintainability index (simplified version)."""
        if loc == 0:
            return 1.0
        
        # Simplified formula
        base_score = 100
        complexity_penalty = complexity * 2
        loc_penalty = loc / 10
        smells_penalty = smells_count * 5
        
        score = base_score - complexity_penalty - loc_penalty - smells_penalty
        return max(0.0, min(1.0, score / 100))
    
    def _analyze_dependencies(self, file_info: Dict[str, Any]) -> None:
        """Analyze dependencies for a file."""
        try:
            content = file_info.get('content', '')
            file_path = file_info.get('path', '')
            
            if file_path.endswith('.py'):
                dependencies = self._analyze_python_dependencies(content, file_path)
            else:
                dependencies = self._analyze_generic_dependencies(content, file_path)
            
            self.dependency_graph[file_path] = dependencies
            
            # Build reverse dependencies
            for dep in dependencies:
                if dep.target not in self.reverse_dependencies:
                    self.reverse_dependencies[dep.target] = []
                self.reverse_dependencies[dep.target].append(dep)
                
        except Exception as e:
            logger.error(f"❌ Error analyzing dependencies for {file_path}: {e}")
    
    def _analyze_python_dependencies(self, content: str, file_path: str) -> List[Dependency]:
        """Analyze Python dependencies."""
        dependencies = []
        
        try:
            tree = ast.parse(content)
            
            # Import dependencies
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.append(Dependency(
                            source=file_path,
                            target=alias.name,
                            dependency_type='import',
                            line_number=node.lineno,
                            confidence=0.9
                        ))
                
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        target = f"{module}.{alias.name}" if module else alias.name
                        dependencies.append(Dependency(
                            source=file_path,
                            target=target,
                            dependency_type='import',
                            line_number=node.lineno,
                            confidence=0.9
                        ))
                
                # Function calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        dependencies.append(Dependency(
                            source=file_path,
                            target=node.func.id,
                            dependency_type='call',
                            line_number=node.lineno,
                            confidence=0.7
                        ))
                    elif isinstance(node.func, ast.Attribute):
                        target = f"{ast.unparse(node.func.value) if hasattr(ast, 'unparse') else 'unknown'}.{node.func.attr}"
                        dependencies.append(Dependency(
                            source=file_path,
                            target=target,
                            dependency_type='call',
                            line_number=node.lineno,
                            confidence=0.6
                        ))
                
                # Inheritance
                elif isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            dependencies.append(Dependency(
                                source=file_path,
                                target=base.id,
                                dependency_type='inheritance',
                                line_number=node.lineno,
                                confidence=0.8
                            ))
        
        except SyntaxError:
            pass  # Already handled in metrics analysis
        
        return dependencies
    
    def _analyze_generic_dependencies(self, content: str, file_path: str) -> List[Dependency]:
        """Analyze dependencies for non-Python files."""
        import re
        dependencies = []
        lines = content.split('\n')
        
        # JavaScript/TypeScript imports
        import_patterns = [
            r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
        ]
        
        for i, line in enumerate(lines):
            for pattern in import_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    dependencies.append(Dependency(
                        source=file_path,
                        target=match.group(1),
                        dependency_type='import',
                        line_number=i + 1,
                        confidence=0.8
                    ))
        
        return dependencies
    
    def _build_call_graph(self) -> None:
        """Build call graph from dependencies."""
        for file_path, deps in self.dependency_graph.items():
            calls = set()
            for dep in deps:
                if dep.dependency_type == 'call':
                    calls.add(dep.target)
            self.call_graph[file_path] = calls
    
    def find_impact_analysis(self, changed_files: List[str]) -> Dict[str, List[str]]:
        """Find files that might be impacted by changes to given files."""
        impacted = {}
        
        for changed_file in changed_files:
            impacted_files = set()
            
            # Direct dependents (files that import/use this file)
            if changed_file in self.reverse_dependencies:
                for dep in self.reverse_dependencies[changed_file]:
                    impacted_files.add(dep.source)
            
            # Files that call functions from this file
            for file_path, calls in self.call_graph.items():
                if any(changed_file in call for call in calls):
                    impacted_files.add(file_path)
            
            impacted[changed_file] = list(impacted_files)
        
        return impacted
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Find circular dependencies in the codebase."""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            
            # Visit dependencies
            for dep in self.dependency_graph.get(node, []):
                if dep.dependency_type in ['import', 'inheritance']:
                    dfs(dep.target, path + [node])
            
            rec_stack.remove(node)
        
        for file_path in self.dependency_graph.keys():
            if file_path not in visited:
                dfs(file_path, [])
        
        return cycles
    
    def get_complexity_hotspots(self, threshold: int = 10) -> List[Tuple[str, int]]:
        """Get files with high cyclomatic complexity."""
        hotspots = []
        
        for file_path, metrics in self.code_metrics.items():
            if metrics.cyclomatic_complexity >= threshold:
                hotspots.append((file_path, metrics.cyclomatic_complexity))
        
        hotspots.sort(key=lambda x: x[1], reverse=True)
        return hotspots
    
    def get_code_smells_summary(self) -> Dict[str, List[str]]:
        """Get summary of code smells by type."""
        smells_by_type = {}
        
        for file_path, metrics in self.code_metrics.items():
            for smell in metrics.code_smells:
                smell_type = smell.split('_')[0]  # Extract smell type
                if smell_type not in smells_by_type:
                    smells_by_type[smell_type] = []
                smells_by_type[smell_type].append(f"{file_path}: {smell}")
        
        return smells_by_type
    
    def suggest_refactoring_candidates(self) -> List[Dict[str, Any]]:
        """Suggest files that are good candidates for refactoring."""
        candidates = []
        
        for file_path, metrics in self.code_metrics.items():
            score = 0
            reasons = []
            
            # High complexity
            if metrics.cyclomatic_complexity > 15:
                score += 3
                reasons.append(f"High complexity ({metrics.cyclomatic_complexity})")
            
            # Many code smells
            if len(metrics.code_smells) > 3:
                score += 2
                reasons.append(f"Multiple code smells ({len(metrics.code_smells)})")
            
            # Low maintainability
            if metrics.maintainability_index < 0.5:
                score += 2
                reasons.append(f"Low maintainability ({metrics.maintainability_index:.2f})")
            
            # Large file
            if metrics.lines_of_code > 500:
                score += 1
                reasons.append(f"Large file ({metrics.lines_of_code} LOC)")
            
            if score >= 3:
                candidates.append({
                    'file_path': file_path,
                    'refactoring_score': score,
                    'reasons': reasons,
                    'metrics': metrics
                })
        
        candidates.sort(key=lambda x: x['refactoring_score'], reverse=True)
        return candidates
    
    def get_dependency_strength(self, file1: str, file2: str) -> float:
        """Calculate dependency strength between two files."""
        strength = 0.0
        
        # Check direct dependencies
        for dep in self.dependency_graph.get(file1, []):
            if dep.target == file2:
                strength += dep.confidence
        
        # Check reverse dependencies
        for dep in self.dependency_graph.get(file2, []):
            if dep.target == file1:
                strength += dep.confidence
        
        return min(strength, 1.0)