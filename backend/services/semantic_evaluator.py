
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
        self.relevance_threshold = 0.8
        self.confidence_threshold = 0.9
        self.keyword_weight = 0.4
        self.similarity_weight = 0.6
    
    async def evaluate_patch_relevance(self, patch_data: Dict[str, Any], jira_issue: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate how relevant a patch is to the JIRA issue"""
        logger.info(f"🔍 Evaluating patch relevance for {patch_data.get('target_file', 'unknown file')}")
        
        # Extract issue context
        issue_text = self._extract_issue_context(jira_issue)
        
        # Extract patch context
        patch_text = self._extract_patch_context(patch_data)
        
        # Calculate keyword overlap
        keyword_score = self._calculate_keyword_overlap(issue_text, patch_text)
        
        # Calculate semantic similarity using embeddings
        similarity_score = await self._calculate_semantic_similarity(issue_text, patch_text)
        
        # Combine scores
        relevance_score = (keyword_score * self.keyword_weight) + (similarity_score * self.similarity_weight)
        
        # Log individual scores for calibration
        logger.info(f"📊 Patch relevance scores:")
        logger.info(f"  - Keyword overlap: {keyword_score:.3f}")
        logger.info(f"  - Semantic similarity: {similarity_score:.3f}")
        logger.info(f"  - Combined relevance: {relevance_score:.3f}")
        
        return {
            "relevance_score": relevance_score,
            "keyword_score": keyword_score,
            "similarity_score": similarity_score,
            "meets_threshold": relevance_score >= self.relevance_threshold,
            "evaluation_details": {
                "issue_keywords": self._extract_keywords(issue_text),
                "patch_keywords": self._extract_keywords(patch_text),
                "common_keywords": self._get_common_keywords(issue_text, patch_text)
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
        """Determine if patch should be accepted based on confidence and relevance"""
        confidence = patch_data.get('confidence_score', 0.0)
        relevance = evaluation.get('relevance_score', 0.0)
        
        # Check thresholds
        confidence_ok = confidence >= self.confidence_threshold
        relevance_ok = relevance >= self.relevance_threshold
        
        if confidence_ok and relevance_ok:
            return True, f"High confidence ({confidence:.2f}) and relevance ({relevance:.2f})"
        elif confidence_ok and not relevance_ok:
            return False, f"High confidence ({confidence:.2f}) but low relevance ({relevance:.2f})"
        elif not confidence_ok and relevance_ok:
            return False, f"High relevance ({relevance:.2f}) but low confidence ({confidence:.2f})"
        else:
            return False, f"Low confidence ({confidence:.2f}) and relevance ({relevance:.2f})"
    
    def get_fallback_message(self, total_patches: int, rejected_patches: int) -> str:
        """Generate fallback message when no patches meet thresholds"""
        if total_patches == 0:
            return "No patches were generated for this file."
        elif rejected_patches == total_patches:
            return f"No confident and relevant fix was found. All {total_patches} generated patches were below quality thresholds. Manual inspection recommended."
        else:
            accepted = total_patches - rejected_patches
            return f"{accepted}/{total_patches} patches accepted. {rejected_patches} patches rejected due to low confidence or relevance."
