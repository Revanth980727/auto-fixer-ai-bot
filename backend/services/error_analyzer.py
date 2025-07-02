import re
import ast
import traceback
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ErrorLocation:
    """Represents a location where an error occurred."""
    file_path: str
    line_number: int
    function_name: Optional[str]
    code_line: Optional[str]
    error_type: str
    confidence: float

@dataclass
class ErrorAnalysis:
    """Complete analysis of an error."""
    error_type: str
    error_message: str
    root_cause: str
    primary_location: Optional[ErrorLocation]
    related_locations: List[ErrorLocation]
    suggested_files: List[str]
    analysis_confidence: float
    fix_suggestions: List[str]

class ErrorAnalyzer:
    """Analyzes errors from stack traces, logs, and test failures."""
    
    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        
    def _load_error_patterns(self) -> Dict[str, Dict]:
        """Load common error patterns and their characteristics."""
        return {
            'AttributeError': {
                'patterns': [
                    r"'(\w+)' object has no attribute '(\w+)'",
                    r"module '(\w+)' has no attribute '(\w+)'"
                ],
                'common_causes': ['typo in attribute name', 'wrong object type', 'missing import'],
                'fix_strategies': ['check attribute spelling', 'verify object type', 'check imports']
            },
            'NameError': {
                'patterns': [
                    r"name '(\w+)' is not defined"
                ],
                'common_causes': ['undefined variable', 'typo in variable name', 'scope issue'],
                'fix_strategies': ['define variable', 'check spelling', 'check variable scope']
            },
            'TypeError': {
                'patterns': [
                    r"(\w+)\(\) takes (\d+) positional argument[s]? but (\d+) (?:was|were) given",
                    r"(\w+)\(\) missing (\d+) required positional argument[s]?: '(\w+)'",
                    r"unsupported operand type\(s\) for (\+|\-|\*|\/): '(\w+)' and '(\w+)'"
                ],
                'common_causes': ['wrong number of arguments', 'type mismatch', 'missing parameters'],
                'fix_strategies': ['check function signature', 'verify argument types', 'add missing parameters']
            },
            'ImportError': {
                'patterns': [
                    r"cannot import name '(\w+)' from '([\w\.]+)'",
                    r"No module named '([\w\.]+)'"
                ],
                'common_causes': ['missing module', 'wrong import path', 'circular import'],
                'fix_strategies': ['install missing module', 'fix import path', 'resolve circular imports']
            },
            'IndentationError': {
                'patterns': [
                    r"expected an indented block",
                    r"unindent does not match any outer indentation level"
                ],
                'common_causes': ['incorrect indentation', 'mixing tabs and spaces'],
                'fix_strategies': ['fix indentation', 'use consistent whitespace']
            },
            'SyntaxError': {
                'patterns': [
                    r"invalid syntax",
                    r"unexpected EOF while parsing",
                    r"EOL while scanning string literal"
                ],
                'common_causes': ['syntax error', 'unclosed brackets', 'unclosed strings'],
                'fix_strategies': ['fix syntax', 'check brackets', 'check string quotes']
            }
        }
    
    def analyze_stack_trace(self, stack_trace: str, available_files: List[str] = None) -> ErrorAnalysis:
        """Analyze a Python stack trace."""
        try:
            logger.info("🔍 Analyzing stack trace for error patterns")
            
            # Extract basic error information
            error_type, error_message = self._extract_error_info(stack_trace)
            
            # Extract file locations from stack trace
            locations = self._extract_error_locations(stack_trace)
            
            # Determine primary error location
            primary_location = self._identify_primary_location(locations, available_files)
            
            # Analyze error pattern
            root_cause = self._analyze_error_pattern(error_type, error_message)
            
            # Get fix suggestions
            fix_suggestions = self._get_fix_suggestions(error_type, error_message)
            
            # Suggest relevant files to examine
            suggested_files = self._suggest_relevant_files(locations, available_files)
            
            # Calculate analysis confidence
            confidence = self._calculate_confidence(error_type, locations, primary_location)
            
            analysis = ErrorAnalysis(
                error_type=error_type,
                error_message=error_message,
                root_cause=root_cause,
                primary_location=primary_location,
                related_locations=locations,
                suggested_files=suggested_files,
                analysis_confidence=confidence,
                fix_suggestions=fix_suggestions
            )
            
            logger.info(f"✅ Error analysis completed: {error_type} with {confidence:.2f} confidence")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing stack trace: {e}")
            return self._create_fallback_analysis(stack_trace)
    
    def _extract_error_info(self, stack_trace: str) -> Tuple[str, str]:
        """Extract error type and message from stack trace."""
        lines = stack_trace.strip().split('\n')
        
        # Last line usually contains the error
        for line in reversed(lines):
            line = line.strip()
            if ':' in line and any(error_type in line for error_type in self.error_patterns.keys()):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    error_type = parts[0].strip()
                    error_message = parts[1].strip()
                    return error_type, error_message
        
        # Fallback
        return "UnknownError", stack_trace.split('\n')[-1] if stack_trace else "Unknown error"
    
    def _extract_error_locations(self, stack_trace: str) -> List[ErrorLocation]:
        """Extract file locations from stack trace."""
        locations = []
        lines = stack_trace.split('\n')
        
        # Pattern for Python stack trace lines
        file_pattern = r'File "([^"]+)", line (\d+)(?:, in (\w+))?'
        code_pattern = r'^\s+(.+)$'
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            match = re.search(file_pattern, line)
            
            if match:
                file_path = match.group(1)
                line_number = int(match.group(2))
                function_name = match.group(3)
                
                # Next line might contain the actual code
                code_line = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    code_match = re.match(code_pattern, next_line)
                    if code_match:
                        code_line = code_match.group(1)
                
                location = ErrorLocation(
                    file_path=file_path,
                    line_number=line_number,
                    function_name=function_name,
                    code_line=code_line,
                    error_type="stack_trace",
                    confidence=0.8
                )
                locations.append(location)
            
            i += 1
        
        return locations
    
    def _identify_primary_location(self, locations: List[ErrorLocation], 
                                 available_files: List[str] = None) -> Optional[ErrorLocation]:
        """Identify the primary error location."""
        if not locations:
            return None
        
        # If we have available files, prefer locations in those files
        if available_files:
            for location in reversed(locations):  # Start from the end (actual error)
                if location.file_path in available_files:
                    return location
        
        # Return the last location (where error actually occurred)
        return locations[-1] if locations else None
    
    def _analyze_error_pattern(self, error_type: str, error_message: str) -> str:
        """Analyze the error pattern to determine root cause."""
        if error_type in self.error_patterns:
            pattern_info = self.error_patterns[error_type]
            
            for pattern in pattern_info['patterns']:
                if re.search(pattern, error_message):
                    causes = pattern_info['common_causes']
                    return f"Most likely: {causes[0]}" if causes else "Pattern-based analysis"
        
        # Generic analysis based on error type
        generic_analysis = {
            'AttributeError': 'Object missing expected attribute or method',
            'NameError': 'Variable or name not defined in current scope',
            'TypeError': 'Type mismatch or incorrect function call',
            'ImportError': 'Module import failure',
            'SyntaxError': 'Code syntax violation',
            'IndentationError': 'Incorrect code indentation'
        }
        
        return generic_analysis.get(error_type, 'Unknown error pattern')
    
    def _get_fix_suggestions(self, error_type: str, error_message: str) -> List[str]:
        """Get specific fix suggestions based on error analysis."""
        suggestions = []
        
        if error_type in self.error_patterns:
            pattern_info = self.error_patterns[error_type]
            suggestions.extend(pattern_info.get('fix_strategies', []))
        
        # Add specific suggestions based on error message analysis
        if 'has no attribute' in error_message:
            suggestions.append("Check for typos in attribute/method names")
            suggestions.append("Verify object type matches expected interface")
        
        if 'is not defined' in error_message:
            suggestions.append("Check if variable is defined before use")
            suggestions.append("Verify imports and module paths")
        
        if 'positional argument' in error_message:
            suggestions.append("Check function call arguments")
            suggestions.append("Review function signature")
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def _suggest_relevant_files(self, locations: List[ErrorLocation], 
                              available_files: List[str] = None) -> List[str]:
        """Suggest files that should be examined."""
        suggested = []
        
        # Add files from error locations
        for location in locations:
            if available_files is None or location.file_path in available_files:
                suggested.append(location.file_path)
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for file_path in suggested:
            if file_path not in seen:
                seen.add(file_path)
                result.append(file_path)
        
        return result
    
    def _calculate_confidence(self, error_type: str, locations: List[ErrorLocation], 
                            primary_location: Optional[ErrorLocation]) -> float:
        """Calculate confidence in the error analysis."""
        confidence = 0.5  # Base confidence
        
        # Higher confidence for known error types
        if error_type in self.error_patterns:
            confidence += 0.2
        
        # Higher confidence if we have clear locations
        if locations:
            confidence += 0.2
            
        # Higher confidence if primary location is identified
        if primary_location:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _create_fallback_analysis(self, stack_trace: str) -> ErrorAnalysis:
        """Create fallback analysis when parsing fails."""
        return ErrorAnalysis(
            error_type="UnknownError",
            error_message=stack_trace[:200] + "..." if len(stack_trace) > 200 else stack_trace,
            root_cause="Unable to parse error details",
            primary_location=None,
            related_locations=[],
            suggested_files=[],
            analysis_confidence=0.1,
            fix_suggestions=["Review error message manually", "Check recent changes"]
        )
    
    def analyze_test_failure(self, test_output: str, test_name: str = "") -> ErrorAnalysis:
        """Analyze test failure output."""
        logger.info(f"🧪 Analyzing test failure: {test_name}")
        
        # Extract assertion failures, test errors, etc.
        if "AssertionError" in test_output:
            return self._analyze_assertion_error(test_output, test_name)
        else:
            return self.analyze_stack_trace(test_output)
    
    def _analyze_assertion_error(self, test_output: str, test_name: str) -> ErrorAnalysis:
        """Analyze assertion error in test."""
        # Extract expected vs actual values
        expected_pattern = r"assert (.+) == (.+)"
        match = re.search(expected_pattern, test_output)
        
        if match:
            actual_value = match.group(1).strip()
            expected_value = match.group(2).strip()
            
            return ErrorAnalysis(
                error_type="AssertionError",
                error_message=f"Expected {expected_value}, got {actual_value}",
                root_cause="Test assertion failed - value mismatch",
                primary_location=None,
                related_locations=[],
                suggested_files=[],
                analysis_confidence=0.7,
                fix_suggestions=[
                    f"Review logic producing {actual_value}",
                    f"Check if expected value {expected_value} is correct",
                    "Debug test setup and data"
                ]
            )
        
        return self.analyze_stack_trace(test_output)
    
    def analyze_log_error(self, log_entry: str, context_lines: List[str] = None) -> ErrorAnalysis:
        """Analyze error from log entries."""
        logger.info("📋 Analyzing log error entry")
        
        # Extract timestamp, level, message
        log_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(ERROR|CRITICAL|FATAL).*?(.+)"
        match = re.search(log_pattern, log_entry)
        
        if match:
            timestamp = match.group(1)
            level = match.group(2)
            message = match.group(3)
            
            # Check if log contains stack trace
            if "Traceback" in log_entry:
                return self.analyze_stack_trace(log_entry)
            
            return ErrorAnalysis(
                error_type="LogError",
                error_message=message,
                root_cause=f"Application error logged at {timestamp}",
                primary_location=None,
                related_locations=[],
                suggested_files=[],
                analysis_confidence=0.6,
                fix_suggestions=[
                    "Review application logic around error time",
                    "Check for recent changes",
                    "Review related log entries"
                ]
            )
        
        return self._create_fallback_analysis(log_entry)
    
    def get_error_context(self, file_path: str, line_number: int, context_lines: int = 5) -> Dict[str, Any]:
        """Get context around an error location (would need file access)."""
        # This would be implemented with actual file reading
        return {
            'file_path': file_path,
            'error_line': line_number,
            'context_start': max(1, line_number - context_lines),
            'context_end': line_number + context_lines,
            'needs_file_access': True
        }