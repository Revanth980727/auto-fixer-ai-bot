from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from services.diff_presenter import DiffPresenter
from core.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances
diff_presenter = DiffPresenter()
websocket_manager = WebSocketManager()

class ApprovalDecision(BaseModel):
    diff_id: str
    decision: str  # 'approve_all', 'approve_partial', 'modify', 'reject'
    selected_files: Optional[List[str]] = None
    comments: Optional[str] = None

@router.get("/diff/{diff_id}")
async def get_diff(diff_id: str):
    """Get diff details for review."""
    try:
        diff_json = diff_presenter.get_diff_json(diff_id)
        if 'error' in diff_json:
            raise HTTPException(status_code=404, detail="Diff not found")
        
        return {
            "success": True,
            "diff": diff_json
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving diff {diff_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diff/{diff_id}/html")
async def get_diff_html(diff_id: str):
    """Get HTML representation of diff for review."""
    try:
        html_content = diff_presenter.get_diff_html(diff_id)
        if "Diff not found" in html_content:
            raise HTTPException(status_code=404, detail="Diff not found")
        
        return {
            "success": True,
            "html": html_content
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving diff HTML {diff_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/diff/{diff_id}/approve")
async def approve_diff(diff_id: str, decision: ApprovalDecision):
    """Apply approval decision to a diff."""
    try:
        logger.info(f"🔍 Processing approval decision for diff {diff_id}: {decision.decision}")
        
        # Apply approval decision
        result = diff_presenter.apply_approval_decision(
            diff_id=diff_id,
            decision=decision.decision,
            selected_files=decision.selected_files
        )
        
        if not result.get('success'):
            raise HTTPException(
                status_code=400, 
                detail=result.get('error', 'Failed to apply approval decision')
            )
        
        # Broadcast approval result
        await websocket_manager.broadcast_approval_result(
            diff_id=diff_id,
            decision=decision.decision,
            result=result
        )
        
        logger.info(f"✅ Approval decision applied successfully for diff {diff_id}")
        
        return {
            "success": True,
            "decision": decision.decision,
            "result": result,
            "message": f"Approval decision '{decision.decision}' applied successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error applying approval decision for diff {diff_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diffs/active")
async def get_active_diffs():
    """Get list of active diffs waiting for approval."""
    try:
        # Get all cached diffs (in a real implementation, this might come from database)
        active_diffs = []
        
        for diff_id, interactive_diff in diff_presenter.diff_cache.items():
            active_diffs.append({
                "diff_id": diff_id,
                "summary": interactive_diff.summary,
                "approval_options": interactive_diff.approval_options,
                "metadata": interactive_diff.metadata,
                "files_count": len(interactive_diff.file_diffs)
            })
        
        return {
            "success": True,
            "active_diffs": active_diffs,
            "count": len(active_diffs)
        }
        
    except Exception as e:
        logger.error(f"❌ Error retrieving active diffs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/diff/{diff_id}")
async def dismiss_diff(diff_id: str):
    """Dismiss/cancel a diff review."""
    try:
        if diff_id in diff_presenter.diff_cache:
            del diff_presenter.diff_cache[diff_id]
            
            # Broadcast dismissal
            await websocket_manager.broadcast_approval_result(
                diff_id=diff_id,
                decision="dismissed",
                result={"dismissed": True, "timestamp": "now"}
            )
            
            return {
                "success": True,
                "message": f"Diff {diff_id} dismissed"
            }
        else:
            raise HTTPException(status_code=404, detail="Diff not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error dismissing diff {diff_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diff/{diff_id}/statistics")
async def get_diff_statistics(diff_id: str):
    """Get detailed statistics for a diff."""
    try:
        diff_json = diff_presenter.get_diff_json(diff_id)
        if 'error' in diff_json:
            raise HTTPException(status_code=404, detail="Diff not found")
        
        # Calculate detailed statistics
        total_additions = sum(fd['stats']['additions'] for fd in diff_json['file_diffs'])
        total_deletions = sum(fd['stats']['deletions'] for fd in diff_json['file_diffs'])
        total_changes = sum(fd['stats']['changes'] for fd in diff_json['file_diffs'])
        
        file_types = {}
        confidence_distribution = {'high': 0, 'medium': 0, 'low': 0}
        
        for file_diff in diff_json['file_diffs']:
            # File type analysis
            file_ext = file_diff['file_path'].split('.')[-1] if '.' in file_diff['file_path'] else 'none'
            file_types[file_ext] = file_types.get(file_ext, 0) + 1
            
            # Confidence distribution
            confidence = file_diff['confidence']
            if confidence >= 0.8:
                confidence_distribution['high'] += 1
            elif confidence >= 0.5:
                confidence_distribution['medium'] += 1
            else:
                confidence_distribution['low'] += 1
        
        return {
            "success": True,
            "statistics": {
                "total_files": len(diff_json['file_diffs']),
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "total_changes": total_changes,
                "file_types": file_types,
                "confidence_distribution": confidence_distribution,
                "average_confidence": diff_json['summary']['average_confidence'],
                "risk_level": diff_json['summary']['risk_level'],
                "estimated_review_time": diff_json['summary']['estimated_review_time']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting diff statistics {diff_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))