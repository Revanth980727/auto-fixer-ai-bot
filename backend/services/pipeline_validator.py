
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
            # ENHANCED DEBUG: Log the complete result structure
            logger.info(f"🔍 PIPELINE VALIDATOR DEBUG - Complete result structure:")
            logger.info(f"  - Result keys: {list(result.keys())}")
            logger.info(f"  - Result type: {type(result)}")
            
            # Log each key-value pair for debugging
            for key, value in result.items():
                if key == "patches":
                    logger.info(f"  - {key}: {len(value) if isinstance(value, list) else 'not a list'} patches")
                    if isinstance(value, list) and value:
                        logger.info(f"    - First patch keys: {list(value[0].keys()) if value else 'no patches'}")
                elif key == "semantic_stats":
                    logger.info(f"  - {key}: {value}")
                else:
                    logger.info(f"  - {key}: {value if not isinstance(value, str) or len(str(value)) < 100 else f'{str(value)[:100]}...'}")
            
            patches = result.get("patches", [])
            semantic_stats = result.get("semantic_stats", {})
            
            # ENHANCED INTELLIGENT PATCHING DETECTION
            using_intelligent_features = False
            detection_methods = []
            
            # Method 1: Direct intelligent_patching flag (NEW)
            if result.get("intelligent_patching", False):
                using_intelligent_features = True
                detection_methods.append("intelligent_patching flag")
                logger.info("🧠 Intelligent patching detected via direct intelligent_patching flag")
            
            # Method 2: Semantic evaluation enabled flag
            if result.get("semantic_evaluation_enabled", False):
                using_intelligent_features = True
                detection_methods.append("semantic_evaluation_enabled flag")
                logger.info("🧠 Intelligent patching detected via semantic_evaluation_enabled flag")
            
            # Method 3: using_intelligent_patching flag
            if result.get("using_intelligent_patching", False):
                using_intelligent_features = True
                detection_methods.append("using_intelligent_patching flag")
                logger.info("🧠 Intelligent patching detected via using_intelligent_patching flag")
            
            # Method 4: Semantic stats present with meaningful data
            if semantic_stats and semantic_stats.get("total_patches_generated", 0) > 0:
                using_intelligent_features = True
                detection_methods.append("semantic_stats data")
                logger.info("🧠 Intelligent patching detected via semantic_stats")
            
            # Method 5: Patches have intelligent features
            if patches:
                for i, patch in enumerate(patches):
                    logger.info(f"🔍 Patch {i} keys: {list(patch.keys())}")
                    
                    # Check for semantic evaluation data
                    if patch.get("semantic_evaluation"):
                        using_intelligent_features = True
                        detection_methods.append(f"patch {i} semantic_evaluation")
                        logger.info(f"🧠 Intelligent patching detected in patch {i} via semantic_evaluation")
                        break
                    
                    # Check for processing strategy
                    strategy = patch.get("processing_strategy", "")
                    if strategy in ["enhanced_single_file", "semantic_chunked"]:
                        using_intelligent_features = True
                        detection_methods.append(f"patch {i} processing_strategy")
                        logger.info(f"🧠 Intelligent patching detected in patch {i} via processing_strategy: {strategy}")
                        break
                    
                    # Check for selection reason
                    if patch.get("selection_reason"):
                        using_intelligent_features = True
                        detection_methods.append(f"patch {i} selection_reason")
                        logger.info(f"🧠 Intelligent patching detected in patch {i} via selection_reason")
                        break
            
            # Method 6: Quality thresholds present
            if result.get("quality_thresholds"):
                using_intelligent_features = True
                detection_methods.append("quality_thresholds")
                logger.info("🧠 Intelligent patching detected via quality_thresholds")
            
            validation["using_intelligent_patching"] = using_intelligent_features
            
            logger.info(f"🧠 INTELLIGENT PATCHING DETECTION RESULT:")
            logger.info(f"  - Detected: {using_intelligent_features}")
            logger.info(f"  - Detection methods: {detection_methods}")
            logger.info(f"  - Total detection methods found: {len(detection_methods)}")
            
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
                
                logger.info(f"🔍 Patch {i} confidence: {confidence:.3f}")
                
                if confidence >= self.min_confidence_threshold:
                    high_quality_patches += 1
            
            avg_confidence = total_confidence / len(patches) if patches else 0
            
            logger.info(f"📊 Quality analysis:")
            logger.info(f"  - Total patches: {len(patches)}")
            logger.info(f"  - High quality patches: {high_quality_patches}")
            logger.info(f"  - Average confidence: {avg_confidence:.3f}")
            logger.info(f"  - Using intelligent patching: {using_intelligent_features}")
            
            # ENHANCED VALIDATION LOGIC - More lenient for intelligent patching
            if using_intelligent_features:
                logger.info("🧠 Applying intelligent patching validation rules (more lenient)")
                
                # For intelligent patching, be more lenient on thresholds
                if high_quality_patches >= self.min_patches_required:
                    validation["patches_quality"] = "high"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} intelligent patches with {high_quality_patches} high-quality patches (avg confidence: {avg_confidence:.3f})"
                elif avg_confidence >= 0.5 or semantic_stats.get("patches_accepted", 0) > 0:
                    validation["patches_quality"] = "medium"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} intelligent patches with moderate confidence (avg: {avg_confidence:.3f})"
                elif len(patches) >= 1 and avg_confidence >= 0.3:
                    # Even lower threshold for intelligent patching
                    validation["patches_quality"] = "acceptable"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} intelligent patches with acceptable confidence (avg: {avg_confidence:.3f})"
                else:
                    validation["patches_quality"] = "low"
                    validation["reason"] = f"Intelligent patches have low confidence scores (avg: {avg_confidence:.3f})"
                    validation["recommendations"].append("Review error analysis and file selection")
            else:
                logger.info("📝 Applying standard validation rules (legacy mode)")
                
                # Standard validation for non-intelligent patching
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
            
            logger.info(f"🎯 PIPELINE VALIDATION FINAL RESULT:")
            logger.info(f"  - Valid: {validation['valid']}")
            logger.info(f"  - Quality: {validation['patches_quality']}")
            logger.info(f"  - Reason: {validation['reason']}")
            logger.info(f"  - Using intelligent patching: {validation['using_intelligent_patching']}")
            
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
            elif quality in ["medium", "acceptable"]:
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
