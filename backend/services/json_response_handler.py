
import json
import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class JSONResponseHandler:
    """Enhanced JSON response handler with robust parsing and validation"""
    
    @staticmethod
    def clean_and_parse_json(response: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """Clean and parse JSON response with multiple fallback strategies"""
        if not response or not response.strip():
            logger.error("❌ Empty response received")
            return None, "Empty response"
        
        logger.info(f"🔍 Attempting to parse JSON response ({len(response)} chars)")
        
        # DEBUG: Log first 1000 characters of raw response
        logger.info(f"📝 RAW RESPONSE (first 1000 chars): {repr(response[:1000])}")
        
        # DEBUG: Log last 500 characters to see how response ends
        logger.info(f"📝 RAW RESPONSE (last 500 chars): {repr(response[-500:])}")
        
        # Strategy 1: Try direct parsing
        try:
            result = json.loads(response.strip())
            logger.info("✅ Direct JSON parsing successful")
            return result, ""
        except json.JSONDecodeError as e:
            logger.warning(f"❌ Direct parsing failed: {e}")
            logger.info(f"🔍 PARSE ERROR at position {e.pos}: {repr(response[max(0, e.pos-50):e.pos+50])}")
        
        # Strategy 2: Clean common markdown formatting
        cleaned = JSONResponseHandler._clean_markdown_formatting(response)
        logger.info(f"🧹 Cleaned markdown formatting ({len(cleaned)} chars)")
        try:
            result = json.loads(cleaned)
            logger.info("✅ Markdown cleanup parsing successful")
            return result, ""
        except json.JSONDecodeError as e:
            logger.warning(f"❌ Markdown cleanup parsing failed: {e}")
            logger.info(f"🔍 CLEANED RESPONSE (first 500 chars): {repr(cleaned[:500])}")
        
        # Strategy 3: Fix common JSON issues
        fixed = JSONResponseHandler._fix_common_json_issues(cleaned)
        logger.info(f"🔧 Applied JSON fixes ({len(fixed)} chars)")
        try:
            result = json.loads(fixed)
            logger.info("✅ JSON fixes parsing successful")
            return result, ""
        except json.JSONDecodeError as e:
            logger.warning(f"❌ JSON fixes parsing failed: {e}")
            logger.info(f"🔍 FIXED RESPONSE (first 500 chars): {repr(fixed[:500])}")
        
        # Strategy 4: Extract JSON from mixed content
        extracted = JSONResponseHandler._extract_json_from_text(response)
        if extracted:
            logger.info(f"🎯 Extracted JSON from text ({len(extracted)} chars)")
            try:
                result = json.loads(extracted)
                logger.info("✅ JSON extraction parsing successful")
                return result, ""
            except json.JSONDecodeError as e:
                logger.warning(f"❌ JSON extraction parsing failed: {e}")
                logger.info(f"🔍 EXTRACTED JSON: {repr(extracted)}")
        
        # Strategy 5: Try to build minimal valid JSON from response
        minimal_json = JSONResponseHandler._create_minimal_json(response)
        if minimal_json:
            logger.info("🔨 Created minimal JSON from response")
            try:
                result = json.loads(minimal_json)
                logger.info("✅ Minimal JSON parsing successful")
                return result, ""
            except json.JSONDecodeError as e:
                logger.warning(f"❌ Minimal JSON parsing failed: {e}")
        
        logger.error("💥 All JSON parsing strategies failed")
        logger.error(f"📝 Raw response sample: {response[:200]}...")
        return None, "Failed to parse JSON after all strategies"
    
    @staticmethod
    def _clean_markdown_formatting(text: str) -> str:
        """Remove markdown code block formatting"""
        # Remove ```json and ``` markers
        text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'```$', '', text)
        return text.strip()
    
    @staticmethod
    def _fix_common_json_issues(text: str) -> str:
        """Fix common JSON formatting issues"""
        # Fix unterminated strings by adding missing quotes
        lines = text.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Fix unterminated strings at end of line
            if '"' in line and line.count('"') % 2 == 1:
                if not line.rstrip().endswith('"'):
                    line = line.rstrip() + '"'
            fixed_lines.append(line)
        
        text = '\n'.join(fixed_lines)
        
        # Fix escaped quotes in strings
        text = re.sub(r'\\\'', "'", text)
        text = re.sub(r'(?<!\\)"([^"]*)"([^"]*)"', r'"\1\2"', text)
        
        return text
    
    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[str]:
        """Extract JSON object from mixed text content"""
        # Look for JSON object pattern
        json_pattern = r'\{(?:[^{}]|{[^{}]*})*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        # Return the largest match (likely the main JSON object)
        if matches:
            return max(matches, key=len)
        
        return None
    
    @staticmethod
    def _create_minimal_json(text: str) -> Optional[str]:
        """Create minimal valid JSON from response text"""
        try:
            # Look for key fields in the text
            patch_content = ""
            patched_code = ""
            explanation = "Minimal patch extracted from response"
            confidence_score = 0.5
            
            # Try to extract patch content
            patch_match = re.search(r'["\']?patch_content["\']?\s*:\s*["\']([^"\']*)["\']', text, re.IGNORECASE | re.DOTALL)
            if patch_match:
                patch_content = patch_match.group(1)
            
            # Try to extract patched code
            code_match = re.search(r'["\']?patched_code["\']?\s*:\s*["\']([^"\']*)["\']', text, re.IGNORECASE | re.DOTALL)
            if code_match:
                patched_code = code_match.group(1)
            
            # Try to extract explanation
            exp_match = re.search(r'["\']?explanation["\']?\s*:\s*["\']([^"\']*)["\']', text, re.IGNORECASE | re.DOTALL)
            if exp_match:
                explanation = exp_match.group(1)
            
            # Only create minimal JSON if we have some content
            if patch_content or patched_code:
                minimal_json = {
                    "patch_content": patch_content,
                    "patched_code": patched_code,
                    "explanation": explanation,
                    "confidence_score": confidence_score,
                    "lines_modified": 1,
                    "commit_message": "Minimal patch fix"
                }
                return json.dumps(minimal_json)
            
        except Exception as e:
            logger.warning(f"Failed to create minimal JSON: {e}")
        
        return None
    
    @staticmethod
    def validate_patch_json(data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate that JSON contains required patch fields"""
        required_fields = ["patch_content", "patched_code", "explanation"]
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
            if not data[field] or not str(data[field]).strip():
                return False, f"Empty required field: {field}"
        
        # Validate confidence score
        confidence = data.get("confidence_score", 0)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            return False, "Invalid confidence score (must be 0-1)"
        
        return True, ""
