
from agents.base_agent import BaseAgent
from core.models import Ticket, AgentExecution, AgentType, PatchAttempt
from core.database import get_sync_db
from services.openai_client import OpenAIClient
from typing import Dict, Any
import json

class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.DEVELOPER)
        self.openai_client = OpenAIClient()
    
    async def process(self, ticket: Ticket, execution_id: int) -> Dict[str, Any]:
        """Generate code patches for the ticket"""
        self.log_execution(execution_id, "Starting code generation process")
        
        # Get planner analysis from previous execution
        planner_data = self._get_planner_analysis(ticket)
        
        # Generate patch for each likely file
        patches = []
        for file_info in planner_data.get("likely_files", []):
            self.log_execution(execution_id, f"Generating patch for {file_info['path']}")
            
            patch_data = await self._generate_patch(ticket, file_info, planner_data)
            if patch_data:
                patches.append(patch_data)
                self._save_patch_attempt(ticket, execution_id, patch_data)
        
        result = {
            "patches_generated": len(patches),
            "patches": patches,
            "planner_analysis": planner_data
        }
        
        self.log_execution(execution_id, f"Generated {len(patches)} patches")
        return result
    
    def _get_planner_analysis(self, ticket: Ticket) -> Dict[str, Any]:
        """Get analysis from planner agent"""
        with next(get_sync_db()) as db:
            planner_execution = db.query(AgentExecution).filter(
                AgentExecution.ticket_id == ticket.id,
                AgentExecution.agent_type == "planner",
                AgentExecution.status == "completed"
            ).first()
            
            return planner_execution.output_data if planner_execution else {}
    
    async def _generate_patch(self, ticket: Ticket, file_info: Dict, analysis: Dict) -> Dict[str, Any]:
        """Generate a patch for a specific file"""
        patch_prompt = f"""
You are an expert software engineer. Generate a minimal code patch to fix this bug:

BUG REPORT:
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace}

TARGET FILE: {file_info['path']}
ROOT CAUSE: {analysis.get('root_cause', 'Unknown')}
SUGGESTED APPROACH: {analysis.get('suggested_approach', 'Standard debugging approach')}

Please provide your solution in JSON format:
{{
    "patch_content": "unified diff format patch",
    "patched_code": "complete file content after patch",
    "test_code": "unit tests for the fix",
    "commit_message": "descriptive commit message",
    "confidence_score": 0.85,
    "explanation": "brief explanation of the fix"
}}
"""
        
        try:
            response = await self.openai_client.complete_chat([
                {"role": "system", "content": "You are an expert software engineer. Provide fixes in the exact JSON format requested."},
                {"role": "user", "content": patch_prompt}
            ])
            
            patch_data = json.loads(response)
            patch_data["target_file"] = file_info["path"]
            return patch_data
            
        except (json.JSONDecodeError, Exception) as e:
            return None
    
    def _save_patch_attempt(self, ticket: Ticket, execution_id: int, patch_data: Dict):
        """Save patch attempt to database"""
        with next(get_sync_db()) as db:
            patch = PatchAttempt(
                ticket_id=ticket.id,
                execution_id=execution_id,
                patch_content=patch_data.get("patch_content", ""),
                patched_code=patch_data.get("patched_code", ""),
                test_code=patch_data.get("test_code", ""),
                commit_message=patch_data.get("commit_message", ""),
                confidence_score=patch_data.get("confidence_score", 0.5)
            )
            db.add(patch)
            db.commit()
