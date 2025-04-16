"""
Configuration file with all bot settings.
These settings can be modified without changing the code.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# OpenAI API settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Admin settings
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))  # Default to 0 if not set

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
LOGGING_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)

# Max message length for Telegram
MAX_MESSAGE_LENGTH = 4096

# Model settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4.1-nano")

# Default preferences
DEFAULT_LANGUAGES = ['ru', 'en']

# YouTube link regex pattern
YOUTUBE_REGEX = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)(\S*)'

# User access settings
DEFAULT_USER_REQUESTS = 1  # Default number of requests allowed for new users
UNLIMITED_REQUESTS = -1    # Value indicating unlimited requests

# Text chunk settings
DEFAULT_CHUNK_SIZE = 2000  # Default size for text chunking
LARGE_CONTEXT_CHUNK_SIZE = 6000  # Size for large context models 

# Model context window sizes (in chars, approximation)
MODEL_CONTEXT_LIMITS = {
    # Place specific models and longer prefixes first to prevent matching issues
    "gpt-4.1-nano": 1000000,   # 1 million context window  
    "gpt-4.1-preview": 1000000,
    "gpt-4-32k": 32000,        # Longer prefixes before shorter ones
    "gpt-4-turbo": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4o": 128000,
    "gpt-3.5-turbo-16k": 16000,
    "gpt-4": 8000,             # Shorter prefixes last
    "gpt-3.5-turbo": 4000
}

# Default context window if model not found in the above mapping
DEFAULT_CONTEXT_WINDOW = 4000 