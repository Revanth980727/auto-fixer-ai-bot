
import os
import ast
import re
from typing import Dict, Any, List, Set, Optional, Tuple
from services.github_client import GitHubClient
import logging
import hashlib
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class FileNode:
    path: str
    type: str  # 'file' or 'directory'
    size: int
    language: Optional[str]
    dependencies: List[str]
    hash: str
    last_modified: Optional[str] = None

@dataclass
class DependencyGraph:
    nodes: Dict[str, FileNode]
    edges: Dict[str, List[str]]  # file -> list of files it depends on
    reverse_edges: Dict[str, List[str]]  # file -> list of files that depend on it

class RepositoryAnalyzer:
    def __init__(self):
        self.github_client = GitHubClient()
        self.supported_languages = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.txt': 'text',
            '.csv': 'csv',
            '.sql': 'sql',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.less': 'less',
            '.xml': 'xml',
            '.sh': 'shell',
            '.bat': 'batch',
            '.dockerfile': 'docker',
            '.env': 'env'
        }
    
    async def analyze_repository(self, branch: str = "main") -> Dict[str, Any]:
        """Perform comprehensive repository analysis using real GitHub API discovery"""
        logger.info(f"Starting comprehensive repository analysis on branch: {branch}")
        
        if not self.github_client._is_configured():
            logger.error("GitHub not configured - cannot analyze repository")
            return {"error": "GitHub not configured", "configured": False}
        
        try:
            # Discover actual repository structure using GitHub API
            repo_structure = await self._discover_repository_structure(branch)
            if not repo_structure:
                return {"error": "Failed to fetch repository structure", "configured": True}
            
            logger.info(f"Repository structure discovered: {len(repo_structure.get('files', []))} files found")
            
            # Build dependency graph from actual files
            dependency_graph = await self._build_dependency_graph(repo_structure, branch)
            
            # Analyze code quality metrics
            quality_metrics = await self._analyze_code_quality(repo_structure, branch)
            
            # Identify critical files
            critical_files = self._identify_critical_files(dependency_graph, quality_metrics)
            
            # Generate file impact map
            impact_map = self._generate_impact_map(dependency_graph)
            
            analysis_result = {
                "repository_structure": repo_structure,
                "dependency_graph": asdict(dependency_graph),
                "quality_metrics": quality_metrics,
                "critical_files": critical_files,
                "impact_map": impact_map,
                "total_files": len(repo_structure.get("files", [])),
                "languages": list(set(node.language for node in dependency_graph.nodes.values() if node.language)),
                "analysis_timestamp": self._get_timestamp(),
                "configured": True
            }
            
            logger.info(f"Repository analysis complete: {len(repo_structure.get('files', []))} files analyzed")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error during repository analysis: {e}")
            return {"error": str(e), "configured": True}
    
    async def _discover_repository_structure(self, branch: str) -> Dict[str, Any]:
        """Discover actual repository file structure using GitHub API"""
        try:
            structure = {
                "directories": [],
                "files": [],
                "total_size": 0
            }
            
            # Get repository tree from GitHub API
            discovered_files = await self._get_repository_tree(branch)
            
            for file_info in discovered_files:
                if file_info["type"] == "blob":  # It's a file
                    structure["files"].append({
                        "path": file_info["path"],
                        "size": file_info.get("size", 0),
                        "language": self._detect_language(file_info["path"]),
                        "hash": file_info.get("sha", "")
                    })
                    structure["total_size"] += file_info.get("size", 0)
                elif file_info["type"] == "tree":  # It's a directory
                    structure["directories"].append(file_info["path"])
            
            logger.info(f"Discovered {len(structure['files'])} files and {len(structure['directories'])} directories")
            return structure
            
        except Exception as e:
            logger.error(f"Error discovering repository structure: {e}")
            return {}
    
    async def _get_repository_tree(self, branch: str) -> List[Dict[str, Any]]:
        """Get complete repository tree using GitHub API"""
        try:
            import requests
            
            if not self.github_client._is_configured():
                logger.warning("GitHub not configured")
                return []
            
            # Get repository tree recursively
            url = f"{self.github_client.base_url}/repos/{self.github_client.repo_owner}/{self.github_client.repo_name}/git/trees/{branch}"
            params = {"recursive": "1"}  # Get all files recursively
            
            response = requests.get(url, headers=self.github_client.headers, params=params)
            
            if response.status_code == 200:
                tree_data = response.json()
                files = tree_data.get("tree", [])
                logger.info(f"GitHub API returned {len(files)} items from repository tree")
                return files
            else:
                logger.error(f"Failed to get repository tree: HTTP {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting repository tree: {e}")
            return []
    
    async def find_relevant_files(self, error_trace: str, ticket_description: str) -> List[Dict[str, Any]]:
        """Smart file discovery based on error context and ticket content"""
        logger.info("Finding relevant files using intelligent analysis")
        
        relevant_files = []
        
        # Get actual repository structure first
        repo_analysis = await self.analyze_repository()
        if repo_analysis.get("error"):
            logger.warning("Repository analysis failed, cannot perform intelligent file discovery")
            return []
        
        repo_structure = repo_analysis.get("repository_structure", {})
        actual_files = repo_structure.get("files", [])
        
        if not actual_files:
            logger.warning("No files found in repository")
            return []
        
        logger.info(f"Analyzing {len(actual_files)} actual repository files for relevance")
        
        # Extract file paths mentioned in error trace
        mentioned_files = self._extract_file_paths_from_error(error_trace)
        logger.info(f"Found {len(mentioned_files)} files mentioned in error trace: {mentioned_files}")
        
        # Find exact matches for files mentioned in error
        for file_info in actual_files:
            file_path = file_info["path"]
            
            # Check if file is mentioned in error trace
            for mentioned_file in mentioned_files:
                if mentioned_file in file_path or file_path.endswith(mentioned_file):
                    relevant_files.append({
                        "path": file_path,
                        "relevance": "error_trace_exact",
                        "confidence": 0.95,
                        "size": file_info["size"],
                        "language": file_info["language"],
                        "reason": f"Mentioned in error trace: {mentioned_file}"
                    })
                    break
        
        # Extract keywords from ticket description
        ticket_keywords = self._extract_keywords_from_ticket(ticket_description)
        error_keywords = self._extract_keywords_from_error(error_trace)
        all_keywords = list(set(ticket_keywords + error_keywords))
        
        logger.info(f"Extracted keywords: {all_keywords}")
        
        # Find files that match keywords
        for file_info in actual_files:
            file_path = file_info["path"]
            
            # Skip if already found in error trace
            if any(rf["path"] == file_path for rf in relevant_files):
                continue
            
            relevance_score = self._calculate_file_relevance(file_path, all_keywords, ticket_description, error_trace)
            
            if relevance_score > 0.3:  # Only include files with meaningful relevance
                relevant_files.append({
                    "path": file_path,
                    "relevance": "keyword_match",
                    "confidence": relevance_score,
                    "size": file_info["size"],
                    "language": file_info["language"],
                    "keywords_matched": [kw for kw in all_keywords if kw.lower() in file_path.lower()]
                })
        
        # Sort by confidence and limit results
        relevant_files.sort(key=lambda x: x["confidence"], reverse=True)
        top_files = relevant_files[:15]  # Top 15 most relevant files
        
        logger.info(f"Found {len(top_files)} relevant files for ticket analysis")
        for file_info in top_files[:5]:  # Log top 5
            logger.info(f"  - {file_info['path']} (confidence: {file_info['confidence']:.2f}, reason: {file_info['relevance']})")
        
        return top_files
    
    def _extract_file_paths_from_error(self, error_trace: str) -> List[str]:
        """Extract file paths from error traces and stack traces"""
        file_paths = set()
        
        # Common error trace patterns
        patterns = [
            r'File "([^"]+)"',
            r'at ([^:]+):\d+',
            r'in ([^:]+) line \d+',
            r'([a-zA-Z0-9_/.-]+\.py):\d+',
            r'([a-zA-Z0-9_/.-]+\.js):\d+',
            r'([a-zA-Z0-9_/.-]+\.ts):\d+',
            r'([a-zA-Z0-9_/.-]+\.tsx):\d+',
            r'([a-zA-Z0-9_/.-]+\.jsx):\d+',
            r'Module not found: ([^\s]+)',
            r'Cannot import ([^\s]+)',
            r'Error in ([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error_trace, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str) and len(match) > 0:
                    # Clean up the file path
                    clean_path = match.strip().strip('"\'')
                    if '.' in clean_path:  # Must have an extension
                        file_paths.add(clean_path)
        
        return list(file_paths)
    
    def _extract_keywords_from_ticket(self, ticket_description: str) -> List[str]:
        """Extract relevant keywords from ticket description"""
        # Technology and framework keywords
        tech_keywords = [
            'python', 'javascript', 'typescript', 'react', 'node', 'flask', 'django',
            'api', 'database', 'sql', 'json', 'config', 'auth', 'login', 'user',
            'error', 'bug', 'fix', 'update', 'create', 'delete', 'modify'
        ]
        
        # Extract words that might be relevant
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', ticket_description.lower())
        
        # Filter for meaningful keywords
        keywords = []
        for word in words:
            if len(word) > 2 and (word in tech_keywords or len(word) > 4):
                keywords.append(word)
        
        return list(set(keywords))[:10]
    
    def _extract_keywords_from_error(self, error_trace: str) -> List[str]:
        """Extract relevant keywords from error messages"""
        # Common error keywords
        error_patterns = [
            r'(\w+Error)',
            r'(\w+Exception)',
            r'Cannot (\w+)',
            r'Failed to (\w+)',
            r'Missing (\w+)',
            r'Invalid (\w+)',
            r'Undefined (\w+)',
            r'(\w+) not found'
        ]
        
        keywords = []
        for pattern in error_patterns:
            matches = re.findall(pattern, error_trace, re.IGNORECASE)
            keywords.extend([match.lower() for match in matches if isinstance(match, str)])
        
        return list(set(keywords))
    
    def _calculate_file_relevance(self, file_path: str, keywords: List[str], ticket_description: str, error_trace: str) -> float:
        """Calculate how relevant a file is to the ticket and error"""
        relevance = 0.0
        
        file_path_lower = file_path.lower()
        ticket_lower = ticket_description.lower()
        error_lower = error_trace.lower()
        
        # Check for keyword matches in file path
        for keyword in keywords:
            if keyword.lower() in file_path_lower:
                relevance += 0.3
        
        # Boost for certain file types based on context
        if 'error' in error_lower or 'exception' in error_lower:
            if file_path_lower.endswith(('.py', '.js', '.ts', '.tsx')):
                relevance += 0.2
        
        if 'config' in ticket_lower or 'setting' in ticket_lower:
            if 'config' in file_path_lower or 'setting' in file_path_lower:
                relevance += 0.4
        
        if 'api' in ticket_lower:
            if 'api' in file_path_lower or 'route' in file_path_lower:
                relevance += 0.3
        
        if 'database' in ticket_lower or 'db' in ticket_lower:
            if 'model' in file_path_lower or 'db' in file_path_lower or 'database' in file_path_lower:
                relevance += 0.3
        
        # Check if file name components appear in ticket or error
        file_name = os.path.basename(file_path_lower)
        file_name_parts = file_name.replace('.', '_').split('_')
        
        for part in file_name_parts:
            if len(part) > 2:
                if part in ticket_lower:
                    relevance += 0.2
                if part in error_lower:
                    relevance += 0.3
        
        return min(relevance, 1.0)  # Cap at 1.0

    # ... keep existing code (all other methods remain the same)
    async def _build_dependency_graph(self, repo_structure: Dict, branch: str) -> DependencyGraph:
        """Build dependency graph for the repository"""
        nodes = {}
        edges = {}
        reverse_edges = {}
        
        for file_info in repo_structure.get("files", []):
            file_path = file_info["path"]
            
            # Create file node
            dependencies = await self._extract_dependencies(file_path, branch)
            node = FileNode(
                path=file_path,
                type="file",
                size=file_info["size"],
                language=file_info.get("language"),
                dependencies=dependencies,
                hash=file_info["hash"]
            )
            nodes[file_path] = node
            edges[file_path] = dependencies
            
            # Build reverse edges
            for dep in dependencies:
                if dep not in reverse_edges:
                    reverse_edges[dep] = []
                reverse_edges[dep].append(file_path)
        
        return DependencyGraph(nodes=nodes, edges=edges, reverse_edges=reverse_edges)
    
    async def _extract_dependencies(self, file_path: str, branch: str) -> List[str]:
        """Extract dependencies from a file"""
        try:
            content = await self.github_client.get_file_content(file_path, branch)
            if not content:
                return []
            
            dependencies = []
            language = self._detect_language(file_path)
            
            if language == "python":
                dependencies = self._extract_python_dependencies(content)
            elif language in ["javascript", "typescript"]:
                dependencies = self._extract_js_dependencies(content)
            
            return dependencies
            
        except Exception as e:
            logger.debug(f"Error extracting dependencies from {file_path}: {e}")
            return []
    
    def _extract_python_dependencies(self, content: str) -> List[str]:
        """Extract Python import dependencies"""
        dependencies = []
        try:
            # Parse import statements
            import_patterns = [
                r'from\s+(\S+)\s+import',
                r'import\s+(\S+)',
                r'from\s+\.(\S+)\s+import'
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if not match.startswith('.'):
                        # Convert module path to file path
                        file_path = match.replace('.', '/') + '.py'
                        dependencies.append(file_path)
            
        except Exception as e:
            logger.debug(f"Error parsing Python dependencies: {e}")
        
        return dependencies
    
    def _extract_js_dependencies(self, content: str) -> List[str]:
        """Extract JavaScript/TypeScript import dependencies"""
        dependencies = []
        try:
            # Parse import statements
            import_patterns = [
                r'import.*from\s+[\'"]([^\'\"]+)[\'"]',
                r'require\([\'"]([^\'\"]+)[\'"]\)'
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if match.startswith('./') or match.startswith('../'):
                        # Relative import
                        dependencies.append(match)
            
        except Exception as e:
            logger.debug(f"Error parsing JS dependencies: {e}")
        
        return dependencies
    
    async def _analyze_code_quality(self, repo_structure: Dict, branch: str) -> Dict[str, Any]:
        """Analyze code quality metrics"""
        metrics = {
            "total_lines": 0,
            "avg_file_size": 0,
            "complexity_score": 0,
            "language_distribution": {},
            "large_files": []
        }
        
        total_size = 0
        file_count = 0
        
        for file_info in repo_structure.get("files", []):
            language = file_info.get("language", "unknown")
            size = file_info["size"]
            
            total_size += size
            file_count += 1
            
            # Language distribution
            if language not in metrics["language_distribution"]:
                metrics["language_distribution"][language] = 0
            metrics["language_distribution"][language] += 1
            
            # Identify large files
            if size > 10000:  # Files larger than 10KB
                metrics["large_files"].append({
                    "path": file_info["path"],
                    "size": size,
                    "language": language
                })
        
        if file_count > 0:
            metrics["avg_file_size"] = total_size / file_count
        
        # Estimate total lines (rough approximation)
        metrics["total_lines"] = total_size // 50  # Assume ~50 chars per line
        
        return metrics
    
    def _identify_critical_files(self, dependency_graph: DependencyGraph, quality_metrics: Dict) -> List[Dict[str, Any]]:
        """Identify critical files based on dependencies and usage"""
        critical_files = []
        
        for file_path, node in dependency_graph.nodes.items():
            # Count how many files depend on this one
            dependents = len(dependency_graph.reverse_edges.get(file_path, []))
            
            # Calculate criticality score
            criticality_score = dependents * 0.6 + len(node.dependencies) * 0.4
            
            if criticality_score > 2 or dependents > 3:
                critical_files.append({
                    "path": file_path,
                    "dependents": dependents,
                    "dependencies": len(node.dependencies),
                    "criticality_score": criticality_score,
                    "language": node.language,
                    "size": node.size
                })
        
        # Sort by criticality score
        critical_files.sort(key=lambda x: x["criticality_score"], reverse=True)
        return critical_files[:10]  # Top 10 critical files
    
    def _generate_impact_map(self, dependency_graph: DependencyGraph) -> Dict[str, List[str]]:
        """Generate impact map showing which files are affected by changes"""
        impact_map = {}
        
        for file_path in dependency_graph.nodes.keys():
            # Files that would be impacted if this file changes
            impacted = self._get_transitive_dependents(file_path, dependency_graph)
            impact_map[file_path] = impacted
        
        return impact_map
    
    def _get_transitive_dependents(self, file_path: str, dependency_graph: DependencyGraph, visited: Optional[Set[str]] = None) -> List[str]:
        """Get all files that transitively depend on the given file"""
        if visited is None:
            visited = set()
        
        if file_path in visited:
            return []
        
        visited.add(file_path)
        dependents = []
        
        direct_dependents = dependency_graph.reverse_edges.get(file_path, [])
        for dependent in direct_dependents:
            dependents.append(dependent)
            # Recursively get transitive dependents
            transitive = self._get_transitive_dependents(dependent, dependency_graph, visited.copy())
            dependents.extend(transitive)
        
        return list(set(dependents))  # Remove duplicates
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        return self.supported_languages.get(ext)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()
