
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
        """Analyze ticket and create execution plan with semantic search integration"""
        self.log_execution(execution_id, "Analyzing ticket with semantic search and repository context")
        
        # Extract repository context
        error_trace_files = context.get("error_trace_files", []) if context else []
        discovered_files = context.get("discovered_files", []) if context else []
        
        self.log_execution(execution_id, f"Processing with {len(discovered_files)} discovered repository files")
        
        # Initialize semantic search for enhanced analysis
        semantic_analysis = await self._perform_semantic_analysis(ticket, discovered_files)
        
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
        
        # If no files from error trace, use repository-aware intelligent selection
        if not files and discovered_files:
            # Prioritize based on actual file analysis instead of hardcoded patterns
            code_files = []
            config_files = []
            
            for file_info in discovered_files:
                file_path = file_info.get("path", "") if isinstance(file_info, dict) else str(file_info)
                file_path_lower = file_path.lower()
                
                # Categorize actual files by type and importance
                if file_path_lower.endswith(('.py', '.js', '.ts', '.tsx', '.jsx')):
                    # Check for common application patterns in actual files
                    if any(pattern in file_path_lower for pattern in ['main', 'app', 'server', 'index', '__init__']):
                        code_files.insert(0, file_info)  # High priority
                    else:
                        code_files.append(file_info)
                elif file_path_lower.endswith(('.json', '.yaml', '.yml', '.env')):
                    config_files.append(file_info)
            
            # Select most relevant files based on actual repository content
            selected_files = code_files[:2] + config_files[:1]  # Top 2 code + 1 config
            
            for file_info in selected_files:
                file_path = file_info.get("path", "") if isinstance(file_info, dict) else str(file_info)
                files.append({
                    "path": file_path,
                    "confidence": 0.4,
                    "reason": "Repository analysis - relevant file type"
                })
        
        # Use first available file from repository if nothing else works
        if not files and discovered_files:
            first_file = discovered_files[0]
            file_path = first_file.get("path", "") if isinstance(first_file, dict) else str(first_file)
            files = [{
                "path": file_path,
                "confidence": 0.2,
                "reason": "First available file in repository"
            }]
        
        # Only use unknown_file if absolutely no repository files exist
        if not files:
            files = [{"path": "unknown_file", "confidence": 0.1, "reason": "No repository files discovered"}]
        
        return {
            "root_cause": "Unable to determine with high confidence - requires manual code review",
            "error_type": "unknown",
            "likely_files": files,
            "affected_functions": [],
            "complexity_estimate": "medium",
            "suggested_approach": "Repository-aware investigation - check actual discovered files",
            "required_tests": [],
            "code_analysis": f"Repository-aware analysis of {len(discovered_files)} discovered files"
        }
    
    async def _perform_semantic_analysis(self, ticket: Ticket, discovered_files: list) -> Dict[str, Any]:
        """Perform semantic analysis to find related code for error resolution."""
        try:
            from services.semantic_search_engine import SemanticSearchEngine
            from services.symbol_resolver import SymbolResolver
            
            # Initialize semantic tools
            semantic_engine = SemanticSearchEngine()
            symbol_resolver = SymbolResolver()
            
            # Build semantic index from discovered files
            await semantic_engine.build_semantic_index(discovered_files)
            symbol_resolver.build_symbol_table(discovered_files)
            
            # Find code related to error
            related_chunks = []
            if ticket.error_trace:
                related_chunks = await semantic_engine.find_related_to_error(
                    ticket.description, ticket.error_trace
                )
            
            # Extract function names from error and find definitions
            symbol_definitions = []
            if ticket.error_trace:
                import re
                function_matches = re.findall(r'in (\w+)', ticket.error_trace)
                for func_name in function_matches[:3]:
                    definition = symbol_resolver.go_to_definition("", 0, func_name)
                    if definition:
                        symbol_definitions.append(definition)
            
            return {
                "related_chunks": related_chunks,
                "symbol_definitions": symbol_definitions,
                "semantic_search_enabled": True
            }
            
        except Exception as e:
            logger.error(f"❌ Semantic analysis failed: {e}")
            return {"semantic_search_enabled": False, "error": str(e)}

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate planner context"""
        return "ticket" in context

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate planner results"""
        required_fields = ["root_cause", "likely_files"]
        return all(field in result for field in required_fields) and len(result.get("likely_files", [])) > 0

