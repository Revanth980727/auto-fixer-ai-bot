
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
            # Debug: Log the complete result structure
            logger.info(f"🔍 PIPELINE VALIDATOR DEBUG - Complete result structure:")
            logger.info(f"  - Result keys: {list(result.keys())}")
            logger.info(f"  - Semantic evaluation enabled: {result.get('semantic_evaluation_enabled', False)}")
            logger.info(f"  - Patches count: {len(result.get('patches', []))}")
            logger.info(f"  - Semantic stats: {result.get('semantic_stats', {})}")
            
            # Check if using intelligent patching
            patches = result.get("patches", [])
            semantic_stats = result.get("semantic_stats", {})
            
            # Enhanced intelligent patching detection
            using_intelligent_features = False
            
            # Check 1: Semantic evaluation enabled flag
            if result.get("semantic_evaluation_enabled", False):
                using_intelligent_features = True
                logger.info("🧠 Intelligent patching detected via semantic_evaluation_enabled flag")
            
            # Check 2: Semantic stats present
            if semantic_stats and semantic_stats.get("total_patches_generated", 0) > 0:
                using_intelligent_features = True
                logger.info("🧠 Intelligent patching detected via semantic_stats")
            
            # Check 3: Patches have intelligent features
            if patches:
                for i, patch in enumerate(patches):
                    logger.info(f"🔍 Patch {i} keys: {list(patch.keys())}")
                    if any(patch.get(indicator) for indicator in self.intelligent_patching_indicators):
                        using_intelligent_features = True
                        logger.info(f"🧠 Intelligent patching detected in patch {i} via indicators")
                        break
            
            # Check 4: Quality thresholds present
            if result.get("quality_thresholds"):
                using_intelligent_features = True
                logger.info("🧠 Intelligent patching detected via quality_thresholds")
            
            validation["using_intelligent_patching"] = using_intelligent_features
            
            logger.info(f"🧠 Pipeline validation - Intelligent patching detected: {validation['using_intelligent_patching']}")
            
            # Check basic requirements
            if not patches:
                validation["reason"] = "No patches generated"
                validation["recommendations"].append("Review file selection and error analysis")
                return validation
            
            # Analyze patch quality with improved logic
            high_quality_patches = 0
            total_confidence = 0
            
            for i, patch in enumerate(patches):
                confidence = patch.get("confidence_score", 0)
                total_confidence += confidence
                
                logger.info(f"🔍 Patch {i} confidence: {confidence}")
                
                if confidence >= self.min_confidence_threshold:
                    high_quality_patches += 1
            
            avg_confidence = total_confidence / len(patches) if patches else 0
            
            logger.info(f"📊 Quality analysis:")
            logger.info(f"  - Total patches: {len(patches)}")
            logger.info(f"  - High quality patches: {high_quality_patches}")
            logger.info(f"  - Average confidence: {avg_confidence:.3f}")
            
            # Determine quality level with intelligent patching consideration
            if using_intelligent_features and len(patches) > 0:
                # For intelligent patching, be more lenient on thresholds
                if high_quality_patches >= self.min_patches_required:
                    validation["patches_quality"] = "high"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} intelligent patches with {high_quality_patches} high-quality patches (avg confidence: {avg_confidence:.3f})"
                elif avg_confidence >= 0.5 or semantic_stats.get("patches_accepted", 0) > 0:
                    validation["patches_quality"] = "medium"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} intelligent patches with moderate confidence (avg: {avg_confidence:.3f})"
                else:
                    validation["patches_quality"] = "low"
                    validation["reason"] = f"Intelligent patches have low confidence scores (avg: {avg_confidence:.3f})"
                    validation["recommendations"].append("Review error analysis and file selection")
            else:
                # Legacy validation for non-intelligent patching
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
            intelligent_patching = validation.get("using_intelligent_patching", False)
            
            if quality in ["high", "semantic_validated"]:
                action["action"] = "create_pr"
                action["jira_status"] = "In Review"
                prefix = "🧠 AI Agent (Intelligent Patching)" if intelligent_patching else "✅ AI Agent"
                action["jira_comment"] = f"{prefix} generated high-quality patches. {validation['reason']}"
            elif quality == "medium":
                action["action"] = "create_pr_with_review"
                action["jira_status"] = "In Review"
                prefix = "🧠 AI Agent (Intelligent Patching)" if intelligent_patching else "⚠️ AI Agent"
                action["jira_comment"] = f"{prefix} generated patches requiring review. {validation['reason']}"
                action["require_manual_review"] = True
            else:
                action["action"] = "manual_review"
                action["jira_status"] = "Needs Review"
                prefix = "🧠 AI Agent (Intelligent Patching)" if intelligent_patching else "🔍 AI Agent"
                action["jira_comment"] = f"{prefix} generated patches requiring manual review. {validation['reason']}"
                action["require_manual_review"] = True
        else:
            action["action"] = "retry_or_escalate"
            action["jira_status"] = "In Progress"
            action["jira_comment"] = f"❌ AI Agent failed to generate suitable patches. {validation['reason']}"
            action["require_manual_review"] = True
        
        return action

# Global validator instance
pipeline_validator = PipelineValidator()
