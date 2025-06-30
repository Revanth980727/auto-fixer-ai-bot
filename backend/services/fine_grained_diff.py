
import difflib
import re
from typing import List, Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class FineGrainedDiffGenerator:
    """Generate minimal, fine-grained diffs that only modify necessary lines."""
    
    def __init__(self):
        self.max_hunk_size = 10  # Warn if hunks are larger than this
        self.context_lines = 3   # Number of context lines to include
    
    def generate_minimal_diff(self, original_content: str, new_content: str, file_path: str) -> Dict[str, Any]:
        """Generate a minimal unified diff with fine-grained line-level changes."""
        try:
            # Split content into lines for line-by-line comparison
            original_lines = original_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            
            # Generate unified diff with minimal context
            diff_lines = list(difflib.unified_diff(
                original_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=self.context_lines,  # Minimal context lines
                lineterm=""
            ))
            
            if not diff_lines:
                logger.info(f"No changes detected for {file_path}")
                return {
                    "success": True,
                    "has_changes": False,
                    "diff_content": "",
                    "change_summary": "No changes needed"
                }
            
            # Convert diff lines to string
            diff_content = '\n'.join(diff_lines)
            
            # Analyze the diff for quality
            analysis = self._analyze_diff_quality(diff_lines, file_path)
            
            logger.info(f"Generated fine-grained diff for {file_path}")
            logger.info(f"  - Hunks: {analysis['hunk_count']}")
            logger.info(f"  - Lines added: {analysis['lines_added']}")
            logger.info(f"  - Lines removed: {analysis['lines_removed']}")
            logger.info(f"  - Large hunks: {analysis['large_hunks']}")
            
            return {
                "success": True,
                "has_changes": True,
                "diff_content": diff_content,
                "change_summary": self._generate_change_summary(analysis),
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"Error generating fine-grained diff for {file_path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _analyze_diff_quality(self, diff_lines: List[str], file_path: str) -> Dict[str, Any]:
        """Analyze the quality and characteristics of a diff."""
        analysis = {
            "hunk_count": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "lines_modified": 0,
            "large_hunks": 0,
            "hunks": [],
            "quality_score": 0.0
        }
        
        current_hunk = None
        in_hunk = False
        
        for line in diff_lines:
            if line.startswith('@@'):
                # New hunk header
                if current_hunk:
                    analysis["hunks"].append(current_hunk)
                
                analysis["hunk_count"] += 1
                current_hunk = {
                    "header": line,
                    "added": 0,
                    "removed": 0,
                    "context": 0,
                    "size": 0
                }
                in_hunk = True
                
            elif in_hunk and line.startswith('+') and not line.startswith('+++'):
                current_hunk["added"] += 1
                current_hunk["size"] += 1
                analysis["lines_added"] += 1
                
            elif in_hunk and line.startswith('-') and not line.startswith('---'):
                current_hunk["removed"] += 1
                current_hunk["size"] += 1
                analysis["lines_removed"] += 1
                
            elif in_hunk and line.startswith(' '):
                current_hunk["context"] += 1
                current_hunk["size"] += 1
        
        # Add the last hunk
        if current_hunk:
            analysis["hunks"].append(current_hunk)
        
        # Count large hunks (exceeding our threshold)
        for hunk in analysis["hunks"]:
            changes = hunk["added"] + hunk["removed"]
            if changes > self.max_hunk_size:
                analysis["large_hunks"] += 1
                logger.warning(f"Large hunk detected in {file_path}: {changes} changes")
        
        # Calculate quality score (0-1, higher is better)
        total_changes = analysis["lines_added"] + analysis["lines_removed"]
        if total_changes > 0:
            # Penalize large hunks and reward small, focused changes
            large_hunk_penalty = analysis["large_hunks"] * 0.2
            focus_bonus = 1.0 / max(1, analysis["hunk_count"] / 3)  # Reward fewer hunks
            analysis["quality_score"] = max(0.0, min(1.0, focus_bonus - large_hunk_penalty))
        
        return analysis
    
    def _generate_change_summary(self, analysis: Dict[str, Any]) -> str:
        """Generate a human-readable summary of changes."""
        parts = []
        
        if analysis["lines_added"] > 0:
            parts.append(f"+{analysis['lines_added']} lines")
        
        if analysis["lines_removed"] > 0:
            parts.append(f"-{analysis['lines_removed']} lines")
        
        hunk_desc = f"{analysis['hunk_count']} hunk{'s' if analysis['hunk_count'] != 1 else ''}"
        
        if analysis["large_hunks"] > 0:
            hunk_desc += f" ({analysis['large_hunks']} large)"
        
        summary = f"{', '.join(parts)} in {hunk_desc}"
        
        if analysis["quality_score"] < 0.5:
            summary += " [CAUTION: Large changes detected]"
        
        return summary
    
    def validate_hunk_size(self, diff_content: str) -> List[str]:
        """Validate hunk sizes and return warnings if they're too large."""
        warnings = []
        
        hunks = re.findall(r'@@[^@]*@@', diff_content)
        for i, hunk_header in enumerate(hunks):
            # Extract hunk size from header like @@ -1,5 +1,8 @@
            match = re.search(r'@@\s*-\d+,?(\d+)?\s*\+\d+,?(\d+)?\s*@@', hunk_header)
            if match:
                old_count = int(match.group(1)) if match.group(1) else 1
                new_count = int(match.group(2)) if match.group(2) else 1
                changes = abs(old_count - new_count) + min(old_count, new_count)
                
                if changes > self.max_hunk_size:
                    warnings.append(f"Hunk {i+1} is large ({changes} changes) - consider splitting")
        
        return warnings

