
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
        
        # Create enhanced analysis prompt with actual code context
        analysis_prompt = self._create_analysis_prompt(ticket, error_trace_files)
        
        self.log_execution(execution_id, f"Sending analysis request to GPT-4 with {len(error_trace_files)} source files")
        analysis_result = await self.openai_client.complete_chat([
            {"role": "system", "content": "You are an expert software engineer analyzing bug reports with access to actual source code. Provide structured analysis in JSON format."},
            {"role": "user", "content": analysis_prompt}
        ])
        
        try:
            parsed_result = json.loads(analysis_result)
            
            # Validate that we identified actual files
            likely_files = parsed_result.get("likely_files", [])
            if not likely_files:
                self.log_execution(execution_id, "No target files identified - using fallback analysis")
                return self._fallback_analysis(ticket)
            
            self.log_execution(execution_id, f"Analysis completed: {len(likely_files)} files identified")
            return parsed_result
        except json.JSONDecodeError:
            self.log_execution(execution_id, "Failed to parse GPT-4 response as JSON, using fallback analysis")
            return self._fallback_analysis(ticket)
    
    def _create_analysis_prompt(self, ticket: Ticket, error_trace_files: list) -> str:
        prompt = f"""
Analyze this bug report with access to the actual source code:

TITLE: {ticket.title}
DESCRIPTION: {ticket.description}
ERROR TRACE: {ticket.error_trace}

SOURCE CODE FILES FROM ERROR TRACE:
"""
        
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

Focus on actual code issues you can see in the provided source files.
"""
        return prompt
    
    def _fallback_analysis(self, ticket: Ticket) -> Dict[str, Any]:
        """Enhanced fallback analysis when GPT-4 fails"""
        files = []
        if ticket.error_trace:
            file_matches = re.findall(r'File "([^"]+)"', ticket.error_trace)
            files = [{"path": f, "confidence": 0.6, "reason": "Found in error trace"} for f in file_matches[:3]]
        
        if not files:
            # If no files in error trace, make some educated guesses
            common_files = ["main.py", "app.py", "index.py", "server.py"]
            files = [{"path": f, "confidence": 0.3, "reason": "Common application file"} for f in common_files[:1]]
        
        return {
            "root_cause": "Unable to determine with high confidence - requires manual code review",
            "error_type": "unknown",
            "likely_files": files,
            "affected_functions": [],
            "complexity_estimate": "medium",
            "suggested_approach": "Manual investigation required - check error trace files",
            "required_tests": [],
            "code_analysis": "Insufficient context for detailed code analysis"
        }

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate planner context"""
        return "ticket" in context

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate planner results"""
        required_fields = ["root_cause", "likely_files"]
        return all(field in result for field in required_fields) and len(result.get("likely_files", [])) > 0
