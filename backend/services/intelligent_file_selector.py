
import re
import os
from typing import List, Dict, Any, Set, Tuple
from services.github_client import GitHubClient
from core.config import config
import logging

logger = logging.getLogger(__name__)

class IntelligentFileSelector:
    """Smart file selection based on error traces and ticket descriptions"""
    
    def __init__(self):
        self.github_client = GitHubClient()
        self.max_files = config.max_source_files
    
    async def select_relevant_files(self, ticket_title: str, ticket_description: str, error_trace: str) -> List[Dict[str, Any]]:
        """Select the most relevant files based on error analysis"""
        logger.info(f"🔍 Starting intelligent file selection for ticket: {ticket_title}")
        
        # Extract file paths and keywords from error trace
        error_files = self._extract_files_from_error_trace(error_trace)
        error_keywords = self._extract_keywords_from_error(error_trace, ticket_description, ticket_title)
        
        logger.info(f"📂 Files from error trace: {error_files}")
        logger.info(f"🔑 Keywords extracted: {error_keywords}")
        
        # Get repository tree
        repo_tree = await self.github_client.get_repository_tree(config.github_target_branch)
        if not repo_tree:
            logger.warning("⚠️ Could not get repository tree - using fallback selection")
            return await self._fallback_file_selection(error_files)
        
        # Score all code files
        code_files = self._filter_code_files(repo_tree)
        scored_files = self._score_files(code_files, error_files, error_keywords)
        
        # Select top files
        selected_files = scored_files[:self.max_files]
        logger.info(f"✅ Selected {len(selected_files)} files for analysis")
        
        # Fetch file contents
        files_with_content = []
        for file_info in selected_files:
            content = await self.github_client.get_file_content(file_info['path'], config.github_target_branch)
            if content:
                files_with_content.append({
                    'path': file_info['path'],
                    'content': content,
                    'relevance_score': file_info['score'],
                    'size': len(content)
                })
                logger.info(f"📄 Loaded {file_info['path']} ({len(content)} chars, score: {file_info['score']:.2f})")
        
        return files_with_content
    
    def _extract_files_from_error_trace(self, error_trace: str) -> Set[str]:
        """Extract file paths from error traces and stack traces"""
        file_paths = set()
        
        if not error_trace:
            return file_paths
        
        # Common patterns for file paths in error traces
        patterns = [
            r'File "([^"]+\.py)"',  # Python file paths in quotes
            r'at ([^\s]+\.js):\d+',  # JavaScript file paths with line numbers
            r'([^\s]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h)):\d+',  # File paths with line numbers
            r'/([a-zA-Z0-9_/]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h))',  # Unix-style paths
            r'\\([a-zA-Z0-9_\\]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h))',  # Windows-style paths
            r'in ([a-zA-Z0-9_]+\.(?:py|js|ts|tsx|jsx))',  # "in filename.py" pattern
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error_trace, re.IGNORECASE)
            for match in matches:
                # Clean up the path
                clean_path = match.strip().lstrip('./\\').replace('\\', '/')
                if clean_path:
                    file_paths.add(clean_path)
        
        return file_paths
    
    def _extract_keywords_from_error(self, error_trace: str, description: str, title: str) -> List[str]:
        """Extract meaningful keywords from error messages and descriptions"""
        keywords = []
        text = f"{title} {description} {error_trace}".lower()
        
        # Function/method names
        function_patterns = [
            r'def ([a-zA-Z_][a-zA-Z0-9_]*)',  # Python functions
            r'function ([a-zA-Z_][a-zA-Z0-9_]*)',  # JavaScript functions
            r'class ([a-zA-Z_][a-zA-Z0-9_]*)',  # Class names
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',  # Function calls
        ]
        
        for pattern in function_patterns:
            matches = re.findall(pattern, text)
            keywords.extend(matches)
        
        # Error-specific keywords
        error_keywords = [
            'import', 'export', 'module', 'undefined', 'null', 'error',
            'exception', 'traceback', 'syntax', 'reference', 'type',
            'attribute', 'method', 'function', 'class', 'variable'
        ]
        
        for keyword in error_keywords:
            if keyword in text:
                keywords.append(keyword)
        
        # Remove duplicates and short keywords
        keywords = list(set([k for k in keywords if len(k) > 2]))
        return keywords[:10]  # Limit to top 10 keywords
    
    def _filter_code_files(self, repo_tree: List[Dict]) -> List[Dict]:
        """Filter repository tree to only include code files"""
        code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', '.cs', '.rb', '.go', '.php'}
        code_files = []
        
        for item in repo_tree:
            if item.get('type') == 'blob':  # Only files, not directories
                path = item.get('path', '')
                if any(path.endswith(ext) for ext in code_extensions):
                    # Skip certain directories/files
                    if not any(skip in path for skip in ['node_modules/', '.git/', '__pycache__/', '.pytest_cache/', 'dist/', 'build/']):
                        code_files.append({
                            'path': path,
                            'size': item.get('size', 0)
                        })
        
        return code_files
    
    def _score_files(self, code_files: List[Dict], error_files: Set[str], keywords: List[str]) -> List[Dict]:
        """Score files based on relevance to the error"""
        scored_files = []
        
        for file_info in code_files:
            path = file_info['path']
            score = 0.0
            
            # Direct match with error files gets highest score
            for error_file in error_files:
                if error_file in path or path.endswith(error_file):
                    score += 10.0
                elif os.path.basename(path) == os.path.basename(error_file):
                    score += 8.0
            
            # Keyword matches
            path_lower = path.lower()
            for keyword in keywords:
                if keyword.lower() in path_lower:
                    score += 2.0
            
            # File type preferences
            if path.endswith('.py'):
                score += 1.0  # Prefer Python files for Python errors
            elif path.endswith(('.ts', '.tsx', '.js', '.jsx')):
                score += 0.5  # Prefer TypeScript/JavaScript
            
            # Prefer main/index files
            filename = os.path.basename(path).lower()
            if filename in ['main.py', 'index.js', 'index.ts', 'app.py', 'server.py']:
                score += 1.5
            
            # Prefer smaller files (easier to analyze)
            size_penalty = min(file_info.get('size', 0) / 10000, 2.0)  # Penalty for very large files
            score -= size_penalty
            
            if score > 0:
                scored_files.append({
                    'path': path,
                    'score': score,
                    'size': file_info.get('size', 0)
                })
        
        # Sort by score (descending)
        scored_files.sort(key=lambda x: x['score'], reverse=True)
        return scored_files
    
    async def _fallback_file_selection(self, error_files: Set[str]) -> List[Dict[str, Any]]:
        """Fallback selection when repository tree is not available"""
        logger.info("🔄 Using fallback file selection")
        
        # Try to get files mentioned in errors first
        files_with_content = []
        for file_path in list(error_files)[:self.max_files]:
            content = await self.github_client.get_file_content(file_path, config.github_target_branch)
            if content:
                files_with_content.append({
                    'path': file_path,
                    'content': content,
                    'relevance_score': 10.0,
                    'size': len(content)
                })
        
        # If we still need more files, try common patterns
        if len(files_with_content) < self.max_files:
            common_files = ['main.py', 'app.py', 'server.py', 'index.js', 'index.ts']
            for file_path in common_files:
                if len(files_with_content) >= self.max_files:
                    break
                content = await self.github_client.get_file_content(file_path, config.github_target_branch)
                if content:
                    files_with_content.append({
                        'path': file_path,
                        'content': content,
                        'relevance_score': 5.0,
                        'size': len(content)
                    })
        
        return files_with_content
