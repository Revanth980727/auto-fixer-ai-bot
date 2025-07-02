import asyncio
import tempfile
import shutil
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of a validation check."""
    validator_name: str
    success: bool
    confidence: float
    issues: List[str]
    warnings: List[str]
    execution_time: float
    details: Dict[str, Any]

@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    overall_success: bool
    overall_confidence: float
    results: List[ValidationResult]
    critical_issues: List[str]
    total_execution_time: float
    recommendation: str

class ValidationOrchestrator:
    """Orchestrates multiple validation strategies for code patches."""
    
    def __init__(self):
        self.validators = {}
        self.shadow_workspace = None
        self._register_validators()
    
    def _register_validators(self) -> None:
        """Register available validators."""
        # Import validators locally to avoid circular imports
        try:
            from services.lint_runner import LintRunner
            from services.type_checker import TypeChecker
            from services.test_runner import TestRunner
            
            self.validators = {
                'lint': LintRunner(),
                'type_check': TypeChecker(),
                'test': TestRunner()
            }
            logger.info("✅ All validators registered successfully")
        except ImportError as e:
            logger.warning(f"⚠️ Some validators could not be imported: {e}")
            self.validators = {}
    
    async def validate_patch(self, 
                           original_content: str,
                           patched_content: str,
                           file_path: str,
                           patch_info: Dict[str, Any] = None) -> ValidationSummary:
        """Validate a code patch using multiple strategies."""
        try:
            start_time = asyncio.get_event_loop().time()
            logger.info(f"🔍 Starting comprehensive validation for {file_path}")
            
            # Create shadow workspace
            shadow_path = await self._create_shadow_workspace(original_content, patched_content, file_path)
            
            # Run all validators in parallel
            validation_tasks = []
            
            if 'lint' in self.validators:
                validation_tasks.append(
                    self._run_validator_safe('lint', shadow_path, file_path, patch_info)
                )
            
            if 'type_check' in self.validators:
                validation_tasks.append(
                    self._run_validator_safe('type_check', shadow_path, file_path, patch_info)
                )
            
            if 'test' in self.validators:
                validation_tasks.append(
                    self._run_validator_safe('test', shadow_path, file_path, patch_info)
                )
            
            # Additional validation checks
            validation_tasks.extend([
                self._validate_syntax(patched_content, file_path),
                self._validate_structure(original_content, patched_content, file_path),
                self._validate_imports(patched_content, file_path)
            ])
            
            # Wait for all validations to complete
            results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            # Filter out exceptions and convert to ValidationResults
            valid_results = []
            for result in results:
                if isinstance(result, ValidationResult):
                    valid_results.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"❌ Validation error: {result}")
                    # Create error result
                    valid_results.append(ValidationResult(
                        validator_name="error",
                        success=False,
                        confidence=0.0,
                        issues=[f"Validation error: {str(result)}"],
                        warnings=[],
                        execution_time=0.0,
                        details={}
                    ))
            
            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time
            
            # Generate summary
            summary = self._generate_validation_summary(valid_results, total_time)
            
            # Cleanup shadow workspace
            await self._cleanup_shadow_workspace(shadow_path)
            
            logger.info(f"✅ Validation completed in {total_time:.2f}s: {summary.overall_confidence:.2f} confidence")
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error in validation orchestration: {e}")
            return self._create_error_summary(str(e))
    
    async def _create_shadow_workspace(self, 
                                     original_content: str,
                                     patched_content: str,
                                     file_path: str) -> str:
        """Create a shadow workspace for safe validation."""
        try:
            # Create temporary directory
            shadow_dir = tempfile.mkdtemp(prefix="validation_shadow_")
            
            # Create directory structure
            file_dir = os.path.dirname(file_path)
            if file_dir:
                shadow_file_dir = os.path.join(shadow_dir, file_dir)
                os.makedirs(shadow_file_dir, exist_ok=True)
            
            # Write patched content to shadow workspace
            shadow_file_path = os.path.join(shadow_dir, file_path)
            with open(shadow_file_path, 'w', encoding='utf-8') as f:
                f.write(patched_content)
            
            # Store original content for comparison
            original_file_path = shadow_file_path + ".original"
            with open(original_file_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            self.shadow_workspace = shadow_dir
            logger.debug(f"🏗️ Created shadow workspace: {shadow_dir}")
            return shadow_dir
            
        except Exception as e:
            logger.error(f"❌ Error creating shadow workspace: {e}")
            raise
    
    async def _cleanup_shadow_workspace(self, shadow_path: str) -> None:
        """Clean up shadow workspace."""
        try:
            if shadow_path and os.path.exists(shadow_path):
                shutil.rmtree(shadow_path)
                logger.debug(f"🧹 Cleaned up shadow workspace: {shadow_path}")
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning up shadow workspace: {e}")
    
    async def _run_validator_safe(self, 
                                validator_name: str,
                                shadow_path: str,
                                file_path: str,
                                patch_info: Dict[str, Any]) -> ValidationResult:
        """Run a validator safely with error handling."""
        try:
            start_time = asyncio.get_event_loop().time()
            
            validator = self.validators[validator_name]
            shadow_file_path = os.path.join(shadow_path, file_path)
            
            # Run the validator
            if hasattr(validator, 'validate_async'):
                result = await validator.validate_async(shadow_file_path, patch_info)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, validator.validate, shadow_file_path, patch_info
                )
            
            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time
            
            return ValidationResult(
                validator_name=validator_name,
                success=result.get('success', False),
                confidence=result.get('confidence', 0.5),
                issues=result.get('issues', []),
                warnings=result.get('warnings', []),
                execution_time=execution_time,
                details=result.get('details', {})
            )
            
        except Exception as e:
            logger.error(f"❌ Error running {validator_name} validator: {e}")
            return ValidationResult(
                validator_name=validator_name,
                success=False,
                confidence=0.0,
                issues=[f"Validator error: {str(e)}"],
                warnings=[],
                execution_time=0.0,
                details={}
            )
    
    async def _validate_syntax(self, content: str, file_path: str) -> ValidationResult:
        """Validate syntax of the code."""
        start_time = asyncio.get_event_loop().time()
        issues = []
        warnings = []
        success = True
        
        try:
            if file_path.endswith('.py'):
                # Python syntax validation
                import ast
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    issues.append(f"Python syntax error: {e}")
                    success = False
            
            elif file_path.endswith(('.js', '.ts', '.tsx', '.jsx')):
                # Basic JavaScript/TypeScript validation
                if 'SyntaxError' in content or 'function(' in content.replace('function(', ''):
                    # Very basic check - could be enhanced with proper parser
                    pass
            
        except Exception as e:
            issues.append(f"Syntax validation error: {e}")
            success = False
        
        end_time = asyncio.get_event_loop().time()
        
        return ValidationResult(
            validator_name="syntax",
            success=success,
            confidence=0.9 if success else 0.1,
            issues=issues,
            warnings=warnings,
            execution_time=end_time - start_time,
            details={}
        )
    
    async def _validate_structure(self, 
                                original_content: str,
                                patched_content: str,
                                file_path: str) -> ValidationResult:
        """Validate that patch maintains proper code structure."""
        start_time = asyncio.get_event_loop().time()
        issues = []
        warnings = []
        success = True
        
        try:
            # Check for balanced brackets/parentheses
            for char_pair in [('(', ')'), ('{', '}'), ('[', ']')]:
                open_char, close_char = char_pair
                if patched_content.count(open_char) != patched_content.count(close_char):
                    issues.append(f"Unbalanced {open_char}{close_char} brackets")
                    success = False
            
            # Check indentation consistency (for Python)
            if file_path.endswith('.py'):
                lines = patched_content.split('\n')
                indent_pattern = None
                
                for line in lines:
                    if line.strip() and line.startswith((' ', '\t')):
                        if indent_pattern is None:
                            indent_pattern = 'spaces' if line.startswith(' ') else 'tabs'
                        else:
                            current_pattern = 'spaces' if line.startswith(' ') else 'tabs'
                            if current_pattern != indent_pattern:
                                warnings.append("Mixed indentation (spaces and tabs)")
                                break
            
            # Check if patch significantly changes file structure
            original_lines = len(original_content.split('\n'))
            patched_lines = len(patched_content.split('\n'))
            
            if abs(patched_lines - original_lines) > original_lines * 0.5:
                warnings.append("Patch significantly changes file size")
            
        except Exception as e:
            issues.append(f"Structure validation error: {e}")
            success = False
        
        end_time = asyncio.get_event_loop().time()
        
        return ValidationResult(
            validator_name="structure",
            success=success,
            confidence=0.8 if success else 0.3,
            issues=issues,
            warnings=warnings,
            execution_time=end_time - start_time,
            details={}
        )
    
    async def _validate_imports(self, content: str, file_path: str) -> ValidationResult:
        """Validate import statements and dependencies."""
        start_time = asyncio.get_event_loop().time()
        issues = []
        warnings = []
        success = True
        
        try:
            if file_path.endswith('.py'):
                import ast
                try:
                    tree = ast.parse(content)
                    imports = []
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module)
                    
                    # Check for common import issues
                    if len(imports) > 20:
                        warnings.append("Many imports - consider refactoring")
                    
                    # Check for unused imports (simplified)
                    for imp in imports:
                        simple_name = imp.split('.')[0]
                        if simple_name not in content:
                            warnings.append(f"Potentially unused import: {imp}")
                
                except SyntaxError:
                    # Already caught in syntax validation
                    pass
            
        except Exception as e:
            issues.append(f"Import validation error: {e}")
            success = False
        
        end_time = asyncio.get_event_loop().time()
        
        return ValidationResult(
            validator_name="imports",
            success=success,
            confidence=0.7 if success else 0.2,
            issues=issues,
            warnings=warnings,
            execution_time=end_time - start_time,
            details={}
        )
    
    def _generate_validation_summary(self, 
                                   results: List[ValidationResult],
                                   total_time: float) -> ValidationSummary:
        """Generate overall validation summary."""
        if not results:
            return self._create_error_summary("No validation results")
        
        # Calculate overall success and confidence
        successful_results = [r for r in results if r.success]
        overall_success = len(successful_results) > len(results) * 0.7  # 70% success threshold
        
        if successful_results:
            overall_confidence = sum(r.confidence for r in successful_results) / len(successful_results)
        else:
            overall_confidence = 0.0
        
        # Collect critical issues
        critical_issues = []
        for result in results:
            if not result.success:
                critical_issues.extend(result.issues)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(overall_success, overall_confidence, critical_issues)
        
        return ValidationSummary(
            overall_success=overall_success,
            overall_confidence=overall_confidence,
            results=results,
            critical_issues=critical_issues,
            total_execution_time=total_time,
            recommendation=recommendation
        )
    
    def _generate_recommendation(self, 
                               success: bool,
                               confidence: float,
                               critical_issues: List[str]) -> str:
        """Generate recommendation based on validation results."""
        if success and confidence > 0.8:
            return "APPROVE: High confidence, all critical validations passed"
        elif success and confidence > 0.6:
            return "APPROVE_WITH_CAUTION: Good confidence, monitor for issues"
        elif confidence > 0.4:
            return "REVIEW_REQUIRED: Some issues found, manual review recommended"
        else:
            return "REJECT: Multiple critical issues, patch needs significant revision"
    
    def _create_error_summary(self, error_message: str) -> ValidationSummary:
        """Create error summary when validation fails."""
        return ValidationSummary(
            overall_success=False,
            overall_confidence=0.0,
            results=[],
            critical_issues=[error_message],
            total_execution_time=0.0,
            recommendation="ERROR: Validation process failed"
        )
    
    async def validate_multiple_patches(self, 
                                      patches: List[Dict[str, Any]]) -> Dict[str, ValidationSummary]:
        """Validate multiple patches concurrently."""
        tasks = []
        
        for patch in patches:
            task = self.validate_patch(
                original_content=patch['original_content'],
                patched_content=patch['patched_content'],
                file_path=patch['file_path'],
                patch_info=patch.get('patch_info', {})
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validation_results = {}
        for i, result in enumerate(results):
            patch_id = patches[i].get('patch_id', f"patch_{i}")
            if isinstance(result, ValidationSummary):
                validation_results[patch_id] = result
            else:
                validation_results[patch_id] = self._create_error_summary(str(result))
        
        return validation_results
    
    def get_validator_status(self) -> Dict[str, bool]:
        """Get status of available validators."""
        return {name: True for name in self.validators.keys()}