import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import hashlib
import json
from services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

@dataclass
class CodeChunk:
    """Represents a semantically meaningful chunk of code."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'method', 'block'
    name: str
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class SemanticSearchEngine:
    """Semantic search engine for finding related code using embeddings."""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.code_chunks: List[CodeChunk] = []
        self.chunk_index: Dict[str, CodeChunk] = {}
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        
    async def build_semantic_index(self, repository_files: List[Dict[str, Any]]) -> None:
        """Build semantic index from repository files."""
        try:
            logger.info(f"🧠 Building semantic index from {len(repository_files)} files")
            
            self.code_chunks.clear()
            self.chunk_index.clear()
            
            # Extract semantic chunks
            for file_info in repository_files:
                if self._should_index_file(file_info.get('path', '')):
                    chunks = await self._extract_semantic_chunks(file_info)
                    self.code_chunks.extend(chunks)
            
            # Generate embeddings for chunks
            await self._generate_embeddings()
            
            # Build index
            for chunk in self.code_chunks:
                chunk_id = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
                self.chunk_index[chunk_id] = chunk
            
            logger.info(f"✅ Semantic index built: {len(self.code_chunks)} chunks indexed")
            
        except Exception as e:
            logger.error(f"❌ Error building semantic index: {e}")
    
    def _should_index_file(self, file_path: str) -> bool:
        """Determine if a file should be included in semantic search."""
        # Index Python, JavaScript, TypeScript files
        indexable_extensions = ['.py', '.js', '.ts', '.tsx', '.jsx']
        return any(file_path.endswith(ext) for ext in indexable_extensions)
    
    async def _extract_semantic_chunks(self, file_info: Dict[str, Any]) -> List[CodeChunk]:
        """Extract semantically meaningful chunks from a file."""
        chunks = []
        content = file_info.get('content', '')
        file_path = file_info.get('path', '')
        
        if not content:
            return chunks
        
        try:
            if file_path.endswith('.py'):
                chunks = await self._extract_python_chunks(content, file_path)
            elif file_path.endswith(('.js', '.ts', '.tsx', '.jsx')):
                chunks = await self._extract_js_chunks(content, file_path)
            
        except Exception as e:
            logger.error(f"❌ Error extracting chunks from {file_path}: {e}")
        
        return chunks
    
    async def _extract_python_chunks(self, content: str, file_path: str) -> List[CodeChunk]:
        """Extract Python-specific semantic chunks."""
        import ast
        
        chunks = []
        lines = content.split('\n')
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chunk = CodeChunk(
                        content=self._get_node_content(node, lines),
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, 'end_lineno', node.lineno),
                        chunk_type='function',
                        name=node.name,
                        metadata={
                            'args': [arg.arg for arg in node.args.args],
                            'returns': self._extract_return_type(node),
                            'docstring': ast.get_docstring(node)
                        }
                    )
                    chunks.append(chunk)
                
                elif isinstance(node, ast.ClassDef):
                    chunk = CodeChunk(
                        content=self._get_node_content(node, lines),
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, 'end_lineno', node.lineno),
                        chunk_type='class',
                        name=node.name,
                        metadata={
                            'bases': [base.id for base in node.bases if hasattr(base, 'id')],
                            'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                            'docstring': ast.get_docstring(node)
                        }
                    )
                    chunks.append(chunk)
        
        except SyntaxError:
            # Fallback to line-based chunking
            chunks = self._fallback_chunking(content, file_path)
        
        return chunks
    
    async def _extract_js_chunks(self, content: str, file_path: str) -> List[CodeChunk]:
        """Extract JavaScript/TypeScript semantic chunks."""
        # Simplified regex-based extraction (could be enhanced with proper AST)
        import re
        
        chunks = []
        lines = content.split('\n')
        
        # Find function declarations
        function_pattern = r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))'
        class_pattern = r'class\s+(\w+)'
        
        for match in re.finditer(function_pattern, content, re.MULTILINE):
            start_line = content[:match.start()].count('\n')
            name = match.group(1) or match.group(2)
            end_line = self._find_block_end(lines, start_line)
            
            chunk = CodeChunk(
                content='\n'.join(lines[start_line:end_line + 1]),
                file_path=file_path,
                start_line=start_line + 1,
                end_line=end_line + 1,
                chunk_type='function',
                name=name or 'anonymous',
                metadata={'language': 'javascript'}
            )
            chunks.append(chunk)
        
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            start_line = content[:match.start()].count('\n')
            name = match.group(1)
            end_line = self._find_block_end(lines, start_line)
            
            chunk = CodeChunk(
                content='\n'.join(lines[start_line:end_line + 1]),
                file_path=file_path,
                start_line=start_line + 1,
                end_line=end_line + 1,
                chunk_type='class',
                name=name,
                metadata={'language': 'javascript'}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _get_node_content(self, node, lines: List[str]) -> str:
        """Get content for an AST node."""
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', node.lineno) - 1
        
        if end_line >= len(lines):
            end_line = len(lines) - 1
            
        return '\n'.join(lines[start_line:end_line + 1])
    
    def _extract_return_type(self, node) -> Optional[str]:
        """Extract return type annotation from function node."""
        if hasattr(node, 'returns') and node.returns:
            return ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        return None
    
    def _find_block_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a code block."""
        brace_count = 0
        in_block = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_block = True
                elif char == '}':
                    brace_count -= 1
                    if in_block and brace_count == 0:
                        return i
        
        return min(start_line + 50, len(lines) - 1)  # Fallback
    
    def _fallback_chunking(self, content: str, file_path: str) -> List[CodeChunk]:
        """Fallback to simple line-based chunking."""
        lines = content.split('\n')
        chunks = []
        
        chunk_size = 50  # lines per chunk
        for i in range(0, len(lines), chunk_size):
            end_line = min(i + chunk_size, len(lines))
            chunk_content = '\n'.join(lines[i:end_line])
            
            chunk = CodeChunk(
                content=chunk_content,
                file_path=file_path,
                start_line=i + 1,
                end_line=end_line,
                chunk_type='block',
                name=f'block_{i // chunk_size}',
                metadata={'fallback': True}
            )
            chunks.append(chunk)
        
        return chunks
    
    async def _generate_embeddings(self) -> None:
        """Generate embeddings for all code chunks."""
        try:
            logger.info(f"🔮 Generating embeddings for {len(self.code_chunks)} chunks")
            
            # Batch embedding generation for efficiency
            batch_size = 20
            for i in range(0, len(self.code_chunks), batch_size):
                batch = self.code_chunks[i:i + batch_size]
                texts = [self._prepare_text_for_embedding(chunk) for chunk in batch]
                
                try:
                    # Use OpenAI embeddings API
                    response = await self.openai_client.client.embeddings.create(
                        model="text-embedding-3-small",
                        input=texts
                    )
                    
                    for j, chunk in enumerate(batch):
                        embedding = np.array(response.data[j].embedding)
                        chunk.embedding = embedding
                        
                        # Cache embedding
                        chunk_hash = self._get_chunk_hash(chunk)
                        self.embeddings_cache[chunk_hash] = embedding
                
                except Exception as e:
                    logger.error(f"❌ Error generating embeddings for batch {i}: {e}")
                    # Set dummy embeddings as fallback
                    for chunk in batch:
                        chunk.embedding = np.random.random(1536)  # text-embedding-3-small size
            
            logger.info("✅ Embeddings generation completed")
            
        except Exception as e:
            logger.error(f"❌ Error in embedding generation: {e}")
    
    def _prepare_text_for_embedding(self, chunk: CodeChunk) -> str:
        """Prepare chunk text for embedding generation."""
        # Include context information
        context_parts = [
            f"File: {chunk.file_path}",
            f"Type: {chunk.chunk_type}",
            f"Name: {chunk.name}"
        ]
        
        if chunk.metadata.get('docstring'):
            context_parts.append(f"Description: {chunk.metadata['docstring']}")
        
        context = " | ".join(context_parts)
        return f"{context}\n\nCode:\n{chunk.content}"
    
    def _get_chunk_hash(self, chunk: CodeChunk) -> str:
        """Generate hash for chunk caching."""
        content = f"{chunk.file_path}:{chunk.content}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def search_similar_code(self, query: str, max_results: int = 10, 
                                 similarity_threshold: float = 0.7) -> List[Tuple[CodeChunk, float]]:
        """Search for code chunks similar to the query."""
        try:
            # Generate embedding for query
            response = await self.openai_client.client.embeddings.create(
                model="text-embedding-3-small",
                input=[query]
            )
            query_embedding = np.array(response.data[0].embedding)
            
            # Calculate similarities
            similarities = []
            for chunk in self.code_chunks:
                if chunk.embedding is not None:
                    similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                    if similarity >= similarity_threshold:
                        similarities.append((chunk, similarity))
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:max_results]
            
        except Exception as e:
            logger.error(f"❌ Error in semantic search: {e}")
            return []
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    async def find_related_to_error(self, error_description: str, stack_trace: str = "") -> List[CodeChunk]:
        """Find code chunks related to an error description."""
        query = f"Error: {error_description}\nStack trace: {stack_trace}"
        results = await self.search_similar_code(query, max_results=5)
        return [chunk for chunk, _ in results]
    
    async def find_similar_functions(self, function_name: str, function_content: str) -> List[CodeChunk]:
        """Find functions similar to the given function."""
        query = f"Function: {function_name}\nCode: {function_content}"
        results = await self.search_similar_code(query, max_results=8)
        
        # Filter to only return functions
        function_chunks = []
        for chunk, similarity in results:
            if chunk.chunk_type in ['function', 'method']:
                function_chunks.append(chunk)
        
        return function_chunks
    
    def get_chunk_by_location(self, file_path: str, line_number: int) -> Optional[CodeChunk]:
        """Get the code chunk containing a specific line."""
        for chunk in self.code_chunks:
            if (chunk.file_path == file_path and 
                chunk.start_line <= line_number <= chunk.end_line):
                return chunk
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the semantic index."""
        chunk_types = {}
        total_embeddings = 0
        
        for chunk in self.code_chunks:
            chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
            if chunk.embedding is not None:
                total_embeddings += 1
        
        return {
            'total_chunks': len(self.code_chunks),
            'chunk_types': chunk_types,
            'embeddings_generated': total_embeddings,
            'cache_size': len(self.embeddings_cache)
        }