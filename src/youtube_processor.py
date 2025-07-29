"""
YouTube Processor for the YouTube Summarizer Bot.
Handles fetching transcripts and metadata from YouTube videos.
"""
import re
import aiohttp
import json
import tempfile
import os
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
                        
                        # Try to fetch and validate
                        try:
                            subtitle_data = await loop.run_in_executor(None, transcript.fetch)
                            if self._validate_subtitle_data(subtitle_data):
                                subtitle_text = self._construct_transcript_text(subtitle_data)
                                if subtitle_text and len(subtitle_text.strip()) >= 10:
                                    logger.info(f"Successfully got subtitles: {len(subtitle_text)} chars")
                                    return subtitle_text
                        except Exception as fetch_e:
                            logger.warning(f"Failed to fetch {lang} subtitles: {str(fetch_e)}")
                            continue
                except Exception as e:
                    logger.debug(f"Could not get subtitles in language {lang}: {str(e)}")
            
            # If direct subtitles failed, try translated subtitles
            logger.info("Trying translated subtitles...")
            for lang in languages:
                try:
                    # Try to get any available transcript and translate it
                    available_transcripts = list(transcript_list)
                    for base_transcript in available_transcripts:
                        try:
                            logger.debug(f"Trying to translate from {base_transcript.language_code} to {lang}")
                            
                            # Try to translate the base transcript
                            translated = await loop.run_in_executor(
                                None, lambda: base_transcript.translate(lang)
                            )
                            
                            if translated:
                                subtitle_data = await loop.run_in_executor(None, translated.fetch)
                                if self._validate_subtitle_data(subtitle_data):
                                    subtitle_text = self._construct_transcript_text(subtitle_data)
                                    if subtitle_text and len(subtitle_text.strip()) >= 10:
                                        logger.info(f"Successfully got translated subtitles ({base_transcript.language_code} -> {lang}): {len(subtitle_text)} chars")
                                        return subtitle_text
                                        
                        except Exception as trans_e:
                            logger.debug(f"Translation failed from {base_transcript.language_code} to {lang}: {str(trans_e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Translation approach failed for {lang}: {str(e)}")
            
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
                        
                        # Try to fetch generated subtitles
                        try:
                            subtitle_data = await loop.run_in_executor(None, transcript.fetch)
                            if self._validate_subtitle_data(subtitle_data):
                                subtitle_text = self._construct_transcript_text(subtitle_data)
                                if subtitle_text and len(subtitle_text.strip()) >= 10:
                                    logger.info(f"Successfully got generated subtitles: {len(subtitle_text)} chars")
                                    return subtitle_text
                        except Exception as gen_e:
                            logger.warning(f"Failed to fetch generated subtitles: {str(gen_e)}")
                            
                except Exception as e:
                    logger.debug(f"Could not get generated subtitles: {str(e)}")
                
            # If that didn't work either, use any available subtitles
            if not transcript:
                logger.info("Trying any available subtitles")
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    # Try each available transcript
                    for available_transcript in available_transcripts:
                        try:
                            used_language = available_transcript.language_code
                            logger.debug(f"Trying available language: {used_language}")
                            
                            subtitle_data = await loop.run_in_executor(None, available_transcript.fetch)
                            if self._validate_subtitle_data(subtitle_data):
                                subtitle_text = self._construct_transcript_text(subtitle_data)
                                if subtitle_text and len(subtitle_text.strip()) >= 10:
                                    logger.info(f"Successfully got subtitles in {used_language}: {len(subtitle_text)} chars")
                                    return subtitle_text
                                    
                        except Exception as avail_e:
                            logger.debug(f"Failed to get subtitles in {available_transcript.language_code}: {str(avail_e)}")
                            continue
                    
                    # If direct approach failed, try translating any available transcript to English
                    logger.info("Trying to translate any available transcript to English")
                    for available_transcript in available_transcripts:
                        try:
                            logger.debug(f"Translating {available_transcript.language_code} to en")
                            translated = await loop.run_in_executor(
                                None, lambda: available_transcript.translate('en')
                            )
                            
                            if translated:
                                subtitle_data = await loop.run_in_executor(None, translated.fetch)
                                if self._validate_subtitle_data(subtitle_data):
                                    subtitle_text = self._construct_transcript_text(subtitle_data)
                                    if subtitle_text and len(subtitle_text.strip()) >= 10:
                                        logger.info(f"Successfully got translated subtitles ({available_transcript.language_code} -> en): {len(subtitle_text)} chars")
                                        return subtitle_text
                                        
                        except Exception as final_trans_e:
                            logger.debug(f"Final translation failed: {str(final_trans_e)}")
                            continue
                else:
                    raise Exception("Для этого видео нет доступных субтитров")
                    
        except TranscriptsDisabled as e:
            logger.error("Subtitles disabled for this video")
            raise Exception("Субтитры отключены для этого видео")
        
        except NoTranscriptFound as e:
            logger.error("No subtitles found for this video")
            raise Exception("Для этого видео не найдены субтитры")
            
        except Exception as e:
            logger.error(f"Error getting subtitles: {str(e)}")
            
            # Try yt-dlp as final fallback
            logger.info("Trying yt-dlp as final fallback")
            try:
                ytdlp_result = await self._get_subtitles_with_ytdlp(video_id, languages)
                if ytdlp_result:
                    return ytdlp_result
            except Exception as ytdlp_e:
                logger.error(f"yt-dlp fallback also failed: {str(ytdlp_e)}")
            
            # If we get here, all attempts failed
            raise Exception(f"Не удалось получить субтитры для видео.\n\n"
                          f"Видео содержит субтитры, но все попытки их извлечения не удались:\n"
                          f"• Основные субтитры повреждены или недоступны\n"
                          f"• Переводные субтитры также недоступны\n"
                          f"• Альтернативные методы извлечения не сработали\n"
                          f"• Технические проблемы с YouTube API\n\n"
                          f"Попробуйте другое видео или повторите попытку позже.")
    
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

    async def _get_subtitles_with_ytdlp(self, video_id: str, languages: List[str] = None) -> str:
        """
        Alternative method to get subtitles using yt-dlp.
        
        Args:
            video_id: YouTube video ID
            languages: Preferred languages
            
        Returns:
            str: Subtitle text or None if failed
        """
        if languages is None:
            languages = ['ru', 'en']
            
        logger.info(f"Trying yt-dlp fallback for video {video_id}")
        
        try:
            import yt_dlp
            
            # Create temporary directory for subtitles
            with tempfile.TemporaryDirectory() as temp_dir:
                
                # Try each language
                for lang in languages:
                    try:
                        logger.debug(f"Trying yt-dlp for language: {lang}")
                        
                        # Configure yt-dlp options
                        ydl_opts = {
                            'writesubtitles': True,
                            'writeautomaticsub': True,
                            'subtitleslangs': [lang, f'{lang}-orig'],
                            'subtitlesformat': 'vtt',
                            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                            'quiet': True,
                            'no_warnings': True,
                            'skip_download': True,
                        }
                        
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        # Run yt-dlp in executor to avoid blocking
                        loop = asyncio.get_event_loop()
                        
                        def run_ytdlp():
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url])
                        
                        await loop.run_in_executor(None, run_ytdlp)
                        
                        # Look for downloaded subtitle files
                        subtitle_files = []
                        for ext in ['vtt', 'ttml', 'srv3', 'srv2', 'srv1']:
                            pattern = f"*.{lang}.{ext}"
                            subtitle_files.extend(Path(temp_dir).glob(pattern))
                            
                            # Also try auto-generated pattern
                            pattern = f"*.{lang}-orig.{ext}"
                            subtitle_files.extend(Path(temp_dir).glob(pattern))
                        
                        if subtitle_files:
                            # Read the first found subtitle file
                            subtitle_file = subtitle_files[0]
                            logger.debug(f"Found subtitle file: {subtitle_file}")
                            
                            with open(subtitle_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Parse VTT format
                            if content and len(content.strip()) > 0:
                                subtitle_text = self._parse_vtt_content(content)
                                if subtitle_text and len(subtitle_text.strip()) >= 10:
                                    logger.info(f"yt-dlp successful for {lang}: {len(subtitle_text)} chars")
                                    return subtitle_text
                        
                    except Exception as e:
                        logger.debug(f"yt-dlp failed for {lang}: {str(e)}")
                        continue
                
                # Try auto-generated subtitles in any language
                logger.debug("Trying yt-dlp with auto-generated subtitles")
                ydl_opts = {
                    'writeautomaticsub': True,
                    'subtitlesformat': 'vtt',
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                }
                
                def run_ytdlp_auto():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                
                await loop.run_in_executor(None, run_ytdlp_auto)
                
                # Look for any subtitle files
                subtitle_files = []
                for ext in ['vtt', 'ttml', 'srv3', 'srv2', 'srv1']:
                    subtitle_files.extend(Path(temp_dir).glob(f"*.{ext}"))
                
                if subtitle_files:
                    subtitle_file = subtitle_files[0]
                    logger.debug(f"Found auto subtitle file: {subtitle_file}")
                    
                    with open(subtitle_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if content and len(content.strip()) > 0:
                        subtitle_text = self._parse_vtt_content(content)
                        if subtitle_text and len(subtitle_text.strip()) >= 10:
                            logger.info(f"yt-dlp auto subtitles successful: {len(subtitle_text)} chars")
                            return subtitle_text
                            
        except ImportError:
            logger.error("yt-dlp not available, install with: pip install yt-dlp")
            return None
        except Exception as e:
            logger.error(f"yt-dlp fallback failed: {str(e)}")
            return None
        
        return None
    
    def _parse_vtt_content(self, vtt_content: str) -> str:
        """
        Parse VTT subtitle content and extract text.
        
        Args:
            vtt_content: VTT file content
            
        Returns:
            str: Extracted text
        """
        try:
            lines = vtt_content.split('\n')
            text_lines = []
            
            skip_next = False
            for line in lines:
                line = line.strip()
                
                # Skip VTT headers and metadata
                if line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
                    continue
                
                # Skip timestamp lines (format: 00:00:00.000 --> 00:00:05.000)
                if '-->' in line:
                    skip_next = False
                    continue
                
                # Skip empty lines and cue identifiers (just numbers)
                if not line or line.isdigit():
                    continue
                
                # Skip positioning tags like <c>
                if line.startswith('<') and line.endswith('>'):
                    continue
                
                # Clean HTML tags from subtitle text
                clean_line = re.sub(r'<[^>]+>', '', line)
                clean_line = clean_line.strip()
                
                if clean_line and len(clean_line) > 1:
                    text_lines.append(clean_line)
            
            result = ' '.join(text_lines)
            return result
            
        except Exception as e:
            logger.error(f"Error parsing VTT content: {str(e)}")
            return "" 