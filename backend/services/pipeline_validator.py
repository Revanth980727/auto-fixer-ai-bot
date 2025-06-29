
from typing import Dict, Any, List, Optional
from core.models import Ticket, TicketStatus
import logging

logger = logging.getLogger(__name__)

class PipelineValidator:
    """Validates pipeline results and determines success criteria"""
    
    def __init__(self):
        self.min_confidence_threshold = 0.7
        self.min_patches_required = 1
        self.intelligent_patching_indicators = [
            "semantic_evaluation",
            "confidence_score", 
            "processing_strategy",
            "selection_reason"
        ]
    
    def validate_developer_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate developer agent results with support for intelligent patching"""
        validation = {
            "valid": False,
            "reason": "",
            "recommendations": [],
            "patches_quality": "unknown",
            "using_intelligent_patching": False
        }
        
        try:
            # Check if using intelligent patching
            patches = result.get("patches", [])
            semantic_stats = result.get("semantic_stats", {})
            
            # Detect intelligent patching features
            using_intelligent_features = any(
                patch.get(indicator) for patch in patches 
                for indicator in self.intelligent_patching_indicators
            )
            
            validation["using_intelligent_patching"] = (
                using_intelligent_features or 
                result.get("semantic_evaluation_enabled", False) or
                bool(semantic_stats)
            )
            
            logger.info(f"🧠 Pipeline validation - Intelligent patching detected: {validation['using_intelligent_patching']}")
            
            # Check basic requirements
            if not patches:
                validation["reason"] = "No patches generated"
                validation["recommendations"].append("Review file selection and error analysis")
                return validation
            
            # Analyze patch quality
            high_quality_patches = 0
            total_confidence = 0
            
            for patch in patches:
                confidence = patch.get("confidence_score", 0)
                total_confidence += confidence
                
                if confidence >= self.min_confidence_threshold:
                    high_quality_patches += 1
            
            avg_confidence = total_confidence / len(patches) if patches else 0
            
            # Determine quality level
            if high_quality_patches >= self.min_patches_required:
                validation["patches_quality"] = "high"
                validation["valid"] = True
                validation["reason"] = f"Generated {len(patches)} patches with {high_quality_patches} high-quality patches (avg confidence: {avg_confidence:.3f})"
            elif avg_confidence >= 0.5:
                validation["patches_quality"] = "medium"
                validation["valid"] = True
                validation["reason"] = f"Generated {len(patches)} patches with moderate confidence (avg: {avg_confidence:.3f})"
            else:
                validation["patches_quality"] = "low"
                validation["reason"] = f"Patches have low confidence scores (avg: {avg_confidence:.3f})"
                validation["recommendations"].append("Review error analysis and file selection")
            
            # Add semantic evaluation insights if available
            if semantic_stats:
                accepted = semantic_stats.get("patches_accepted", 0)
                rejected = semantic_stats.get("patches_rejected", 0)
                
                if accepted > 0:
                    validation["reason"] += f" | Semantic evaluation: {accepted} accepted, {rejected} rejected"
                    if not validation["valid"] and accepted >= 1:
                        validation["valid"] = True
                        validation["patches_quality"] = "semantic_validated"
            
            # Additional recommendations
            if validation["valid"]:
                if avg_confidence < 0.8:
                    validation["recommendations"].append("Consider refining error analysis for higher confidence")
                if len(patches) == 1:
                    validation["recommendations"].append("Single patch generated - verify comprehensive fix")
            
            logger.info(f"🎯 Pipeline validation result: {validation['valid']} - {validation['reason']}")
            
        except Exception as e:
            logger.error(f"❌ Pipeline validation error: {e}")
            validation["reason"] = f"Validation error: {str(e)}"
            validation["recommendations"].append("Check pipeline execution logs")
        
        return validation
    
    def determine_next_action(self, validation: Dict[str, Any], ticket: Ticket) -> Dict[str, Any]:
        """Determine next action based on validation results"""
        action = {
            "action": "unknown",
            "jira_status": "",
            "jira_comment": "",
            "require_manual_review": False
        }
        
        if validation["valid"]:
            quality = validation["patches_quality"]
            
            if quality in ["high", "semantic_validated"]:
                action["action"] = "create_pr"
                action["jira_status"] = "In Review"
                action["jira_comment"] = f"✅ AI Agent generated high-quality patches. {validation['reason']}"
            elif quality == "medium":
                action["action"] = "create_pr_with_review"
                action["jira_status"] = "In Review"
                action["jira_comment"] = f"⚠️ AI Agent generated patches requiring review. {validation['reason']}"
                action["require_manual_review"] = True
            else:
                action["action"] = "manual_review"
                action["jira_status"] = "Needs Review"
                action["jira_comment"] = f"🔍 AI Agent generated patches requiring manual review. {validation['reason']}"
                action["require_manual_review"] = True
        else:
            action["action"] = "retry_or_escalate"
            action["jira_status"] = "In Progress"
            action["jira_comment"] = f"❌ AI Agent failed to generate suitable patches. {validation['reason']}"
            action["require_manual_review"] = True
        
        return action

# Global validator instance
pipeline_validator = PipelineValidator()
