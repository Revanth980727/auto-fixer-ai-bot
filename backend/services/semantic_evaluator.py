
import numpy as np
import logging
from typing import Dict, Any, List, Tuple, Optional
from services.openai_client import OpenAIClient
import json
import re
from collections import Counter

logger = logging.getLogger(__name__)

class SemanticEvaluator:
    """Evaluates semantic relevance between JIRA issues and code fixes using embeddings and keyword analysis"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.relevance_threshold = 0.4  # Lowered from 0.8 for generic tickets
        self.confidence_threshold = 0.7  # Lowered from 0.9 for realistic acceptance
        self.keyword_weight = 0.3
        self.similarity_weight = 0.4
        self.context_weight = 0.3  # New weight for file context
    
    async def evaluate_patch_relevance(self, patch_data: Dict[str, Any], jira_issue: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate how relevant a patch is to the JIRA issue with enhanced context enrichment"""
        logger.info(f"🔍 Evaluating patch relevance for {patch_data.get('target_file', 'unknown file')}")
        
        # Extract and enrich issue context with file-specific information
        issue_text = self._extract_issue_context(jira_issue)
        enriched_issue_text = self._enrich_issue_context(issue_text, patch_data)
        
        # Extract patch context
        patch_text = self._extract_patch_context(patch_data)
        
        # Calculate keyword overlap with enriched context
        keyword_score = self._calculate_keyword_overlap(enriched_issue_text, patch_text)
        
        # Calculate semantic similarity using embeddings
        similarity_score = await self._calculate_semantic_similarity(enriched_issue_text, patch_text)
        
        # Calculate file context boost
        context_boost = self._calculate_file_context_boost(patch_data, jira_issue)
        
        # Multi-factor scoring with context boost
        base_relevance = (keyword_score * self.keyword_weight) + (similarity_score * self.similarity_weight)
        final_relevance = base_relevance + (context_boost * self.context_weight)
        
        # Clamp final score to [0, 1]
        final_relevance = max(0.0, min(1.0, final_relevance))
        
        # Log individual scores for calibration
        logger.info(f"📊 Enhanced patch relevance scores:")
        logger.info(f"  - Keyword overlap: {keyword_score:.3f}")
        logger.info(f"  - Semantic similarity: {similarity_score:.3f}")
        logger.info(f"  - File context boost: {context_boost:.3f}")
        logger.info(f"  - Base relevance: {base_relevance:.3f}")
        logger.info(f"  - Final relevance: {final_relevance:.3f}")
        
        return {
            "relevance_score": final_relevance,
            "keyword_score": keyword_score,
            "similarity_score": similarity_score,
            "context_boost": context_boost,
            "base_relevance": base_relevance,
            "meets_threshold": final_relevance >= self.relevance_threshold,
            "evaluation_details": {
                "issue_keywords": self._extract_keywords(enriched_issue_text),
                "patch_keywords": self._extract_keywords(patch_text),
                "common_keywords": self._get_common_keywords(enriched_issue_text, patch_text),
                "enriched_context": enriched_issue_text != issue_text
            }
        }
    
    def _extract_issue_context(self, jira_issue: Dict[str, Any]) -> str:
        """Extract relevant text from JIRA issue"""
        title = jira_issue.get('title', '')
        description = jira_issue.get('description', '')
        error_trace = jira_issue.get('error_trace', '')
        
        # Combine and clean the text
        combined_text = f"{title} {description} {error_trace}"
        return self._clean_text(combined_text)
    
    def _extract_patch_context(self, patch_data: Dict[str, Any]) -> str:
        """Extract relevant text from patch data"""
        explanation = patch_data.get('explanation', '')
        patch_content = patch_data.get('patch_content', '')
        justification = patch_data.get('justification', '')
        
        # Combine and clean the text
        combined_text = f"{explanation} {patch_content} {justification}"
        return self._clean_text(combined_text)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for analysis"""
        # Remove code syntax and special characters
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text.lower()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        # Common stop words to ignore
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'up', 'about', 'into', 'over', 'after', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'a', 'an', 'if', 'then', 'else', 'when', 'where', 'why',
            'how', 'what', 'which', 'who', 'whom', 'whose', 'all', 'any', 'both',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very'
        }
        
        words = text.split()
        keywords = []
        
        for word in words:
            if len(word) > 3 and word not in stop_words:
                keywords.append(word)
        
        return keywords
    
    def _calculate_keyword_overlap(self, issue_text: str, patch_text: str) -> float:
        """Calculate keyword overlap score between issue and patch"""
        issue_keywords = set(self._extract_keywords(issue_text))
        patch_keywords = set(self._extract_keywords(patch_text))
        
        if not issue_keywords or not patch_keywords:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(issue_keywords.intersection(patch_keywords))
        union = len(issue_keywords.union(patch_keywords))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _get_common_keywords(self, issue_text: str, patch_text: str) -> List[str]:
        """Get common keywords between issue and patch"""
        issue_keywords = set(self._extract_keywords(issue_text))
        patch_keywords = set(self._extract_keywords(patch_text))
        return list(issue_keywords.intersection(patch_keywords))
    
    async def _calculate_semantic_similarity(self, issue_text: str, patch_text: str) -> float:
        """Calculate semantic similarity using OpenAI embeddings"""
        try:
            # Get embeddings for both texts
            issue_embedding = await self._get_text_embedding(issue_text)
            patch_embedding = await self._get_text_embedding(patch_text)
            
            if issue_embedding is None or patch_embedding is None:
                logger.warning("Failed to get embeddings, falling back to keyword-only scoring")
                return 0.0
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(issue_embedding, patch_embedding)
            return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
            
        except Exception as e:
            logger.error(f"Error calculating semantic similarity: {e}")
            return 0.0
    
    async def _get_text_embedding(self, text: str) -> Optional[List[float]]:
        """Get OpenAI embedding for text"""
        try:
            if not self.openai_client.client:
                return None
            
            # Truncate text to avoid API limits
            truncated_text = text[:8000]
            
            response = await self.openai_client.client.embeddings.create(
                model="text-embedding-3-small",
                input=truncated_text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            # Convert to numpy arrays
            a = np.array(vec1)
            b = np.array(vec2)
            
            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return dot_product / (norm_a * norm_b)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def should_accept_patch(self, patch_data: Dict[str, Any], evaluation: Dict[str, Any]) -> Tuple[bool, str]:
        """Enhanced multi-factor patch acceptance with tiered logic and safety constraints"""
        confidence = patch_data.get('confidence_score', 0.0)
        relevance = evaluation.get('relevance_score', 0.0)
        context_boost = evaluation.get('context_boost', 0.0)
        lines_modified = patch_data.get('lines_modified', 0)
        
        # Calculate multi-factor score
        final_score = (0.5 * relevance) + (0.3 * confidence) + (0.2 * context_boost)
        final_score = max(0.0, min(1.0, final_score))  # Clamp to [0, 1]
        
        # Tier 1: High confidence + High relevance (always accept)
        if confidence >= 0.9 and relevance >= 0.8:
            return True, f"Tier 1: High confidence ({confidence:.2f}) and relevance ({relevance:.2f})"
        
        # Tier 2: Small patches with high confidence (safe minimal fixes)
        elif lines_modified <= 5 and confidence >= 0.9:
            return True, f"Tier 2: Small patch ({lines_modified} lines) with high confidence ({confidence:.2f})"
        
        # Tier 3: Multi-factor scoring for borderline cases
        elif final_score >= 0.6:
            return True, f"Tier 3: Multi-factor score ({final_score:.2f}) - confidence: {confidence:.2f}, relevance: {relevance:.2f}, context: {context_boost:.2f}"
        
        # Tier 4: Reject everything else
        else:
            return False, f"Rejected: Multi-factor score ({final_score:.2f}) below threshold - confidence: {confidence:.2f}, relevance: {relevance:.2f}, context: {context_boost:.2f}"
    
    def get_fallback_message(self, total_patches: int, rejected_patches: int) -> str:
        """Generate fallback message when no patches meet thresholds"""
        if total_patches == 0:
            return "No patches were generated for this file."
        elif rejected_patches == total_patches:
            return f"No confident and relevant fix was found. All {total_patches} generated patches were below quality thresholds. Manual inspection recommended."
        else:
            accepted = total_patches - rejected_patches
            return f"{accepted}/{total_patches} patches accepted. {rejected_patches} patches rejected due to low confidence or relevance."

    def _enrich_issue_context(self, issue_text: str, patch_data: Dict[str, Any]) -> str:
        """Enrich JIRA issue context with file-specific information from the patch"""
        enriched_text = issue_text
        
        # Add target file information
        target_file = patch_data.get('target_file', '')
        if target_file:
            file_name = target_file.split('/')[-1]  # Get just the filename
            file_extension = file_name.split('.')[-1] if '.' in file_name else ''
            enriched_text += f" target_file {file_name} {file_extension}"
        
        # Extract technical context from patch content
        patch_content = patch_data.get('patch_content', '')
        if patch_content:
            # Extract import statements
            import_matches = re.findall(r'import\s+(\w+)', patch_content)
            for imp in import_matches:
                enriched_text += f" import_{imp}"
            
            # Extract function names being modified
            function_matches = re.findall(r'def\s+(\w+)', patch_content)
            for func in function_matches:
                enriched_text += f" function_{func}"
            
            # Extract class names
            class_matches = re.findall(r'class\s+(\w+)', patch_content)
            for cls in class_matches:
                enriched_text += f" class_{cls}"
        
        # Add explanation context (AI's understanding of what the patch does)
        explanation = patch_data.get('explanation', '')
        if explanation:
            enriched_text += f" {explanation}"
        
        return enriched_text

    def _calculate_file_context_boost(self, patch_data: Dict[str, Any], jira_issue: Dict[str, Any]) -> float:
        """Calculate boost score based on file context and common error patterns"""
        boost = 0.0
        
        # File targeting boost - if the file was specifically selected for this ticket
        target_file = patch_data.get('target_file', '')
        if target_file:
            # Check if file mentioned in error trace or description
            error_trace = jira_issue.get('error_trace', '')
            description = jira_issue.get('description', '')
            combined_text = f"{error_trace} {description}".lower()
            
            file_name = target_file.split('/')[-1].lower()
            if file_name in combined_text or target_file.lower() in combined_text:
                boost += 0.3  # Strong boost for files mentioned in ticket
        
        # Technical pattern boost - common fix patterns get relevance boost
        patch_content = patch_data.get('patch_content', '').lower()
        explanation = patch_data.get('explanation', '').lower()
        combined_patch_text = f"{patch_content} {explanation}"
        
        # Import/syntax fixes
        if any(pattern in combined_patch_text for pattern in ['import', 'syntax', 'alias', 'missing']):
            boost += 0.2  # Import and syntax fixes are common and often relevant
        
        # Error handling fixes
        if any(pattern in combined_patch_text for pattern in ['error', 'exception', 'fix', 'bug']):
            boost += 0.15  # Error fixes get moderate boost
        
        # Null/undefined fixes
        if any(pattern in combined_patch_text for pattern in ['null', 'none', 'undefined', 'missing']):
            boost += 0.1  # Null checks and missing value fixes
        
        # Type/reference fixes
        if any(pattern in combined_patch_text for pattern in ['type', 'reference', 'attribute']):
            boost += 0.1  # Type and reference fixes
        
        return min(boost, 0.5)  # Cap boost at 0.5 to avoid over-boosting
