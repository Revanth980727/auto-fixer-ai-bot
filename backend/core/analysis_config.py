
import os
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class APIConfig:
    """Configuration for all API-related settings"""
    
    def __init__(self):
        # GitHub API Configuration
        self.github_api_url = os.getenv("GITHUB_API_URL", "https://api.github.com")
        self.github_timeout = float(os.getenv("GITHUB_TIMEOUT", "30.0"))
        self.github_max_retries = int(os.getenv("GITHUB_MAX_RETRIES", "3"))
        
        # OpenAI API Configuration
        self.openai_timeout = float(os.getenv("OPENAI_TIMEOUT", "90.0"))
        self.openai_request_timeout = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "60.0"))
        self.openai_max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
        
        logger.info(f"API Config - GitHub URL: {self.github_api_url}")
        logger.info(f"API Config - GitHub timeout: {self.github_timeout}s")
        logger.info(f"API Config - OpenAI timeout: {self.openai_timeout}s")

class ModelConfig:
    """Configuration for AI model settings"""
    
    def __init__(self):
        # Model Selection
        self.default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o")
        self.analysis_model = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4o-mini")
        self.patch_generation_model = os.getenv("OPENAI_PATCH_MODEL", "gpt-4o")
        
        # Token Limits
        self.max_tokens_patch = int(os.getenv("OPENAI_MAX_TOKENS_PATCH", "3000"))
        self.max_tokens_analysis = int(os.getenv("OPENAI_MAX_TOKENS_ANALYSIS", "2000"))
        
        # Model Parameters
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        self.temperature_analysis = float(os.getenv("OPENAI_TEMPERATURE_ANALYSIS", "0.2"))
        
        logger.info(f"Model Config - Default: {self.default_model}")
        logger.info(f"Model Config - Analysis: {self.analysis_model}")
        logger.info(f"Model Config - Patch: {self.patch_generation_model}")

class ProcessingConfig:
    """Configuration for content processing and limits"""
    
    def __init__(self):
        # Content Truncation Limits
        self.error_trace_limit = int(os.getenv("ERROR_TRACE_LIMIT", "2000"))
        self.code_context_limit = int(os.getenv("CODE_CONTEXT_LIMIT", "2000"))
        self.analysis_content_limit = int(os.getenv("ANALYSIS_CONTENT_LIMIT", "1500"))
        self.file_content_limit = int(os.getenv("FILE_CONTENT_LIMIT", "3000"))
        self.description_content_limit = int(os.getenv("DESCRIPTION_CONTENT_LIMIT", "500"))
        
        # Chunk Processing
        self.max_chunk_tokens = int(os.getenv("MAX_CHUNK_TOKENS", "600"))
        self.overlap_tokens = int(os.getenv("OVERLAP_TOKENS", "100"))
        self.chars_per_token = int(os.getenv("CHARS_PER_TOKEN", "4"))
        
        # Concurrency Limits
        self.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
        self.max_analysis_files = int(os.getenv("MAX_ANALYSIS_FILES", "8"))
        
        logger.info(f"Processing Config - Error trace limit: {self.error_trace_limit}")
        logger.info(f"Processing Config - Max concurrent: {self.max_concurrent_requests}")

class AnalysisConfig:
    """Configuration for file analysis and scoring"""
    
    def __init__(self):
        # File Size Preferences
        self.min_file_size = int(os.getenv("MIN_FILE_SIZE", "100"))
        self.optimal_min_size = int(os.getenv("OPTIMAL_MIN_SIZE", "500"))
        self.optimal_max_size = int(os.getenv("OPTIMAL_MAX_SIZE", "50000"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "100000"))
        
        # Scoring Weights
        self.heuristic_weight = float(os.getenv("HEURISTIC_WEIGHT", "0.3"))
        self.semantic_weight = float(os.getenv("SEMANTIC_WEIGHT", "0.7"))
        self.error_match_score = float(os.getenv("ERROR_MATCH_SCORE", "10.0"))
        self.keyword_match_score = float(os.getenv("KEYWORD_MATCH_SCORE", "3.0"))
        self.main_file_score = float(os.getenv("MAIN_FILE_SCORE", "2.0"))
        self.size_preference_score = float(os.getenv("SIZE_PREFERENCE_SCORE", "1.0"))
        
        # File Type Scores
        self.python_file_score = float(os.getenv("PYTHON_FILE_SCORE", "1.0"))
        self.js_file_score = float(os.getenv("JS_FILE_SCORE", "0.8"))
        self.test_file_penalty = float(os.getenv("TEST_FILE_PENALTY", "-2.0"))
        
        # Analysis Thresholds
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
        self.min_semantic_score = float(os.getenv("MIN_SEMANTIC_SCORE", "0.1"))
        
        # File Patterns
        self.main_indicators = self._parse_list(os.getenv("MAIN_FILE_INDICATORS", "main,index,app,server,core,engine"))
        self.test_indicators = self._parse_list(os.getenv("TEST_FILE_INDICATORS", "test,spec,__pycache__,.git"))
        self.supported_extensions = self._parse_list(os.getenv("SUPPORTED_EXTENSIONS", "py,js,ts,jsx,tsx,java,cpp,c,h"))
        
        logger.info(f"Analysis Config - File size range: {self.optimal_min_size}-{self.optimal_max_size}")
        logger.info(f"Analysis Config - Scoring weights: heuristic={self.heuristic_weight}, semantic={self.semantic_weight}")
    
    def _parse_list(self, value: str) -> List[str]:
        """Parse comma-separated environment variable into list"""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

class FileTypeConfig:
    """Configuration for file type handling"""
    
    def __init__(self):
        # Language-specific file extensions
        self.python_extensions = self._parse_list(os.getenv("PYTHON_EXTENSIONS", "py,pyx,pyi"))
        self.javascript_extensions = self._parse_list(os.getenv("JAVASCRIPT_EXTENSIONS", "js,ts,jsx,tsx,mjs"))
        self.java_extensions = self._parse_list(os.getenv("JAVA_EXTENSIONS", "java,scala,kt"))
        self.cpp_extensions = self._parse_list(os.getenv("CPP_EXTENSIONS", "cpp,c,cc,cxx,h,hpp"))
        
        # Comment patterns for different languages
        self.comment_patterns = {
            'python': {'single': '#', 'multi_start': '"""', 'multi_end': '"""'},
            'javascript': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
            'java': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
            'cpp': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'}
        }
        
        # Default branch names
        self.default_branches = self._parse_list(os.getenv("DEFAULT_BRANCHES", "main,master,develop"))
        
        logger.info(f"FileType Config - Python exts: {self.python_extensions}")
        logger.info(f"FileType Config - JS exts: {self.javascript_extensions}")
    
    def _parse_list(self, value: str) -> List[str]:
        """Parse comma-separated environment variable into list"""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def get_language_for_extension(self, extension: str) -> str:
        """Get language type for file extension"""
        ext = extension.lower().lstrip('.')
        
        if ext in self.python_extensions:
            return 'python'
        elif ext in self.javascript_extensions:
            return 'javascript'
        elif ext in self.java_extensions:
            return 'java'
        elif ext in self.cpp_extensions:
            return 'cpp'
        else:
            return 'generic'

# Global configuration instances
api_config = APIConfig()
model_config = ModelConfig()
processing_config = ProcessingConfig()
analysis_config = AnalysisConfig()
file_type_config = FileTypeConfig()
