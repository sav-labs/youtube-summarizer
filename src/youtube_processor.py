"""
YouTube Processor for the YouTube Summarizer Bot.
Handles fetching transcripts and metadata from YouTube videos.
"""
import re
import aiohttp
from pathlib import Path
from typing import List, Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from loguru import logger
import asyncio
import xml.etree.ElementTree as ET

class YouTubeProcessor:
    """
    Handles fetching and processing YouTube video transcripts.
    """
    def __init__(self, temp_dir: str = "temp"):
        """
        Initializes the YouTube processor.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.temp_dir = temp_dir
        # Create temp directory if it doesn't exist
        Path(temp_dir).mkdir(exist_ok=True)
        logger.info(f"YouTubeProcessor initialized, temp directory: {temp_dir}")
    
    async def extract_video_id(self, url: str) -> str:
        """
        Extracts the video ID from a YouTube URL.
        
        Args:
            url: YouTube video URL
            
        Returns:
            str: YouTube video ID
            
        Raises:
            ValueError: If the video ID cannot be extracted
        """
        # Regular expressions for extracting video ID from different URL formats
        youtube_regex = [
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&\s]+)',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^\?\s]+)',
            r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^\?\s]+)',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([^\?\s]+)'
        ]
        
        for pattern in youtube_regex:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        logger.error(f"Failed to extract video ID from URL: {url}")
        raise ValueError(f"Failed to extract video ID from URL: {url}")
    
    async def get_video_info(self, video_id: str) -> dict:
        """
        Gets information about a YouTube video including title and author.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            dict: Dictionary containing video information (title, author_name)
        """
        try:
            # Get video info through YouTube oEmbed API
            api_url = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        video_info = await response.json()
                        title = video_info.get('title', f"Video {video_id}")
                        author = video_info.get('author_name', 'Unknown creator')
                        logger.info(f"Got video info: '{title}' by {author} (ID: {video_id})")
                        return {
                            'title': title,
                            'author_name': author
                        }
                    else:
                        logger.warning(f"Failed to get video info, status: {response.status}")
                        return {
                            'title': f"Video {video_id}",
                            'author_name': 'Unknown creator'
                        }
                
        except Exception as e:
            logger.warning(f"Error getting video info: {str(e)}")
            return {
                'title': f"Video {video_id}",
                'author_name': 'Unknown creator'
            }
    
    def _validate_subtitle_data(self, data) -> bool:
        """
        Validates subtitle data before processing.
        
        Args:
            data: Subtitle data to validate
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        if not data:
            return False
        
        if isinstance(data, str):
            # Check if it's empty or just whitespace
            if not data.strip():
                return False
            # Check if it looks like valid XML
            try:
                ET.fromstring(data)
                return True
            except ET.ParseError:
                return False
        
        if isinstance(data, list):
            # Check if list is not empty and contains valid items
            if not data:
                return False
            # Check first item to see if it has expected structure
            first_item = data[0]
            return isinstance(first_item, dict) and 'text' in first_item
        
        return False

    async def get_subtitles(self, video_id: str, languages: List[str] = None) -> str:
        """
        Gets subtitles for a YouTube video using youtube-transcript-api 1.2.1.
        
        Args:
            video_id: YouTube video ID
            languages: List of language codes to try, in order of preference
            
        Returns:
            str: Video transcript text
            
        Raises:
            Exception: If subtitles cannot be retrieved
        """
        if languages is None:
            languages = ['ru', 'en']
            
        logger.info(f"Getting subtitles for video ID: {video_id}, preferred languages: {languages}")
        
        loop = asyncio.get_event_loop()
        
        # Method 1: Try direct transcript API with each language
        for lang in languages:
            try:
                logger.debug(f"Trying direct API for language: {lang}")
                transcript = await loop.run_in_executor(
                    None, lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                )
                
                if transcript and len(transcript) > 0:
                    subtitle_text = self._construct_transcript_text(transcript)
                    if subtitle_text and len(subtitle_text.strip()) >= 10:
                        logger.info(f"Direct API successful for {lang}: {len(subtitle_text)} chars")
                        return subtitle_text
                        
            except Exception as e:
                logger.debug(f"Direct API failed for {lang}: {str(e)}")
                continue
        
        # Method 2: Try with transcript list and find available
        try:
            logger.debug("Trying transcript list approach")
            transcript_list = await loop.run_in_executor(
                None, lambda: YouTubeTranscriptApi.list_transcripts(video_id)
            )
            
            # Try each preferred language
            for lang in languages:
                try:
                    transcript_obj = await loop.run_in_executor(
                        None, lambda: transcript_list.find_transcript([lang])
                    )
                    
                    if transcript_obj:
                        transcript = await loop.run_in_executor(None, transcript_obj.fetch)
                        if transcript and len(transcript) > 0:
                            subtitle_text = self._construct_transcript_text(transcript)
                            if subtitle_text and len(subtitle_text.strip()) >= 10:
                                logger.info(f"Transcript list successful for {lang}: {len(subtitle_text)} chars")
                                return subtitle_text
                                
                except Exception as e:
                    logger.debug(f"Transcript list failed for {lang}: {str(e)}")
                    continue
            
            # Try auto-generated transcripts
            logger.debug("Trying auto-generated transcripts")
            try:
                transcript_obj = await loop.run_in_executor(
                    None, lambda: transcript_list.find_generated_transcript(languages)
                )
                
                if transcript_obj:
                    transcript = await loop.run_in_executor(None, transcript_obj.fetch)
                    if transcript and len(transcript) > 0:
                        subtitle_text = self._construct_transcript_text(transcript)
                        if subtitle_text and len(subtitle_text.strip()) >= 10:
                            logger.info(f"Auto-generated successful: {len(subtitle_text)} chars")
                            return subtitle_text
                            
            except Exception as e:
                logger.debug(f"Auto-generated failed: {str(e)}")
            
            # Try any available transcript
            logger.debug("Trying any available transcript")
            available_transcripts = list(transcript_list)
            for transcript_obj in available_transcripts:
                try:
                    transcript = await loop.run_in_executor(None, transcript_obj.fetch)
                    if transcript and len(transcript) > 0:
                        subtitle_text = self._construct_transcript_text(transcript)
                        if subtitle_text and len(subtitle_text.strip()) >= 10:
                            logger.info(f"Any available successful ({transcript_obj.language_code}): {len(subtitle_text)} chars")
                            return subtitle_text
                            
                except Exception as e:
                    logger.debug(f"Available transcript failed ({transcript_obj.language_code}): {str(e)}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Transcript list approach failed: {str(e)}")
        
        # Method 3: Try with different video URL formats
        logger.debug("Trying different URL formats")
        url_variants = [
            video_id,  # Just ID
            f"https://www.youtube.com/watch?v={video_id}",  # Full URL
            f"https://youtu.be/{video_id}",  # Short URL
        ]
        
        for url_variant in url_variants:
            for lang in languages:
                try:
                    logger.debug(f"Trying URL variant {url_variant} with language {lang}")
                    transcript = await loop.run_in_executor(
                        None, lambda: YouTubeTranscriptApi.get_transcript(url_variant, languages=[lang])
                    )
                    
                    if transcript and len(transcript) > 0:
                        subtitle_text = self._construct_transcript_text(transcript)
                        if subtitle_text and len(subtitle_text.strip()) >= 10:
                            logger.info(f"URL variant successful: {len(subtitle_text)} chars")
                            return subtitle_text
                            
                except Exception as e:
                    logger.debug(f"URL variant failed for {url_variant} lang {lang}: {str(e)}")
                    continue
        
        # Method 4: Try with manual language codes including auto-generated
        logger.debug("Trying extended language codes")
        extended_languages = []
        for lang in languages:
            extended_languages.extend([
                lang, 
                f"{lang}-orig", 
                f"{lang}-auto", 
                f"{lang}-generated"
            ])
        
        for lang in extended_languages:
            try:
                logger.debug(f"Trying extended language: {lang}")
                transcript = await loop.run_in_executor(
                    None, lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                )
                
                if transcript and len(transcript) > 0:
                    subtitle_text = self._construct_transcript_text(transcript)
                    if subtitle_text and len(subtitle_text.strip()) >= 10:
                        logger.info(f"Extended language successful for {lang}: {len(subtitle_text)} chars")
                        return subtitle_text
                        
            except Exception as e:
                logger.debug(f"Extended language failed for {lang}: {str(e)}")
                continue
        
        # All methods failed
        raise Exception(f"Не удалось получить субтитры для видео {video_id}.\n\n"
                      f"Попробованы все доступные методы:\n"
                      f"• Прямой API запрос\n"
                      f"• Поиск через список транскриптов\n"
                      f"• Автогенерируемые субтитры\n"
                      f"• Различные форматы URL\n"
                      f"• Расширенные языковые коды\n\n"
                      f"Видео может не содержать субтитров или они недоступны.")
    
    def _construct_transcript_text(self, subtitle_data: List[dict]) -> str:
        """
        Constructs transcript text from subtitle data, preserving sentence structure.
        
        Args:
            subtitle_data: List of subtitle items (dict with 'text', 'start' and 'duration')
            
        Returns:
            str: Formatted transcript text
        """
        if not subtitle_data:
            return ""
        
        # Sort subtitle items by start time
        sorted_items = sorted(subtitle_data, key=lambda x: x['start'])
        
        # Join text items with proper spacing
        transcript_parts = []
        for i, item in enumerate(sorted_items):
            text = item['text'].strip()
            if not text:
                continue
                
            # Check if the text item ends with punctuation
            ends_with_punctuation = text[-1] in '.!?…,:;'
            
            # Add a space after items that don't end with punctuation
            # (except for the last item or items followed by punctuation)
            if (not ends_with_punctuation and 
                i < len(sorted_items) - 1 and 
                sorted_items[i+1]['text'] and 
                sorted_items[i+1]['text'][0] not in '.!?…,:;'):
                text += ' '
                
            transcript_parts.append(text)
        
        # Join all parts
        return ''.join(transcript_parts)
    
    def chunk_text(self, text: str, max_chunk_size: int = 2000) -> List[str]:
        """
        Splits text into chunks, ensuring that sentences are not broken.
        
        Args:
            text: Text to split
            max_chunk_size: Maximum size of each chunk
            
        Returns:
            List[str]: List of text chunks
        """
        if len(text) <= max_chunk_size:
            return [text]
        
        # Split text into sentences
        # This regex looks for sentence endings (., !, ?) followed by space or newline
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed the limit, start a new chunk
            if len(current_chunk) + len(sentence) + 1 > max_chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                # Add a space if the current chunk is not empty
                if current_chunk:
                    current_chunk += " "
                current_chunk += sentence
        
        # Add the last chunk if there's anything left
        if current_chunk:
            chunks.append(current_chunk)
            
        # Handle case where a single sentence is longer than max_chunk_size
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chunk_size:
                final_chunks.append(chunk)
            else:
                # If a single sentence is too long, split it by words
                words = chunk.split()
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 > max_chunk_size and sub_chunk:
                        final_chunks.append(sub_chunk)
                        sub_chunk = word
                    else:
                        if sub_chunk:
                            sub_chunk += " "
                        sub_chunk += word
                
                if sub_chunk:
                    final_chunks.append(sub_chunk)
        
        logger.info(f"Split text into {len(final_chunks)} chunks")
        return final_chunks
    
    async def process_video(self, url: str, languages: List[str] = None) -> tuple:
        """
        Process a YouTube video by extracting its title and transcript.
        
        Args:
            url (str): YouTube video URL
            languages (List[str], optional): Preferred languages for subtitles. Defaults to ['ru', 'en'].
        
        Returns:
            tuple: (video_title, transcript) or (None, None) in case of errors
        """
        if languages is None:
            languages = ['ru', 'en']
        
        logger.info(f"Processing video: {url}")
        logger.info(f"Using languages for subtitles: {', '.join(languages)}")
        
        try:
            video_id = await self.extract_video_id(url)
            logger.info(f"Extracted video ID: {video_id}")
        except ValueError as e:
            logger.error(f"Error extracting video ID: {str(e)}")
            return None, None
        
        try:
            # Get video title
            video_info = await self.get_video_info(video_id)
            video_title = video_info['title']
            
            # Try to get video transcript - FIRST try standard API
            transcript = None
            
            try:
                logger.info("Trying standard YouTube API for subtitles...")
                transcript = await self.get_subtitles(video_id, languages)
                if transcript and len(transcript.strip()) >= 10:
                    logger.info(f"Standard API successful: {len(transcript)} characters")
                    return video_title, transcript
            except Exception as api_error:
                logger.warning(f"Standard API failed: {str(api_error)}")
            
            # If standard API failed
            logger.warning("All subtitle extraction methods failed")
            return None, None
        
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            return None, None 