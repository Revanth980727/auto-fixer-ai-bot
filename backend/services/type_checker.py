import subprocess
import tempfile
import os
import json
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TypeChecker:
    """Runs type checking tools for code validation."""
    
    def __init__(self):
        self.python_checkers = ['mypy', 'pyright']
        self.js_checkers = ['tsc --noEmit', 'flow check']
        self.available_checkers = self._check_available_checkers()
    
    def _check_available_checkers(self) -> Dict[str, List[str]]:
        """Check which type checkers are available in the system."""
        available = {'python': [], 'javascript': []}
        
        # Check Python type checkers
        for checker in self.python_checkers:
            command = checker.split()[0]
            if self._is_command_available(command):
                available['python'].append(checker)
        
        # Check JavaScript type checkers
        for checker in self.js_checkers:
            command = checker.split()[0]
            if self._is_command_available(command):
                available['javascript'].append(checker)
        
        logger.info(f"Available type checkers: {available}")
        return available
    
    def _is_command_available(self, command: str) -> bool:
        """Check if a command is available in the system."""
        try:
            result = subprocess.run(['which', command], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def validate(self, file_path: str, patch_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run type checking validation on a file."""
        try:
            logger.info(f"🔍 Running type checking on {file_path}")
            
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'confidence': 0.0,
                    'issues': [f"File not found: {file_path}"],
                    'warnings': [],
                    'details': {}
                }
            
            file_ext = os.path.splitext(file_path)[1]
            
            if file_ext == '.py':
                return self._validate_python_types(file_path)
            elif file_ext in ['.ts', '.tsx']:
                return self._validate_typescript(file_path)
            elif file_ext in ['.js', '.jsx']:
                return self._validate_javascript_types(file_path)
            else:
                return {
                    'success': True,
                    'confidence': 0.5,
                    'issues': [],
                    'warnings': [f"No type checker available for {file_ext} files"],
                    'details': {}
                }
                
        except Exception as e:
            logger.error(f"❌ Error in type checking: {e}")
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Type checking error: {str(e)}"],
                'warnings': [],
                'details': {}
            }
    
    def _validate_python_types(self, file_path: str) -> Dict[str, Any]:
        """Validate Python types using available checkers."""
        all_issues = []
        all_warnings = []
        details = {}
        success = True
        
        for checker in self.available_checkers.get('python', []):
            try:
                result = self._run_python_type_checker(checker, file_path)
                details[checker] = result
                
                if result['issues']:
                    all_issues.extend([f"{checker}: {issue}" for issue in result['issues']])
                if result['warnings']:
                    all_warnings.extend([f"{checker}: {warning}" for warning in result['warnings']])
                
                if not result['success']:
                    success = False
                    
            except Exception as e:
                logger.error(f"❌ Error running {checker}: {e}")
                all_issues.append(f"{checker}: Failed to run type checker")
                success = False
        
        # If no type checkers available, do basic validation
        if not self.available_checkers.get('python'):
            return self._basic_python_type_validation(file_path)
        
        confidence = 0.8 if success else 0.3
        
        return {
            'success': success,
            'confidence': confidence,
            'issues': all_issues,
            'warnings': all_warnings,
            'details': details
        }
    
    def _run_python_type_checker(self, checker: str, file_path: str) -> Dict[str, Any]:
        """Run a specific Python type checker."""
        command_parts = checker.split()
        command = command_parts + [file_path]
        
        try:
            result = subprocess.run(command, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=60)
            
            if command_parts[0] == 'mypy':
                return self._parse_mypy_output(result)
            elif command_parts[0] == 'pyright':
                return self._parse_pyright_output(result)
            else:
                return self._parse_generic_type_output(result)
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['Type checker timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _parse_mypy_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse mypy output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        
        lines = result.stdout.split('\n')
        for line in lines:
            if line.strip():
                # mypy format: file:line: error: message
                if ': error:' in line:
                    issues.append(line.strip())
                elif ': warning:' in line:
                    warnings.append(line.strip())
                elif ': note:' in line:
                    warnings.append(line.strip())
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout
        }
    
    def _parse_pyright_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse pyright output."""
        issues = []
        warnings = []
        
        try:
            # Try to parse as JSON
            output = json.loads(result.stdout)
            diagnostics = output.get('generalDiagnostics', [])
            
            for diag in diagnostics:
                message = f"Line {diag.get('range', {}).get('start', {}).get('line', '?')}: {diag.get('message', '')}"
                severity = diag.get('severity', 'error')
                
                if severity == 'error':
                    issues.append(message)
                else:
                    warnings.append(message)
                    
        except json.JSONDecodeError:
            # Fallback to text parsing
            lines = result.stdout.split('\n')
            for line in lines:
                if 'error:' in line.lower():
                    issues.append(line.strip())
                elif 'warning:' in line.lower():
                    warnings.append(line.strip())
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout
        }
    
    def _parse_generic_type_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse generic type checker output."""
        return {
            'success': result.returncode == 0,
            'issues': [result.stderr] if result.stderr else [],
            'warnings': [result.stdout] if result.stdout and result.returncode != 0 else [],
            'output': result.stdout + result.stderr
        }
    
    def _basic_python_type_validation(self, file_path: str) -> Dict[str, Any]:
        """Basic Python type validation when no type checkers are available."""
        issues = []
        warnings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for type annotations
            import ast
            try:
                tree = ast.parse(content)
                
                # Count functions with/without type annotations
                functions_with_annotations = 0
                total_functions = 0
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_functions += 1
                        
                        # Check for return type annotation
                        has_return_annotation = node.returns is not None
                        
                        # Check for parameter type annotations
                        has_param_annotations = any(arg.annotation for arg in node.args.args)
                        
                        if has_return_annotation or has_param_annotations:
                            functions_with_annotations += 1
                
                if total_functions > 0:
                    annotation_ratio = functions_with_annotations / total_functions
                    if annotation_ratio < 0.5:
                        warnings.append(f"Low type annotation coverage: {annotation_ratio:.1%}")
                
            except SyntaxError:
                issues.append("Syntax error prevents type analysis")
            
            return {
                'success': len(issues) == 0,
                'confidence': 0.4,  # Lower confidence for basic validation
                'issues': issues,
                'warnings': warnings,
                'details': {'validator': 'basic_python_types'}
            }
            
        except Exception as e:
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Basic type validation error: {e}"],
                'warnings': [],
                'details': {}
            }
    
    def _validate_typescript(self, file_path: str) -> Dict[str, Any]:
        """Validate TypeScript files."""
        all_issues = []
        all_warnings = []
        details = {}
        success = True
        
        # Try TypeScript compiler
        if 'tsc --noEmit' in self.available_checkers.get('javascript', []):
            try:
                result = self._run_typescript_checker(file_path)
                details['tsc'] = result
                
                if result['issues']:
                    all_issues.extend(result['issues'])
                if result['warnings']:
                    all_warnings.extend(result['warnings'])
                
                if not result['success']:
                    success = False
                    
            except Exception as e:
                logger.error(f"❌ Error running TypeScript checker: {e}")
                all_issues.append("TypeScript checker failed")
                success = False
        else:
            return self._basic_typescript_validation(file_path)
        
        confidence = 0.8 if success else 0.3
        
        return {
            'success': success,
            'confidence': confidence,
            'issues': all_issues,
            'warnings': all_warnings,
            'details': details
        }
    
    def _run_typescript_checker(self, file_path: str) -> Dict[str, Any]:
        """Run TypeScript compiler for type checking."""
        try:
            # Create a temporary tsconfig for this file
            temp_dir = os.path.dirname(file_path)
            
            result = subprocess.run(['tsc', '--noEmit', '--skipLibCheck', file_path], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=60)
            
            return self._parse_typescript_output(result)
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['TypeScript checker timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _parse_typescript_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse TypeScript compiler output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        
        lines = result.stderr.split('\n')
        for line in lines:
            if line.strip() and '(' in line and ')' in line:
                # TypeScript format: file(line,col): error TS####: message
                if 'error TS' in line:
                    issues.append(line.strip())
                elif 'warning TS' in line:
                    warnings.append(line.strip())
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stderr
        }
    
    def _validate_javascript_types(self, file_path: str) -> Dict[str, Any]:
        """Validate JavaScript files (with Flow if available)."""
        if 'flow check' in self.available_checkers.get('javascript', []):
            try:
                result = subprocess.run(['flow', 'check', file_path], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=60)
                
                return self._parse_flow_output(result)
                
            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'issues': ['Flow checker timed out'],
                    'warnings': [],
                    'details': {}
                }
            except Exception as e:
                logger.error(f"❌ Error running Flow: {e}")
        
        return {
            'success': True,
            'confidence': 0.5,
            'issues': [],
            'warnings': ['No type checking available for JavaScript files'],
            'details': {}
        }
    
    def _parse_flow_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse Flow output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        
        lines = result.stderr.split('\n')
        for line in lines:
            if 'Error:' in line:
                issues.append(line.strip())
            elif 'Warning:' in line:
                warnings.append(line.strip())
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stderr
        }
    
    def _basic_typescript_validation(self, file_path: str) -> Dict[str, Any]:
        """Basic TypeScript validation when no type checker is available."""
        issues = []
        warnings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic TypeScript checks
            if ': any' in content:
                warnings.append("Usage of 'any' type detected")
            
            # Check for basic TypeScript syntax
            if content.count('<') != content.count('>'):
                issues.append("Unbalanced angle brackets (potential generic type issue)")
            
            return {
                'success': len(issues) == 0,
                'confidence': 0.3,  # Very low confidence for basic validation
                'issues': issues,
                'warnings': warnings,
                'details': {'validator': 'basic_typescript'}
            }
            
        except Exception as e:
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Basic TypeScript validation error: {e}"],
                'warnings': [],
                'details': {}
            }
    
    async def validate_async(self, file_path: str, patch_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Async wrapper for validate method."""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.validate, file_path, patch_info)