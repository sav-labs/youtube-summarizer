import os
import telebot
import re
import sys
import traceback
import logging
from telebot import types
from youtube_processor import YouTubeProcessor
from summarizer import Summarizer
from logger import setup_logger
from dotenv import load_dotenv
import time
import openai

# Настраиваем логирование с более подробным уровнем для отображения полной транскрипции
logger = setup_logger(logging.DEBUG)  # Меняем уровень с INFO на DEBUG
logger.info("================================================")
logger.info("Запуск YouTube Summarizer Bot")
logger.info("================================================")

# Загружаем переменные окружения
load_dotenv()
logger.info("Загрузка переменных окружения выполнена")

# Проверяем наличие токена
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    sys.exit(1)

logger.info("Токен Telegram получен")

# Инициализируем бота
bot = telebot.TeleBot(BOT_TOKEN)
logger.info("Telegram бот инициализирован")

# Словарь для хранения выбранных моделей пользователей
user_models = {}
# Словарь для хранения выбранных языков пользователей
user_languages = {}

# Константы
MAX_MESSAGE_LENGTH = 4096  # Максимальная длина сообщения в Telegram

try:
    # Инициализируем обработчики
    logger.info("Инициализация YouTube процессора...")
    youtube_processor = YouTubeProcessor(logger=logger.getChild("processor"))
    logger.info("YouTube процессор инициализирован успешно")
    
    logger.info("Инициализация суммаризатора...")
    summarizer = Summarizer(logger=logger.getChild("summarizer"))
    logger.info("Суммаризатор инициализирован успешно")
    
except Exception as e:
    logger.critical(f"Критическая ошибка при инициализации: {str(e)}", exc_info=True)
    sys.exit(1)

# Регулярное выражение для проверки YouTube ссылок
YOUTUBE_REGEX = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)(\S*)'

def create_main_keyboard():
    """Создание основной клавиатуры с кнопками команд"""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    help_button = types.KeyboardButton('❓ Помощь')
    models_button = types.KeyboardButton('🔄 Выбрать модель')
    language_button = types.KeyboardButton('🌐 Выбрать язык')
    settings_button = types.KeyboardButton('⚙️ Настройки')
    keyboard.add(help_button, models_button, language_button, settings_button)
    return keyboard

def create_models_keyboard(current_model=None):
    """
    Создает клавиатуру с доступными моделями и отмечает текущую модель.
    
    Args:
        current_model (str): Текущая модель пользователя
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками моделей
    """
    summarizer = Summarizer()
    
    # Получаем доступные модели из summarizer
    available_models = summarizer.list_available_models()
    logger.info(f"Получено {len(available_models)} моделей для создания клавиатуры")
    
    # Фильтруем модели (только общие модели, без специальных)
    filtered_models = []
    for model in available_models:
        # Пропускаем модели с аудио, поиском и транскрипцией
        if any(skip in model for skip in ["audio", "search", "transcribe", "tts", "realtime", "instruct"]):
            continue
        filtered_models.append(model)
    
    # Сортируем модели по категориям для лучшей организации
    model_categories = {
        "gpt-4.5": 1,
        "gpt-4o": 2,
        "gpt-4o-mini": 3,
        "gpt-4": 4,
        "gpt-4-turbo": 5,
        "gpt-3.5-turbo-16k": 6,
        "gpt-3.5-turbo": 7
    }
    
    # Сортируем модели
    sorted_models = sorted(filtered_models, key=lambda x: (
        next((i for prefix, i in model_categories.items() if x.startswith(prefix)), 99),
        x
    ))
    
    # Формируем клавиатуру
    keyboard = []
    added_models = set()  # Для отслеживания уже добавленных моделей
    
    for model in sorted_models:
        # Пропускаем если уже добавили такую модель (проверка на абсолютные дубликаты)
        if model in added_models:
            continue
        
        # Добавляем модель в список обработанных
        added_models.add(model)
        
        # Определяем, является ли текущая модель выбранной
        is_current = (model == current_model)
        
        # Используем точный ID модели как текст кнопки и добавляем галочку при необходимости
        button_text = f"{model} ✓" if is_current else model
        
        # Используем полный ID модели для callback-данных
        keyboard.append([types.InlineKeyboardButton(button_text, callback_data=f"set_model_{model}")])
    
    # Добавляем кнопку "Назад"
    keyboard.append([types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])
    
    logger.info(f"Создано {len(keyboard)-1} кнопок для выбора модели")
    return types.InlineKeyboardMarkup(keyboard)

