
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from services.openai_client import OpenAIClient
from services.semantic_evaluator import SemanticEvaluator
import time

logger = logging.getLogger(__name__)

class LargeFileHandler:
    """Handler for processing large files with aggressive chunking and semantic evaluation"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.semantic_evaluator = SemanticEvaluator()
        self.chunk_size_limit = 12000  # Reduced from 15000 for better processing
        self.context_overlap_lines = 8  # Smart overlap: 5-10 lines for better context
        # Confidence thresholds for tiered evaluation
        self.low_confidence_threshold = 0.3
        self.high_confidence_threshold = 0.9
    
    def should_chunk_file(self, file_content: str) -> bool:
        """Determine if file should be processed in chunks - more aggressive"""
        return len(file_content) > self.chunk_size_limit
    
    def create_file_chunks(self, file_content: str, file_path: str) -> List[Dict[str, Any]]:
        """Create optimized chunks with smart overlap for context preservation - FIXED ALGORITHM"""
        if not self.should_chunk_file(file_content):
            return [{
                "content": file_content,
                "start_line": 1,
                "end_line": len(file_content.splitlines()),
                "chunk_id": 0,
                "is_single_chunk": True
            }]
        
        lines = file_content.splitlines(keepends=True)
        total_lines = len(lines)
        chunks = []
        chunk_id = 0
        
        # Calculate optimal lines per chunk with better distribution
        total_chars = len(file_content)
        chars_per_chunk = self.chunk_size_limit
        estimated_lines_per_chunk = max(40, int(total_lines * chars_per_chunk / total_chars))
        
        # Ensure reasonable chunk sizes
        min_lines_per_chunk = 30
        max_lines_per_chunk = min(200, total_lines // 2)  # Don't make chunks too large
        lines_per_chunk = max(min_lines_per_chunk, min(estimated_lines_per_chunk, max_lines_per_chunk))
        
        logger.info(f"📊 Chunking {file_path}: {total_lines} lines into ~{lines_per_chunk} lines per chunk with {self.context_overlap_lines}-line overlap")
        
        current_line = 0
        processed_line_ranges = set()  # Track processed ranges to prevent duplicates
        
        while current_line < total_lines:
            # Calculate chunk boundaries
            chunk_start = current_line
            chunk_end = min(current_line + lines_per_chunk, total_lines)
            
            # Add overlap from previous chunk for context
            overlap_start = max(0, chunk_start - self.context_overlap_lines)
            
            # CRITICAL FIX: Prevent duplicate chunks
            range_key = (overlap_start, chunk_end)
            if range_key in processed_line_ranges:
                logger.warning(f"⚠️ Detected duplicate chunk range {range_key}, advancing to prevent infinite loop")
                current_line = chunk_end
                continue
            
            processed_line_ranges.add(range_key)
            
            # Extract chunk content
            chunk_content = ''.join(lines[overlap_start:chunk_end])
            
            # Validate chunk size and adjust if necessary
            if len(chunk_content) > self.chunk_size_limit:
                # Reduce chunk size if it's too large
                reduced_end = chunk_start + (lines_per_chunk // 2)
                chunk_end = min(reduced_end, total_lines)
                chunk_content = ''.join(lines[overlap_start:chunk_end])
                logger.info(f"📏 Reduced chunk {chunk_id + 1} size from {len(''.join(lines[overlap_start:chunk_end]))} to {len(chunk_content)} chars")
            
            # SAFETY CHECK: Ensure chunk makes progress
            if chunk_end <= chunk_start and chunk_id > 0:
                logger.error(f"🚨 CHUNKING ERROR: Chunk {chunk_id + 1} would not advance (start={chunk_start}, end={chunk_end})")
                break
            
            # Create chunk metadata
            chunk_info = {
                "content": chunk_content,
                "start_line": chunk_start + 1,  # 1-based line numbers
                "end_line": chunk_end,
                "chunk_id": chunk_id,
                "is_single_chunk": False,
                "overlap_start": overlap_start + 1,  # 1-based
                "overlap_lines": min(self.context_overlap_lines, chunk_start),
                "total_chunks": 0,  # Will be filled later
                "size": len(chunk_content),
                "actual_lines": chunk_end - chunk_start,
                "with_overlap_lines": chunk_end - overlap_start
            }
            
            chunks.append(chunk_info)
            
            # CRITICAL FIX: Proper advancement logic
            # Move to next chunk position, ensuring we always make progress
            next_start = chunk_end
            
            # If we're near the end and would create a tiny chunk, merge with current
            remaining_lines = total_lines - next_start
            if remaining_lines > 0 and remaining_lines < min_lines_per_chunk:
                logger.info(f"📝 Merging remaining {remaining_lines} lines into current chunk {chunk_id + 1}")
                # Expand current chunk to include remaining lines
                expanded_content = ''.join(lines[overlap_start:total_lines])
                chunks[-1].update({
                    "content": expanded_content,
                    "end_line": total_lines,
                    "size": len(expanded_content),
                    "actual_lines": total_lines - chunk_start,
                    "with_overlap_lines": total_lines - overlap_start
                })
                break
            
            current_line = next_start
            chunk_id += 1
            
            # SAFETY LIMIT: Prevent infinite loops
            if chunk_id > 100:
                logger.error(f"🚨 SAFETY LIMIT: Reached maximum chunk limit (100) for {file_path}")
                break
        
        # Update total chunks count
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)
        
        # VALIDATION: Check for chunking quality
        total_processed_lines = sum(chunk["actual_lines"] for chunk in chunks)
        if total_processed_lines < total_lines * 0.9:  # Should cover at least 90% of file
            logger.warning(f"⚠️ Chunking may be incomplete: processed {total_processed_lines}/{total_lines} lines ({total_processed_lines/total_lines*100:.1f}%)")
        
        logger.info(f"✅ Created {len(chunks)} validated chunks for {file_path}")
        for i, chunk in enumerate(chunks):
            logger.info(f"  📦 Chunk {i+1}: lines {chunk['start_line']}-{chunk['end_line']} (actual: {chunk['actual_lines']}, with overlap: {chunk['with_overlap_lines']}), size: {chunk['size']} chars")
        
        return chunks
    
    def create_chunk_context(self, chunk: Dict[str, Any], file_info: Dict[str, Any], ticket) -> str:
        """Create enhanced context for chunk with explicit relevance requirements"""
        overlap_info = ""
        if not chunk.get('is_single_chunk', False):
            overlap_info = f"""
