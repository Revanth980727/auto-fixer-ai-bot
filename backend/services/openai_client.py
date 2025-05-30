
import openai
from typing import List, Dict, Any, Optional
import os
import logging

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.client: Optional[openai.AsyncOpenAI] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client with error handling"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found. Client will not function properly.")
            return
        
        try:
            self.client = openai.AsyncOpenAI(
                api_key=api_key,
                timeout=30.0
            )
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    async def complete_chat(self, messages: List[Dict[str, str]], model: str = "gpt-4o") -> str:
        """Complete a chat conversation using GPT-4"""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Check API key and dependencies.")
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2000,
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise e
    
    async def analyze_code_error(self, error_trace: str, code_context: str = "") -> str:
        """Analyze code error and suggest fixes"""
        if not self.client:
            return '{"error": "OpenAI client not available", "suggestion": "Check API configuration"}'
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert software engineer. Analyze the error and provide a detailed fix suggestion in JSON format."
            },
            {
                "role": "user",
                "content": f"Error trace:\n{error_trace}\n\nCode context:\n{code_context}\n\nProvide analysis and fix suggestion."
            }
        ]
        
        return await self.complete_chat(messages)
    
    async def generate_code_patch(self, analysis: str, file_content: str, error_description: str) -> str:
        """Generate code patch based on analysis"""
        if not self.client:
            return '{"error": "OpenAI client not available", "patch_content": "", "explanation": "API not configured"}'
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert software engineer. Generate a minimal code patch to fix the issue. Provide the response in JSON format with 'patch_content', 'patched_code', 'test_code', and 'explanation' fields."
            },
            {
                "role": "user",
                "content": f"Analysis: {analysis}\n\nCurrent file content:\n{file_content}\n\nError: {error_description}\n\nGenerate a patch to fix this issue."
            }
        ]
        
        return await self.complete_chat(messages)
