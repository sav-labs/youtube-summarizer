"""
YouTube Processor for the YouTube Summarizer Bot.
Handles fetching transcripts and metadata from YouTube videos.
"""
import re
import time
import aiohttp
from pathlib import Path
from typing import List, Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from loguru import logger

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
    
    async def get_video_info(self, video_id: str) -> str:
        """
        Gets the title of a YouTube video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            str: Video title or a fallback title
        """
        try:
            # Get video info through YouTube oEmbed API
            api_url = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        video_info = await response.json()
                        title = video_info.get('title', f"Video {video_id}")
                        logger.info(f"Got video info: '{title}' (ID: {video_id})")
                        return title
                    else:
                        logger.warning(f"Failed to get video info, using ID as title")
                        return f"Video {video_id}"
                
        except Exception as e:
            logger.warning(f"Error getting video info: {str(e)}")
            return f"Video {video_id}"
    
    async def get_subtitles(self, video_id: str, languages: List[str] = None) -> str:
        """
        Gets subtitles for a YouTube video.
        
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
            # Try to get subtitles in preferred languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get subtitles in preferred languages
            transcript = None
            
            # Try each preferred language
            for lang in languages:
                try:
                    if lang in [t.language_code for t in transcript_list]:
                        transcript = transcript_list.find_transcript([lang])
                        logger.info(f"Found subtitles in language: {lang}")
                        break
                except Exception as e:
                    logger.debug(f"Could not get subtitles in language {lang}: {str(e)}")
            
            # If no subtitles in preferred languages, try generated ones
            if not transcript:
                logger.info("No subtitles in preferred languages, trying generated ones")
                transcript = transcript_list.find_generated_transcript(languages)
                
            # If that didn't work either, use any available subtitles
            if not transcript:
                logger.info("No subtitles in preferred languages, using first available")
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    logger.info(f"Using subtitles in language: {transcript.language_code}")
                else:
                    raise NoTranscriptFound("No subtitles found")
            
            # Get subtitles as text
            subtitle_data = transcript.fetch()
            
            # Join all subtitle parts into one text
            # The original implementation simply joined with spaces, which could break sentences
            # This updated version preserves sentence structure better
            subtitle_text = self._construct_transcript_text(subtitle_data)
            
            logger.info(f"Got subtitles with length {len(subtitle_text)} characters")
            return subtitle_text
            
        except TranscriptsDisabled as e:
            logger.error("Subtitles disabled for this video")
            raise Exception("Subtitles disabled for this video")
        
        except NoTranscriptFound as e:
            logger.error("No subtitles found for this video")
            raise Exception("No subtitles found for this video")
            
        except Exception as e:
            logger.error(f"Error getting subtitles: {str(e)}", exc_info=True)
            raise Exception(f"Error getting subtitles: {str(e)}")
    
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
    
    async def process_video(self, url: str, languages: List[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Processes a YouTube video to get its title and transcript.
        
        Args:
            url: YouTube video URL
            languages: List of preferred languages for subtitles
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (video title, transcript) or (None, None) on error
        """
        try:
            logger.info(f"Processing video URL: {url}")
            
            # Use provided languages or default
            pref_languages = languages or ['ru', 'en']
            logger.info(f"Using languages for subtitles: {pref_languages}")
            
            # Extract video ID from URL
            video_id = await self.extract_video_id(url)
            if not video_id:
                logger.error(f"Could not extract video ID from URL: {url}")
                return None, None
            
            logger.info(f"Extracted video ID: {video_id}")
            
            # Get video info (string with title)
            video_title = await self.get_video_info(video_id)
            if not video_title:
                logger.error(f"Could not get video info for ID: {video_id}")
                return None, None
            
            logger.info(f"Got video info: '{video_title}' (ID: {video_id})")
            
            # Get subtitles with specified preferred languages
            transcript = await self.get_subtitles(video_id, pref_languages)
            if not transcript:
                logger.error(f"Could not get subtitles for video: {video_title}")
                return video_title, None
            
            # Log transcript length and preview
            transcript_length = len(transcript)
            preview = transcript[:200].replace('\n', ' ').strip() + '...'
            
            logger.info(f"Got subtitles for video. Text length: {transcript_length} characters")
            logger.debug(f"Subtitle preview: {preview}")
            
            if transcript_length > 10000:
                logger.info(f"Long subtitles ({transcript_length} characters). This is normal for a long video.")
            
            return video_title, transcript
            
        except Exception as e:
            logger.exception(f"Error processing video {url}: {str(e)}")
            return None, None 