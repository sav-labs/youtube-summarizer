import os
import logging
import time
from dotenv import load_dotenv
import math
import openai
import re

class Summarizer:
    def __init__(self, logger=None):
        """Инициализация суммаризатора с использованием OpenAI API через официальную библиотеку (0.28.0)"""
        load_dotenv()
        
        # Настраиваем логгер
        self.logger = logger or logging.getLogger("youtube_summarizer.summarizer")
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.logger.error("OPENAI_API_KEY не найден в переменных окружения")
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        
        # Устанавливаем API ключ для openai (используя старый API 0.28.0)
        openai.api_key = self.api_key
        self.logger.info("OpenAI клиент успешно инициализирован (версия 0.28.0)")
        
        # Получаем список доступных моделей
        available_models = self.list_available_models()
            
        # Предпочтительные модели в порядке предпочтения (модель 16k на первом месте)
        preferred_models = [
            "gpt-3.5-turbo-16k",  # Теперь на первом месте
            "gpt-3.5-turbo-0125",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo",
            "gpt-3.5"
        ]
        
        # Выбираем модель из доступных предпочтительных моделей
        self.model = None
        for model_name in preferred_models:
            if any(model_name in model for model in available_models):
                matching_models = [m for m in available_models if model_name in m]
                self.model = matching_models[0]  # берем первую подходящую модель
                self.logger.info(f"Выбрана модель: {self.model}")
                break
        
        # Если не нашли подходящую модель, используем первую доступную GPT модель
        if not self.model and available_models:
            self.model = available_models[0]
            self.logger.info(f"Используем первую доступную модель: {self.model}")
        # Запасной вариант
        elif not self.model:
            self.model = "gpt-3.5-turbo-16k"  # Изменил модель по умолчанию
            self.logger.warning(f"Не удалось найти доступные модели, используем модель по умолчанию: {self.model}")
        
        self.logger.info(f"Summarizer инициализирован, модель: {self.model}")
        
        # Уменьшаем размер одной части для суммаризации (примерно 6000-7000 токенов, ~2000 слов)
        self.chunk_size = 2000
        self.logger.info(f"Установлен размер чанка: {self.chunk_size} символов")
        
        # Убираем ограничение на количество чанков - обрабатываем все части
        self.max_chunks = float('inf')  # Бесконечное значение - без ограничения
        self.logger.info(f"Ограничение на количество чанков отключено - обрабатываем все части текста")
        
        # Запоминаем, какие модели имеют расширенный контекст
        self.large_context_models = [m for m in available_models if "16k" in m or "32k" in m]
        if self.large_context_models:
            self.logger.info(f"Обнаружены модели с расширенным контекстом: {', '.join(self.large_context_models)}")
            # Если текущая модель имеет расширенный контекст, увеличиваем размер чанка
            if any(ctx_marker in self.model for ctx_marker in ["16k", "32k"]):
                self.chunk_size = 6000
                self.logger.info(f"Обнаружена модель с расширенным контекстом, установлен размер чанка: {self.chunk_size} символов")
    
    def list_available_models(self):
        """
        Получает список доступных моделей для суммаризации.
        
        Returns:
            list: Список строк с названиями доступных моделей
        """
        try:
            # Сначала пробуем получить модели через API
            models_list = []
            
            try:
                # Попытка получить список моделей через API
                response = openai.Model.list()
                
                # Проверяем, что ответ содержит данные
                if hasattr(response, 'data') and response.data:
                    # Собираем все GPT модели
                    for model in response.data:
                        model_id = model.id
                        if 'gpt' in model_id.lower():
                            models_list.append(model_id)
                    
                    self.logger.info(f"Успешно получены модели из API: {models_list}")
            except Exception as api_error:
                self.logger.warning(f"Не удалось получить список моделей через API: {str(api_error)}")
            
            # Если получение из API не удалось, используем расширенный статический список
            if not models_list:
                models_list = [
                    "gpt-3.5-turbo", 
                    "gpt-3.5-turbo-16k",
                    "gpt-3.5-turbo-0125",
                    "gpt-3.5-turbo-1106",
                    "gpt-4",
                    "gpt-4-32k",
                    "gpt-4-turbo", 
                    "gpt-4-0125-preview",
                    "gpt-4-1106-preview",
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4o-2024-05-13",
                    "gpt-4o-2024-08-06"
                ]
                self.logger.info(f"Используем расширенный статический список моделей: {models_list}")
            
            return models_list
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении списка моделей: {str(e)}")
            # Если произошла ошибка, возвращаем список по умолчанию
            default_models = ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4o", "gpt-4o-mini"]
            self.logger.info(f"Используем список моделей по умолчанию: {default_models}")
            return default_models
    
    def summarize(self, text, title="", model=None):
        """
        Суммаризация текста с использованием OpenAI API.
        Автоматически разбивает длинный текст на части, если это необходимо.
        """
        if not text:
            self.logger.error("Получен пустой текст для суммаризации")
            return "Не удалось создать суммаризацию из-за пустого текста."

        self.logger.info(f"Началась суммаризация текста длиной {len(text)} символов")
        summarize_start_time = time.time()  # Переименовываем, чтобы избежать конфликтов
        
        # Используем переданную модель или модель по умолчанию
        model_to_use = model or self.model
        self.logger.info(f"Используется модель {model_to_use} для суммаризации")
        
        # Получаем оптимальный размер чанка для выбранной модели
        chunk_size = self._get_optimal_chunk_size(model_to_use)
        
        # Если текст слишком длинный для одного запроса, разбиваем его
        if len(text) > chunk_size:
            self.logger.info(f"Текст превышает {chunk_size} символов, разбиваем на части")
            result = self._split_text_and_summarize(text, title, model_to_use)
            
            # Измеряем общее время выполнения
            summarize_end_time = time.time()
            total_time = summarize_end_time - summarize_start_time
            self.logger.info(f"Общее время суммаризации: {total_time:.2f} секунд")
            
            return result
        else:
            result = self._summarize_single_chunk(text, title, model_to_use)
            
            # Измеряем общее время выполнения
            summarize_end_time = time.time()
            total_time = summarize_end_time - summarize_start_time
            self.logger.info(f"Общее время суммаризации: {total_time:.2f} секунд")
            
            return result
    
    def _get_optimal_chunk_size(self, model):
        """Определяет оптимальный размер чанка в зависимости от модели"""
        # Модели с большим контекстным окном
        large_context_models = ['gpt-4-turbo', 'gpt-4-1106-preview']
        
        if any(model_name in model.lower() for model_name in large_context_models):
            return 12000  # Для моделей с контекстом 128k используем чанки больше
        elif '16k' in model.lower():
            return 8000   # Для моделей с контекстом 16k
        else:
            return 4000   # Для базовых моделей
    
    def _summarize_single_chunk(self, text, title, model):
        """Суммаризация одного фрагмента текста"""
        start_time = time.time()  # Перемещено в начало метода
        try:
            self.logger.info(f"Отправка запроса на суммаризацию в OpenAI API (модель: {model})")
            
            # Формируем новый, более лаконичный запрос на аналитический обзор видео
            prompt = f"""
Проанализируй транскрипцию видео и создай очень краткий аналитический обзор, сфокусированный на ключевых моментах и практических рекомендациях.

Название видео: "{title}"

Транскрипция: 
{text}

Твоя задача - создать краткое и прямолинейное резюме, которое включает:

1. КЛЮЧЕВАЯ ИДЕЯ: 
   - В одном-двух предложениях выдели основную мысль или тезис видео
   - О чем это видео на самом деле?

2. ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ:
   - Какие конкретные действия предлагает автор предпринять зрителям?
   - Если в видео содержатся советы по инвестициям или другим практическим шагам, укажи их кратко

Будь предельно лаконичен. Избегай детального анализа, теоретических рассуждений и критики.
Результат должен быть максимально полезным и прямолинейным - "вот о чем это видео и вот что нужно делать".
Целевая длина ответа - не более 10-15 строк.
"""
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ты аналитик контента, создающий очень краткие и практичные обзоры видео, фокусируясь только на сути и конкретных рекомендациях."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            summary = response.choices[0].message.content.strip()
            self.logger.info(f"Успешно получена суммаризация длиной {len(summary)} символов")
            
            end_time = time.time()
            self.logger.info(f"Суммаризация завершена за {end_time - start_time:.2f} секунд")
            
            return summary
        
        except Exception as e:
            self.logger.error(f"Ошибка при суммаризации: {str(e)}", exc_info=True)
            return f"Не удалось создать суммаризацию: {str(e)}"
    
    def _split_text_into_chunks(self, text, chunk_size):
        """Разбивает текст на части оптимального размера по границам предложений"""
        self.logger.info(f"Разбиваю текст на части примерно по {chunk_size} символов")
        
        # Разбиваем текст на предложения
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        # Если предложение длиннее chunk_size, дополнительно разбиваем его
        processed_sentences = []
        for sentence in sentences:
            if len(sentence) > chunk_size:
                # Разбиваем длинное предложение на части
                parts = [sentence[i:i+chunk_size] for i in range(0, len(sentence), chunk_size)]
                processed_sentences.extend(parts)
            else:
                processed_sentences.append(sentence)
        
        # Теперь формируем чанки из обработанных предложений
        for sentence in processed_sentences:
            # Если добавление нового предложения превысит лимит, сохраняем текущий чанк
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Добавляем последний чанк, если он не пустой
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Убеждаемся, что текст действительно разбит на нужное количество частей
        expected_chunks = max(1, (len(text) // chunk_size) + (1 if len(text) % chunk_size > 0 else 0))
        
        self.logger.info(f"Текст разбит на {len(chunks)} частей (ожидалось примерно {expected_chunks})")
        
        # Если разбиение не сработало, делаем принудительное разбиение по символам
        if len(chunks) < expected_chunks * 0.5 and len(text) > chunk_size:
            self.logger.warning(f"Нормальное разбиение не удалось, выполняю принудительное разбиение")
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            self.logger.info(f"После принудительного разбиения получено {len(chunks)} частей")
            
        return chunks
    
    def _split_text_and_summarize(self, text, title, model):
        """Разбивает текст на части, суммаризирует каждую часть, затем объединяет результаты"""
        # Получаем оптимальный размер чанка для выбранной модели
        chunk_size = self._get_optimal_chunk_size(model)
        
        # Разбиваем текст на части
        chunks = self._split_text_into_chunks(text, chunk_size)
        num_chunks = len(chunks)
        
        # Проверяем, корректно ли разбит текст
        expected_chunks = max(1, (len(text) // chunk_size) + (1 if len(text) % chunk_size > 0 else 0))
        
        # Если всё равно получилась только одна часть, а текст большой - принудительно разбиваем
        if num_chunks == 1 and len(text) > chunk_size * 1.5:
            # Принудительно разбиваем текст на части
            self.logger.warning(f"Разбиение текста не дало ожидаемого результата (получили {num_chunks} часть вместо ожидаемых {expected_chunks})")
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            num_chunks = len(chunks)
            self.logger.info(f"Принудительное разбиение дало {num_chunks} частей")
        
        # Если всё равно получилась только одна часть, просто обрабатываем её
        if num_chunks == 1:
            self.logger.info(f"После разбиения получена всего 1 часть, обрабатываем как единый текст")
            return self._summarize_single_chunk(chunks[0], title, model)
        
        # Суммаризируем каждую часть
        part_summaries = []
        for i, chunk in enumerate(chunks):
            self.logger.info(f"Суммаризация части {i+1}/{num_chunks}")
            
            # Проверяем наличие текста в чанке
            if not chunk or len(chunk.strip()) == 0:
                self.logger.warning(f"Часть {i+1}/{num_chunks} пуста, пропускаем")
                continue
                
            part_summary = self._summarize_single_chunk(
                chunk, 
                f"{title} (часть {i+1} из {num_chunks})" if title else f"Часть {i+1} из {num_chunks}",
                model
            )
            part_summaries.append(part_summary)
        
        # Если частей мало (2-3), можно просто объединить результаты
        # Если частей много, нужно выполнить дополнительную суммаризацию
        if num_chunks <= 3:
            self.logger.info(f"Объединяем {num_chunks} части без дополнительной суммаризации")
            final_text = part_summaries[0] if part_summaries else ""  # Берем первую часть как основу
            
            # Добавляем уникальное содержимое остальных частей
            for i, summary in enumerate(part_summaries[1:], 1):
                final_text += "\n\n" + summary
            
            return final_text
        else:
            # Если частей много, выполняем дополнительную суммаризацию
            self.logger.info(f"Выполняем финальную суммаризацию для {num_chunks} частей")
            return self._combine_summaries(part_summaries, title, model)
    
    def _combine_summaries(self, summaries, title, model):
        """Объединяет суммаризации нескольких частей в единый текст"""
        self.logger.info(f"Объединение {len(summaries)} суммаризаций в финальный текст")
        combine_start_time = time.time()  # Добавляем локальную переменную для времени
        
        # Объединяем все суммаризации в один текст
        combined_text = "\n\n".join([f"Часть {i+1}:\n{summary}" for i, summary in enumerate(summaries)])
        
        prompt = f"""
Я дам тебе несколько суммаризаций разных частей одного видео. Объедини их в один краткий и целостный обзор.

Название видео: "{title}"

Суммаризации частей:
{combined_text}

Твоя задача - создать финальное резюме, которое:
1. Выделяет единую ключевую идею всего видео (1-2 предложения)
2. Собирает все практические рекомендации в единый список (если они есть)

Будь предельно лаконичен. Избегай повторений, теоретических рассуждений и критики.
Финальный текст должен быть не длиннее 15 строк и содержать только самую важную информацию.
"""

        try:
            self.logger.info("Отправка запроса на объединение суммаризаций в OpenAI API")
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ты аналитик контента, объединяющий разрозненные части анализа в единый краткий и практичный обзор."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            final_summary = response.choices[0].message.content.strip()
            self.logger.info(f"Успешно получен объединенный текст длиной {len(final_summary)} символов")
            
            # Измеряем время выполнения
            combine_end_time = time.time()
            self.logger.info(f"Объединение суммаризаций завершено за {combine_end_time - combine_start_time:.2f} секунд")
            
            return final_summary
        
        except Exception as e:
            self.logger.error(f"Ошибка при объединении суммаризаций: {str(e)}", exc_info=True)
            # В случае ошибки просто объединяем части как есть
            return "\n\n".join(summaries) 