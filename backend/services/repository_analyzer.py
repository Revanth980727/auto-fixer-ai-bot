
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
            '.md': 'markdown'
        }
    
    async def analyze_repository(self, branch: str = "main") -> Dict[str, Any]:
        """Perform comprehensive repository analysis"""
        logger.info(f"Starting comprehensive repository analysis on branch: {branch}")
        
        if not self.github_client._is_configured():
            logger.error("GitHub not configured - cannot analyze repository")
            return {"error": "GitHub not configured", "configured": False}
        
        try:
            # Get repository structure
            repo_structure = await self._get_repository_structure(branch)
            if not repo_structure:
                return {"error": "Failed to fetch repository structure", "configured": True}
            
            # Build dependency graph
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
    
    async def _get_repository_structure(self, branch: str) -> Dict[str, Any]:
        """Get complete repository file structure"""
        try:
            # For simplicity, we'll analyze common directories
            structure = {
                "directories": [],
                "files": [],
                "total_size": 0
            }
            
            common_paths = [
                "", "src", "backend", "frontend", "components", "services", 
                "utils", "lib", "api", "models", "agents", "core"
            ]
            
            for path in common_paths:
                files = await self._scan_directory(path, branch)
                structure["files"].extend(files)
            
            # Remove duplicates
            seen = set()
            unique_files = []
            for file_info in structure["files"]:
                if file_info["path"] not in seen:
                    seen.add(file_info["path"])
                    unique_files.append(file_info)
                    structure["total_size"] += file_info["size"]
            
            structure["files"] = unique_files
            logger.info(f"Repository structure: {len(unique_files)} unique files found")
            return structure
            
        except Exception as e:
            logger.error(f"Error getting repository structure: {e}")
            return {}
    
    async def _scan_directory(self, path: str, branch: str) -> List[Dict[str, Any]]:
        """Scan a directory for files"""
        files = []
        try:
            # Try to get common file patterns
            common_files = [
                "main.py", "app.py", "index.js", "index.ts", "App.tsx", "App.js",
                "requirements.txt", "package.json", "README.md", "config.py"
            ]
            
            for filename in common_files:
                file_path = os.path.join(path, filename) if path else filename
                content = await self.github_client.get_file_content(file_path, branch)
                if content:
                    files.append({
                        "path": file_path,
                        "size": len(content),
                        "language": self._detect_language(file_path),
                        "hash": hashlib.sha256(content.encode()).hexdigest()
                    })
            
        except Exception as e:
            logger.debug(f"Error scanning directory {path}: {e}")
        
        return files
    
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

    async def find_relevant_files(self, error_trace: str, ticket_description: str) -> List[Dict[str, Any]]:
        """Smart file discovery based on error context"""
        logger.info("Finding relevant files using intelligent analysis")
        
        relevant_files = []
        
        # Extract file paths from error trace
        file_patterns = [
            r'File "([^"]+)"',
            r'at ([^:]+):\d+',
            r'in ([^:]+) line \d+'
        ]
        
        mentioned_files = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, error_trace)
            mentioned_files.update(matches)
        
        # Get repository analysis
        repo_analysis = await self.analyze_repository()
        if repo_analysis.get("error"):
            logger.warning("Repository analysis failed, falling back to basic file discovery")
            return [{"path": f, "relevance": "error_trace", "confidence": 0.9} for f in mentioned_files]
        
        dependency_graph = repo_analysis.get("dependency_graph", {})
        nodes = dependency_graph.get("nodes", {})
        edges = dependency_graph.get("edges", {})
        
        # Find files mentioned in error trace
        for file_path in mentioned_files:
            if file_path in nodes:
                relevant_files.append({
                    "path": file_path,
                    "relevance": "error_trace",
                    "confidence": 0.95,
                    "size": nodes[file_path]["size"],
                    "language": nodes[file_path]["language"]
                })
        
        # Find related files through dependencies
        for file_path in mentioned_files:
            if file_path in edges:
                for dep in edges[file_path]:
                    if dep in nodes:
                        relevant_files.append({
                            "path": dep,
                            "relevance": "dependency",
                            "confidence": 0.7,
                            "size": nodes[dep]["size"],
                            "language": nodes[dep]["language"]
                        })
        
        # Search for files by keywords in ticket description
        keywords = self._extract_keywords(ticket_description)
        for file_path, node in nodes.items():
            for keyword in keywords:
                if keyword.lower() in file_path.lower():
                    relevant_files.append({
                        "path": file_path,
                        "relevance": "keyword_match",
                        "confidence": 0.6,
                        "size": node["size"],
                        "language": node["language"],
                        "keyword": keyword
                    })
        
        # Remove duplicates and sort by confidence
        unique_files = {}
        for file_info in relevant_files:
            path = file_info["path"]
            if path not in unique_files or file_info["confidence"] > unique_files[path]["confidence"]:
                unique_files[path] = file_info
        
        sorted_files = sorted(unique_files.values(), key=lambda x: x["confidence"], reverse=True)
        logger.info(f"Found {len(sorted_files)} relevant files")
        return sorted_files[:10]  # Top 10 most relevant files
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        # Common programming keywords to ignore
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
        
        # Extract words that might be relevant
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]
        
        return list(set(keywords))[:10]  # Top 10 unique keywords
