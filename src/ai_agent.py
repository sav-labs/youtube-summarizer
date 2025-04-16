"""
AI Agent for the YouTube Summarizer Bot.
Handles OpenAI API interactions for various AI tasks.
"""
import asyncio
import os
import json
import hashlib
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
import httpx
from loguru import logger
from src.config.settings import (
    OPENAI_API_KEY, 
    MODEL_CONTEXT_LIMITS,
    DEFAULT_CONTEXT_WINDOW
)
from src.config.prompts import (
    SYSTEM_PROMPTS, SYSTEM_PROMPTS_CONFIG, SUMMARIZE_PROMPT, COMBINE_SUMMARIES_PROMPT, 
    ERROR_RESPONSE_PROMPT, UNKNOWN_MESSAGE_PROMPT, ACCESS_REQUEST_ADMIN_PROMPT,
    save_custom_prompts
)

class AIAgent:
    """
    AI Agent that handles OpenAI API interactions.
    Provides methods for different AI tasks like summarization, error handling, etc.
    """
    def __init__(self):
        """
        Initializes the AI Agent with OpenAI client.
        """
        # Create a clean httpx client with no proxy settings
        http_client = httpx.AsyncClient()
        
        # Initialize the OpenAI client with our custom http_client
        self.client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            http_client=http_client
        )
        
        # Initialize cache
        self.cache_dir = os.path.join("data", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.info("AI Agent initialized with OpenAI client and caching")
    
    def _generate_cache_key(self, text: str, title: str, model: str) -> str:
        """
        Generate a cache key based on input parameters.
        
        Args:
            text: Input text
            title: Content title
            model: OpenAI model used
            
        Returns:
            str: Cache key (MD5 hash)
        """
        # Create a unique identifier based on text, title and model
        content = f"{text}|{title}|{model}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """
        Try to get a cached response.
        
        Args:
            cache_key: Cache key to look for
            
        Returns:
            Optional[str]: Cached response or None if not found
        """
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Cache hit for key {cache_key}")
                    return data.get('response')
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        return None
    
    def _cache_response(self, cache_key: str, response: str) -> None:
        """
        Cache a response for future use.
        
        Args:
            cache_key: Cache key to store under
            response: Response to cache
        """
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'response': response}, f, ensure_ascii=False, indent=2)
            logger.info(f"Cached response for key {cache_key}")
        except Exception as e:
            logger.error(f"Error writing cache: {e}")
    
    def get_model_context_limit(self, model: str) -> int:
        """
        Get the context window limit for a specific model.
        
        Args:
            model: Model name
            
        Returns:
            int: Context window size in characters
        """
        # Exact match for gpt-4.1-nano to ensure it doesn't match with gpt-4
        if "gpt-4.1-nano" in model.lower():
            return MODEL_CONTEXT_LIMITS["gpt-4.1-nano"]
        
        # Check other models
        for model_key, context_limit in MODEL_CONTEXT_LIMITS.items():
            # Skip gpt-4.1-nano since we already checked it
            if model_key == "gpt-4.1-nano":
                continue
                
            if model.lower().startswith(model_key.lower()):
                return context_limit
        
        # Return default if model not found
        logger.warning(f"No context limit found for model {model}, using default {DEFAULT_CONTEXT_WINDOW}")
        return DEFAULT_CONTEXT_WINDOW
    
    async def list_models(self) -> List[str]:
        """
        List available OpenAI models.
        
        Returns:
            List[str]: List of model IDs
        """
        try:
            models = await self.client.models.list()
            # Filter to only GPT models
            gpt_models = [model.id for model in models.data if 'gpt' in model.id.lower()]
            logger.info(f"Retrieved {len(gpt_models)} GPT models from OpenAI API")
            return gpt_models
        except Exception as e:
            logger.error(f"Failed to list models: {str(e)}")
            # Fallback to static list
            fallback_models = [
                "gpt-3.5-turbo", 
                "gpt-3.5-turbo-16k",
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4.1-nano"
            ]
            logger.info(f"Using fallback model list: {fallback_models}")
            return fallback_models
    
    def get_default_model(self, prompt_type: str) -> str:
        """
        Get the default model for a specific prompt type.
        
        Args:
            prompt_type: Type of prompt (summarizer, error_handler, etc.)
            
        Returns:
            str: Default model for the prompt type
        """
        try:
            return SYSTEM_PROMPTS_CONFIG.get(prompt_type, {}).get("model", "gpt-4.1-nano")
        except Exception as e:
            logger.error(f"Error getting default model for {prompt_type}: {e}")
            return "gpt-4.1-nano"
    
    async def update_prompt_model(self, prompt_type: str, model: str) -> bool:
        """
        Update the default model for a prompt type.
        
        Args:
            prompt_type: Type of prompt to update
            model: New model to use
            
        Returns:
            bool: True if update was successful
        """
        try:
            if prompt_type in SYSTEM_PROMPTS_CONFIG:
                SYSTEM_PROMPTS_CONFIG[prompt_type]["model"] = model
                save_custom_prompts(SYSTEM_PROMPTS_CONFIG)
                logger.info(f"Updated default model for {prompt_type} to {model}")
                return True
            else:
                logger.error(f"Prompt type {prompt_type} not found")
                return False
        except Exception as e:
            logger.error(f"Error updating prompt model: {e}")
            return False
    
    async def summarize_text(self, text: str, title: str, model: str = None) -> str:
        """
        Summarize text using OpenAI API.
        
        Args:
            text: Text to summarize
            title: Title of the content
            model: OpenAI model to use (optional, uses default if None)
            
        Returns:
            str: Generated summary
        """
        # Use default model if none provided
        if model is None:
            model = self.get_default_model("summarizer")
        
        # Generate cache key
        cache_key = self._generate_cache_key(text, title, model)
        
        # Try to get from cache first
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.info(f"Returning cached summary response for {title}")
            return cached_response
        
        try:
            logger.info(f"Summarizing text with length {len(text)} using model {model}")
            
            # Get appropriate token limit based on model
            max_tokens = 1000
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS["summarizer"]},
                    {"role": "user", "content": SUMMARIZE_PROMPT.format(title=title, text=text)}
                ],
                temperature=0.5,
                max_tokens=max_tokens
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary with length {len(summary)}")
            
            # Cache the response
            self._cache_response(cache_key, summary)
            
            return summary
        except Exception as e:
            logger.error(f"Error summarizing text: {str(e)}")
            raise
    
    async def combine_summaries(self, summaries: List[str], title: str, model: str = None) -> str:
        """
        Combine multiple summaries into one coherent summary.
        
        Args:
            summaries: List of summaries to combine
            title: Title of the content
            model: OpenAI model to use (optional, uses default if None)
            
        Returns:
            str: Combined summary
        """
        # Use default model if none provided
        if model is None:
            model = self.get_default_model("summarizer")
        
        # Generate cache key based on all summaries
        combined_text = "\n".join(summaries)
        cache_key = self._generate_cache_key(combined_text, title, model)
        
        # Try to get from cache first
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.info(f"Returning cached combined summary for {title}")
            return cached_response
        
        try:
            combined_input = "\n\n---\n\n".join(summaries)
            logger.info(f"Combining {len(summaries)} summaries using model {model}")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS["summarizer"]},
                    {"role": "user", "content": COMBINE_SUMMARIES_PROMPT.format(
                        title=title, 
                        summaries=combined_input
                    )}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            combined_summary = response.choices[0].message.content.strip()
            logger.info(f"Generated combined summary with length {len(combined_summary)}")
            
            # Cache the response
            self._cache_response(cache_key, combined_summary)
            
            return combined_summary
        except Exception as e:
            logger.error(f"Error combining summaries: {str(e)}")
            raise
    
    async def get_openai_balance(self) -> Dict[str, Any]:
        """
        Get the remaining balance for the OpenAI API key.
        
        Returns:
            Dict[str, Any]: Balance information including total_available, total_used, and expires_at
        """
        try:
            # This endpoint might change depending on OpenAI's API structure
            # We're using a direct HTTP request as the OpenAI SDK might not have this endpoint
            url = "https://api.openai.com/dashboard/billing/credit_grants"
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    balance_data = response.json()
                    logger.info(f"Successfully retrieved OpenAI balance information")
                    return {
                        "total_available": balance_data.get("total_available", 0),
                        "total_used": balance_data.get("total_used", 0),
                        "expires_at": balance_data.get("grants", {}).get("data", [{}])[0].get("expires_at", "Unknown")
                    }
                else:
                    logger.error(f"Failed to get OpenAI balance: {response.status_code} - {response.text}")
                    return {
                        "error": f"API returned status code {response.status_code}",
                        "message": response.text
                    }
                    
        except Exception as e:
            logger.error(f"Error getting OpenAI balance: {str(e)}")
            return {"error": str(e)}
    
    async def generate_error_response(self, video_url: str, model: str = None) -> str:
        """
        Generate a user-friendly error response.
        
        Args:
            video_url: URL of the video that caused the error
            model: OpenAI model to use (optional, uses default if None)
            
        Returns:
            str: User-friendly error message
        """
        # Use default model if none provided
        if model is None:
            model = self.get_default_model("error_handler")
        
        try:
            logger.info(f"Generating error response for URL {video_url}")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS["error_handler"]},
                    {"role": "user", "content": ERROR_RESPONSE_PROMPT.format(video_url=video_url)}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            error_message = response.choices[0].message.content.strip()
            logger.info(f"Generated error message with length {len(error_message)}")
            return error_message
        except Exception as e:
            logger.error(f"Error generating error response: {str(e)}")
            return "Не удалось получить информацию об этом видео. Пожалуйста, проверьте ссылку и попробуйте другое видео."
    
    async def handle_unknown_message(self, text: str, model: str = None) -> str:
        """
        Generate a response for unknown messages.
        
        Args:
            text: User's message text
            model: OpenAI model to use (optional, uses default if None)
            
        Returns:
            str: Response message
        """
        # Use default model if none provided
        if model is None:
            model = self.get_default_model("error_handler")
        
        try:
            logger.info(f"Handling unknown message: {text[:50]}...")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS["error_handler"]},
                    {"role": "user", "content": UNKNOWN_MESSAGE_PROMPT.format(text=text)}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            message = response.choices[0].message.content.strip()
            logger.info(f"Generated response for unknown message with length {len(message)}")
            return message
        except Exception as e:
            logger.error(f"Error handling unknown message: {str(e)}")
            return "Бот работает только с ссылками на YouTube видео. Пожалуйста, отправьте ссылку на YouTube видео."
            
    async def generate_admin_notification(self, user_data: Dict[str, Any], model: str = None) -> str:
        """
        Generate a notification for admin about a user requesting access.
        
        Args:
            user_data: User data dictionary
            model: OpenAI model to use (optional, uses default if None)
            
        Returns:
            str: Admin notification message
        """
        # Use default model if none provided
        if model is None:
            model = self.get_default_model("admin_assistant")
        
        try:
            logger.info(f"Generating admin notification for user {user_data.get('user_id')}")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS["admin_assistant"]},
                    {"role": "user", "content": ACCESS_REQUEST_ADMIN_PROMPT.format(**user_data)}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            message = response.choices[0].message.content.strip()
            logger.info(f"Generated admin notification with length {len(message)}")
            return message
        except Exception as e:
            logger.error(f"Error generating admin notification: {str(e)}")
            return f"Пользователь {user_data.get('user_name')} (ID: {user_data.get('user_id')}) запрашивает доступ к боту." 