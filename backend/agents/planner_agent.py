
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType
from services.openai_client import OpenAIClient
from typing import Dict, Any, Optional
import json
import re

class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.PLANNER)
        self.openai_client = OpenAIClient()
    
    async def process(self, ticket: Ticket, execution_id: int, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze ticket and create execution plan with repository context"""
        self.log_execution(execution_id, "Analyzing ticket content and error traces with repository context")
        
        # Extract repository context
        error_trace_files = context.get("error_trace_files", []) if context else []
        discovered_files = context.get("discovered_files", []) if context else []
        
        self.log_execution(execution_id, f"Processing with {len(discovered_files)} discovered repository files")
        
        # Create enhanced analysis prompt with actual code context
        analysis_prompt = self._create_analysis_prompt(ticket, error_trace_files, discovered_files)
        
        self.log_execution(execution_id, f"Sending analysis request to GPT-4 with {len(error_trace_files)} source files")
        analysis_result = await self.openai_client.complete_chat([
            {"role": "system", "content": "You are an expert software engineer analyzing bug reports with access to actual source code. Provide structured analysis in JSON format."},
            {"role": "user", "content": analysis_prompt}
        ])
        
        try:
            parsed_result = json.loads(analysis_result)
            
            # Validate that we identified actual files from the discovered repository files
            likely_files = parsed_result.get("likely_files", [])
            if not likely_files:
                self.log_execution(execution_id, "No target files identified - using intelligent fallback analysis")
                return self._intelligent_fallback_analysis(ticket, discovered_files)
            
            # Validate that suggested files exist in the discovered repository
            validated_files = self._validate_files_against_repository(likely_files, discovered_files)
            if not validated_files:
                self.log_execution(execution_id, "No valid files found in repository - using intelligent fallback")
                return self._intelligent_fallback_analysis(ticket, discovered_files)
            
            # Update the result with validated files
            parsed_result["likely_files"] = validated_files
            
            self.log_execution(execution_id, f"Analysis completed: {len(validated_files)} validated files identified")
            return parsed_result
        except json.JSONDecodeError:
            self.log_execution(execution_id, "Failed to parse GPT-4 response as JSON, using intelligent fallback analysis")
            return self._intelligent_fallback_analysis(ticket, discovered_files)
    
    def _create_analysis_prompt(self, ticket: Ticket, error_trace_files: list, discovered_files: list) -> str:
        prompt = f"""
Analyze this bug report with access to the actual source code:

TITLE: {ticket.title}
DESCRIPTION: {ticket.description}
ERROR TRACE: {ticket.error_trace}

DISCOVERED REPOSITORY FILES:
"""
        
        # Include discovered files summary for context
        if discovered_files:
            prompt += f"Repository contains {len(discovered_files)} files including:\n"
            for file_info in discovered_files[:20]:  # Show first 20 files
                file_path = file_info.get("path", "") if isinstance(file_info, dict) else str(file_info)
                prompt += f"- {file_path}\n"
        
        prompt += "\nSOURCE CODE FILES FROM ERROR TRACE:\n"
        
        for file_info in error_trace_files:
            prompt += f"""
FILE: {file_info['path']}
CONTENT:
```
{file_info['content'][:2000]}...
```
"""
        
        prompt += """
Please provide your analysis in the following JSON format:
{
    "root_cause": "Brief description of the likely root cause based on actual code analysis",
    "error_type": "Type of error (syntax, logic, runtime, etc.)",
    "likely_files": [
        {
            "path": "actual/file/path.py",
            "confidence": 0.9,
            "reason": "Specific reason why this file needs to be modified (reference actual code lines)"
        }
    ],
    "affected_functions": ["function1", "function2"],
    "complexity_estimate": "low|medium|high",
    "suggested_approach": "Specific approach to fix this issue based on code analysis",
    "required_tests": ["test_function1", "test_integration"],
    "code_analysis": "Detailed analysis of the problematic code sections"
}

IMPORTANT: Only suggest files that exist in the discovered repository files list above.
Focus on actual code issues you can see in the provided source files.
"""
        return prompt
    
    def _validate_files_against_repository(self, likely_files: list, discovered_files: list) -> list:
        """Validate that suggested files exist in the discovered repository"""
        if not discovered_files:
            return likely_files  # If no discovered files, return as-is
        
        # Create a set of discovered file paths for quick lookup
        discovered_paths = set()
        for file_info in discovered_files:
            if isinstance(file_info, dict):
                discovered_paths.add(file_info.get("path", ""))
            else:
                discovered_paths.add(str(file_info))
        
        validated_files = []
        for file_info in likely_files:
            if isinstance(file_info, dict):
                file_path = file_info.get("path", "")
            else:
                file_path = str(file_info)
                file_info = {"path": file_path, "confidence": 0.7, "reason": "From planner analysis"}
            
            if file_path in discovered_paths:
                validated_files.append(file_info)
            else:
                # Try to find similar files in the repository
                similar_file = self._find_similar_file(file_path, discovered_paths)
                if similar_file:
                    validated_files.append({
                        "path": similar_file,
                        "confidence": file_info.get("confidence", 0.5) * 0.8,  # Reduce confidence for substitution
                        "reason": f"Similar to suggested {file_path}: {file_info.get('reason', '')}"
                    })
        
        return validated_files
    
    def _find_similar_file(self, target_path: str, discovered_paths: set) -> Optional[str]:
        """Find a similar file in the discovered paths"""
        target_name = target_path.split('/')[-1]  # Get filename
        target_name_no_ext = target_name.split('.')[0]  # Remove extension
        
        # Look for exact filename matches
        for path in discovered_paths:
            if path.endswith(target_name):
                return path
        
        # Look for filename without extension matches
        for path in discovered_paths:
            if target_name_no_ext in path:
                return path
        
        return None
    
    def _intelligent_fallback_analysis(self, ticket: Ticket, discovered_files: list) -> Dict[str, Any]:
        """Enhanced fallback analysis using discovered repository files"""
        files = []
        
        if ticket.error_trace and discovered_files:
            # Extract file patterns from error trace
            file_matches = re.findall(r'File "([^"]+)"', ticket.error_trace)
            
            # Create a set of discovered file paths for quick lookup
            discovered_paths = set()
            for file_info in discovered_files:
                if isinstance(file_info, dict):
                    discovered_paths.add(file_info.get("path", ""))
                else:
                    discovered_paths.add(str(file_info))
            
            # Try to match error trace files with discovered files
            for file_match in file_matches[:3]:
                if file_match in discovered_paths:
                    files.append({"path": file_match, "confidence": 0.8, "reason": "Found in error trace and repository"})
                else:
                    # Try to find similar files
                    similar_file = self._find_similar_file(file_match, discovered_paths)
                    if similar_file:
                        files.append({"path": similar_file, "confidence": 0.6, "reason": f"Similar to error trace file {file_match}"})
        
        # If no files from error trace, use some of the discovered files intelligently
        if not files and discovered_files:
            # Prioritize Python files, main files, or files with common patterns
            priority_patterns = ["main", "app", "server", "index", "__init__"]
            
            for pattern in priority_patterns:
                for file_info in discovered_files[:10]:  # Limit search
                    file_path = file_info.get("path", "") if isinstance(file_info, dict) else str(file_info)
                    if pattern in file_path.lower() and file_path.endswith(('.py', '.js', '.ts')):
                        files.append({
                            "path": file_path, 
                            "confidence": 0.4, 
                            "reason": f"Common application file pattern: {pattern}"
                        })
                        break
                if files:  # Found at least one file
                    break
            
            # If still no files, use the first few discovered files as last resort
            if not files:
                for file_info in discovered_files[:2]:
                    file_path = file_info.get("path", "") if isinstance(file_info, dict) else str(file_info)
                    if file_path.endswith(('.py', '.js', '.ts')):
                        files.append({
                            "path": file_path,
                            "confidence": 0.3,
                            "reason": "Repository file (fallback selection)"
                        })
        
        # Final fallback if absolutely no files can be identified
        if not files:
            files = [{"path": "unknown_file", "confidence": 0.1, "reason": "No valid files identified in repository"}]
        
        return {
            "root_cause": "Unable to determine with high confidence - requires manual code review",
            "error_type": "unknown",
            "likely_files": files,
            "affected_functions": [],
            "complexity_estimate": "medium",
            "suggested_approach": "Manual investigation required - check discovered repository files",
            "required_tests": [],
            "code_analysis": f"Intelligent analysis of {len(discovered_files)} discovered repository files"
        }

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate planner context"""
        return "ticket" in context

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate planner results"""
        required_fields = ["root_cause", "likely_files"]
        return all(field in result for field in required_fields) and len(result.get("likely_files", [])) > 0

