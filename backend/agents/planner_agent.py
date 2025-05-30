
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType
from services.openai_client import OpenAIClient
from typing import Dict, Any
import json
import re

class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.PLANNER)
        self.openai_client = OpenAIClient()
    
    async def process(self, ticket: Ticket, execution_id: int) -> Dict[str, Any]:
        """Analyze ticket and create execution plan"""
        self.log_execution(execution_id, "Analyzing ticket content and error traces")
        
        # Extract key information from ticket
        analysis_prompt = self._create_analysis_prompt(ticket)
        
        self.log_execution(execution_id, "Sending analysis request to GPT-4")
        analysis_result = await self.openai_client.complete_chat([
            {"role": "system", "content": "You are an expert software engineer analyzing bug reports. Provide structured analysis in JSON format."},
            {"role": "user", "content": analysis_prompt}
        ])
        
        try:
            parsed_result = json.loads(analysis_result)
            self.log_execution(execution_id, f"Analysis completed: {len(parsed_result.get('likely_files', []))} files identified")
            return parsed_result
        except json.JSONDecodeError:
            self.log_execution(execution_id, "Failed to parse GPT-4 response as JSON, using fallback analysis")
            return self._fallback_analysis(ticket)
    
    def _create_analysis_prompt(self, ticket: Ticket) -> str:
        return f"""
Analyze this bug report and provide a structured analysis:

TITLE: {ticket.title}
DESCRIPTION: {ticket.description}
ERROR TRACE: {ticket.error_trace}

Please provide your analysis in the following JSON format:
{{
    "root_cause": "Brief description of the likely root cause",
    "error_type": "Type of error (syntax, logic, runtime, etc.)",
    "likely_files": [
        {{
            "path": "predicted/file/path.py",
            "confidence": 0.8,
            "reason": "Why this file is likely involved"
        }}
    ],
    "affected_functions": ["function1", "function2"],
    "complexity_estimate": "low|medium|high",
    "suggested_approach": "How to approach fixing this issue",
    "required_tests": ["test_function1", "test_integration"]
}}
"""
    
    def _fallback_analysis(self, ticket: Ticket) -> Dict[str, Any]:
        """Fallback analysis when GPT-4 fails"""
        # Simple regex-based file extraction
        files = []
        if ticket.error_trace:
            file_matches = re.findall(r'File "([^"]+)"', ticket.error_trace)
            files = [{"path": f, "confidence": 0.5, "reason": "Found in error trace"} for f in file_matches]
        
        return {
            "root_cause": "Unable to determine with high confidence",
            "error_type": "unknown",
            "likely_files": files,
            "affected_functions": [],
            "complexity_estimate": "medium",
            "suggested_approach": "Manual investigation required",
            "required_tests": []
        }