OVERLAP INFO:
- This chunk includes {chunk.get('overlap_lines', 0)} lines of overlap from the previous section for context
- Overlap starts at line {chunk.get('overlap_start', 'N/A')}
- Focus on lines {chunk['start_line']}-{chunk['end_line']} for actual changes
- Actual content lines: {chunk.get('actual_lines', 'N/A')}
"""
        
        return f"""
ENHANCED CHUNK ANALYSIS CONTEXT:
File: {file_info['path']}
Chunk {chunk['chunk_id'] + 1}/{chunk['total_chunks']}
Lines {chunk['start_line']}-{chunk['end_line']}
Content Length: {len(chunk['content'])} characters
{overlap_info}

ISSUE TO FIX (CRITICAL - READ CAREFULLY):
Title: {ticket.title}
Description: {ticket.description}
Error Trace: {ticket.error_trace or 'No error trace provided'}

CHUNK CONTENT:
```
{chunk['content']}
```

CRITICAL INSTRUCTIONS:
1. ONLY propose a fix if it directly resolves the issue described above
2. If this chunk doesn't contain code related to the issue, return confidence_score: 0.1
3. Analyze the problem thoroughly before proposing any changes
4. Consider the broader context and don't break existing functionality

REQUIRED RESPONSE FORMAT (JSON ONLY):
{{
    "confidence_score": 0.95,
    "relevance_score": 0.90,
    "patch_content": "unified diff format patch for this chunk only",
    "patched_code": "this chunk content after applying the fix",
    "explanation": "detailed technical explanation of the problem and solution",
    "justification": "Why do you think this change addresses the issue?",
    "chunk_id": {chunk['chunk_id']},
    "start_line": {chunk['start_line']},
    "end_line": {chunk['end_line']},
    "addresses_issue": true
}}

