
import openai
import os
import asyncio
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.default_model = "gpt-4o"
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def complete_chat(self, messages: List[Dict[str, str]], 
                           model: str = None, 
                           temperature: float = 0.1,
                           max_tokens: int = 4000) -> str:
        """Complete a chat conversation"""
        model = model or self.default_model
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise e
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        return ""
    
    async def analyze_code(self, code: str, error_trace: str) -> Dict[str, Any]:
        """Analyze code and error trace"""
        messages = [
            {"role": "system", "content": "You are an expert code analyzer. Provide structured analysis."},
            {"role": "user", "content": f"Analyze this code and error:\n\nCODE:\n{code}\n\nERROR:\n{error_trace}"}
        ]
        
        response = await self.complete_chat(messages)
        return {"analysis": response}
    
    async def generate_tests(self, code: str, function_name: str) -> str:
        """Generate unit tests for given code"""
        messages = [
            {"role": "system", "content": "You are an expert test writer. Generate comprehensive unit tests."},
            {"role": "user", "content": f"Generate unit tests for this function:\n\n{code}\n\nFunction: {function_name}"}
        ]
        
        return await self.complete_chat(messages)
