"""
AI Agent for the YouTube Summarizer Bot.
Handles OpenAI API interactions for various AI tasks.
"""
import asyncio
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
from loguru import logger
from src.config.settings import OPENAI_API_KEY
from src.config.prompts import SYSTEM_PROMPTS, SUMMARIZE_PROMPT, COMBINE_SUMMARIES_PROMPT, ERROR_RESPONSE_PROMPT, UNKNOWN_MESSAGE_PROMPT, ACCESS_REQUEST_ADMIN_PROMPT

class AIAgent:
    """
    AI Agent that handles OpenAI API interactions.
    Provides methods for different AI tasks like summarization, error handling, etc.
    """
    def __init__(self):
        """
        Initializes the AI Agent with OpenAI client.
        """
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info("AI Agent initialized with OpenAI client")
    
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
                "gpt-4o-mini"
            ]
            logger.info(f"Using fallback model list: {fallback_models}")
            return fallback_models
    
    async def summarize_text(self, text: str, title: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Summarize text using OpenAI API.
        
        Args:
            text: Text to summarize
            title: Title of the content
            model: OpenAI model to use
            
        Returns:
            str: Generated summary
        """
        try:
            logger.info(f"Summarizing text with length {len(text)} using model {model}")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS["summarizer"]},
                    {"role": "user", "content": SUMMARIZE_PROMPT.format(title=title, text=text)}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary with length {len(summary)}")
            return summary
        except Exception as e:
            logger.error(f"Error summarizing text: {str(e)}")
            raise
    
    async def combine_summaries(self, summaries: List[str], title: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Combine multiple summaries into one coherent summary.
        
        Args:
            summaries: List of summaries to combine
            title: Title of the content
            model: OpenAI model to use
            
        Returns:
            str: Combined summary
        """
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
            return combined_summary
        except Exception as e:
            logger.error(f"Error combining summaries: {str(e)}")
            raise
    
    async def generate_error_response(self, video_url: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Generate a user-friendly error response.
        
        Args:
            video_url: URL of the video that caused the error
            model: OpenAI model to use
            
        Returns:
            str: User-friendly error message
        """
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
    
    async def handle_unknown_message(self, text: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Generate a response for unknown messages.
        
        Args:
            text: User's message text
            model: OpenAI model to use
            
        Returns:
            str: Response message
        """
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
            
    async def generate_admin_notification(self, user_data: Dict[str, Any], model: str = "gpt-3.5-turbo") -> str:
        """
        Generate a notification for admin about a user requesting access.
        
        Args:
            user_data: User data dictionary
            model: OpenAI model to use
            
        Returns:
            str: Admin notification message
        """
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