
import asyncio
import logging
from typing import List, Dict, Any, Optional
from services.openai_client import OpenAIClient
from services.code_preprocessor import CodePreprocessor
import json

logger = logging.getLogger(__name__)

class SemanticAnalyzer:
    """Analyzes code semantically using LLM to understand purpose and relevance"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.preprocessor = CodePreprocessor()
        self.max_concurrent_requests = 3  # Limit concurrent OpenAI requests
    
    async def analyze_files_for_relevance(self, files: List[Dict], project_context: Dict[str, Any]) -> List[Dict]:
        """Analyze multiple files for relevance to project context"""
        logger.info(f"🔍 Starting semantic analysis for {len(files)} files")
        
        # First, do quick heuristic filtering to get top candidates
        top_candidates = self._heuristic_prefilter(files, project_context)
        logger.info(f"📊 Heuristic filtering selected {len(top_candidates)} candidates for semantic analysis")
        
        # Analyze top candidates with LLM
        analyzed_files = await self._analyze_files_with_llm(top_candidates, project_context)
        
        # Combine analyzed files with remaining files (with lower default scores)
        remaining_files = [f for f in files if f['path'] not in {af['path'] for af in analyzed_files}]
        for file in remaining_files:
            file['semantic_score'] = 0.1  # Low default score
            file['semantic_analysis'] = "Not analyzed - filtered out by heuristics"
        
        all_files = analyzed_files + remaining_files
        
        # Calculate final relevance scores
        scored_files = self._calculate_final_scores(all_files, project_context)
        
        logger.info(f"✅ Semantic analysis completed for {len(files)} files")
        return scored_files
    
    def _heuristic_prefilter(self, files: List[Dict], project_context: Dict[str, Any]) -> List[Dict]:
        """Quick heuristic filtering to select top candidates for expensive LLM analysis"""
        scored_files = []
        
        # Extract project keywords from context
        project_keywords = self._extract_project_keywords(project_context)
        error_files = project_context.get('error_files', set())
        
        for file in files:
            path = file['path']
            filename = path.split('/')[-1].lower()
            path_lower = path.lower()
            
            heuristic_score = 0.0
            
            # Error trace matches (highest priority)
            for error_file in error_files:
                if error_file.lower() in path_lower or path.endswith(error_file):
                    heuristic_score += 10.0
                elif filename == error_file.lower().split('/')[-1]:
                    heuristic_score += 8.0
            
            # Project keyword matches
            for keyword in project_keywords:
                if keyword.lower() in path_lower:
                    heuristic_score += 3.0
                if keyword.lower() in filename:
                    heuristic_score += 2.0
            
            # Main file indicators
            main_indicators = ['main', 'index', 'app', 'server', 'core', 'engine']
            for indicator in main_indicators:
                if indicator in filename:
                    heuristic_score += 2.0
            
            # File type preferences
            if path.endswith('.py'):
                heuristic_score += 1.0
            elif path.endswith(('.js', '.ts', '.tsx', '.jsx')):
                heuristic_score += 0.8
            
            # Avoid test files and config files for general analysis
            if any(test_indicator in path_lower for test_indicator in ['test', 'spec', '__pycache__', '.git']):
                heuristic_score -= 2.0
            
            # Reasonable size preference (not too small, not too large)
            size = file.get('size', 0)
            if 500 <= size <= 50000:  # Sweet spot for meaningful files
                heuristic_score += 1.0
            elif size > 100000:  # Very large files
                heuristic_score -= 1.0
            elif size < 100:  # Very small files
                heuristic_score -= 0.5
            
            file['heuristic_score'] = heuristic_score
            scored_files.append(file)
        
        # Sort by heuristic score and take top candidates
        scored_files.sort(key=lambda x: x['heuristic_score'], reverse=True)
        top_count = min(8, len(scored_files))  # Analyze top 8 files with LLM
        return scored_files[:top_count]
    
    def _extract_project_keywords(self, project_context: Dict[str, Any]) -> List[str]:
        """Extract relevant keywords from project context"""
        keywords = []
        
        # From ticket title and description
        title = project_context.get('ticket_title', '').lower()
        description = project_context.get('ticket_description', '').lower()
        
        # Extract meaningful words (ignore common words)
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after'}
        
        for text in [title, description]:
            words = text.split()
            for word in words:
                clean_word = word.strip('.,!?;:"()[]{}')
                if len(clean_word) > 3 and clean_word not in common_words:
                    keywords.append(clean_word)
        
        # From repository or project name if available
        repo_name = project_context.get('repository_name', '')
        if repo_name:
            keywords.extend(repo_name.lower().split('-'))
            keywords.extend(repo_name.lower().split('_'))
        
        return list(set(keywords))[:10]  # Limit to top 10 unique keywords
    
    async def _analyze_files_with_llm(self, files: List[Dict], project_context: Dict[str, Any]) -> List[Dict]:
        """Analyze files using LLM in parallel batches"""
        if not files:
            return []
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # Create analysis tasks
        tasks = []
        for file in files:
            task = self._analyze_single_file(file, project_context, semaphore)
            tasks.append(task)
        
        # Execute tasks in parallel
        analyzed_files = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful analyses
        successful_analyses = []
        for i, result in enumerate(analyzed_files):
            if isinstance(result, Exception):
                logger.warning(f"Failed to analyze file {files[i]['path']}: {result}")
                # Add with default values
                file = files[i].copy()
                file['semantic_score'] = 0.2
                file['semantic_analysis'] = f"Analysis failed: {str(result)}"
                successful_analyses.append(file)
            else:
                successful_analyses.append(result)
        
        return successful_analyses
    
    async def _analyze_single_file(self, file: Dict, project_context: Dict[str, Any], semaphore: asyncio.Semaphore) -> Dict:
        """Analyze a single file using LLM"""
        async with semaphore:
            try:
                # Preprocess the file
                preprocessed = self.preprocessor.preprocess_file(file['path'], file['content'])
                
                # Analyze each chunk
                chunk_analyses = []
                for chunk in preprocessed.get('chunks', []):
                    analysis = await self._analyze_chunk(chunk, file['path'], project_context)
                    if analysis:
                        chunk_analyses.append(analysis)
                
                # Combine chunk analyses
                combined_analysis = self._combine_chunk_analyses(chunk_analyses)
                
                # Calculate semantic score based on analysis
                semantic_score = self._calculate_semantic_score(combined_analysis, project_context)
                
                result = file.copy()
                result['semantic_score'] = semantic_score
                result['semantic_analysis'] = combined_analysis
                result['preprocessing_stats'] = {
                    'compression_ratio': preprocessed.get('compression_ratio', 0),
                    'chunks_analyzed': len(chunk_analyses)
                }
                
                return result
                
            except Exception as e:
                logger.error(f"Error analyzing file {file['path']}: {e}")
                result = file.copy()
                result['semantic_score'] = 0.1
                result['semantic_analysis'] = f"Analysis error: {str(e)}"
                return result
    
    async def _analyze_chunk(self, chunk: Dict, file_path: str, project_context: Dict[str, Any]) -> Optional[str]:
        """Analyze a single code chunk with LLM"""
        try:
            prompt = f"""Analyze this code chunk from file '{file_path}' and respond with a JSON object containing:
