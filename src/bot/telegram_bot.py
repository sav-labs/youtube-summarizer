"""
Telegram Bot for YouTube Summarizer Bot.
Handles user interactions, commands, and button presses.
"""
import re
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from src.config.settings import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID, YOUTUBE_REGEX
from src.models.user_manager import UserManager
from src.youtube_processor import YouTubeProcessor
from src.summarizer import Summarizer
from src.ai_agent import AIAgent
from .keyboards import (
    create_main_keyboard,
    create_admin_keyboard,
    create_models_keyboard,
    create_language_keyboard,
    create_settings_keyboard,
    create_access_request_keyboard,
    create_admin_notification_keyboard,
    create_user_list_keyboard,
    create_user_management_keyboard
)

class TelegramBot:
    """
    Main Telegram bot class for YouTube Summarizer.
    Handles all bot interactions and