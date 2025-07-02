import subprocess
import os
import json
import tempfile
import shutil
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TestRunner:
    """Runs automated tests for code validation."""
    
    def __init__(self):
        self.python_runners = ['pytest', 'python -m unittest', 'python -m pytest']
        self.js_runners = ['npm test', 'yarn test', 'jest', 'mocha']
        self.available_runners = self._check_available_runners()
    
    def _check_available_runners(self) -> Dict[str, List[str]]:
        """Check which test runners are available in the system."""
        available = {'python': [], 'javascript': []}
        
        # Check Python test runners
        for runner in self.python_runners:
            command = runner.split()[0]
            if self._is_command_available(command):
                available['python'].append(runner)
        
        # Check JavaScript test runners
        for runner in self.js_runners:
            command = runner.split()[0]
            if self._is_command_available(command):
                available['javascript'].append(runner)
        
        logger.info(f"Available test runners: {available}")
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
        """Run test validation for a file."""
        try:
            logger.info(f"🧪 Running test validation for {file_path}")
            
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'confidence': 0.0,
                    'issues': [f"File not found: {file_path}"],
                    'warnings': [],
                    'details': {}
                }
            
            # Determine project type and find tests
            project_info = self._analyze_project_structure(file_path)
            
            if project_info['type'] == 'python':
                return self._run_python_tests(file_path, project_info)
            elif project_info['type'] == 'javascript':
                return self._run_javascript_tests(file_path, project_info)
            else:
                return {
                    'success': True,
                    'confidence': 0.5,
                    'issues': [],
                    'warnings': ['No test runner available for this file type'],
                    'details': {}
                }
                
        except Exception as e:
            logger.error(f"❌ Error in test validation: {e}")
            return {
                'success': False,
                'confidence': 0.0,
                'issues': [f"Test validation error: {str(e)}"],
                'warnings': [],
                'details': {}
            }
    
    def _analyze_project_structure(self, file_path: str) -> Dict[str, Any]:
        """Analyze project structure to find tests and determine project type."""
        project_root = self._find_project_root(file_path)
        project_type = 'unknown'
        test_files = []
        test_dirs = []
        
        # Determine project type
        if file_path.endswith('.py'):
            project_type = 'python'
            test_patterns = ['test_*.py', '*_test.py', 'tests/*.py']
        elif file_path.endswith(('.js', '.ts', '.tsx', '.jsx')):
            project_type = 'javascript'
            test_patterns = ['*.test.js', '*.test.ts', '*.spec.js', '*.spec.ts', '__tests__/*.js']
        
        # Find test files
        if project_root:
            test_files = self._find_test_files(project_root, test_patterns if project_type != 'unknown' else [])
            test_dirs = self._find_test_directories(project_root)
        
        return {
            'type': project_type,
            'root': project_root,
            'test_files': test_files,
            'test_dirs': test_dirs,
            'has_tests': len(test_files) > 0 or len(test_dirs) > 0
        }
    
    def _find_project_root(self, file_path: str) -> Optional[str]:
        """Find the project root directory."""
        current_dir = os.path.dirname(os.path.abspath(file_path))
        
        # Look for common project indicators
        indicators = [
            'requirements.txt', 'setup.py', 'pyproject.toml',  # Python
            'package.json', 'yarn.lock', 'package-lock.json',  # JavaScript
            '.git', 'README.md'  # General
        ]
        
        while current_dir != '/':
            for indicator in indicators:
                if os.path.exists(os.path.join(current_dir, indicator)):
                    return current_dir
            
            parent = os.path.dirname(current_dir)
            if parent == current_dir:  # Reached filesystem root
                break
            current_dir = parent
        
        # Fallback to directory containing the file
        return os.path.dirname(os.path.abspath(file_path))
    
    def _find_test_files(self, project_root: str, patterns: List[str]) -> List[str]:
        """Find test files matching patterns."""
        import fnmatch
        test_files = []
        
        for root, dirs, files in os.walk(project_root):
            for pattern in patterns:
                for file in files:
                    if fnmatch.fnmatch(file, pattern.split('/')[-1]):
                        test_files.append(os.path.join(root, file))
        
        return test_files
    
    def _find_test_directories(self, project_root: str) -> List[str]:
        """Find test directories."""
        test_dirs = []
        test_dir_names = ['tests', 'test', '__tests__', 'spec']
        
        for root, dirs, files in os.walk(project_root):
            for dir_name in dirs:
                if dir_name in test_dir_names:
                    test_dirs.append(os.path.join(root, dir_name))
        
        return test_dirs
    
    def _run_python_tests(self, file_path: str, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Run Python tests."""
        if not project_info['has_tests']:
            return {
                'success': True,
                'confidence': 0.3,
                'issues': [],
                'warnings': ['No tests found for validation'],
                'details': {'reason': 'no_tests_found'}
            }
        
        # Try to find specific tests for this file
        specific_tests = self._find_related_tests(file_path, project_info['test_files'])
        
        all_issues = []
        all_warnings = []
        details = {}
        success = True
        
        for runner in self.available_runners.get('python', []):
            try:
                if specific_tests:
                    # Run specific tests
                    for test_file in specific_tests[:3]:  # Limit to 3 test files
                        result = self._run_python_test_file(runner, test_file, project_info['root'])
                        details[f"{runner}_{os.path.basename(test_file)}"] = result
                        
                        if result['issues']:
                            all_issues.extend(result['issues'])
                        if result['warnings']:
                            all_warnings.extend(result['warnings'])
                        if not result['success']:
                            success = False
                else:
                    # Run all tests in test directory
                    if project_info['test_dirs']:
                        test_dir = project_info['test_dirs'][0]
                        result = self._run_python_test_directory(runner, test_dir, project_info['root'])
                        details[f"{runner}_all"] = result
                        
                        if result['issues']:
                            all_issues.extend(result['issues'])
                        if result['warnings']:
                            all_warnings.extend(result['warnings'])
                        if not result['success']:
                            success = False
                
                # Only try first available runner to avoid redundancy
                break
                
            except Exception as e:
                logger.error(f"❌ Error running {runner}: {e}")
                all_issues.append(f"{runner}: Failed to run tests")
                success = False
        
        confidence = 0.8 if success else 0.2
        
        return {
            'success': success,
            'confidence': confidence,
            'issues': all_issues,
            'warnings': all_warnings,
            'details': details
        }
    
    def _find_related_tests(self, file_path: str, test_files: List[str]) -> List[str]:
        """Find test files related to the given file."""
        related_tests = []
        file_name = os.path.basename(file_path)
        file_name_without_ext = os.path.splitext(file_name)[0]
        
        for test_file in test_files:
            test_name = os.path.basename(test_file)
            
            # Check if test file name contains the source file name
            if file_name_without_ext in test_name:
                related_tests.append(test_file)
            # Check for standard naming patterns
            elif f"test_{file_name_without_ext}" in test_name:
                related_tests.append(test_file)
            elif f"{file_name_without_ext}_test" in test_name:
                related_tests.append(test_file)
        
        return related_tests
    
    def _run_python_test_file(self, runner: str, test_file: str, project_root: str) -> Dict[str, Any]:
        """Run a specific Python test file."""
        try:
            command_parts = runner.split()
            command = command_parts + [test_file, '-v']  # Verbose output
            
            result = subprocess.run(command,
                                  capture_output=True,
                                  text=True,
                                  timeout=120,  # 2 minutes timeout
                                  cwd=project_root)
            
            return self._parse_python_test_output(result, runner)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['Test execution timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _run_python_test_directory(self, runner: str, test_dir: str, project_root: str) -> Dict[str, Any]:
        """Run all tests in a directory."""
        try:
            command_parts = runner.split()
            command = command_parts + [test_dir, '-v']
            
            result = subprocess.run(command,
                                  capture_output=True,
                                  text=True,
                                  timeout=180,  # 3 minutes timeout
                                  cwd=project_root)
            
            return self._parse_python_test_output(result, runner)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['Test directory execution timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _parse_python_test_output(self, result: subprocess.CompletedProcess, runner: str) -> Dict[str, Any]:
        """Parse Python test output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            # Tests passed
            return {
                'success': True,
                'issues': [],
                'warnings': [],
                'output': result.stdout,
                'stats': self._extract_test_stats(result.stdout, 'python')
            }
        
        # Parse failure output
        output_lines = (result.stdout + result.stderr).split('\n')
        
        for line in output_lines:
            line = line.strip()
            if line:
                if 'FAILED' in line or 'ERROR' in line:
                    issues.append(line)
                elif 'WARNING' in line or 'SKIPPED' in line:
                    warnings.append(line)
        
        return {
            'success': False,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout + result.stderr,
            'stats': self._extract_test_stats(result.stdout + result.stderr, 'python')
        }
    
    def _run_javascript_tests(self, file_path: str, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Run JavaScript tests."""
        if not project_info['has_tests']:
            return {
                'success': True,
                'confidence': 0.3,
                'issues': [],
                'warnings': ['No tests found for validation'],
                'details': {'reason': 'no_tests_found'}
            }
        
        all_issues = []
        all_warnings = []
        details = {}
        success = True
        
        for runner in self.available_runners.get('javascript', []):
            try:
                result = self._run_javascript_test_runner(runner, project_info['root'])
                details[runner] = result
                
                if result['issues']:
                    all_issues.extend(result['issues'])
                if result['warnings']:
                    all_warnings.extend(result['warnings'])
                if not result['success']:
                    success = False
                
                # Only try first available runner
                break
                
            except Exception as e:
                logger.error(f"❌ Error running {runner}: {e}")
                all_issues.append(f"{runner}: Failed to run tests")
                success = False
        
        confidence = 0.8 if success else 0.2
        
        return {
            'success': success,
            'confidence': confidence,
            'issues': all_issues,
            'warnings': all_warnings,
            'details': details
        }
    
    def _run_javascript_test_runner(self, runner: str, project_root: str) -> Dict[str, Any]:
        """Run JavaScript test runner."""
        try:
            command_parts = runner.split()
            
            result = subprocess.run(command_parts,
                                  capture_output=True,
                                  text=True,
                                  timeout=180,
                                  cwd=project_root)
            
            return self._parse_javascript_test_output(result, runner)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'issues': ['JavaScript test execution timed out'],
                'warnings': [],
                'output': ''
            }
    
    def _parse_javascript_test_output(self, result: subprocess.CompletedProcess, runner: str) -> Dict[str, Any]:
        """Parse JavaScript test output."""
        issues = []
        warnings = []
        
        if result.returncode == 0:
            return {
                'success': True,
                'issues': [],
                'warnings': [],
                'output': result.stdout,
                'stats': self._extract_test_stats(result.stdout, 'javascript')
            }
        
        # Parse failure output
        output_lines = (result.stdout + result.stderr).split('\n')
        
        for line in output_lines:
            line = line.strip()
            if line:
                if any(keyword in line.lower() for keyword in ['fail', 'error', '✕', '×']):
                    issues.append(line)
                elif any(keyword in line.lower() for keyword in ['warn', 'skip', '⚠']):
                    warnings.append(line)
        
        return {
            'success': False,
            'issues': issues,
            'warnings': warnings,
            'output': result.stdout + result.stderr,
            'stats': self._extract_test_stats(result.stdout + result.stderr, 'javascript')
        }
    
    def _extract_test_stats(self, output: str, test_type: str) -> Dict[str, Any]:
        """Extract test statistics from output."""
        stats = {'passed': 0, 'failed': 0, 'skipped': 0, 'total': 0}
        
        try:
            if test_type == 'python':
                # Look for pytest/unittest patterns
                import re
                patterns = [
                    r'(\d+) passed',
                    r'(\d+) failed',
                    r'(\d+) skipped',
                    r'(\d+) error'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, output)
                    if match:
                        count = int(match.group(1))
                        if 'passed' in pattern:
                            stats['passed'] = count
                        elif 'failed' in pattern or 'error' in pattern:
                            stats['failed'] += count
                        elif 'skipped' in pattern:
                            stats['skipped'] = count
            
            elif test_type == 'javascript':
                # Look for Jest/Mocha patterns
                import re
                patterns = [
                    r'(\d+) passing',
                    r'(\d+) failing',
                    r'(\d+) pending'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, output)
                    if match:
                        count = int(match.group(1))
                        if 'passing' in pattern:
                            stats['passed'] = count
                        elif 'failing' in pattern:
                            stats['failed'] = count
                        elif 'pending' in pattern:
                            stats['skipped'] = count
            
            stats['total'] = stats['passed'] + stats['failed'] + stats['skipped']
            
        except Exception as e:
            logger.error(f"❌ Error extracting test stats: {e}")
        
        return stats
    
    async def validate_async(self, file_path: str, patch_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Async wrapper for validate method."""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.validate, file_path, patch_info)