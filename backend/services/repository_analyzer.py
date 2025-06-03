import asyncio
from typing import Dict, List, Any, Optional
from services.github_client import GitHubClient
from services.intelligent_file_selector import IntelligentFileSelector
from core.config import config
import logging

logger = logging.getLogger(__name__)

class RepositoryAnalyzer:
    def __init__(self):
        self.github_client = GitHubClient()
        self.file_selector = IntelligentFileSelector()
    
    async def analyze_repository(self) -> Dict[str, Any]:
        """General repository analysis for initial system setup"""
        logger.info("🔍 Starting general repository analysis")
        
        try:
            # Use intelligent file selection with generic parameters
            selected_files = await self.file_selector.select_relevant_files(
                ticket_title="General Repository Analysis",
                ticket_description="Initial system repository scan",
                error_trace=""
            )
            
            if not selected_files:
                logger.warning("⚠️ No files found during general repository analysis")
                return {
                    "source_files": [],
                    "analysis_summary": "No source files found in repository",
                    "github_access_failed": True,
                    "repository_structure": "Unknown",
                    "total_files_analyzed": 0
                }
            
            # Generate general analysis summary
            analysis_summary = self._generate_general_analysis_summary(selected_files)
            
            result = {
                "source_files": selected_files,
                "analysis_summary": analysis_summary,
                "total_files_analyzed": len(selected_files),
                "github_access_failed": False,
                "repository_structure": self._detect_repository_structure(selected_files),
                "file_types_found": self._analyze_file_types(selected_files),
                "target_branch": config.github_target_branch
            }
            
            logger.info(f"✅ General repository analysis completed: {len(selected_files)} files analyzed")
            return result
            
        except Exception as e:
            logger.error(f"❌ General repository analysis failed: {e}")
            # Always return a dictionary, even on error
            return {
                "source_files": [],
                "analysis_summary": f"Repository analysis failed: {str(e)}",
                "github_access_failed": True,
                "repository_structure": "Unknown",
                "total_files_analyzed": 0,
                "error": str(e)
            }
    
    async def analyze_repository_for_ticket(self, ticket_title: str, ticket_description: str, error_trace: str = "") -> Dict[str, Any]:
        """Analyze repository with intelligent file selection for a specific ticket"""
        logger.info(f"🔍 Starting intelligent repository analysis for: {ticket_title}")
        
        try:
            # Use intelligent file selection
            selected_files = await self.file_selector.select_relevant_files(
                ticket_title, ticket_description, error_trace
            )
            
            if not selected_files:
                logger.warning("⚠️ No relevant files found for analysis")
                return {
                    "source_files": [],
                    "analysis_summary": "No relevant source files found",
                    "github_access_failed": True,
                    "intelligent_selection": True
                }
            
            # Analyze the selected files
            analysis_summary = self._generate_analysis_summary(selected_files, ticket_title, error_trace)
            
            result = {
                "source_files": selected_files,
                "analysis_summary": analysis_summary,
                "total_files_analyzed": len(selected_files),
                "github_access_failed": False,
                "intelligent_selection": True,
                "selection_criteria": {
                    "max_files": config.max_source_files,
                    "target_branch": config.github_target_branch,
                    "has_error_trace": bool(error_trace)
                }
            }
            
            logger.info(f"✅ Repository analysis completed: {len(selected_files)} files analyzed")
            return result
            
        except Exception as e:
            logger.error(f"❌ Repository analysis failed: {e}")
            return {
                "source_files": [],
                "analysis_summary": f"Analysis failed: {str(e)}",
                "github_access_failed": True,
                "intelligent_selection": True,
                "error": str(e)
            }
    
    def _generate_general_analysis_summary(self, files: List[Dict]) -> str:
        """Generate a general repository analysis summary"""
        total_lines = sum(len(f['content'].splitlines()) for f in files)
        total_chars = sum(len(f['content']) for f in files)
        
        file_info = []
        for f in files:
            lines = len(f['content'].splitlines())
            score = f.get('relevance_score', 0)
            file_info.append(f"- {f['path']}: {lines} lines (score: {score:.1f})")
        
        summary = f"""
General Repository Analysis

Selected Files ({len(files)}):
{chr(10).join(file_info)}

Total Code: {total_lines} lines, {total_chars} characters
Target Branch: {config.github_target_branch}
Selection Method: Intelligent file selection

Repository Overview:
- Analysis includes {config.max_source_files} most relevant files
- Files selected based on common patterns and importance
- Ready for ticket-specific analysis and processing
"""
        
        return summary.strip()
    
    def _generate_analysis_summary(self, files: List[Dict], ticket_title: str, error_trace: str) -> str:
        """Generate a comprehensive analysis summary"""
        total_lines = sum(len(f['content'].splitlines()) for f in files)
        total_chars = sum(len(f['content']) for f in files)
        
        file_info = []
        for f in files:
            lines = len(f['content'].splitlines())
            score = f.get('relevance_score', 0)
            file_info.append(f"- {f['path']}: {lines} lines (relevance: {score:.1f})")
        
        summary = f"""
Repository Analysis Summary for: {ticket_title}

Selected Files ({len(files)}):
{chr(10).join(file_info)}

Total Code: {total_lines} lines, {total_chars} characters
Target Branch: {config.github_target_branch}
Selection Method: Intelligent error-based selection

Analysis Strategy:
- Prioritized files mentioned in error traces
- Focused on relevant file types and patterns
- Limited scope to {config.max_source_files} most relevant files
- Used keyword matching for enhanced relevance
"""
        
        if error_trace:
            summary += f"\nError Context: Available and used for file selection"
        
        return summary.strip()
    
    def _detect_repository_structure(self, files: List[Dict]) -> str:
        """Detect the general structure/type of repository"""
        file_paths = [f['path'] for f in files]
        
        # Check for common patterns
        if any('requirements.txt' in path or path.endswith('.py') for path in file_paths):
            return "Python"
        elif any(path.endswith(('.js', '.ts', '.jsx', '.tsx')) for path in file_paths):
            return "JavaScript/TypeScript"
        elif any(path.endswith('.java') for path in file_paths):
            return "Java"
        elif any(path.endswith(('.cpp', '.c', '.h')) for path in file_paths):
            return "C/C++"
        else:
            return "Mixed/Unknown"
    
    def _analyze_file_types(self, files: List[Dict]) -> Dict[str, int]:
        """Analyze the distribution of file types"""
        file_types = {}
        for f in files:
            ext = f['path'].split('.')[-1] if '.' in f['path'] else 'no_extension'
            file_types[ext] = file_types.get(ext, 0) + 1
        return file_types
    
    # Legacy method for backward compatibility
    async def get_source_files(self, max_files: int = None) -> List[Dict[str, Any]]:
        """Legacy method - redirects to intelligent selection with generic parameters"""
        logger.warning("🔄 Using legacy get_source_files method - consider using analyze_repository_for_ticket")
        
        # Use intelligent selector with generic parameters
        selected_files = await self.file_selector.select_relevant_files(
            ticket_title="Legacy Analysis",
            ticket_description="No specific description provided",
            error_trace=""
        )
        
        if max_files:
            selected_files = selected_files[:max_files]
        
        return selected_files