- "purpose": Brief description of what this code does (max 50 words)
- "keywords": List of 3-5 key technical terms/concepts
- "complexity": "low", "medium", or "high"
- "relevance_indicators": List of terms that would make this relevant to different types of issues

Code chunk:
{chunk['content'][:2000]}"""  # Limit chunk size for API

            response = await self.openai_client.complete_chat(
                [{"role": "user", "content": prompt}],
                model="gpt-4o-mini",  # Use faster, cheaper model for chunk analysis
                max_retries=1
            )
            
            # Try to parse JSON response
            try:
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                # Fallback to text analysis
                return {"purpose": response[:100], "keywords": [], "complexity": "medium", "relevance_indicators": []}
                
        except Exception as e:
            logger.warning(f"Failed to analyze chunk: {e}")
            return None
    
    def _combine_chunk_analyses(self, chunk_analyses: List[Dict]) -> Dict[str, Any]:
        """Combine multiple chunk analyses into a single file analysis"""
        if not chunk_analyses:
            return {"purpose": "Unknown", "keywords": [], "complexity": "low", "relevance_indicators": []}
        
        # Combine purposes
        purposes = [analysis.get("purpose", "") for analysis in chunk_analyses if analysis.get("purpose")]
        combined_purpose = " | ".join(purposes[:3])  # Take first 3 purposes
        
        # Combine keywords
        all_keywords = []
        for analysis in chunk_analyses:
            all_keywords.extend(analysis.get("keywords", []))
        unique_keywords = list(set(all_keywords))[:10]  # Top 10 unique keywords
        
        # Determine overall complexity
        complexities = [analysis.get("complexity", "low") for analysis in chunk_analyses]
        complexity_scores = {"low": 1, "medium": 2, "high": 3}
        avg_complexity = sum(complexity_scores.get(c, 1) for c in complexities) / len(complexities)
        
        if avg_complexity >= 2.5:
            overall_complexity = "high"
        elif avg_complexity >= 1.5:
            overall_complexity = "medium"
        else:
            overall_complexity = "low"
        
        # Combine relevance indicators
        all_indicators = []
        for analysis in chunk_analyses:
            all_indicators.extend(analysis.get("relevance_indicators", []))
        unique_indicators = list(set(all_indicators))[:15]
        
        return {
            "purpose": combined_purpose,
            "keywords": unique_keywords,
            "complexity": overall_complexity,
            "relevance_indicators": unique_indicators,
            "chunks_analyzed": len(chunk_analyses)
        }
    
    def _calculate_semantic_score(self, analysis: Dict[str, Any], project_context: Dict[str, Any]) -> float:
        """Calculate semantic relevance score based on analysis and project context"""
        score = 0.0
        
        # Extract context information
        ticket_title = project_context.get('ticket_title', '').lower()
        ticket_description = project_context.get('ticket_description', '').lower()
        error_trace = project_context.get('error_trace', '').lower()
        
        # Combine all context text
        context_text = f"{ticket_title} {ticket_description} {error_trace}"
        
        # Score based on keyword matches
        keywords = analysis.get('keywords', [])
        for keyword in keywords:
            if keyword.lower() in context_text:
                score += 2.0
        
        # Score based on relevance indicators
        relevance_indicators = analysis.get('relevance_indicators', [])
        for indicator in relevance_indicators:
            if indicator.lower() in context_text:
                score += 1.5
        
        # Score based on purpose alignment
        purpose = analysis.get('purpose', '').lower()
        purpose_words = purpose.split()
        for word in purpose_words:
            if len(word) > 3 and word in context_text:
                score += 1.0
        
        # Complexity bonus (more complex files might be more relevant for fixing issues)
        complexity = analysis.get('complexity', 'low')
        if complexity == 'high':
            score += 1.0
        elif complexity == 'medium':
            score += 0.5
        
        # Normalize score to 0-10 range
        max_possible_score = len(keywords) * 2 + len(relevance_indicators) * 1.5 + len(purpose_words) * 1 + 1
        if max_possible_score > 0:
            normalized_score = min(10.0, (score / max_possible_score) * 10)
        else:
            normalized_score = 0.1
        
        return max(0.1, normalized_score)  # Ensure minimum score
    
    def _calculate_final_scores(self, files: List[Dict], project_context: Dict[str, Any]) -> List[Dict]:
        """Calculate final relevance scores combining heuristic and semantic scores"""
        for file in files:
            heuristic_score = file.get('heuristic_score', 0.0)
            semantic_score = file.get('semantic_score', 0.1)
            
            # Weight the scores (semantic analysis is more important but heuristics help)
            final_score = (semantic_score * 0.7) + (min(heuristic_score, 10.0) * 0.3)
            
            file['final_relevance_score'] = final_score
        
        # Sort by final score
        files.sort(key=lambda x: x['final_relevance_score'], reverse=True)
        return files
