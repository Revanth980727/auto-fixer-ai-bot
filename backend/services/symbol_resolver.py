import ast
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Symbol:
    """Represents a symbol in the codebase."""
    name: str
    symbol_type: str  # 'function', 'class', 'variable', 'import'
    file_path: str
    line_number: int
    end_line: int
    definition: str
    scope: str
    references: List[Tuple[str, int]] = None  # [(file_path, line_number)]
    
    def __post_init__(self):
        if self.references is None:
            self.references = []

class SymbolResolver:
    """AST-based symbol resolution for 'go to definition' and 'find references'."""
    
    def __init__(self):
        self.symbol_table: Dict[str, Symbol] = {}
        self.file_symbols: Dict[str, List[Symbol]] = {}
        self.reference_map: Dict[str, List[Tuple[str, int]]] = {}
        
    def build_symbol_table(self, repository_files: List[Dict[str, Any]]) -> None:
        """Build comprehensive symbol table from repository files."""
        try:
            logger.info(f"🔍 Building symbol table from {len(repository_files)} files")
            
            self.symbol_table.clear()
            self.file_symbols.clear()
            self.reference_map.clear()
            
            # First pass: Extract all definitions
            for file_info in repository_files:
                if self._is_python_file(file_info.get('path', '')):
                    self._extract_definitions(file_info)
            
            # Second pass: Find all references
            for file_info in repository_files:
                if self._is_python_file(file_info.get('path', '')):
                    self._find_references(file_info)
            
            logger.info(f"✅ Symbol table built: {len(self.symbol_table)} symbols across {len(self.file_symbols)} files")
            
        except Exception as e:
            logger.error(f"❌ Error building symbol table: {e}")
    
    def _is_python_file(self, file_path: str) -> bool:
        """Check if file is a Python file."""
        return file_path.endswith('.py')
    
    def _extract_definitions(self, file_info: Dict[str, Any]) -> None:
        """Extract symbol definitions from a file."""
        try:
            content = file_info.get('content', '')
            file_path = file_info.get('path', '')
            
            if not content:
                return
                
            tree = ast.parse(content)
            lines = content.split('\n')
            
            file_symbols = []
            
            for node in ast.walk(tree):
                symbols = self._extract_node_symbols(node, file_path, lines)
                file_symbols.extend(symbols)
                
                for symbol in symbols:
                    self.symbol_table[f"{file_path}:{symbol.name}"] = symbol
            
            self.file_symbols[file_path] = file_symbols
            
        except SyntaxError:
            logger.warning(f"⚠️ Syntax error in {file_path}, skipping symbol extraction")
        except Exception as e:
            logger.error(f"❌ Error extracting definitions from {file_path}: {e}")
    
    def _extract_node_symbols(self, node: ast.AST, file_path: str, lines: List[str]) -> List[Symbol]:
        """Extract symbols from an AST node."""
        symbols = []
        
        if isinstance(node, ast.FunctionDef):
            symbols.append(Symbol(
                name=node.name,
                symbol_type='function',
                file_path=file_path,
                line_number=node.lineno,
                end_line=getattr(node, 'end_lineno', node.lineno),
                definition=self._get_node_definition(node, lines),
                scope=self._get_scope(node)
            ))
        
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(Symbol(
                name=node.name,
                symbol_type='async_function',
                file_path=file_path,
                line_number=node.lineno,
                end_line=getattr(node, 'end_lineno', node.lineno),
                definition=self._get_node_definition(node, lines),
                scope=self._get_scope(node)
            ))
        
        elif isinstance(node, ast.ClassDef):
            symbols.append(Symbol(
                name=node.name,
                symbol_type='class',
                file_path=file_path,
                line_number=node.lineno,
                end_line=getattr(node, 'end_lineno', node.lineno),
                definition=self._get_node_definition(node, lines),
                scope=self._get_scope(node)
            ))
        
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                symbols.append(Symbol(
                    name=alias.asname or alias.name,
                    symbol_type='import',
                    file_path=file_path,
                    line_number=node.lineno,
                    end_line=node.lineno,
                    definition=self._get_node_definition(node, lines),
                    scope='module'
                ))
        
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append(Symbol(
                        name=target.id,
                        symbol_type='variable',
                        file_path=file_path,
                        line_number=node.lineno,
                        end_line=node.lineno,
                        definition=self._get_node_definition(node, lines),
                        scope=self._get_scope(node)
                    ))
        
        return symbols
    
    def _get_node_definition(self, node: ast.AST, lines: List[str]) -> str:
        """Get the definition text for a node."""
        try:
            start_line = node.lineno - 1
            end_line = getattr(node, 'end_lineno', node.lineno) - 1
            
            if end_line >= len(lines):
                end_line = len(lines) - 1
                
            return '\n'.join(lines[start_line:end_line + 1])
        except:
            return ""
    
    def _get_scope(self, node: ast.AST) -> str:
        """Determine the scope of a node."""
        # Simple scope detection - can be enhanced
        if hasattr(node, 'col_offset') and node.col_offset == 0:
            return 'module'
        else:
            return 'local'
    
    def _find_references(self, file_info: Dict[str, Any]) -> None:
        """Find all references to symbols in a file."""
        try:
            content = file_info.get('content', '')
            file_path = file_info.get('path', '')
            
            if not content:
                return
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    symbol_key = f"{file_path}:{node.id}"
                    if symbol_key in self.symbol_table:
                        self.symbol_table[symbol_key].references.append((file_path, node.lineno))
                    
                    # Also check for cross-file references
                    for key, symbol in self.symbol_table.items():
                        if symbol.name == node.id and symbol.file_path != file_path:
                            symbol.references.append((file_path, node.lineno))
                            
        except SyntaxError:
            pass  # Already logged in _extract_definitions
        except Exception as e:
            logger.error(f"❌ Error finding references in {file_path}: {e}")
    
    def go_to_definition(self, file_path: str, line_number: int, symbol_name: str) -> Optional[Symbol]:
        """Find the definition of a symbol."""
        # First try exact file match
        symbol_key = f"{file_path}:{symbol_name}"
        if symbol_key in self.symbol_table:
            return self.symbol_table[symbol_key]
        
        # Then try to find in other files
        for symbol in self.symbol_table.values():
            if symbol.name == symbol_name:
                return symbol
        
        return None
    
    def find_references(self, symbol_name: str, file_path: Optional[str] = None) -> List[Tuple[str, int]]:
        """Find all references to a symbol."""
        references = []
        
        for symbol in self.symbol_table.values():
            if symbol.name == symbol_name:
                if file_path is None or symbol.file_path == file_path:
                    references.extend(symbol.references)
        
        return list(set(references))  # Remove duplicates
    
    def get_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """Get all symbols defined in a file."""
        return self.file_symbols.get(file_path, [])
    
    def find_related_symbols(self, symbol_name: str, max_results: int = 10) -> List[Symbol]:
        """Find symbols related to the given symbol."""
        related = []
        
        for symbol in self.symbol_table.values():
            # Check if symbol is referenced in the same files
            symbol_files = {ref[0] for ref in symbol.references}
            target_symbol = self.symbol_table.get(f"{symbol.file_path}:{symbol_name}")
            
            if target_symbol:
                target_files = {ref[0] for ref in target_symbol.references}
                if symbol_files.intersection(target_files):
                    related.append(symbol)
        
        return related[:max_results]
    
    def get_symbol_context(self, symbol: Symbol, context_lines: int = 5) -> Dict[str, Any]:
        """Get extended context around a symbol definition."""
        try:
            # This would need file content access - simplified for now
            return {
                'symbol': symbol,
                'context_start': max(0, symbol.line_number - context_lines),
                'context_end': symbol.end_line + context_lines,
                'references_count': len(symbol.references),
                'related_symbols': self.find_related_symbols(symbol.name, 5)
            }
        except Exception as e:
            logger.error(f"❌ Error getting symbol context: {e}")
            return {'symbol': symbol}