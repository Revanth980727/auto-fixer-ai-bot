import subprocess
import tempfile
import os
import json
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class LintRunner:
    """Runs linting tools for code quality validation."""
    
    def __init__(self):
        self.python_linters = ['flake8', 'pylint', 'black --check']
        self.js_linters = ['eslint', 'prettier --check']
        self.available_linters = self._check_available_linters()
    
    def _check_available_linters(self) -> Dict[str, List[str]]:
        """Check which linters are available in the system."""
        available = {'python': [], 'javascript': []}
        
        # Check Python linters
        for linter in self.python_linters:
            command = linter.split()[0]
            if self._is_command_available(command):
                available['python'].append(linter)
        
        # Check JavaScript linters
        for linter in self.js_linters:
            command = linter.split()[0]
            if self._is_command_available(command):
                available['javascript'].append(linter)
        
        logger.info(f"Available linters: {available}")
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
        """Run linting validation on a file."""
        try:
            logger.info(f"🔍 Running lint validation on {file_path}")
            
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
                return self._validate_python(file_path)
            elif file_ext in ['.js', '.ts', '.tsx', '.jsx']:
                return self._validate_javascript(file_path)
            else:
                return {
                    'success': True,
                    'confidence': 0.5,
                    'issues': [],
                    'warnings': [f"No linter available for {file_ext} files"],
                    'details': {}
                }
                
        except Exception as e:
            logger.error(f"❌ Error in lint validation: {e}")
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Lint validation error: {str(e)}"],
                'warnings': [],
                'details': {}
            }
    
    def _validate_python(self, file_path: str) -> Dict[str, Any]:
        """Validate Python file using available linters."""
        all_issues = []
        all_warnings = []
        details = {}
        success = True
        
        for linter in self.available_linters.get('python', []):
            try:
                result = self._run_python_linter(linter, file_path)
                details[linter] = result
                
                if result['issues']:
                    all_issues.extend([f"{linter}: {issue}" for issue in result['issues']])
                if result['warnings']:
                    all_warnings.extend([f"{linter}: {warning}" for warning in result['warnings']])
                
                if not result['success']:
                    success = False
                    
            except Exception as e:
                logger.error(f"❌ Error running {linter}: {e}")
                all_issues.append(f"{linter}: Failed to run linter")
                success = False
        
        # If no linters available, do basic validation
        if not self.available_linters.get('python'):
            return self._basic_python_validation(file_path)
        
        confidence = 0.8 if success else 0.3
        
        return {
            'success': success,
            'confidence': confidence,
            'issues': all_issues,
            'warnings': all_warnings,
            'details': details
        }
    
    def _run_python_linter(self, linter: str, file_path: str) -> Dict[str, Any]:
        """Run a specific Python linter."""
        command_parts = linter.split()
        command = command_parts + [file_path]
        
        try:
            result = subprocess.run(command, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=30)
            
            if command_parts[0] == 'flake8':
                return self._parse_flake8_output(result)
            elif command_parts[0] == 'pylint':
                return self._parse_pylint_output(result)
            elif command_parts[0] == 'black':
                return self._parse_black_output(result)
            else:
                return self._parse_generic_output(result)
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['Linter timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _parse_flake8_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse flake8 output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        
        lines = result.stdout.split('\n')
        for line in lines:
            if line.strip():
                # flake8 format: file:line:col: error_code error_message
                if ':' in line:
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        error_code = parts[3].strip().split()[0]
                        message = parts[3].strip()
                        
                        # Categorize by error code
                        if error_code.startswith(('E1', 'E9', 'F8')):  # Syntax errors
                            issues.append(message)
                        else:
                            warnings.append(message)
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout
        }
    
    def _parse_pylint_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse pylint output."""
        issues = []
        warnings = []
        
        try:
            # Try to parse as JSON first
            output = json.loads(result.stdout)
            for item in output:
                message = f"Line {item.get('line', '?')}: {item.get('message', '')}"
                if item.get('type') in ['error', 'fatal']:
                    issues.append(message)
                else:
                    warnings.append(message)
        except json.JSONDecodeError:
            # Fallback to text parsing
            lines = result.stdout.split('\n')
            for line in lines:
                if ':' in line and any(severity in line for severity in ['E:', 'W:', 'C:', 'R:']):
                    if line.startswith('E:'):
                        issues.append(line)
                    else:
                        warnings.append(line)
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout
        }
    
    def _parse_black_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse black --check output."""
        issues = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        elif result.returncode == 1:
            issues.append("File would be reformatted by black")
        else:
            issues.append("Black formatting check failed")
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': [],
            'output': result.stdout + result.stderr
        }
    
    def _parse_generic_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse generic linter output."""
        return {
            'success': result.returncode == 0,
            'issues': [result.stderr] if result.stderr else [],
            'warnings': [result.stdout] if result.stdout and result.returncode != 0 else [],
            'output': result.stdout + result.stderr
        }
    
    def _basic_python_validation(self, file_path: str) -> Dict[str, Any]:
        """Basic Python validation when no linters are available."""
        issues = []
        warnings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic checks
            lines = content.split('\n')
            
            # Check for long lines
            for i, line in enumerate(lines):
                if len(line) > 120:
                    warnings.append(f"Line {i+1}: Line too long ({len(line)} chars)")
            
            # Check for syntax
            try:
                compile(content, file_path, 'exec')
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")
            
            # Check for basic style issues
            if '\t' in content and '    ' in content:
                warnings.append("Mixed indentation (tabs and spaces)")
            
            return {
                'success': len(issues) == 0,
                'confidence': 0.4,  # Lower confidence for basic validation
                'issues': issues,
                'warnings': warnings,
                'details': {'validator': 'basic_python'}
            }
            
        except Exception as e:
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Basic validation error: {e}"],
                'warnings': [],
                'details': {}
            }
    
    def _validate_javascript(self, file_path: str) -> Dict[str, Any]:
        """Validate JavaScript/TypeScript file."""
        all_issues = []
        all_warnings = []
        details = {}
        success = True
        
        for linter in self.available_linters.get('javascript', []):
            try:
                result = self._run_javascript_linter(linter, file_path)
                details[linter] = result
                
                if result['issues']:
                    all_issues.extend([f"{linter}: {issue}" for issue in result['issues']])
                if result['warnings']:
                    all_warnings.extend([f"{linter}: {warning}" for warning in result['warnings']])
                
                if not result['success']:
                    success = False
                    
            except Exception as e:
                logger.error(f"❌ Error running {linter}: {e}")
                all_issues.append(f"{linter}: Failed to run linter")
                success = False
        
        # If no linters available, do basic validation
        if not self.available_linters.get('javascript'):
            return self._basic_javascript_validation(file_path)
        
        confidence = 0.8 if success else 0.3
        
        return {
            'success': success,
            'confidence': confidence,
            'issues': all_issues,
            'warnings': all_warnings,
            'details': details
        }
    
    def _run_javascript_linter(self, linter: str, file_path: str) -> Dict[str, Any]:
        """Run a specific JavaScript linter."""
        command_parts = linter.split()
        command = command_parts + [file_path]
        
        try:
            result = subprocess.run(command, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=30)
            
            if command_parts[0] == 'eslint':
                return self._parse_eslint_output(result)
            elif command_parts[0] == 'prettier':
                return self._parse_prettier_output(result)
            else:
                return self._parse_generic_output(result)
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['Linter timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _parse_eslint_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse ESLint output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        
        lines = result.stdout.split('\n')
        for line in lines:
            if 'error' in line.lower():
                issues.append(line.strip())
            elif 'warning' in line.lower():
                warnings.append(line.strip())
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout
        }
    
    def _parse_prettier_output(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse Prettier output."""
        issues = []
        
        if result.returncode == 0:
            return {'success': True, 'issues': [], 'warnings': [], 'output': result.stdout}
        else:
            issues.append("File would be reformatted by prettier")
        
        return {
            'success': len(issues) == 0,
            'issues': issues,
            'warnings': [],
            'output': result.stdout + result.stderr
        }
    
    def _basic_javascript_validation(self, file_path: str) -> Dict[str, Any]:
        """Basic JavaScript validation when no linters are available."""
        issues = []
        warnings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic checks
            lines = content.split('\n')
            
            # Check for long lines
            for i, line in enumerate(lines):
                if len(line) > 120:
                    warnings.append(f"Line {i+1}: Line too long ({len(line)} chars)")
            
            # Basic syntax checks
            if content.count('{') != content.count('}'):
                issues.append("Unbalanced curly braces")
            if content.count('(') != content.count(')'):
                issues.append("Unbalanced parentheses")
            if content.count('[') != content.count(']'):
                issues.append("Unbalanced square brackets")
            
            return {
                'success': len(issues) == 0,
                'confidence': 0.4,  # Lower confidence for basic validation
                'issues': issues,
                'warnings': warnings,
                'details': {'validator': 'basic_javascript'}
            }
            
        except Exception as e:
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Basic validation error: {e}"],
                'warnings': [],
                'details': {}
            }
    
    async def validate_async(self, file_path: str, patch_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Async wrapper for validate method."""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.validate, file_path, patch_info)