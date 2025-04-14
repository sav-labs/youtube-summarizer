import os
import logging
import time
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

class YouTubeProcessor:
    def __init__(self, temp_dir="temp", logger=None):
        """Инициализация процессора YouTube видео"""
        self.temp_dir = temp_dir
        # Создаем временную директорию если её нет
        Path(temp_dir).mkdir(exist_ok=True)
        
        # Настраиваем логгер
        self.logger = logger or logging.getLogger("youtube_summarizer.processor")
        self.logger.info(f"YouTubeProcessor инициализирован, временная директория: {temp_dir}")
    
    def _extract_video_id(self, url):
        """Извлечение ID видео из URL"""
        import re
        
        # Регулярные выражения для извлечения ID видео из разных форматов URL
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
        
        self.logger.error(f"Не удалось извлечь ID видео из URL: {url}")
        raise ValueError(f"Не удалось извлечь ID видео из URL: {url}")
    
    def get_video_info(self, video_id):
        """Получение информации о видео"""
        import requests
        import json
        
        try:
            # Получаем информацию о видео через oEmbed API YouTube
            api_url = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(api_url)
            
            if response.status_code == 200:
                video_info = response.json()
                title = video_info.get('title', 'Неизвестное видео')
                self.logger.info(f"Получена информация о видео: '{title}' (ID: {video_id})")
                return title
            else:
                self.logger.warning(f"Не удалось получить информацию о видео, используем ID как название")
                return f"Видео {video_id}"
                
        except Exception as e:
            self.logger.warning(f"Ошибка при получении информации о видео: {str(e)}")
            return f"Видео {video_id}"
    
    def get_subtitles(self, video_id, languages=['ru', 'en']):
        """Получение субтитров видео на указанных языках"""
        self.logger.info(f"Получение субтитров для видео ID: {video_id}, предпочитаемые языки: {languages}")
        
        try:
            # Попытка получить субтитры на предпочитаемых языках
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Пробуем получить субтитры на русском языке
            transcript = None
            
            # Проходим по предпочитаемым языкам
            for lang in languages:
                try:
                    if lang in [t.language_code for t in transcript_list]:
                        transcript = transcript_list.find_transcript([lang])
                        self.logger.info(f"Найдены субтитры на языке: {lang}")
                        break
                except Exception as e:
                    self.logger.debug(f"Не удалось получить субтитры на языке {lang}: {str(e)}")
            
            # Если не нашли субтитры на предпочитаемых языках, пробуем получить автоматически сгенерированные
            if not transcript:
                self.logger.info("Субтитры на предпочитаемых языках не найдены, пробуем получить автоматически сгенерированные")
                transcript = transcript_list.find_generated_transcript(languages)
                
            # Если и это не сработало, берем любые доступные субтитры
            if not transcript:
                self.logger.info("Не найдены субтитры на предпочитаемых языках, берем первые доступные")
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    self.logger.info(f"Используем субтитры на языке: {transcript.language_code}")
                else:
                    raise NoTranscriptFound("Субтитры не найдены")
            
            # Получаем субтитры в виде текста
            subtitle_data = transcript.fetch()
            
            # Объединяем все части субтитров в один текст
            full_text = " ".join([item['text'] for item in subtitle_data])
            
            self.logger.info(f"Получены субтитры длиной {len(full_text)} символов")
            return full_text
            
        except TranscriptsDisabled as e:
            self.logger.error("Субтитры отключены для этого видео")
            raise Exception("Субтитры отключены для этого видео")
        
        except NoTranscriptFound as e:
            self.logger.error("Субтитры не найдены для этого видео")
            raise Exception("Субтитры не найдены для этого видео")
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении субтитров: {str(e)}", exc_info=True)
            raise Exception(f"Ошибка при получении субтитров: {str(e)}")
    
    def process_video(self, url, languages=None):
        """
        Обработка видео по URL - получение информации и субтитров
        
        Args:
            url (str): URL видео на YouTube
            languages (list, optional): Список предпочитаемых языков для субтитров.
                                     По умолчанию ['ru', 'en']
        
        Returns:
            tuple: (название видео, транскрипт)
        """
        try:
            self.logger.info(f"Начало обработки видео по URL: {url}")
            
            # Используем список языков из параметров или по умолчанию
            pref_languages = languages or ['ru', 'en']
            self.logger.info(f"Используем следующие языки для субтитров: {pref_languages}")
            
            # Извлекаем ID видео из URL
            video_id = self._extract_video_id(url)
            if not video_id:
                self.logger.error(f"Не удалось извлечь ID видео из URL: {url}")
                return None, None
            
            self.logger.info(f"Извлечен ID видео: {video_id}")
            
            # Получаем информацию о видео (уже строка с названием)
            video_title = self.get_video_info(video_id)
            if not video_title:
                self.logger.error(f"Не удалось получить информацию о видео с ID: {video_id}")
                return None, None
            
            self.logger.info(f"Получена информация о видео: '{video_title}' (ID: {video_id})")
            
            # Получаем субтитры с указанными предпочтительными языками
            transcript = self.get_subtitles(video_id, pref_languages)
            if not transcript:
                self.logger.error(f"Не удалось получить субтитры для видео: {video_title}")
                return video_title, None
            
            # Логирование количества символов в субтитрах и первые 200 символов для проверки
            transcript_length = len(transcript)
            preview = transcript[:200].replace('\n', ' ').strip() + '...'
            
            self.logger.info(f"Получены субтитры для видео. Длина текста: {transcript_length} символов")
            self.logger.info(f"Превью текста субтитров: {preview}")
            
            if transcript_length > 10000:
                self.logger.info(f"Длинные субтитры ({transcript_length} символов). Это нормально для длинного видео.")
            
            return video_title, transcript
            
        except Exception as e:
            self.logger.exception(f"Ошибка при обработке видео {url}: {str(e)}")
            return None, None 