
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class PipelineStage(Enum):
    INTAKE = "intake"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    QA = "qa"
    COMMUNICATION = "communication"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class StageResult:
    stage: PipelineStage
    status: str
    timestamp: str
    duration: float
    data: Dict[str, Any]
    error: Optional[str] = None

@dataclass
class PipelineContext:
    ticket_id: int
    context_id: str
    current_stage: PipelineStage
    stages_completed: List[StageResult] = field(default_factory=list)
    global_data: Dict[str, Any] = field(default_factory=dict)
    checkpoints: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def __post_init__(self):
        if not self.context_id:
            self.context_id = self._generate_context_id()
    
    def _generate_context_id(self) -> str:
        """Generate unique context ID"""
        content = f"{self.ticket_id}_{datetime.now(timezone.utc).isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

class PipelineContextManager:
    def __init__(self):
        self._contexts: Dict[str, PipelineContext] = {}
        self._ticket_contexts: Dict[int, str] = {}  # ticket_id -> context_id mapping
    
    def create_context(self, ticket_id: int) -> PipelineContext:
        """Create new pipeline context for a ticket"""
        context = PipelineContext(
            ticket_id=ticket_id,
            context_id="",  # Will be generated in __post_init__
            current_stage=PipelineStage.INTAKE
        )
        
        self._contexts[context.context_id] = context
        self._ticket_contexts[ticket_id] = context.context_id
        
        logger.info(f"Created pipeline context {context.context_id} for ticket {ticket_id}")
        return context
    
    def get_context(self, ticket_id: int) -> Optional[PipelineContext]:
        """Get existing context for a ticket"""
        context_id = self._ticket_contexts.get(ticket_id)
        if context_id:
            return self._contexts.get(context_id)
        return None
    
    def get_context_by_id(self, context_id: str) -> Optional[PipelineContext]:
        """Get context by context ID"""
        return self._contexts.get(context_id)
    
    def update_stage(self, context_id: str, stage: PipelineStage, stage_data: Dict[str, Any], 
                    status: str = "success", error: Optional[str] = None, duration: float = 0.0) -> bool:
        """Update pipeline stage with results"""
        context = self._contexts.get(context_id)
        if not context:
            logger.error(f"Context {context_id} not found")
            return False
        
        # Create stage result
        stage_result = StageResult(
            stage=stage,
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration=duration,
            data=stage_data,
            error=error
        )
        
        # Update context
        context.stages_completed.append(stage_result)
        context.current_stage = stage
        context.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Merge stage data into global data
        if status == "success":
            context.global_data.update(stage_data)
        
        logger.info(f"Updated context {context_id} to stage {stage.value} with status {status}")
        return True
    
    def create_checkpoint(self, context_id: str, checkpoint_name: str) -> bool:
        """Create a checkpoint of current context state"""
        context = self._contexts.get(context_id)
        if not context:
            return False
        
        checkpoint_data = {
            "stage": context.current_stage.value,
            "global_data": context.global_data.copy(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        context.checkpoints[checkpoint_name] = checkpoint_data
        logger.info(f"Created checkpoint '{checkpoint_name}' for context {context_id}")
        return True
    
    def restore_checkpoint(self, context_id: str, checkpoint_name: str) -> bool:
        """Restore context to a previous checkpoint"""
        context = self._contexts.get(context_id)
        if not context or checkpoint_name not in context.checkpoints:
            return False
        
        checkpoint_data = context.checkpoints[checkpoint_name]
        context.current_stage = PipelineStage(checkpoint_data["stage"])
        context.global_data = checkpoint_data["global_data"].copy()
        context.updated_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Restored context {context_id} to checkpoint '{checkpoint_name}'")
        return True
    
    def validate_context(self, context_id: str, required_data: List[str]) -> Dict[str, Any]:
        """Validate that context contains required data"""
        context = self._contexts.get(context_id)
        if not context:
            return {"valid": False, "error": "Context not found"}
        
        missing_data = []
        for key in required_data:
            if key not in context.global_data:
                missing_data.append(key)
        
        if missing_data:
            return {
                "valid": False,
                "error": f"Missing required data: {missing_data}",
                "missing_data": missing_data
            }
        
        return {"valid": True}
    
    def get_stage_data(self, context_id: str, stage: PipelineStage) -> Optional[Dict[str, Any]]:
        """Get data from a specific completed stage"""
        context = self._contexts.get(context_id)
        if not context:
            return None
        
        for stage_result in context.stages_completed:
            if stage_result.stage == stage and stage_result.status == "success":
                return stage_result.data
        
        return None
    
    def get_pipeline_summary(self, context_id: str) -> Dict[str, Any]:
        """Get summary of pipeline execution"""
        context = self._contexts.get(context_id)
        if not context:
            return {"error": "Context not found"}
        
        summary = {
            "context_id": context_id,
            "ticket_id": context.ticket_id,
            "current_stage": context.current_stage.value,
            "stages_completed": len(context.stages_completed),
            "total_duration": sum(stage.duration for stage in context.stages_completed),
            "status_counts": {},
            "created_at": context.created_at,
            "updated_at": context.updated_at,
            "has_errors": any(stage.error for stage in context.stages_completed),
            "checkpoints": list(context.checkpoints.keys())
        }
        
        # Count stage statuses
        for stage_result in context.stages_completed:
            status = stage_result.status
            summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1
        
        return summary
    
    def serialize_context(self, context_id: str) -> Optional[str]:
        """Serialize context to JSON for debugging/storage"""
        context = self._contexts.get(context_id)
        if not context:
            return None
        
        try:
            # Convert to dict and handle enums
            context_dict = asdict(context)
            context_dict["current_stage"] = context.current_stage.value
            
            for stage_result in context_dict["stages_completed"]:
                stage_result["stage"] = stage_result["stage"].value
            
            return json.dumps(context_dict, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error serializing context {context_id}: {e}")
            return None
    
    def cleanup_old_contexts(self, max_age_hours: int = 24) -> int:
        """Clean up old contexts to prevent memory leaks"""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        cleaned_count = 0
        
        contexts_to_remove = []
        for context_id, context in self._contexts.items():
            created_timestamp = datetime.fromisoformat(context.created_at.replace('Z', '+00:00')).timestamp()
            if created_timestamp < cutoff_time:
                contexts_to_remove.append(context_id)
        
        for context_id in contexts_to_remove:
            context = self._contexts[context_id]
            del self._contexts[context_id]
            if context.ticket_id in self._ticket_contexts:
                del self._ticket_contexts[context.ticket_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old pipeline contexts")
        
        return cleaned_count
    
    def get_all_active_contexts(self) -> List[Dict[str, Any]]:
        """Get summary of all active contexts"""
        summaries = []
        for context_id in self._contexts.keys():
            summary = self.get_pipeline_summary(context_id)
            if "error" not in summary:
                summaries.append(summary)
        
        return summaries

# Global context manager instance
context_manager = PipelineContextManager()
