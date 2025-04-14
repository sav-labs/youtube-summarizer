"""
Summarizer module for the YouTube Summarizer Bot.
Handles text summarization using OpenAI API.
"""
import re
import time
from typing import List, Optional
from loguru import logger
from src.ai_agent import AIAgent
from src.config.settings import DEFAULT_CHUNK_SIZE, LARGE_CONTEXT_CHUNK_SIZE, DEFAULT_MODEL

class Summarizer:
    """
    Handles text summarization using OpenAI API through AI agent.
    """
    def __init__(self):
        """
        Initializes the summarizer with the AI agent.
        """
        self.ai_agent = AIAgent()
        self.model = DEFAULT_MODEL
        self.chunk_size = DEFAULT_CHUNK_SIZE
        logger.info(f"Summarizer initialized with default model: {self.model}, chunk size: {self.chunk_size}")
    
    async def list_available_models(self) -> List[str]:
        """
        Gets a list of available models for summarization.
        
        Returns:
            List[str]: List of available model names
        """
        try:
            models = await self.ai_agent.list_models()
            logger.info(f"Retrieved {len(models)} available models")
            return models
        except Exception as e:
            logger.error(f"Error retrieving models: {str(e)}")
            # Fall back to a static list if API call fails
            models = [
                "gpt-3.5-turbo", 
                "gpt-3.5-turbo-16k",
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini"
            ]
            logger.info(f"Using fallback model list: {models}")
            return models
    
    def get_optimal_chunk_size(self, model: str) -> int:
        """
        Determines the optimal chunk size based on the model's context window.
        
        Args:
            model: Model name
            
        Returns:
            int: Optimal chunk size in characters
        """
        if any(marker in model.lower() for marker in ["32k", "128k"]):
            return 12000  # For models with very large context windows
        elif any(marker in model.lower() for marker in ["16k", "turbo", "preview"]):
            return 8000   # For models with larger context windows
        elif model.lower().endswith(("o", "o-mini")):  # GPT-4o models
            return 8000
        else:
            return DEFAULT_CHUNK_SIZE  # For base models
    
    def split_text_into_chunks(self, text: str, chunk_size: Optional[int] = None) -> List[str]:
        """
        Splits text into chunks for processing.
        Uses sentence boundaries to avoid breaking sentences between chunks.
        
        Args:
            text: Text to split
            chunk_size: Maximum size of each chunk (optional)
            
        Returns:
            List[str]: List of text chunks
        """
        if chunk_size is None:
            chunk_size = self.chunk_size
            
        # If text is short enough, return as is
        if len(text) <= chunk_size:
            return [text]
        
        # Split by paragraph boundaries first
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        
        # Group paragraphs into chunks
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # If adding this paragraph would exceed chunk size, start a new chunk
            if len(current_chunk) + len(paragraph) + 4 > chunk_size and current_chunk:  # +4 for "\n\n"
                chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        # Handle case where a single paragraph is too long for a chunk
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= chunk_size:
                final_chunks.append(chunk)
            else:
                # Split long paragraphs by sentence boundaries
                sentences = re.split(r'(?<=[.!?])\s+', chunk)
                sub_chunk = ""
                
                for sentence in sentences:
                    if len(sub_chunk) + len(sentence) + 2 <= chunk_size and sub_chunk:  # +2 for space
                        sub_chunk += " " + sentence
                    elif len(sub_chunk) + len(sentence) <= chunk_size:
                        sub_chunk += sentence
                    else:
                        if sub_chunk:
                            final_chunks.append(sub_chunk)
                        
                        # If the sentence itself is too long, split it
                        if len(sentence) > chunk_size:
                            # Split by words
                            words = sentence.split()
                            sub_chunk = ""
                            
                            for word in words:
                                if len(sub_chunk) + len(word) + 1 <= chunk_size and sub_chunk:  # +1 for space
                                    sub_chunk += " " + word
                                elif len(sub_chunk) + len(word) <= chunk_size:
                                    sub_chunk += word
                                else:
                                    if sub_chunk:
                                        final_chunks.append(sub_chunk)
                                    sub_chunk = word
                            
                            if sub_chunk:
                                sub_chunk = sub_chunk
                        else:
                            sub_chunk = sentence
                
                if sub_chunk:
                    final_chunks.append(sub_chunk)
        
        logger.info(f"Split text into {len(final_chunks)} chunks (average chunk size: {sum(len(c) for c in final_chunks) // len(final_chunks)} chars)")
        return final_chunks
    
    async def summarize(self, text: str, title: str = "", model: Optional[str] = None) -> str:
        """
        Summarizes text using the OpenAI API through the AI agent.
        
        Args:
            text: Text to summarize
            title: Content title
            model: Model to use (falls back to default if not specified)
            
        Returns:
            str: Summarized text
        """
        if not text:
            logger.error("Received empty text for summarization")
            return "Не удалось создать суммаризацию из-за пустого текста."

        logger.info(f"Starting summarization of text with length {len(text)} characters")
        start_time = time.time()
        
        # Use specified model or default
        model_to_use = model or self.model
        logger.info(f"Using model {model_to_use} for summarization")
        
        # Determine optimal chunk size for the selected model
        chunk_size = self.get_optimal_chunk_size(model_to_use)
        
        # If text is too long for a single request, split it
        if len(text) > chunk_size:
            logger.info(f"Text exceeds {chunk_size} characters, splitting into chunks")
            result = await self._split_and_summarize(text, title, model_to_use, chunk_size)
        else:
            result = await self.ai_agent.summarize_text(text, title, model_to_use)
        
        # Measure total execution time
        total_time = time.time() - start_time
        logger.info(f"Total summarization time: {total_time:.2f} seconds")
        
        return result
    
    async def _split_and_summarize(self, text: str, title: str, model: str, chunk_size: int) -> str:
        """
        Splits text into chunks, summarizes each chunk, and combines the summaries.
        
        Args:
            text: Text to summarize
            title: Content title
            model: Model to use
            chunk_size: Maximum chunk size
            
        Returns:
            str: Combined summary
        """
        # Split text into chunks
        chunks = self.split_text_into_chunks(text, chunk_size)
        logger.info(f"Split text into {len(chunks)} chunks for processing")
        
        # Summarize each chunk
        summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Summarizing chunk {i+1}/{len(chunks)} with length {len(chunk)}")
            
            try:
                chunk_summary = await self.ai_agent.summarize_text(chunk, f"{title} (часть {i+1} из {len(chunks)})", model)
                summaries.append(chunk_summary)
                logger.info(f"Completed summary for chunk {i+1}/{len(chunks)}")
            except Exception as e:
                logger.error(f"Error summarizing chunk {i+1}: {str(e)}")
                summaries.append(f"Ошибка при обработке части {i+1}: {str(e)}")
        
        # If only one chunk was processed, return its summary
        if len(summaries) == 1:
            return summaries[0]
        
        # Otherwise, combine the summaries
        logger.info(f"Combining {len(summaries)} chunk summaries")
        try:
            combined_summary = await self.ai_agent.combine_summaries(summaries, title, model)
            return combined_summary
        except Exception as e:
            logger.error(f"Error combining summaries: {str(e)}")
            # Fallback: join summaries with headers
            fallback = "\n\n".join([f"## Часть {i+1}\n\n{summary}" for i, summary in enumerate(summaries)])
            return fallback 