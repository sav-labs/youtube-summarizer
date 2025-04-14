import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(level=logging.INFO):
    """
    Настройка логирования для приложения
    
    Args:
        level: Уровень логирования (по умолчанию INFO)
        
    Returns:
        logger: Настроенный логгер
    """
    # Создаем директорию для логов если не существует
    os.makedirs('logs', exist_ok=True)
    
    # Получаем логгер
    logger = logging.getLogger('youtube_summarizer')
    logger.setLevel(level)  # Устанавливаем уровень логирования
    
    # Очищаем любые существующие хендлеры (для переиспользования)
    if logger.handlers:
        logger.handlers.clear()
    
    # Формат логов
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                   datefmt='%Y-%m-%d %H:%M:%S')
    
    # Хендлер для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(level)
    
    # Хендлер для записи в файл с ротацией (5 файлов по 5MB)
    file_handler = RotatingFileHandler(
        'logs/youtube_summarizer.log', 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(level)
    
    # Добавляем хендлеры к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    logger.info(f"Настроено логирование с уровнем: {logging.getLevelName(level)}")
    
    return logger 