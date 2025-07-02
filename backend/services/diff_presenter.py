import difflib
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class DiffHunk:
    """Represents a hunk of changes in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[Dict[str, Any]]  # [{'type': 'add/remove/context', 'content': str, 'line_no': int}]
    context: str

@dataclass
class FileDiff:
    """Represents diff for a single file."""
    file_path: str
    original_content: str
    patched_content: str
    hunks: List[DiffHunk]
    stats: Dict[str, int]  # {'additions': int, 'deletions': int, 'changes': int}
    confidence: float
    patch_type: str

@dataclass
class InteractiveDiff:
    """Interactive diff presentation with approval options."""
    diff_id: str
    file_diffs: List[FileDiff]
    summary: Dict[str, Any]
    approval_options: List[str]  # ['approve_all', 'approve_partial', 'modify', 'reject']
    metadata: Dict[str, Any]

class DiffPresenter:
    """Generates interactive diff presentations for patch review."""
    
    def __init__(self):
        self.diff_cache: Dict[str, InteractiveDiff] = {}
        
    def create_interactive_diff(self, 
                              patches: List[Dict[str, Any]], 
                              patch_metadata: Dict[str, Any] = None) -> InteractiveDiff:
        """Create an interactive diff from patches."""
        try:
            logger.info(f"🎨 Creating interactive diff for {len(patches)} patches")
            
            diff_id = self._generate_diff_id(patches)
            file_diffs = []
            
            for patch in patches:
                file_diff = self._create_file_diff(patch)
                if file_diff:
                    file_diffs.append(file_diff)
            
            summary = self._create_diff_summary(file_diffs)
            approval_options = self._determine_approval_options(file_diffs, summary)
            
            interactive_diff = InteractiveDiff(
                diff_id=diff_id,
                file_diffs=file_diffs,
                summary=summary,
                approval_options=approval_options,
                metadata=patch_metadata or {}
            )
            
            # Cache the diff
            self.diff_cache[diff_id] = interactive_diff
            
            logger.info(f"✅ Interactive diff created: {diff_id}")
            return interactive_diff
            
        except Exception as e:
            logger.error(f"❌ Error creating interactive diff: {e}")
            raise
    
    def _generate_diff_id(self, patches: List[Dict[str, Any]]) -> str:
        """Generate unique ID for diff."""
        import hashlib
        import time
        
        content = json.dumps(patches, sort_keys=True) + str(time.time())
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _create_file_diff(self, patch: Dict[str, Any]) -> Optional[FileDiff]:
        """Create file diff from patch data."""
        try:
            file_path = patch.get('file_path', '')
            original_content = patch.get('original_content', '')
            patched_content = patch.get('patched_content', patch.get('patched_code', ''))
            confidence = patch.get('confidence_score', 0.5)
            patch_type = patch.get('patch_type', 'unknown')
            
            if not all([file_path, patched_content]):
                logger.warning(f"⚠️ Incomplete patch data for {file_path}")
                return None
            
            # Generate unified diff
            hunks = self._generate_hunks(original_content, patched_content, file_path)
            stats = self._calculate_diff_stats(hunks)
            
            return FileDiff(
                file_path=file_path,
                original_content=original_content,
                patched_content=patched_content,
                hunks=hunks,
                stats=stats,
                confidence=confidence,
                patch_type=patch_type
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating file diff: {e}")
            return None
    
    def _generate_hunks(self, original: str, patched: str, file_path: str) -> List[DiffHunk]:
        """Generate diff hunks from original and patched content."""
        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        
        # Use difflib to generate unified diff
        diff_lines = list(difflib.unified_diff(
            original_lines,
            patched_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3,  # 3 lines of context
            lineterm=""
        ))
        
        hunks = []
        current_hunk = None
        
        for line in diff_lines:
            if line.startswith('@@'):
                # New hunk header
                if current_hunk:
                    hunks.append(current_hunk)
                
                current_hunk = self._parse_hunk_header(line)
                
            elif current_hunk and (line.startswith(' ') or line.startswith('+') or line.startswith('-')):
                # Hunk content line
                self._add_line_to_hunk(current_hunk, line)
        
        # Add the last hunk
        if current_hunk:
            hunks.append(current_hunk)
        
        return hunks
    
    def _parse_hunk_header(self, header_line: str) -> DiffHunk:
        """Parse a hunk header line."""
        # Format: @@ -old_start,old_count +new_start,new_count @@
        import re
        
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', header_line)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            context = match.group(5).strip()
        else:
            # Fallback values
            old_start = new_start = 1
            old_count = new_count = 0
            context = ""
        
        return DiffHunk(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            lines=[],
            context=context
        )
    
    def _add_line_to_hunk(self, hunk: DiffHunk, line: str) -> None:
        """Add a line to a hunk."""
        if line.startswith(' '):
            line_type = 'context'
            content = line[1:]
        elif line.startswith('+'):
            line_type = 'add'
            content = line[1:]
        elif line.startswith('-'):
            line_type = 'remove'
            content = line[1:]
        else:
            return  # Skip unknown line types
        
        hunk.lines.append({
            'type': line_type,
            'content': content,
            'line_no': len(hunk.lines) + 1
        })
    
    def _calculate_diff_stats(self, hunks: List[DiffHunk]) -> Dict[str, int]:
        """Calculate diff statistics."""
        stats = {'additions': 0, 'deletions': 0, 'changes': 0}
        
        for hunk in hunks:
            for line in hunk.lines:
                if line['type'] == 'add':
                    stats['additions'] += 1
                elif line['type'] == 'remove':
                    stats['deletions'] += 1
        
        stats['changes'] = stats['additions'] + stats['deletions']
        return stats
    
    def _create_diff_summary(self, file_diffs: List[FileDiff]) -> Dict[str, Any]:
        """Create summary of all diffs."""
        total_stats = {'additions': 0, 'deletions': 0, 'changes': 0}
        total_files = len(file_diffs)
        avg_confidence = 0.0
        patch_types = {}
        
        for file_diff in file_diffs:
            total_stats['additions'] += file_diff.stats['additions']
            total_stats['deletions'] += file_diff.stats['deletions']
            total_stats['changes'] += file_diff.stats['changes']
            avg_confidence += file_diff.confidence
            
            patch_type = file_diff.patch_type
            patch_types[patch_type] = patch_types.get(patch_type, 0) + 1
        
        avg_confidence = avg_confidence / total_files if total_files > 0 else 0.0
        
        return {
            'total_files': total_files,
            'total_stats': total_stats,
            'average_confidence': avg_confidence,
            'patch_types': patch_types,
            'risk_level': self._assess_risk_level(total_stats, avg_confidence),
            'estimated_review_time': self._estimate_review_time(total_stats)
        }
    
    def _assess_risk_level(self, stats: Dict[str, int], confidence: float) -> str:
        """Assess risk level of the changes."""
        if confidence < 0.3:
            return 'high'
        elif stats['changes'] > 100:
            return 'high'
        elif confidence < 0.6 or stats['changes'] > 50:
            return 'medium'
        else:
            return 'low'
    
    def _estimate_review_time(self, stats: Dict[str, int]) -> str:
        """Estimate review time based on change size."""
        changes = stats['changes']
        
        if changes < 10:
            return '< 5 minutes'
        elif changes < 50:
            return '5-15 minutes'
        elif changes < 200:
            return '15-30 minutes'
        else:
            return '> 30 minutes'
    
    def _determine_approval_options(self, file_diffs: List[FileDiff], summary: Dict[str, Any]) -> List[str]:
        """Determine available approval options based on diff characteristics."""
        options = ['approve_all', 'reject']
        
        # Add partial approval if multiple files
        if len(file_diffs) > 1:
            options.insert(-1, 'approve_partial')
        
        # Add modify option for low-confidence changes
        if summary['average_confidence'] < 0.7:
            options.insert(-1, 'modify')
        
        return options
    
    def get_diff_html(self, diff_id: str) -> str:
        """Generate HTML representation of the diff."""
        if diff_id not in self.diff_cache:
            return "<p>Diff not found</p>"
        
        interactive_diff = self.diff_cache[diff_id]
        
        html_parts = [
            "<div class='interactive-diff'>",
            self._generate_summary_html(interactive_diff.summary),
            self._generate_approval_options_html(interactive_diff.approval_options),
            "<div class='file-diffs'>"
        ]
        
        for file_diff in interactive_diff.file_diffs:
            html_parts.append(self._generate_file_diff_html(file_diff))
        
        html_parts.extend([
            "</div>",
            "</div>"
        ])
        
        return "\n".join(html_parts)
    
    def _generate_summary_html(self, summary: Dict[str, Any]) -> str:
        """Generate HTML for diff summary."""
        risk_class = f"risk-{summary['risk_level']}"
        
        return f"""
        <div class='diff-summary {risk_class}'>
            <h3>Change Summary</h3>
            <div class='stats'>
                <span class='files'>{summary['total_files']} files</span>
                <span class='additions'>+{summary['total_stats']['additions']}</span>
                <span class='deletions'>-{summary['total_stats']['deletions']}</span>
                <span class='confidence'>Confidence: {summary['average_confidence']:.2f}</span>
                <span class='risk'>Risk: {summary['risk_level']}</span>
                <span class='time'>Est. review: {summary['estimated_review_time']}</span>
            </div>
        </div>
        """
    
    def _generate_approval_options_html(self, options: List[str]) -> str:
        """Generate HTML for approval options."""
        option_buttons = []
        
        for option in options:
            display_name = option.replace('_', ' ').title()
            button_class = self._get_button_class(option)
            option_buttons.append(
                f"<button class='approval-option {button_class}' data-action='{option}'>{display_name}</button>"
            )
        
        return f"""
        <div class='approval-options'>
            <h4>Review Actions</h4>
            <div class='options'>
                {' '.join(option_buttons)}
            </div>
        </div>
        """
    
    def _get_button_class(self, option: str) -> str:
        """Get CSS class for approval button."""
        class_map = {
            'approve_all': 'btn-success',
            'approve_partial': 'btn-warning',
            'modify': 'btn-info',
            'reject': 'btn-danger'
        }
        return class_map.get(option, 'btn-secondary')
    
    def _generate_file_diff_html(self, file_diff: FileDiff) -> str:
        """Generate HTML for a single file diff."""
        confidence_class = self._get_confidence_class(file_diff.confidence)
        
        html_parts = [
            f"<div class='file-diff {confidence_class}' data-file='{file_diff.file_path}'>",
            f"<div class='file-header'>",
            f"<h4>{file_diff.file_path}</h4>",
            f"<div class='file-stats'>",
            f"<span class='patch-type'>{file_diff.patch_type}</span>",
            f"<span class='confidence'>Confidence: {file_diff.confidence:.2f}</span>",
            f"<span class='changes'>+{file_diff.stats['additions']} -{file_diff.stats['deletions']}</span>",
            f"</div>",
            f"</div>",
            f"<div class='hunks'>"
        ]
        
        for hunk in file_diff.hunks:
            html_parts.append(self._generate_hunk_html(hunk))
        
        html_parts.extend([
            "</div>",
            "</div>"
        ])
        
        return "\n".join(html_parts)
    
    def _get_confidence_class(self, confidence: float) -> str:
        """Get CSS class based on confidence level."""
        if confidence >= 0.8:
            return 'high-confidence'
        elif confidence >= 0.5:
            return 'medium-confidence'
        else:
            return 'low-confidence'
    
    def _generate_hunk_html(self, hunk: DiffHunk) -> str:
        """Generate HTML for a diff hunk."""
        html_parts = [
            f"<div class='hunk'>",
            f"<div class='hunk-header'>",
            f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@ {hunk.context}",
            f"</div>",
            f"<div class='hunk-lines'>"
        ]
        
        for line in hunk.lines:
            line_class = f"line-{line['type']}"
            prefix = self._get_line_prefix(line['type'])
            html_parts.append(
                f"<div class='diff-line {line_class}'>{prefix}{self._escape_html(line['content'])}</div>"
            )
        
        html_parts.extend([
            "</div>",
            "</div>"
        ])
        
        return "\n".join(html_parts)
    
    def _get_line_prefix(self, line_type: str) -> str:
        """Get prefix character for diff line."""
        prefixes = {
            'add': '+',
            'remove': '-',
            'context': ' '
        }
        return prefixes.get(line_type, ' ')
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML characters."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    def get_diff_json(self, diff_id: str) -> Dict[str, Any]:
        """Get JSON representation of the diff."""
        if diff_id not in self.diff_cache:
            return {'error': 'Diff not found'}
        
        interactive_diff = self.diff_cache[diff_id]
        
        return {
            'diff_id': interactive_diff.diff_id,
            'summary': interactive_diff.summary,
            'approval_options': interactive_diff.approval_options,
            'file_diffs': [
                {
                    'file_path': fd.file_path,
                    'stats': fd.stats,
                    'confidence': fd.confidence,
                    'patch_type': fd.patch_type,
                    'hunks': [
                        {
                            'old_start': h.old_start,
                            'old_count': h.old_count,
                            'new_start': h.new_start,
                            'new_count': h.new_count,
                            'context': h.context,
                            'lines': h.lines
                        }
                        for h in fd.hunks
                    ]
                }
                for fd in interactive_diff.file_diffs
            ],
            'metadata': interactive_diff.metadata
        }
    
    def apply_approval_decision(self, diff_id: str, decision: str, selected_files: List[str] = None) -> Dict[str, Any]:
        """Apply approval decision to a diff."""
        if diff_id not in self.diff_cache:
            return {'success': False, 'error': 'Diff not found'}
        
        interactive_diff = self.diff_cache[diff_id]
        
        try:
            if decision == 'approve_all':
                result = self._approve_all_files(interactive_diff)
            elif decision == 'approve_partial':
                result = self._approve_partial_files(interactive_diff, selected_files or [])
            elif decision == 'reject':
                result = self._reject_diff(interactive_diff)
            elif decision == 'modify':
                result = self._request_modifications(interactive_diff)
            else:
                return {'success': False, 'error': f'Unknown decision: {decision}'}
            
            logger.info(f"✅ Applied decision '{decision}' to diff {diff_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error applying decision: {e}")
            return {'success': False, 'error': str(e)}
    
    def _approve_all_files(self, diff: InteractiveDiff) -> Dict[str, Any]:
        """Approve all files in the diff."""
        approved_files = [fd.file_path for fd in diff.file_diffs]
        
        return {
            'success': True,
            'decision': 'approve_all',
            'approved_files': approved_files,
            'message': f'Approved all {len(approved_files)} files'
        }
    
    def _approve_partial_files(self, diff: InteractiveDiff, selected_files: List[str]) -> Dict[str, Any]:
        """Approve only selected files."""
        available_files = {fd.file_path for fd in diff.file_diffs}
        approved_files = [f for f in selected_files if f in available_files]
        
        return {
            'success': True,
            'decision': 'approve_partial',
            'approved_files': approved_files,
            'rejected_files': list(available_files - set(approved_files)),
            'message': f'Approved {len(approved_files)} of {len(available_files)} files'
        }
    
    def _reject_diff(self, diff: InteractiveDiff) -> Dict[str, Any]:
        """Reject the entire diff."""
        return {
            'success': True,
            'decision': 'reject',
            'approved_files': [],
            'rejected_files': [fd.file_path for fd in diff.file_diffs],
            'message': 'Rejected all changes'
        }
    
    def _request_modifications(self, diff: InteractiveDiff) -> Dict[str, Any]:
        """Request modifications to the diff."""
        return {
            'success': True,
            'decision': 'modify',
            'message': 'Requested modifications - diff sent back for revision',
            'suggestions': self._generate_modification_suggestions(diff)
        }
    
    def _generate_modification_suggestions(self, diff: InteractiveDiff) -> List[str]:
        """Generate suggestions for modifications."""
        suggestions = []
        
        # Low confidence suggestions
        low_confidence_files = [fd.file_path for fd in diff.file_diffs if fd.confidence < 0.5]
        if low_confidence_files:
            suggestions.append(f"Review low-confidence changes in: {', '.join(low_confidence_files)}")
        
        # Large change suggestions
        large_changes = [fd.file_path for fd in diff.file_diffs if fd.stats['changes'] > 50]
        if large_changes:
            suggestions.append(f"Consider breaking down large changes in: {', '.join(large_changes)}")
        
        return suggestions
    
    def cleanup_diff(self, diff_id: str) -> bool:
        """Remove diff from cache."""
        if diff_id in self.diff_cache:
            del self.diff_cache[diff_id]
            return True
        return False