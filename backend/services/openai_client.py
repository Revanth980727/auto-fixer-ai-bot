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
        self.max_request_size = 100000  # 100KB limit for single requests
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
    
    def _check_request_size(self, messages: List[Dict[str, str]]) -> bool:
        """Check if request size is within limits"""
        total_size = sum(len(str(msg)) for msg in messages)
        if total_size > self.max_request_size:
            logger.warning(f"Request size {total_size} exceeds limit {self.max_request_size}")
            return False
        return True
    
    async def complete_chat(self, messages: List[Dict[str, str]], model: str = None, max_retries: int = None, force_json: bool = False) -> str:
        """Complete a chat conversation with enhanced timeout and monitoring"""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Check API key and dependencies.")
        
        # Check request size
        if not self._check_request_size(messages):
            raise Exception("Request size exceeds maximum allowed limit")
        
        # Use configured defaults if not specified
        if model is None:
            model = model_config.default_model
        if max_retries is None:
            max_retries = api_config.openai_max_retries
        
        # Reduce timeout for patch generation to detect hangs faster
        timeout = 120.0 if "patch" in str(messages).lower() else api_config.openai_request_timeout
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🤖 OpenAI request attempt {attempt + 1}/{max_retries} using model {model}")
                logger.info(f"📊 Request size: {sum(len(str(msg)) for msg in messages)} characters")
                logger.info(f"⏱️ Timeout set to: {timeout}s")
                
                # Add heartbeat logging for long requests
                async def heartbeat():
                    for i in range(int(timeout // 10)):
                        await asyncio.sleep(10)
                        logger.info(f"💓 Still processing OpenAI request... ({(i+1)*10}s elapsed)")
                
                heartbeat_task = asyncio.create_task(heartbeat())
                
                try:
                    # Prepare completion parameters
                    completion_params = {
                        "model": model,
                        "messages": messages,
                        "max_tokens": model_config.max_tokens_patch,
                        "temperature": model_config.temperature
                    }
                    
                    # Force JSON mode for patch generation if requested
                    if force_json and model in ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]:
                        completion_params["response_format"] = {"type": "json_object"}
                    
                    response = await asyncio.wait_for(
                        self.client.chat.completions.create(**completion_params),
                        timeout=timeout
                    )
                    
                    heartbeat_task.cancel()
                    
                    # Log raw response for debugging
                    raw_content = response.choices[0].message.content
                    if force_json:
                        logger.info(f"📝 Raw OpenAI JSON response (first 500 chars): {raw_content[:500]}")
                    
                    logger.info(f"✅ OpenAI request successful on attempt {attempt + 1}")
                    return raw_content
                    
                except asyncio.CancelledError:
                    heartbeat_task.cancel()
                    raise
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ OpenAI request timeout ({timeout}s) on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise Exception(f"OpenAI request timed out after {timeout}s and all retries")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"💥 OpenAI API error on attempt {attempt + 1}/{max_retries}: {e}")
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
