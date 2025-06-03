
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
            return None, "Empty response"
        
        # Strategy 1: Try direct parsing
        try:
            return json.loads(response.strip()), ""
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Clean common markdown formatting
        cleaned = JSONResponseHandler._clean_markdown_formatting(response)
        try:
            return json.loads(cleaned), ""
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Fix common JSON issues
        fixed = JSONResponseHandler._fix_common_json_issues(cleaned)
        try:
            return json.loads(fixed), ""
        except json.JSONDecodeError:
            pass
        
        # Strategy 4: Extract JSON from mixed content
        extracted = JSONResponseHandler._extract_json_from_text(response)
        if extracted:
            try:
                return json.loads(extracted), ""
            except json.JSONDecodeError:
                pass
        
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
