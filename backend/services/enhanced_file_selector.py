import asyncio
import logging
from typing import List, Dict, Any, Optional
from services.github_client import GitHubClient
from services.semantic_analyzer import SemanticAnalyzer
from core.config import config
from core.analysis_config import analysis_config, file_type_config

logger = logging.getLogger(__name__)

class EnhancedFileSelector:
    """Enhanced file selector with chunked semantic analysis and intelligent scoring"""
    
    def __init__(self):
        self.github_client = GitHubClient()
        self.semantic_analyzer = SemanticAnalyzer()
    
    async def select_relevant_files(self, ticket_title: str, ticket_description: str, error_trace: str = "") -> List[Dict[str, Any]]:
        """Select the most relevant files using enhanced chunked semantic analysis"""
        logger.info(f"🚀 Starting enhanced file selection for: {ticket_title}")
        
        try:
            # Get all source files from repository
            all_files = await self._get_all_source_files()
            
            if not all_files:
                logger.warning("No source files found in repository")
                return []
            
            logger.info(f"📁 Found {len(all_files)} total source files")
            
            # Prepare project context for analysis
            project_context = {
                'ticket_title': ticket_title,
                'ticket_description': ticket_description,
                'error_trace': error_trace,
                'error_files': self._extract_file_names_from_error(error_trace),
                'repository_name': f"{config.github_repo_owner}/{config.github_repo_name}" if config.github_repo_owner and config.github_repo_name else ""
            }
            
            # Filter files by basic criteria first
            filtered_files = self._basic_filter_files(all_files)
            logger.info(f"🔍 After basic filtering: {len(filtered_files)} files")
            
            # Apply semantic analysis with chunked processing
            analyzed_files = await self.semantic_analyzer.analyze_files_for_relevance(filtered_files, project_context)
            
            # Select top files based on configured limit
            selected_files = analyzed_files[:config.max_source_files]
            
            # Add metadata to selected files
            for i, file in enumerate(selected_files):
                file['selection_rank'] = i + 1
                file['relevance_score'] = file.get('final_relevance_score', 0)
                file['selection_method'] = 'enhanced_semantic_chunked'
            
            logger.info(f"✅ Selected {len(selected_files)} most relevant files using enhanced analysis")
            
            # Log selection summary
            for file in selected_files:
                logger.info(f"📄 Selected: {file['path']} (score: {file.get('relevance_score', 0):.2f})")
            
            return selected_files
            
        except Exception as e:
            logger.error(f"❌ Enhanced file selection failed: {e}")
            # Fallback to basic selection
            return await self._fallback_file_selection()
    
    async def _get_all_source_files(self) -> List[Dict[str, Any]]:
        """Get all source files from the repository with content"""
        try:
            # Get repository tree
            tree = await self.github_client.get_repository_tree(config.github_target_branch)
            if not tree:
                logger.warning("No repository tree found")
                return []
            
            # Filter for source code files
            source_files = []
            for item in tree:
                if item.get('type') == 'blob' and self._is_source_file(item['path']):
                    source_files.append(item)
            
            logger.info(f"📂 Found {len(source_files)} potential source files")
            
            # Get file contents in parallel
            content_tasks = []
            for file_item in source_files:
                task = self._get_file_with_content(file_item)
                content_tasks.append(task)
            
            # Execute with reasonable concurrency
            semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
            
            async def bounded_task(task):
                async with semaphore:
                    return await task
            
            bounded_tasks = [bounded_task(task) for task in content_tasks]
            files_with_content = await asyncio.gather(*bounded_tasks, return_exceptions=True)
            
            # Filter out failed requests
            valid_files = []
            for result in files_with_content:
                if isinstance(result, dict) and result.get('content'):
                    valid_files.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Failed to get file content: {result}")
            
            logger.info(f"📖 Successfully loaded {len(valid_files)} files with content")
            return valid_files
            
        except Exception as e:
            logger.error(f"Error getting source files: {e}")
            return []
    
    async def _get_file_with_content(self, file_item: Dict) -> Dict[str, Any]:
        """Get file with its content"""
        try:
            content = await self.github_client.get_file_content(file_item['path'], config.github_target_branch)
            if content:
                return {
                    'path': file_item['path'],
                    'content': content,
                    'size': file_item.get('size', len(content)),
                    'sha': file_item.get('sha', ''),
                }
            return {}
        except Exception as e:
            logger.warning(f"Failed to get content for {file_item['path']}: {e}")
            return {}
    
    def _is_source_file(self, file_path: str) -> bool:
        """Check if file is a source code file based on configured extensions"""
        if not file_path or '.' not in file_path:
            return False
        
        extension = file_path.split('.')[-1].lower()
        return extension in analysis_config.supported_extensions
    
    def _basic_filter_files(self, files: List[Dict]) -> List[Dict]:
        """Apply basic filtering to remove obviously irrelevant files"""
        filtered = []
        
        for file in files:
            path = file['path'].lower()
            size = file.get('size', 0)
            
            # Skip if too small or too large
            if size < analysis_config.min_file_size or size > analysis_config.max_file_size:
                continue
            
            # Skip binary-looking files
            if any(pattern in path for pattern in ['.git/', '__pycache__/', '.pyc', '.exe', '.bin']):
                continue
            
            # Skip obvious test files for now (they can be added back if needed)
            if any(test_pattern in path for test_pattern in ['test_', '_test.', '/tests/', '/test/']):
                continue
            
            filtered.append(file)
        
        return filtered
    
    def _extract_file_names_from_error(self, error_trace: str) -> set:
        """Extract file names mentioned in error traces"""
        import re
        
        if not error_trace:
            return set()
        
        # Common patterns for file references in stack traces
        patterns = [
            r'File "([^"]+)"',  # Python traceback
            r'at ([^\s]+\.py):\d+',  # Python with line numbers
            r'([^\s/]+\.(py|js|ts|jsx|tsx|java|cpp|c|h))',  # General file extensions
            r'/([^/\s]+\.(py|js|ts|jsx|tsx|java|cpp|c|h))',  # Files with paths
        ]
        
        file_names = set()
        for pattern in patterns:
            matches = re.findall(pattern, error_trace, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    file_names.add(match[0])
                else:
                    file_names.add(match)
        
        # Clean up file names (remove leading paths, keep just filename)
        cleaned_names = set()
        for name in file_names:
            clean_name = name.split('/')[-1]  # Get just the filename
            if clean_name and '.' in clean_name:
                cleaned_names.add(clean_name)
        
        return cleaned_names
    
    async def _fallback_file_selection(self) -> List[Dict[str, Any]]:
        """Fallback file selection when enhanced analysis fails"""
        logger.info("🔄 Using fallback file selection")
        
        try:
            # Get repository tree
            tree = await self.github_client.get_repository_tree(config.github_target_branch)
            if not tree:
                return []
            
            # Simple heuristic selection
            important_files = []
            for item in tree:
                if item.get('type') == 'blob':
                    path = item['path']
                    filename = path.split('/')[-1].lower()
                    
                    # Look for obviously important files
                    if any(important in filename for important in analysis_config.main_indicators):
                        content = await self.github_client.get_file_content(path, config.github_target_branch)
                        if content:
                            important_files.append({
                                'path': path,
                                'content': content,
                                'size': len(content),
                                'relevance_score': 5.0,
                                'selection_method': 'fallback_heuristic'
                            })
            
            return important_files[:config.max_source_files]
            
        except Exception as e:
            logger.error(f"Fallback selection also failed: {e}")
            return []