def create_language_keyboard():
    """Создание клавиатуры для выбора языка субтитров"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопки выбора языка
    ru_button = types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")
    en_button = types.InlineKeyboardButton(text="🇬🇧 Английский", callback_data="lang:en")
    de_button = types.InlineKeyboardButton(text="🇩🇪 Немецкий", callback_data="lang:de")
    fr_button = types.InlineKeyboardButton(text="🇫🇷 Французский", callback_data="lang:fr")
    es_button = types.InlineKeyboardButton(text="🇪🇸 Испанский", callback_data="lang:es")
    it_button = types.InlineKeyboardButton(text="🇮🇹 Итальянский", callback_data="lang:it")
    
    # Добавляем кнопку для предпочтения русского и английского (по умолчанию)
    ru_en_button = types.InlineKeyboardButton(
        text="🇷🇺🇬🇧 Русский+Английский (по умолчанию)", 
        callback_data="lang:ru,en"
    )
    
    # Добавляем кнопки в клавиатуру
    keyboard.add(ru_en_button)
    keyboard.add(ru_button, en_button)
    keyboard.add(de_button, fr_button)
    keyboard.add(es_button, it_button)
    
    # Кнопка для возврата на основную клавиатуру
    back_button = types.InlineKeyboardButton(text="↩️ Вернуться", callback_data="back_to_main")
    keyboard.add(back_button)
    
    return keyboard

def create_settings_keyboard():
    """Создание клавиатуры для настроек"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки для настроек
    reset_button = types.InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="settings:reset")
    about_button = types.InlineKeyboardButton(text="ℹ️ О боте", callback_data="settings:about")
    
    # Кнопка для возврата на основную клавиатуру
    back_button = types.InlineKeyboardButton(text="↩️ Вернуться", callback_data="back_to_main")
    
    keyboard.add(reset_button, about_button, back_button)
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    
    logger.info(f"Пользователь {username} (ID: {chat_id}) запустил бота командой /start")
    
    # Инициализируем настройки пользователя по умолчанию
    user_models[chat_id] = summarizer.model
    user_languages[chat_id] = ['ru', 'en']
    
    # Отправляем приветственное сообщение с клавиатурой
    bot.send_message(
        chat_id, 
        "👋 Привет! Я бот для суммаризации YouTube видео.\n\n"
        "Просто отправь мне ссылку на YouTube видео, и я создам краткое резюме его содержания.\n\n"
        "Поддерживаются ссылки формата:\n"
        "- https://youtube.com/watch?v=...\n"
        "- https://youtu.be/...\n"
        "- https://youtube.com/shorts/...\n\n"
        "Используйте кнопки для настройки бота:",
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '❓ Помощь')
@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработчик команды /help и кнопки Помощь"""
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    
    logger.info(f"Пользователь {username} (ID: {chat_id}) запросил помощь")
    
    # Создаем клавиатуру
    keyboard = create_main_keyboard()
    
    bot.send_message(
        chat_id, 
        "🔍 *Как использовать этого бота:*\n\n"
        "1. Отправьте ссылку на YouTube видео\n"
        "2. Подождите, пока я анализирую контент видео\n"
        "3. Получите аналитический обзор содержания видео\n\n"
        "⚠️ *Ограничения:*\n"
        "- Качество обзора зависит от выбранной модели\n"
        "- Поддерживаются различные языки (можно выбрать в настройках)\n\n"
        "⚙️ *Настройки:*\n"
        "- Выбор модели AI для анализа (кнопка 'Выбрать модель')\n"
        "- Выбор предпочитаемого языка (кнопка 'Выбрать язык')\n",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda message: message.text == '🔄 Выбрать модель')
def select_model(message):
    """Обработчик кнопки выбора модели"""
    # Логирование действия пользователя
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    logger.info(f"Пользователь {username} (ID: {chat_id}) запросил список моделей")
    
    # Получаем текущую модель пользователя
    current_model = user_models.get(chat_id, summarizer.model)
    logger.info(f"Текущая модель пользователя {username}: {current_model}")
    
    # Отправляем сообщение с информацией о моделях и клавиатурой
    bot.send_message(
        chat_id,
        "🤖 *Выберите модель для создания аналитического обзора:*\n\n"
        "📚 *GPT-4* - лучшее качество, но медленнее\n"
        "🚀 *GPT-4o* - хорошее качество и быстрее, чем GPT-4\n"
        "⚡ *GPT-3.5* - быстрый, но качество ниже\n"
        "📝 *GPT-3.5-16k* - для длинных видео\n\n"
        f"Ваша текущая модель: {current_model}",
        parse_mode="Markdown", 
        reply_markup=create_models_keyboard(current_model)
    )

@bot.message_handler(func=lambda message: message.text == '🌐 Выбрать язык')
def select_language(message):
    """Обработчик кнопки выбора языка"""
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    
    logger.info(f"Пользователь {username} (ID: {chat_id}) открыл меню выбора языка")
    
    # Определяем текущий язык пользователя
    current_langs = user_languages.get(chat_id, ['ru', 'en'])
    current_langs_str = ", ".join(current_langs)
    
    # Создаем клавиатуру языков
    language_keyboard = create_language_keyboard()
    
    bot.send_message(
        chat_id, 
        f"🌐 *Выберите предпочитаемый язык субтитров*\n\n"
        f"Текущий выбор: `{current_langs_str}`\n\n"
        f"Бот будет искать субтитры на выбранном языке.\n"
        f"Если они недоступны, будет использован любой доступный язык.\n",
        parse_mode="Markdown",
        reply_markup=language_keyboard
    )

@bot.message_handler(func=lambda message: message.text == '⚙️ Настройки')
def settings_menu(message):
    """Обработчик кнопки настроек"""
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    
    logger.info(f"Пользователь {username} (ID: {chat_id}) открыл меню настроек")
    
    # Определяем текущие настройки пользователя
    current_model = user_models.get(chat_id, summarizer.model)
    current_langs = user_languages.get(chat_id, ['ru', 'en'])
    current_langs_str = ", ".join(current_langs)
    
    # Создаем клавиатуру настроек
    settings_keyboard = create_settings_keyboard()
    
    bot.send_message(
        chat_id, 
        f"⚙️ *Текущие настройки*\n\n"
        f"Модель: `{current_model}`\n"
        f"Язык субтитров: `{current_langs_str}`\n\n"
        f"Выберите действие:",
        parse_mode="Markdown",
        reply_markup=settings_keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Обработчик всех callback кнопок"""
    chat_id = call.message.chat.id
    username = call.from_user.username or call.from_user.first_name or str(chat_id)
    
    if call.data.startswith('set_model_'):
        # Обработка выбора модели - исправляем формат callback
        model_name = call.data.replace('set_model_', '')
        user_models[chat_id] = model_name
        logger.info(f"Пользователь {username} (ID: {chat_id}) выбрал модель: {model_name}")
        
        bot.edit_message_text(
            f"✅ Выбрана модель: `{model_name}`\n\n"
            f"Теперь все суммаризации будут выполняться с использованием этой модели.",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        
        # Отправляем сообщение с основной клавиатурой
        bot.send_message(
            chat_id, 
            "Модель успешно изменена! Теперь можете отправить видео для суммаризации.",
            reply_markup=create_main_keyboard()
        )
        
    elif call.data.startswith('lang:'):
        # Обработка выбора языка
        langs = call.data.split(':')[1].split(',')
        user_languages[chat_id] = langs
        logger.info(f"Пользователь {username} (ID: {chat_id}) выбрал языки: {langs}")
        
        bot.edit_message_text(
            f"✅ Выбраны языки: `{', '.join(langs)}`\n\n"
            f"Теперь бот будет искать субтитры на этих языках в первую очередь.",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        
        # Отправляем сообщение с основной клавиатурой
        bot.send_message(
            chat_id, 
            "Язык субтитров успешно изменен! Теперь можете отправить видео для суммаризации.",
            reply_markup=create_main_keyboard()
        )
        
    elif call.data == 'back_to_main':
        # Возврат в основное меню
        bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
        
        # Отправляем сообщение с основной клавиатурой
        bot.send_message(
            chat_id, 
            "Вернулись в главное меню. Отправьте YouTube ссылку или выберите действие:",
            reply_markup=create_main_keyboard()
        )
        
    elif call.data.startswith('settings:'):
        # Обработка действий из меню настроек
        action = call.data.split(':')[1]
        
        if action == 'reset':
            # Сброс настроек пользователя
            user_models[chat_id] = summarizer.model
            user_languages[chat_id] = ['ru', 'en']
            logger.info(f"Пользователь {username} (ID: {chat_id}) сбросил настройки")
            
            bot.edit_message_text(
                "✅ Настройки сброшены до значений по умолчанию.",
                chat_id=chat_id,
                message_id=call.message.message_id
            )
            
            # Отправляем сообщение с основной клавиатурой
            bot.send_message(
                chat_id, 
                "Настройки сброшены! Теперь используются значения по умолчанию.",
                reply_markup=create_main_keyboard()
            )
            
        elif action == 'about':
            # Информация о боте
            bot.edit_message_text(
                "ℹ️ *О боте YouTube Summarizer*\n\n"
                "Этот бот позволяет получать аналитические обзоры YouTube видео с использованием AI.\n\n"
                "💡 *Возможности:*\n"
                "- Аналитика видео на основе их аудио-контента\n"
                "- Интеллектуальная обработка с помощью AI\n"
                "- Поддержка различных языков\n"
                "- Выбор модели AI для оптимальных результатов\n\n"
                "🛠 *Технологии:*\n"
                "- Python\n"
                "- YouTube Transcript API\n"
                "- OpenAI API\n"
                "- Telegram Bot API\n",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            
            # Отправляем сообщение с основной клавиатурой после задержки
            bot.send_message(
                chat_id, 
                "Используйте кнопки ниже для настройки или отправьте YouTube ссылку:",
                reply_markup=create_main_keyboard()
            )
    
    # Убираем "часики" с кнопки
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_unknown_message(message):
    """Обработчик всех остальных сообщений"""
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    
    text = message.text.strip() if message.text else ""
    logger.info(f"Пользователь {username} (ID: {chat_id}) отправил сообщение: {text[:50]}")
    
    # Сначала проверяем, есть ли в сообщении YouTube ссылка по регулярному выражению
    youtube_match = re.search(YOUTUBE_REGEX, text)
    if youtube_match:
        # Если нашли YouTube ссылку, обрабатываем её как видео
        youtube_url = youtube_match.group(0)
        logger.info(f"Найдена YouTube ссылка в сообщении: {youtube_url}, передаю на обработку")
        # Создаем новое сообщение с той же ссылкой и передаем его в обработчик ссылок
        new_message = telebot.types.Message(
            message_id=message.message_id,
            from_user=message.from_user,
            date=message.date,
            chat=message.chat,
            content_type='text',
            options={},
            json_string='{}'
        )
        new_message.text = youtube_url
        # Вызываем обработчик YouTube ссылок напрямую
        return process_youtube_link(new_message)
    
    # Если YouTube ссылка не найдена, продолжаем с обычной обработкой
    # Проверяем, похоже ли сообщение на YouTube ссылку, но с ошибкой
    youtube_terms = ["youtube", "youtu.be", "ютуб", "ютюб", "youtube.com"]
    message_has_youtube_term = any(term in text.lower() for term in youtube_terms)
    
    # Генерируем острый ответ с GPT-3.5
    try:
        # Формируем контекст в зависимости от содержания сообщения
        context_prompt = ""
        if message_has_youtube_term or (len(text) > 10 and ("http" in text or "www" in text)):
            # Если похоже на попытку ввести ссылку
            context_prompt = f"""
            Пользователь отправил сообщение, которое похоже на попытку отправить ссылку на YouTube, но ссылка неверная: "{text}"
            
            Сгенерируй агрессивный, матерный, но юморной ответ, который высмеивает неспособность пользователя отправить нормальную ссылку на YouTube.
            Используй выражения типа "ты что, долбоёб?", "в шары долбишься?", "руки из жопы растут?" или подобные грубые фразы.
            Ответ должен быть коротким (2-3 предложения), смешным и содержать мат или сленг.
            
            В конце добавь краткую инструкцию, как правильно отправить ссылку на YouTube.
            """
        else:
            # Для обычных сообщений
            context_prompt = f"""
            Пользователь отправил боту сообщение: "{text}", но бот занимается только суммаризацией YouTube видео.
            
            Сгенерируй агрессивный, матерный, но юморной ответ, который высмеивает пользователя за отправку нерелевантного сообщения.
            Используй выражения типа "ты совсем дурак?", "я же бот для суммаризации ютуб видео долбаёб", "ты нахрена мне это пишешь?" или подобные грубые фразы.
            Ответ должен быть коротким (2-3 предложения), смешным и содержать мат или сленг.
            
            В конце напомни, что бот работает только с YouTube ссылками.
            """
        
        # Отправляем запрос к GPT-3.5-turbo
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты генератор агрессивных и матерных ответов для Telegram бота. Твои ответы должны быть грубыми, смешными и с использованием мата. Не стесняйся в выражениях!"},
                {"role": "user", "content": context_prompt}
            ],
            temperature=0.9,  # Высокая температура для разнообразия
            max_tokens=200
        )
        
        funny_response = response.choices[0].message.content.strip()
        
        # Создаем клавиатуру
        keyboard = create_main_keyboard()
        
        # Отправляем смешной ответ
        bot.reply_to(
            message, 
            f"{funny_response}",
            reply_markup=keyboard
        )
        logger.info(f"Отправлен агрессивный ответ пользователю {username}")
        return
        
    except Exception as e:
        logger.error(f"Ошибка при генерации агрессивного ответа: {str(e)}")
        # В случае ошибки отправляем стандартный ответ
        keyboard = create_main_keyboard()
        bot.reply_to(
            message, 
            "Чё за хрень ты мне прислал? Давай нормальную ссылку на YouTube видео, а не эту дичь.",
            reply_markup=keyboard
        )

@bot.message_handler(func=lambda message: re.search(YOUTUBE_REGEX, message.text))
def process_youtube_link(message):
    """Обработчик ссылок на YouTube"""
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name or str(chat_id)
    
    match = re.search(YOUTUBE_REGEX, message.text)
    youtube_url = match.group(0)
    
    logger.info(f"Пользователь {username} (ID: {chat_id}) отправил YouTube ссылку: {youtube_url}")
    
    # Получаем настройки пользователя или используем значения по умолчанию
    model_name = user_models.get(chat_id, summarizer.model)
    languages = user_languages.get(chat_id, ['ru', 'en'])
    
    logger.info(f"Используем модель {model_name} и языки {languages} для пользователя {username}")
    
    # Отправляем сообщение о начале обработки
    processing_msg = bot.send_message(chat_id, "⏳ Анализирую видео, это может занять некоторое время...")
    
    try:
        # Получение субтитров и информации о видео
        logger.info(f"Начинаю обработку видео для пользователя {username}")
        bot.edit_message_text("⏳ Получаю информацию о видео...", chat_id, processing_msg.message_id)
        
        # Получаем субтитры с учетом выбранных языков пользователя
        title, transcript = youtube_processor.process_video(youtube_url, languages)
        
        if not title or not transcript:
            error_text = "❌ Не удалось получить информацию о видео."
            bot.delete_message(chat_id, processing_msg.message_id)
            
            # Генерируем агрессивный ответ при ошибке с видео
            try:
                error_prompt = f"""
                Пользователь отправил ссылку на YouTube, но не удалось получить информацию о видео: "{youtube_url}"
                
                Сгенерируй агрессивный и матерный ответ, который высмеивает пользователя за отправку нерабочей ссылки.
                Используй выражения типа "ты че в шары долбишься придурок?", "не можешь нормально скопировать ссылку на видео?", "у тебя руки нормально работают вообще?" или подобные грубые фразы.
                Ответ должен быть коротким (2-3 предложения), смешным и содержать мат или сленг.
                
                В конце предложи отправить другое видео или проверить ссылку.
                """
                
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Ты генератор агрессивных и матерных ответов для Telegram бота. Твои ответы должны быть грубыми, смешными и с использованием мата. Не стесняйся в выражениях!"},
                        {"role": "user", "content": error_prompt}
                    ],
                    temperature=0.9,
                    max_tokens=200
                )
                
                error_response = response.choices[0].message.content.strip()
                
                # Отправляем сообщение с клавиатурой отдельно, чтобы она точно отобразилась
                bot.send_message(chat_id, error_response, reply_markup=create_main_keyboard())
                
            except Exception as error_gen_error:
                logger.error(f"Ошибка при генерации агрессивного ответа об ошибке: {str(error_gen_error)}")
                bot.send_message(chat_id, 
                                "Ты чё, дебил? Это видео не существует или у него нет субтитров. Давай нормальное видео.", 
                                reply_markup=create_main_keyboard())
            return
        
        # Логируем полный текст транскрипции
        logger.info(f"Получена транскрипция для видео '{title}', длина: {len(transcript)} символов")
        logger.info(f"ПОЛНЫЙ ТЕКСТ ТРАНСКРИПЦИИ ВИДЕО '{title}':\n{'-' * 50}\n{transcript[:500]}... [обрезано]\n{'-' * 50}")
        
        # Сохраняем транскрипцию в файл для возможности дальнейшего анализа
        transcript_file = f"transcript_{chat_id}_{int(time.time())}.txt"
        try:
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(f"Видео: {title}\nURL: {youtube_url}\n\n{transcript}")
            logger.info(f"Транскрипция сохранена в файл {transcript_file}")
        except Exception as e:
            logger.warning(f"Не удалось сохранить транскрипцию в файл: {str(e)}")
        
        # Проверяем длину субтитров
        transcript_length = len(transcript)
        if transcript_length > 5000:
            bot.edit_message_text(f"⏳ Обрабатываю контент видео... Создаю краткий обзор с моделью {model_name}, это может занять некоторое время...", chat_id, processing_msg.message_id)
        else:
            bot.edit_message_text(f"⏳ Создаю краткий обзор видео с помощью модели {model_name}...", chat_id, processing_msg.message_id)
        
        # Суммаризация текста с выбранной пользователем моделью
        logger.info(f"Начинаю аналитическую обработку текста для пользователя {username} с моделью {model_name}")
        summary = summarizer.summarize(text=transcript, title=title, model=model_name)
        
        # Удаляем указание на части из заголовка и текста
        clean_title = re.sub(r'\s*\([Чч]асть \d+ из \d+\)\s*', '', title)
        clean_summary = re.sub(r'^\s*\*?\s*[Чч]асть \d+ из \d+\s*\*?\s*$', '', summary, flags=re.MULTILINE)
        
        # Отправляем результат
        logger.info(f"Отправляю результат аналитической обработки пользователю {username}")
        
        # Упрощенное форматирование результата
        result_text = f"🎬 *{clean_title}*\n\n{clean_summary}"
        
        # Обрабатываем случай, если резюме слишком длинное для одного сообщения
        keyboard = create_main_keyboard()
        if len(result_text) <= MAX_MESSAGE_LENGTH:
            bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            # Отправляем сначала заголовок
            bot.send_message(chat_id, f"🎬 *{clean_title}*", parse_mode="Markdown")
            
            # Разбиваем на части и отправляем последовательно
            logger.info(f"Обзор слишком длинный, разбиваю на части для отправки пользователю {username}")
            
            # Разбиваем текст на части подходящего размера
            max_chunk_size = MAX_MESSAGE_LENGTH - 50  # Оставляем запас для форматирования
            chunks = []
            
            # Сначала пробуем разбить по параграфам
            paragraphs = clean_summary.split("\n\n")
            current_chunk = ""
            
            for paragraph in paragraphs:
                if len(current_chunk) + len(paragraph) + 4 <= max_chunk_size:  # +4 для "\n\n"
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # Если параграф сам по себе слишком длинный, разбиваем его
                    if len(paragraph) > max_chunk_size:
                        # Разбиваем длинный параграф по предложениям
                        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                        sub_chunk = ""
                        
                        for sentence in sentences:
                            if len(sub_chunk) + len(sentence) + 2 <= max_chunk_size:  # +2 для ". "
                                if sub_chunk:
                                    sub_chunk += " " + sentence
                                else:
                                    sub_chunk = sentence
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk)
                                
                                # Если предложение само по себе слишком длинное
                                if len(sentence) > max_chunk_size:
                                    # Разбиваем по словам/символам
                                    for i in range(0, len(sentence), max_chunk_size):
                                        chunks.append(sentence[i:i+max_chunk_size])
                                else:
                                    sub_chunk = sentence
                        
                        # Добавляем последний подчанк, если есть
                        if sub_chunk:
                            chunks.append(sub_chunk)
                    else:
                        current_chunk = paragraph
            
            # Добавляем последний чанк, если есть
            if current_chunk:
                chunks.append(current_chunk)
            
            # Если по какой-то причине не удалось разбить текст, делаем это принудительно
            if not chunks:
                chunks = [clean_summary[i:i+max_chunk_size] for i in range(0, len(clean_summary), max_chunk_size)]
            
            # Отправляем каждую часть
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:  # Последняя часть с клавиатурой
                    bot.send_message(chat_id, chunk, parse_mode="Markdown", reply_markup=keyboard)
                else:
                    bot.send_message(chat_id, chunk, parse_mode="Markdown")
        
        # Удаляем сообщение о обработке
        bot.delete_message(chat_id, processing_msg.message_id)
        logger.info(f"Обработка видео для пользователя {username} успешно завершена")
        
    except Exception as e:
        error_message = f"❌ Произошла ошибка при обработке видео: {str(e)}"
        bot.edit_message_text(error_message, chat_id, processing_msg.message_id)
        
        # Отправляем клавиатуру в любом случае
        bot.send_message(chat_id, "Попробуйте другое видео или измените настройки.", 
                         reply_markup=create_main_keyboard())
        
        logger.error(f"Ошибка при обработке видео для пользователя {username}: {str(e)}", exc_info=True)

# Получаем доступные модели
def get_default_model():
    """Возвращает модель по умолчанию"""
    try:
        default_model = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")
        return default_model
    except Exception as e:
        logger.error(f"Ошибка при получении модели по умолчанию: {str(e)}")
        return "gpt-3.5-turbo"

if __name__ == "__main__":
    logger.info("Запускаю бесконечный polling...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при работе бота: {str(e)}", exc_info=True)
        sys.exit(1) 