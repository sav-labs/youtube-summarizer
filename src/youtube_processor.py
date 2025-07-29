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
        Gets subtitles for a YouTube video with improved error handling.
        
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
        
        try:
            # Run the synchronous YouTube API call in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            
            # First, try to get transcript list
            try:
                transcript_list = await loop.run_in_executor(
                    None, lambda: YouTubeTranscriptApi.list_transcripts(video_id)
                )
            except Exception as e:
                logger.error(f"Failed to get transcript list: {str(e)}")
                raise Exception(f"Не удалось получить список субтитров: {str(e)}")
            
            # Try to get subtitles in preferred languages
            transcript = None
            used_language = None
            
            # Try each preferred language
            for lang in languages:
                try:
                    # Check if language is available
                    available_languages = [t.language_code for t in transcript_list]
                    logger.debug(f"Available languages: {available_languages}")
                    
                    if lang in available_languages:
                        transcript = await loop.run_in_executor(
                            None, lambda: transcript_list.find_transcript([lang])
                        )
                        used_language = lang
                        logger.info(f"Found subtitles in language: {lang}")
                        break
                except Exception as e:
                    logger.debug(f"Could not get subtitles in language {lang}: {str(e)}")
            
            # If no subtitles in preferred languages, try generated ones
            if not transcript:
                logger.info("No subtitles in preferred languages, trying generated ones")
                try:
                    transcript = await loop.run_in_executor(
                        None, lambda: transcript_list.find_generated_transcript(languages)
                    )
                    if transcript:
                        used_language = transcript.language_code
                        logger.info(f"Found generated subtitles in: {used_language}")
                except Exception as e:
                    logger.debug(f"Could not get generated subtitles: {str(e)}")
                
            # If that didn't work either, use any available subtitles
            if not transcript:
                logger.info("No subtitles in preferred languages, using first available")
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    used_language = transcript.language_code
                    logger.info(f"Using subtitles in language: {used_language}")
                else:
                    raise Exception("Для этого видео нет доступных субтитров")
            
            # Get subtitles as text with validation
            try:
                logger.debug(f"Fetching subtitle data for language: {used_language}")
                subtitle_data = await loop.run_in_executor(None, transcript.fetch)
                
                # Debug: log subtitle data info
                logger.debug(f"Received subtitle data type: {type(subtitle_data)}, length: {len(subtitle_data) if subtitle_data else 0}")
                
                # Enhanced validation
                if not subtitle_data:
                    logger.error("No subtitle data received")
                    raise Exception("Не получены данные субтитров")
                
                if isinstance(subtitle_data, list) and len(subtitle_data) == 0:
                    logger.error("Empty subtitle data list")
                    raise Exception("Получен пустой список субтитров")
                
                # Check if first item has expected structure
                if isinstance(subtitle_data, list) and len(subtitle_data) > 0:
                    first_item = subtitle_data[0]
                    logger.debug(f"First subtitle item: {first_item}")
                    
                    if not isinstance(first_item, dict) or 'text' not in first_item:
                        logger.error(f"Invalid subtitle item structure: {first_item}")
                        raise Exception("Некорректная структура данных субтитров")
                
                # Validate subtitle data using existing method
                if not self._validate_subtitle_data(subtitle_data):
                    logger.error("Subtitle data validation failed")
                    raise Exception("Данные субтитров не прошли валидацию")
                
                # Join all subtitle parts into one text
                subtitle_text = self._construct_transcript_text(subtitle_data)
                
                if not subtitle_text or len(subtitle_text.strip()) < 10:
                    logger.error(f"Subtitle text too short: '{subtitle_text[:100]}...'")
                    raise Exception("Полученный текст субтитров слишком короткий")
                
                logger.info(f"Successfully got subtitles with length {len(subtitle_text)} characters in language {used_language}")
                return subtitle_text
                
            except Exception as e:
                logger.error(f"Error fetching subtitle data: {str(e)}")
                
                # Try alternative approach: direct transcript API call
                logger.info("Trying alternative direct transcript approach...")
                try:
                    for lang in languages:
                        try:
                            logger.debug(f"Trying direct API for language: {lang}")
                            direct_data = await loop.run_in_executor(
                                None, lambda l=lang: YouTubeTranscriptApi.get_transcript(video_id, languages=[l])
                            )
                            
                            if direct_data and len(direct_data) > 0:
                                logger.info(f"Direct API successful for language: {lang}")
                                
                                # Validate and construct text
                                if self._validate_subtitle_data(direct_data):
                                    subtitle_text = self._construct_transcript_text(direct_data)
                                    if subtitle_text and len(subtitle_text.strip()) >= 10:
                                        logger.info(f"Successfully got subtitles via direct API: {len(subtitle_text)} chars")
                                        return subtitle_text
                                
                        except Exception as direct_e:
                            logger.debug(f"Direct API failed for {lang}: {str(direct_e)}")
                            continue
                            
                except Exception as alt_e:
                    logger.error(f"Alternative approach failed: {str(alt_e)}")
                
                raise Exception(f"Ошибка при получении текста субтитров: {str(e)}")
            
        except TranscriptsDisabled as e:
            logger.error("Subtitles disabled for this video")
            raise Exception("Субтитры отключены для этого видео")
        
        except NoTranscriptFound as e:
            logger.error("No subtitles found for this video")
            raise Exception("Для этого видео не найдены субтитры")
            
        except Exception as e:
            logger.error(f"Error getting subtitles: {str(e)}")
            
            # Final fallback: Try direct API request with all available languages
            try:
                logger.info("Attempting final fallback with all available languages")
                
                # Get all available languages
                try:
                    transcript_list = await loop.run_in_executor(
                        None, lambda: YouTubeTranscriptApi.list_transcripts(video_id)
                    )
                    all_languages = [t.language_code for t in transcript_list]
                    logger.debug(f"All available languages: {all_languages}")
                    
                    # Try each available language
                    for lang in all_languages[:5]:  # Limit to first 5 to avoid too many attempts
                        try:
                            direct_data = await loop.run_in_executor(
                                None, lambda l=lang: YouTubeTranscriptApi.get_transcript(video_id, languages=[l])
                            )
                            
                            if direct_data and len(direct_data) > 0:
                                subtitle_text = self._construct_transcript_text(direct_data)
                                if subtitle_text and len(subtitle_text.strip()) >= 10:
                                    logger.info(f"Final fallback successful in language: {lang}")
                                    return subtitle_text
                                    
                        except Exception:
                            continue
                            
                except Exception as final_e:
                    logger.error(f"Final fallback failed: {str(final_e)}")
                    
            except Exception as fallback_e:
                logger.error(f"All fallbacks failed: {str(fallback_e)}")
            
            # If we get here, all attempts failed
            raise Exception(f"Не удалось получить субтитры для видео. Возможные причины:\n"
                          f"• Видео содержит субтитры, но они повреждены или недоступны\n"
                          f"• Субтитры защищены от автоматического извлечения\n"
                          f"• Технические проблемы с YouTube API\n"
                          f"• Региональные ограничения\n\n"
                          f"Попробуйте другое видео или проверьте доступность субтитров вручную.")
    
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
            
            # Get video transcript
            transcript = await self.get_subtitles(video_id, languages)
            
            if transcript:
                logger.info(f"Got transcript, length: {len(transcript)} characters")
                if len(transcript) > 0:
                    preview = transcript[:200] + "..." if len(transcript) > 200 else transcript
                    logger.info(f"Transcript preview: {preview}")
                
                if len(transcript) > 10000:
                    logger.info("Long subtitles detected (>10k chars)")
                
                return video_title, transcript
            else:
                logger.warning("Failed to get transcript")
                return None, None
        
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            return None, None 