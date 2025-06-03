
import openai
from typing import List, Dict, Any, Optional
import os
import logging
import asyncio
from core.analysis_config import api_config, model_config, processing_config

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
                timeout=api_config.openai_timeout
            )
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    async def complete_chat(self, messages: List[Dict[str, str]], model: str = None, max_retries: int = None) -> str:
        """Complete a chat conversation with timeout and retry logic"""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Check API key and dependencies.")
        
        # Use configured defaults if not specified
        if model is None:
            model = model_config.default_model
        if max_retries is None:
            max_retries = api_config.openai_max_retries
        
        for attempt in range(max_retries):
            try:
                logger.info(f"OpenAI request attempt {attempt + 1}/{max_retries} using model {model}")
                
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=model_config.max_tokens_patch,
                        temperature=model_config.temperature
                    ),
                    timeout=api_config.openai_request_timeout
                )
                
                logger.info(f"OpenAI request successful on attempt {attempt + 1}")
                return response.choices[0].message.content
                
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI request timeout on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise Exception("OpenAI request timed out after all retries")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"OpenAI API error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def analyze_code_error(self, error_trace: str, code_context: str = "") -> str:
        """Analyze code error with enhanced timeout handling"""
        if not self.client:
            return '{"error": "OpenAI client not available", "suggestion": "Check API configuration"}'
        
        # Truncate content based on configuration
        truncated_error = error_trace[:processing_config.error_trace_limit]
        truncated_context = code_context[:processing_config.code_context_limit]
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert software engineer. Analyze the error and provide a detailed fix suggestion in JSON format. Keep responses concise but comprehensive."
            },
            {
                "role": "user",
                "content": f"Error trace:\n{truncated_error}\n\nCode context:\n{truncated_context}\n\nProvide analysis and fix suggestion."
            }
        ]
        
        try:
            return await self.complete_chat(
                messages, 
                model=model_config.analysis_model, 
                max_retries=2
            )
        except Exception as e:
            logger.error(f"Error in analyze_code_error: {e}")
            return f'{{"error": "Analysis failed: {str(e)}", "suggestion": "Manual review required"}}'
    
    async def generate_code_patch(self, analysis: str, file_content: str, error_description: str) -> str:
        """Generate code patch with enhanced error handling"""
        if not self.client:
            return '{"error": "OpenAI client not available", "patch_content": "", "explanation": "API not configured"}'
        
        # Truncate content based on configuration
        truncated_analysis = analysis[:processing_config.analysis_content_limit]
        truncated_content = file_content[:processing_config.file_content_limit]
        truncated_description = error_description[:processing_config.description_content_limit]
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert software engineer. Generate a minimal code patch to fix the issue. Provide the response in JSON format with 'patch_content', 'patched_code', 'test_code', and 'explanation' fields. Keep responses focused and precise."
            },
            {
                "role": "user",
                "content": f"Analysis: {truncated_analysis}\n\nCurrent file content:\n{truncated_content}\n\nError: {truncated_description}\n\nGenerate a patch to fix this issue."
            }
        ]
        
        try:
            return await self.complete_chat(
                messages, 
                model=model_config.patch_generation_model, 
                max_retries=2
            )
        except Exception as e:
            logger.error(f"Error in generate_code_patch: {e}")
            return f'{{"error": "Patch generation failed: {str(e)}", "patch_content": "", "explanation": "Manual intervention required"}}'
