from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/diff-approval", tags=["diff-approval"])

class ApprovalDecision(BaseModel):
    workspace_id: str
    decision: str  # 'approved', 'rejected', 'modify'
    comment: Optional[str] = None

@router.post("/decision")
async def set_approval_decision(approval: ApprovalDecision):
    """Set approval decision for a patch in shadow workspace."""
    try:
        from services.patch_service import PatchService
        patch_service = PatchService()
        
        success = patch_service.set_approval_decision(
            approval.workspace_id, 
            approval.decision
        )
        
        if success:
            return {
                "success": True,
                "workspace_id": approval.workspace_id,
                "decision": approval.decision
            }
        else:
            raise HTTPException(status_code=404, detail="Workspace not found")
            
    except Exception as e:
        logger.error(f"❌ Error setting approval decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))