IMPORTANT: Generate ONLY valid JSON. If you're not confident this chunk contains the issue, set confidence_score to 0.1 and addresses_issue to false.
"""
    
    async def combine_chunk_patches(self, chunk_patches: List[Dict[str, Any]], file_info: Dict[str, Any], ticket) -> Optional[Dict[str, Any]]:
        """Combine multiple chunk patches with confidence-based tiered semantic evaluation"""
        if not chunk_patches:
            logger.warning(f"No chunk patches provided for {file_info['path']}")
            return None
        
        start_time = time.time()
        logger.info(f"🧠 Starting confidence-based semantic evaluation for {file_info['path']} with {len(chunk_patches)} patches")
        
        # Initialize processing counters
        evaluation_stats = {
            "total_chunks": len(chunk_patches),
            "skipped_low_confidence": 0,
            "fast_accepted_high_confidence": 0,
            "evaluated_medium_confidence": 0,
            "api_calls_saved": 0
        }
        
        # Tiered evaluation with confidence-based filtering
        evaluated_patches = []
        jira_context = {
            'title': ticket.title,
            'description': ticket.description,
            'error_trace': ticket.error_trace or ''
        }
        
        for i, patch in enumerate(chunk_patches):
            chunk_id = patch.get('chunk_id', i)
            confidence = patch.get('confidence_score', 0.0)
            
            # Tier 1: Skip very low confidence chunks
            if confidence < self.low_confidence_threshold:
                logger.info(f"[🚫 Skipped] Chunk #{chunk_id} skipped due to low confidence: {confidence:.3f}")
                evaluation_stats["skipped_low_confidence"] += 1
                evaluation_stats["api_calls_saved"] += 1
                continue
            
            # Tier 2: Fast accept very high confidence chunks
            elif confidence >= self.high_confidence_threshold:
                logger.info(f"[⚡ Fast Accept] Chunk #{chunk_id} accepted based on high confidence ({confidence:.3f})")
                
                # Create fast-accept evaluation without API calls
                evaluation = {
                    "relevance_score": 1.0,
                    "keyword_score": 0.8,
                    "similarity_score": 0.9,
                    "meets_threshold": True,
                    "evaluation_details": {
                        "issue_keywords": [],
                        "patch_keywords": [],
                        "common_keywords": []
                    }
                }
                
                patch_info = {
                    'patch': patch,
                    'evaluation': evaluation,
                    'should_accept': True,
                    'reason': f"High confidence score: {confidence:.3f}",
                    'combined_score': confidence,
                    'processing_tier': 'fast_accept'
                }
                
                evaluated_patches.append(patch_info)
                evaluation_stats["fast_accepted_high_confidence"] += 1
                evaluation_stats["api_calls_saved"] += 2  # Saved embedding API calls
            
            # Tier 3: Full semantic evaluation for medium confidence chunks
            else:
                try:
                    logger.info(f"[🔍 Evaluating] Chunk #{chunk_id}: Confidence={confidence:.3f} - Running full semantic evaluation")
                    
                    # Run full semantic evaluation with embeddings
                    evaluation = await self.semantic_evaluator.evaluate_patch_relevance(patch, jira_context)
                    should_accept, reason = self.semantic_evaluator.should_accept_patch(patch, evaluation)
                    
                    relevance = evaluation.get('relevance_score', 0)
                    logger.info(f"[🔍 Evaluated] Chunk #{chunk_id}: Confidence={confidence:.2f}, Relevance={relevance:.2f}, Reason={reason}")
                    
                    patch_info = {
                        'patch': patch,
                        'evaluation': evaluation,
                        'should_accept': should_accept,
                        'reason': reason,
                        'combined_score': (confidence * 0.6) + (relevance * 0.4),
                        'processing_tier': 'full_evaluation'
                    }
                    
                    evaluated_patches.append(patch_info)
                    evaluation_stats["evaluated_medium_confidence"] += 1
                    
                except Exception as e:
                    logger.error(f"Error evaluating patch for chunk {chunk_id}: {e}")
                    continue
        
        # Log processing summary
        processing_time = time.time() - start_time
        logger.info(f"📊 CONFIDENCE-BASED EVALUATION SUMMARY for {file_info['path']}:")
        logger.info(f"  - Total chunks: {evaluation_stats['total_chunks']}")
        logger.info(f"  - 🚫 Skipped (low confidence): {evaluation_stats['skipped_low_confidence']}")
        logger.info(f"  - ⚡ Fast accepted (high confidence): {evaluation_stats['fast_accepted_high_confidence']}")
        logger.info(f"  - 🔍 Evaluated (medium confidence): {evaluation_stats['evaluated_medium_confidence']}")
        logger.info(f"  - 💰 API calls saved: {evaluation_stats['api_calls_saved']}")
        logger.info(f"  - ⏱️ Processing time: {processing_time:.2f}s")
        
        # Filter patches that should be accepted
        accepted_patches = [p for p in evaluated_patches if p['should_accept']]
        rejected_patches = [p for p in evaluated_patches if not p['should_accept']]
        
        logger.info(f"✅ Accepted {len(accepted_patches)}/{len(evaluated_patches)} evaluated patches")
        logger.info(f"❌ Rejected {len(rejected_patches)} patches")
        
        # Log rejection reasons
        for rejected in rejected_patches:
            tier = rejected.get('processing_tier', 'unknown')
            logger.info(f"  - Chunk {rejected['patch'].get('chunk_id', 'N/A')} ({tier}): {rejected['reason']}")
        
        if not accepted_patches:
            fallback_msg = self.semantic_evaluator.get_fallback_message(len(chunk_patches), len(rejected_patches))
            logger.warning(f"No acceptable patches for {file_info['path']}: {fallback_msg}")
            return None
        
        # Sort accepted patches by combined score (best first)
        accepted_patches.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # If only one accepted patch, return it with enhancements
        if len(accepted_patches) == 1:
            best_patch = accepted_patches[0]
            enhanced_patch = best_patch['patch'].copy()
            enhanced_patch.update({
                'semantic_evaluation': best_patch['evaluation'],
                'selection_reason': f"Single high-quality patch: {best_patch['reason']}",
                'rejected_alternatives': len(rejected_patches),
                'processing_tier': best_patch.get('processing_tier', 'unknown'),
                'evaluation_stats': evaluation_stats
            })
            return enhanced_patch
        
        # Combine multiple high-quality patches
        logger.info(f"🔗 Combining {len(accepted_patches)} high-quality patches")
        
        # Sort patches by line number for proper combination
        accepted_patches.sort(key=lambda x: x['patch'].get('start_line', 0))
        
        combined_patch_content = []
        combined_explanation = []
        combined_justification = []
        combined_confidence = sum(p['patch'].get('confidence_score', 0) for p in accepted_patches) / len(accepted_patches)
        combined_relevance = sum(p['evaluation'].get('relevance_score', 0) for p in accepted_patches) / len(accepted_patches)
        
        for patch_info in accepted_patches:
            patch = patch_info['patch']
            tier = patch_info.get('processing_tier', 'unknown')
            combined_patch_content.append(patch.get('patch_content', ''))
            combined_explanation.append(f"Chunk {patch.get('chunk_id', 'N/A')} ({tier}): {patch.get('explanation', '')}")
            combined_justification.append(f"Chunk {patch.get('chunk_id', 'N/A')} ({tier}): {patch.get('justification', '')}")
        
        # Reconstruct full file content with all patches applied
        patched_code = file_info['content']
        for patch_info in accepted_patches:
            patch = patch_info['patch']
            if patch.get('patched_code'):
                patched_code = patch.get('patched_code')
        
        return {
            "patch_content": "\n\n".join(combined_patch_content),
            "patched_code": patched_code,
            "test_code": accepted_patches[0]['patch'].get('test_code', ''),
            "commit_message": f"Confidence-based multi-chunk fix for {file_info['path']} ({len(accepted_patches)} sections)",
            "confidence_score": min(combined_confidence, 0.95),
            "relevance_score": combined_relevance,
            "explanation": "\n\n".join(combined_explanation),
            "justification": "\n\n".join(combined_justification),
            "target_file": file_info['path'],
            "base_file_hash": file_info['hash'],
            "patch_type": "confidence_tiered_chunks",
            "chunks_processed": len(accepted_patches),
            "chunks_rejected": len(rejected_patches),
            "selection_summary": f"Tiered evaluation: {evaluation_stats['fast_accepted_high_confidence']} fast-accepted, {evaluation_stats['evaluated_medium_confidence']} evaluated, {evaluation_stats['skipped_low_confidence']} skipped",
            "semantic_evaluation": {
                "total_evaluated": len(evaluated_patches),
                "accepted_count": len(accepted_patches),
                "rejected_count": len(rejected_patches),
                "average_relevance": combined_relevance,
                "selection_criteria": f"Tiered: Skip <{self.low_confidence_threshold}, Fast ≥{self.high_confidence_threshold}, Evaluate middle range"
            },
            "performance_optimization": {
                "api_calls_saved": evaluation_stats["api_calls_saved"],
                "processing_time_seconds": processing_time,
                "efficiency_gain": f"{(evaluation_stats['api_calls_saved'] / evaluation_stats['total_chunks'] * 100):.1f}% API calls saved"
            }
        }
