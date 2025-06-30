
# ... keep existing code (imports and class definition)

class PipelineValidator:
    """Validates pipeline results and determines success criteria"""
    
    def __init__(self):
        self.min_confidence_threshold = 0.7
        self.min_patches_required = 1
        self.surgical_patching_indicators = [
            "surgical_single_file",
            "surgical_chunked", 
            "minimal_change_approach",
            "size_validation_enabled",
            "enhanced_prompting"
        ]
    
    def validate_developer_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate developer agent results with support for surgical patching"""
        validation = {
            "valid": False,
            "reason": "",
            "recommendations": [],
            "patches_quality": "unknown",
            "using_surgical_patching": False
        }
        
        try:
            # Enhanced debug logging
            logger.info(f"🔍 PIPELINE VALIDATOR - Analyzing developer results:")
            logger.info(f"  - Result keys: {list(result.keys())}")
            
            patches = result.get("patches", [])
            processing_stats = result.get("processing_stats", {})
            
            # SURGICAL PATCHING DETECTION
            using_surgical_features = False
            detection_methods = []
            
            # Method 1: Direct surgical patching flags
            if result.get("minimal_change_approach", False):
                using_surgical_features = True
                detection_methods.append("minimal_change_approach flag")
            
            if result.get("size_validation_enabled", False):
                using_surgical_features = True
                detection_methods.append("size_validation_enabled flag")
            
            if result.get("enhanced_prompting", False):
                using_surgical_features = True
                detection_methods.append("enhanced_prompting flag")
            
            # Method 2: Processing stats indicate surgical approach
            if processing_stats.get("patches_rejected_for_size", 0) > 0:
                using_surgical_features = True
                detection_methods.append("size_based_rejection stats")
            
            if processing_stats.get("truly_minimal_changes", 0) > 0:
                using_surgical_features = True
                detection_methods.append("truly_minimal_changes stats")
            
            # Method 3: Patches have surgical strategies
            if patches:
                for i, patch in enumerate(patches):
                    strategy = patch.get("processing_strategy", "")
                    if strategy in ["surgical_single_file", "surgical_chunked"]:
                        using_surgical_features = True
                        detection_methods.append(f"patch {i} surgical strategy")
                        break
                    
                    # Check for surgical validation thresholds
                    if patch.get("validation_thresholds"):
                        using_surgical_features = True
                        detection_methods.append(f"patch {i} validation_thresholds")
                        break
            
            validation["using_surgical_patching"] = using_surgical_features
            
            logger.info(f"🔧 SURGICAL PATCHING DETECTION:")
            logger.info(f"  - Detected: {using_surgical_features}")
            logger.info(f"  - Detection methods: {detection_methods}")
            
            # Check basic requirements
            if not patches:
                validation["reason"] = "No patches generated"
                validation["recommendations"].append("Review file selection and error analysis")
                return validation
            
            # Analyze patch quality with surgical approach considerations
            high_quality_patches = 0
            total_confidence = 0
            surgical_patches = 0
            
            for i, patch in enumerate(patches):
                confidence = patch.get("confidence_score", 0)
                total_confidence += confidence
                
                # Count surgical patches
                if patch.get("processing_strategy", "").startswith("surgical_"):
                    surgical_patches += 1
                
                if confidence >= self.min_confidence_threshold:
                    high_quality_patches += 1
            
            avg_confidence = total_confidence / len(patches) if patches else 0
            
            logger.info(f"📊 Quality analysis:")
            logger.info(f"  - Total patches: {len(patches)}")
            logger.info(f"  - Surgical patches: {surgical_patches}")
            logger.info(f"  - High quality patches: {high_quality_patches}")
            logger.info(f"  - Average confidence: {avg_confidence:.3f}")
            
            # ENHANCED VALIDATION LOGIC - More lenient for surgical patching
            if using_surgical_features:
                logger.info("🔧 Applying surgical patching validation rules")
                
                # For surgical patching, focus on quality over quantity
                rejected_for_size = processing_stats.get("patches_rejected_for_size", 0)
                truly_minimal = processing_stats.get("truly_minimal_changes", 0)
                
                if high_quality_patches >= self.min_patches_required:
                    validation["patches_quality"] = "high"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} surgical patches with {high_quality_patches} high-quality patches"
                    if truly_minimal > 0:
                        validation["reason"] += f" ({truly_minimal} truly minimal)"
                elif avg_confidence >= 0.6 and surgical_patches > 0:
                    validation["patches_quality"] = "medium"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {surgical_patches} surgical patches with good confidence (avg: {avg_confidence:.3f})"
                elif len(patches) >= 1 and avg_confidence >= 0.4:
                    validation["patches_quality"] = "acceptable"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} surgical patches with acceptable confidence"
                else:
                    validation["patches_quality"] = "low"
                    validation["reason"] = f"Surgical patches have insufficient confidence (avg: {avg_confidence:.3f})"
                    validation["recommendations"].append("Review surgical prompting and validation thresholds")
                
                # Add size rejection information
                if rejected_for_size > 0:
                    validation["reason"] += f" | {rejected_for_size} patches rejected for size"
                    if validation["valid"]:
                        validation["recommendations"].append("Size validation prevented oversized patches - good!")
                    
            else:
                logger.info("📝 Applying standard validation rules")
                
                # Standard validation for non-surgical patching
                if high_quality_patches >= self.min_patches_required:
                    validation["patches_quality"] = "high"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} patches with {high_quality_patches} high-quality patches"
                elif avg_confidence >= 0.5:
                    validation["patches_quality"] = "medium"
                    validation["valid"] = True
                    validation["reason"] = f"Generated {len(patches)} patches with moderate confidence"
                else:
                    validation["patches_quality"] = "low"
                    validation["reason"] = f"Patches have low confidence scores (avg: {avg_confidence:.3f})"
                    validation["recommendations"].append("Review error analysis and file selection")
            
            # Add processing stats insights
            if processing_stats:
                processed_files = processing_stats.get("total_patches_generated", 0)
                no_fixes = processing_stats.get("files_with_no_relevant_fixes", 0)
                
                if processed_files > 0:
                    validation["reason"] += f" | Processed: {processed_files} files"
                if no_fixes > 0:
                    validation["reason"] += f", {no_fixes} had no relevant fixes"
            
            # Additional recommendations for surgical patching
            if validation["valid"] and using_surgical_features:
                if avg_confidence < 0.8:
                    validation["recommendations"].append("Consider refining surgical prompts for higher confidence")
                if surgical_patches < len(patches):
                    validation["recommendations"].append("Some patches may not be using surgical approach")
            
            logger.info(f"🎯 PIPELINE VALIDATION RESULT:")
            logger.info(f"  - Valid: {validation['valid']}")
            logger.info(f"  - Quality: {validation['patches_quality']}")
            logger.info(f"  - Using surgical patching: {validation['using_surgical_patching']}")
            logger.info(f"  - Reason: {validation['reason']}")
            
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
            surgical_patching = validation.get("using_surgical_patching", False)
            
            if quality in ["high"]:
                action["action"] = "create_pr"
                action["jira_status"] = "In Review"
                prefix = "🔧 AI Agent (Surgical Patching)" if surgical_patching else "✅ AI Agent"
                action["jira_comment"] = f"{prefix} generated high-quality patches. {validation['reason']}"
            elif quality in ["medium", "acceptable"]:
                action["action"] = "create_pr_with_review"
                action["jira_status"] = "In Review"
                prefix = "🔧 AI Agent (Surgical Patching)" if surgical_patching else "⚠️ AI Agent"
                action["jira_comment"] = f"{prefix} generated patches requiring review. {validation['reason']}"
                action["require_manual_review"] = True
            else:
                action["action"] = "manual_review"
                action["jira_status"] = "Needs Review"
                prefix = "🔧 AI Agent (Surgical Patching)" if surgical_patching else "🔍 AI Agent"
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
