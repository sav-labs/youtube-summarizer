"""
Configuration file with all prompts used in the application.
All AI prompts are stored here for easy modification.
"""
import os
import json
from loguru import logger

# Path to custom prompts configuration file
CUSTOM_PROMPTS_PATH = os.path.join("data", "config", "custom_prompts.json")

# Prompt for video summarization
SUMMARIZE_PROMPT = """
Проанализируй транскрипцию видео и создай очень краткий аналитический обзор, сфокусированный на ключевых моментах и практических рекомендациях.

Название видео: "{title}"

Транскрипция: 
{text}

Твоя задача - создать краткое и прямолинейное резюме, которое включает:

1. КЛЮЧЕВАЯ ИДЕЯ: 
   - В одном-двух предложениях выдели основную мысль или тезис видео

2. ОСНОВНЫЕ МОМЕНТЫ:
   - Перечисли 3-5 ключевых аспектов или тезисов
   - Будь конкретным и используй фактическую информацию
   - Избегай общих фраз и воды

3. ПРАКТИЧЕСКАЯ ЦЕННОСТЬ:
   - Укажи 2-3 практических совета или применения
   - Сосредоточься на действиях, которые можно предпринять

Твой ответ должен быть в формате Markdown с выделением заголовков.
Будь лаконичным и давай только существенную информацию. Избегай повторов и воды.

ВАЖНО: 
- Не включай никаких упоминаний о "части" или "части X из Y" в текст
- Не добавляй ссылки на YouTube видео в резюме
- Не указывай источник информации - это делается автоматически
- Обязательно добавляй эмодзи к разделам для наглядности
- Используй строго Markdown синтаксис для форматирования
- Не используй дополнительные символы вроде ** или ## внутри заголовков
"""

# Prompt for combining summaries of multiple chunks
COMBINE_SUMMARIES_PROMPT = """
Мне нужно объединить несколько частей аналитического обзора видео в единое целое.

Название видео: "{title}"

Части обзора:
{summaries}

Твоя задача - создать единый связный аналитический обзор. При объединении:
1. Убери повторяющиеся идеи и информацию
2. Обеспечь логический порядок и плавные переходы между частями
3. Сохрани самые важные моменты из каждой части
4. Сделай резюме кратким и информативным
5. Используй формат Markdown с выделением разделов
6. Добавляй подходящие по смыслу эмодзи для телеграм
7. ВАЖНО: Не включай никаких упоминаний о "части X из Y" или номерах частей в финальный обзор
8. ВАЖНО: Не включай ссылку на YouTube в результат
9. ВАЖНО: Стандартизируй форматирование - избегай использования дополнительных символов форматирования внутри заголовков

Результат должен быть структурированным, лаконичным и содержать только существенную информацию.
"""

# Prompt for handling error responses
ERROR_RESPONSE_PROMPT = """
Пользователь отправил ссылку на YouTube, но не удалось получить информацию о видео: "{video_url}"

Сгенерируй корректный ответ, объясняющий проблему. Укажи возможные причины:
- Видео может быть недоступно
- Видео может не иметь субтитров
- Ссылка может быть неверной

Предложи пользователю отправить другую ссылку на видео.
"""

# Prompt for handling unknown messages
UNKNOWN_MESSAGE_PROMPT = """
Пользователь отправил боту сообщение: "{text}", но бот занимается только суммаризацией YouTube видео.

Сгенерируй вежливый ответ, объясняющий, что бот работает только с YouTube ссылками.
Напомни, что нужно отправить ссылку на YouTube видео для получения его краткого содержания.
"""

# Prompt for access request notification to admin
ACCESS_REQUEST_ADMIN_PROMPT = """
Пользователь {user_name} (ID: {user_id}) запрашивает доступ к боту.

Информация о пользователе:
- ID: {user_id}
- Имя: {user_name}
- Username: {username}
- Дата запроса: {request_date}

Желаете предоставить доступ этому пользователю?
"""

# Default system prompts configuration with default models
DEFAULT_SYSTEM_PROMPTS = {
    "summarizer": {
        "content": "Ты аналитик видеоконтента. Твоя задача - создавать краткие, информативные и структурированные обзоры на основе транскрипций видео. Выделяй главное, отбрасывай второстепенное. Обязательно используй эмодзи для каждого раздела и форматируй текст строго по Markdown.",
        "model": "gpt-3.5-turbo-16k"
    },
    
    "error_handler": {
        "content": "Ты вежливый помощник, объясняющий пользователям проблемы при работе с ботом. Твои сообщения должны быть понятными и содержать рекомендации по решению проблемы.",
        "model": "gpt-3.5-turbo"
    },
    
    "admin_assistant": {
        "content": "Ты помощник администратора бота. Твоя задача - предоставлять чёткую информацию о пользователях и их запросах, помогая администратору принимать решения.",
        "model": "gpt-3.5-turbo"
    }
}

# Function to load custom prompts if they exist
def load_custom_prompts():
    """
    Load custom prompts from file if it exists,
    otherwise use the default prompts.
    
    Returns:
        dict: System prompts with content and model settings
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(CUSTOM_PROMPTS_PATH), exist_ok=True)
    
    # If custom prompts file exists, load it
    if os.path.exists(CUSTOM_PROMPTS_PATH):
        try:
            with open(CUSTOM_PROMPTS_PATH, 'r', encoding='utf-8') as f:
                custom_prompts = json.load(f)
            logger.info(f"Loaded custom prompts from {CUSTOM_PROMPTS_PATH}")
            return custom_prompts
        except Exception as e:
            logger.error(f"Error loading custom prompts: {e}")
            # Create the file with default values if there was an error
            save_custom_prompts(DEFAULT_SYSTEM_PROMPTS)
            return DEFAULT_SYSTEM_PROMPTS
    else:
        # Create the file with default values if it doesn't exist
        save_custom_prompts(DEFAULT_SYSTEM_PROMPTS)
        logger.info(f"Created default custom prompts file at {CUSTOM_PROMPTS_PATH}")
        return DEFAULT_SYSTEM_PROMPTS

def save_custom_prompts(prompts_data):
    """
    Save custom prompts to file.
    
    Args:
        prompts_data (dict): Prompts data to save
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CUSTOM_PROMPTS_PATH), exist_ok=True)
        
        with open(CUSTOM_PROMPTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(prompts_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved custom prompts to {CUSTOM_PROMPTS_PATH}")
    except Exception as e:
        logger.error(f"Error saving custom prompts: {e}")

# Load system prompts configuration (content and models)
SYSTEM_PROMPTS_CONFIG = load_custom_prompts()

# Extract just the content for backward compatibility
SYSTEM_PROMPTS = {k: v["content"] for k, v in SYSTEM_PROMPTS_CONFIG.items()} 