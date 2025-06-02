
import logging
from typing import List, Dict, Any, Set
from services.github_client import GitHubClient
from services.semantic_analyzer import SemanticAnalyzer
from core.config import config

logger = logging.getLogger(__name__)

class EnhancedFileSelector:
    """Enhanced file selection using semantic analysis and intelligent scoring"""
    
    def __init__(self):
        self.github_client = GitHubClient()
        self.semantic_analyzer = SemanticAnalyzer()
        self.max_files = config.max_source_files
    
    async def select_relevant_files(self, ticket_title: str, ticket_description: str, error_trace: str = "") -> List[Dict[str, Any]]:
        """Select the most relevant files using semantic analysis"""
        logger.info(f"🚀 Starting enhanced file selection for: {ticket_title}")
        
        # Extract error files for context
        error_files = self._extract_files_from_error_trace(error_trace)
        
        # Create project context
        project_context = {
            'ticket_title': ticket_title,
            'ticket_description': ticket_description,
            'error_trace': error_trace,
            'error_files': error_files,
            'repository_name': f"{config.github_repo_owner}/{config.github_repo_name}" if config.github_repo_owner and config.github_repo_name else ""
        }
        
        logger.info(f"📋 Project context: {len(error_files)} error files, repo: {project_context['repository_name']}")
        
        # Get repository files
        repo_tree = await self.github_client.get_repository_tree(config.github_target_branch)
        if not repo_tree:
            logger.warning("⚠️ Could not get repository tree - using fallback selection")
            return await self._fallback_file_selection(error_files)
        
        # Filter to code files
        code_files = self._filter_code_files(repo_tree)
        logger.info(f"📁 Found {len(code_files)} code files in repository")
        
        # Apply duplicate detection and initial filtering
        filtered_files = self._deduplicate_and_filter(code_files)
        logger.info(f"🔍 After deduplication and filtering: {len(filtered_files)} files")
        
        # Limit to reasonable number for analysis (avoid API costs)
        analysis_candidates = filtered_files[:20]  # Analyze top 20 candidates max
        
        # Fetch file contents for analysis candidates
        files_with_content = await self._fetch_file_contents(analysis_candidates)
        logger.info(f"📄 Fetched content for {len(files_with_content)} files")
        
        # Perform semantic analysis
        analyzed_files = await self.semantic_analyzer.analyze_files_for_relevance(
            files_with_content, project_context
        )
        
        # Select top files
        selected_files = analyzed_files[:self.max_files]
        
        # Add metadata for logging and debugging
        for file in selected_files:
            logger.info(f"✅ Selected: {file['path']} (score: {file.get('final_relevance_score', 0):.2f}, semantic: {file.get('semantic_score', 0):.2f})")
        
        return selected_files
    
    def _extract_files_from_error_trace(self, error_trace: str) -> Set[str]:
        """Extract file paths from error traces and stack traces"""
        import re
        
        file_paths = set()
        
        if not error_trace:
            return file_paths
        
        # Enhanced patterns for different error formats
        patterns = [
            r'File "([^"]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h))"',  # Python style
            r'at ([^\s]+\.(?:js|ts|tsx|jsx)):\d+',  # JavaScript style
            r'([^\s]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h)):\d+',  # Generic with line numbers
            r'/([a-zA-Z0-9_/]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h))',  # Unix paths
            r'\\([a-zA-Z0-9_\\]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h))',  # Windows paths
            r'in ([a-zA-Z0-9_]+\.(?:py|js|ts|tsx|jsx))',  # "in filename.py" pattern
            r'([a-zA-Z0-9_]+\.(?:py|js|ts|tsx|jsx))(?:\s|:|\)|$)',  # Filename at word boundary
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error_trace, re.IGNORECASE)
            for match in matches:
                # Clean up the path
                clean_path = match.strip().lstrip('./\\').replace('\\', '/')
                if clean_path and len(clean_path) > 0:
                    file_paths.add(clean_path)
        
        return file_paths
    
    def _filter_code_files(self, repo_tree: List[Dict]) -> List[Dict]:
        """Filter repository tree to only include relevant code files"""
        code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', '.cs', '.rb', '.go', '.php', '.rs', '.scala', '.kt'}
        code_files = []
        
        # Directories to skip
        skip_patterns = [
            'node_modules/', '.git/', '__pycache__/', '.pytest_cache/', 
            'dist/', 'build/', '.next/', '.vscode/', '.idea/', 'coverage/',
            'venv/', 'env/', '.env/', 'target/', 'bin/', 'obj/',
            'migrations/', 'static/admin/', 'locale/'
        ]
        
        for item in repo_tree:
            if item.get('type') == 'blob':  # Only files, not directories
                path = item.get('path', '')
                
                # Check if it's a code file
                if any(path.endswith(ext) for ext in code_extensions):
                    # Skip certain directories/files
                    if not any(skip in path for skip in skip_patterns):
                        # Skip very small files (likely empty or just imports)
                        size = item.get('size', 0)
                        if size >= 50:  # At least 50 bytes
                            code_files.append({
                                'path': path,
                                'size': size,
                                'type': 'blob'
                            })
        
        return code_files
    
    def _deduplicate_and_filter(self, code_files: List[Dict]) -> List[Dict]:
        """Remove duplicate files and apply intelligent filtering"""
        # Group files by name to detect duplicates
        file_groups = {}
        for file in code_files:
            filename = file['path'].split('/')[-1]
            if filename not in file_groups:
                file_groups[filename] = []
            file_groups[filename].append(file)
        
        # Select best file from each group
        filtered_files = []
        for filename, group in file_groups.items():
            if len(group) == 1:
                # No duplicates, include the file
                filtered_files.append(group[0])
            else:
                # Multiple files with same name, pick the best one
                best_file = self._select_best_duplicate(group)
                filtered_files.append(best_file)
                logger.info(f"🔀 Deduplicated {filename}: selected {best_file['path']} from {len(group)} candidates")
        
        # Sort by preference (main files first, then by size)
        filtered_files.sort(key=lambda f: (
            -self._get_file_priority(f['path']),  # Higher priority first
            -f['size']  # Larger files first (within same priority)
        ))
        
        return filtered_files
    
    def _select_best_duplicate(self, duplicates: List[Dict]) -> Dict:
        """Select the best file from a group of duplicates"""
        # Prefer files in root directory
        root_files = [f for f in duplicates if '/' not in f['path']]
        if root_files:
            return max(root_files, key=lambda f: f['size'])
        
        # Prefer files in main directories over subdirectories
        main_dirs = ['src/', 'lib/', 'app/', 'core/', 'main/']
        for main_dir in main_dirs:
            main_files = [f for f in duplicates if f['path'].startswith(main_dir)]
            if main_files:
                return max(main_files, key=lambda f: f['size'])
        
        # Fall back to largest file
        return max(duplicates, key=lambda f: f['size'])
    
    def _get_file_priority(self, path: str) -> int:
        """Get priority score for file based on its path and name"""
        filename = path.split('/')[-1].lower()
        path_lower = path.lower()
        
        # Highest priority: main application files
        if filename in ['main.py', 'app.py', 'server.py', 'index.js', 'index.ts', 'app.js', 'app.ts']:
            return 100
        
        # High priority: core functionality
        if any(indicator in filename for indicator in ['core', 'engine', 'manager', 'service', 'client']):
            return 80
        
        # Medium-high priority: API and routes
        if any(indicator in path_lower for indicator in ['api/', 'routes/', 'controllers/', 'handlers/']):
            return 70
        
        # Medium priority: models and data
        if any(indicator in path_lower for indicator in ['models/', 'data/', 'entities/', 'schemas/']):
            return 60
        
        # Lower priority: utilities and helpers
        if any(indicator in path_lower for indicator in ['utils/', 'helpers/', 'tools/', 'lib/']):
            return 40
        
        # Lowest priority: tests and configs
        if any(indicator in path_lower for indicator in ['test', 'spec', 'config', '__init__']):
            return 10
        
        return 50  # Default priority
    
    async def _fetch_file_contents(self, files: List[Dict]) -> List[Dict[str, Any]]:
        """Fetch file contents for analysis"""
        files_with_content = []
        
        for file_info in files:
            try:
                content = await self.github_client.get_file_content(
                    file_info['path'], 
                    config.github_target_branch
                )
                
                if content:
                    files_with_content.append({
                        'path': file_info['path'],
                        'content': content,
                        'size': len(content),
                        'original_size': file_info.get('size', 0)
                    })
                else:
                    logger.warning(f"⚠️ Could not fetch content for {file_info['path']}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error fetching {file_info['path']}: {e}")
        
        return files_with_content
    
    async def _fallback_file_selection(self, error_files: Set[str]) -> List[Dict[str, Any]]:
        """Fallback selection when repository tree is not available"""
        logger.info("🔄 Using fallback file selection")
        
        files_with_content = []
        
        # Try to get files mentioned in errors first
        for file_path in list(error_files)[:self.max_files]:
            content = await self.github_client.get_file_content(file_path, config.github_target_branch)
            if content:
                files_with_content.append({
                    'path': file_path,
                    'content': content,
                    'final_relevance_score': 10.0,
                    'size': len(content)
                })
        
        # If we still need more files, try common patterns
        if len(files_with_content) < self.max_files:
            common_files = ['main.py', 'app.py', 'server.py', 'index.js', 'index.ts', '__init__.py', 'setup.py']
            for file_path in common_files:
                if len(files_with_content) >= self.max_files:
                    break
                    
                content = await self.github_client.get_file_content(file_path, config.github_target_branch)
                if content:
                    files_with_content.append({
                        'path': file_path,
                        'content': content,
                        'final_relevance_score': 5.0,
                        'size': len(content)
                    })
        
        return files_with_content
