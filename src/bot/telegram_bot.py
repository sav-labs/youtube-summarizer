"""
Telegram bot module for the YouTube Summarizer Bot.
Handles user interactions via Telegram using aiogram.
"""
import asyncio
import re
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold, hitalic, hcode, hlink
from aiogram.enums import ParseMode

from loguru import logger
from src.config.settings import (
    TELEGRAM_BOT_TOKEN, 
    ADMIN_USER_ID, 
    MAX_MESSAGE_LENGTH,
    YOUTUBE_REGEX,
    DEFAULT_MODEL,
    DEFAULT_LANGUAGES,
    UNLIMITED_REQUESTS
)
from src.bot.keyboards import (
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
from src.models.user import User
from src.models.user_manager import UserManager
from src.youtube_processor import YouTubeProcessor
from src.summarizer import Summarizer
from src.ai_agent import AIAgent

class TelegramBot:
    """
    Main Telegram bot class for YouTube Summarizer.
    Handles all bot interactions and logic.
    """
    def __init__(self):
        """
        Initialize the Telegram bot with all required components.
        """
        # Initialize bot and dispatcher
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
        self.dp = Dispatcher()
        
        # Initialize components
        self.user_manager = UserManager(logger=logger)
        self.youtube_processor = YouTubeProcessor()
        self.summarizer = Summarizer()
        self.ai_agent = AIAgent()
        
        # Register message handlers
        self.register_handlers()
        
        logger.info("Telegram bot initialized")
    
    def register_handlers(self):
        """Register all message and callback handlers."""
        # Command handlers
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_help, Command("help"))
        
        # Button command handlers
        self.dp.message.register(self.cmd_help, lambda msg: msg.text == "❓ Помощь")
        self.dp.message.register(self.select_model, lambda msg: msg.text == "🔄 Выбрать модель")
        self.dp.message.register(self.select_language, lambda msg: msg.text == "🌐 Выбрать язык")
        self.dp.message.register(self.settings_menu, lambda msg: msg.text == "⚙️ Настройки")
        self.dp.message.register(self.list_users, lambda msg: msg.text == "👥 Пользователи")
        
        # YouTube link handler
        self.dp.message.register(
            self.process_youtube_link, 
            lambda msg: re.search(YOUTUBE_REGEX, msg.text or "")
        )
        
        # Callback query handler
        self.dp.callback_query.register(self.callback_handler)
        
        # Default message handler (must be last)
        self.dp.message.register(self.handle_unknown_message)
        
        logger.info("All handlers registered")
    
    async def start(self):
        """Start the bot polling."""
        try:
            logger.info("Starting bot polling")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def cmd_start(self, message: Message):
        """
        Handle /start command.
        
        Args:
            message: Telegram message with the command
        """
        user_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""
        last_name = message.from_user.last_name or ""
        
        # Get or create user
        user = self.user_manager.get_or_create_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        logger.info(f"User {user.display_name} (ID: {user_id}) started the bot")
        
        # Select appropriate keyboard
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        
        # Send welcome message
        await message.answer(
            "👋 Привет! Я бот для суммаризации YouTube видео.\n\n"
            "Просто отправь мне ссылку на YouTube видео, и я создам краткое резюме его содержания.\n\n"
            "Поддерживаются ссылки формата:\n"
            "- https://youtube.com/watch?v=...\n"
            "- https://youtu.be/...\n"
            "- https://youtube.com/shorts/...\n\n"
            "Используйте кнопки для настройки бота:",
            reply_markup=keyboard
        )
    
    async def cmd_help(self, message: Message):
        """
        Handle /help command and Help button.
        
        Args:
            message: Telegram message with the command
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        logger.info(f"User {user.display_name} (ID: {user_id}) requested help")
        
        # Select appropriate keyboard
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        
        # Send help message
        await message.answer(
            "🔍 Как использовать этого бота:\n\n"
            "1. Отправьте ссылку на YouTube видео\n"
            "2. Подождите, пока я анализирую контент видео\n"
            "3. Получите аналитический обзор содержания видео\n\n"
            "⚙️ Настройки:\n"
            "- Выбор модели AI для анализа (кнопка 'Выбрать модель')\n"
            "- Выбор предпочитаемого языка (кнопка 'Выбрать язык')\n",
            reply_markup=keyboard
        )
    
    async def select_model(self, message: Message):
        """
        Handle model selection button.
        
        Args:
            message: Telegram message with the button press
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        logger.info(f"User {user.display_name} (ID: {user_id}) requested model selection")
        
        # Get models list
        models = await self.summarizer.list_available_models()
        
        # Get current model
        current_model = user.model or self.summarizer.model
        
        # Create keyboard
        keyboard = create_models_keyboard(models, current_model)
        
        # Send model selection message
        await message.answer(
            "🤖 Выберите модель для создания аналитического обзора:\n\n"
            "📚 GPT-4 - лучшее качество, но медленнее\n"
            "🚀 GPT-4o - хорошее качество и быстрее, чем GPT-4\n"
            "⚡ GPT-3.5 - быстрый, но качество ниже\n"
            "📝 GPT-3.5-16k - для длинных видео\n\n"
            f"Ваша текущая модель: {current_model}",
            reply_markup=keyboard
        )
    
    async def select_language(self, message: Message):
        """
        Handle language selection button.
        
        Args:
            message: Telegram message with the button press
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        logger.info(f"User {user.display_name} (ID: {user_id}) requested language selection")
        
        # Get current languages
        current_langs = user.languages
        current_langs_str = ", ".join(current_langs)
        
        # Create keyboard
        keyboard = create_language_keyboard()
        
        # Send language selection message
        await message.answer(
            f"🌐 Выберите предпочитаемый язык субтитров\n\n"
            f"Текущий выбор: {hcode(current_langs_str)}\n\n"
            f"Бот будет искать субтитры на выбранном языке.\n"
            f"Если они недоступны, будет использован любой доступный язык.\n",
            reply_markup=keyboard
        )
    
    async def settings_menu(self, message: Message):
        """
        Handle settings button.
        
        Args:
            message: Telegram message with the button press
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        logger.info(f"User {user.display_name} (ID: {user_id}) opened settings menu")
        
        # Get current settings
        current_model = user.model or self.summarizer.model
        current_langs = user.languages
        current_langs_str = ", ".join(current_langs)
        
        # Create keyboard
        keyboard = create_settings_keyboard()
        
        # Send settings message
        await message.answer(
            f"⚙️ Текущие настройки\n\n"
            f"Модель: {hcode(current_model)}\n"
            f"Язык субтитров: {hcode(current_langs_str)}\n\n"
            f"Выберите действие:",
            reply_markup=keyboard
        )
    
    async def list_users(self, message: Message):
        """
        Handle users list button (admin only).
        
        Args:
            message: Telegram message with the button press
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        # Only admins can access this
        if not user.is_admin:
            logger.warning(f"Non-admin user {user.display_name} (ID: {user_id}) tried to access user list")
            await message.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        logger.info(f"Admin {user.display_name} (ID: {user_id}) requested user list")
        
        # Get all users
        users = self.user_manager.get_all_users()
        user_ids = [u.user_id for u in users if u.user_id != user_id]  # Exclude current admin
        
        if not user_ids:
            await message.answer("👥 Нет зарегистрированных пользователей.")
            return
        
        # Create keyboard
        keyboard = create_user_list_keyboard(user_ids)
        
        # Send user list message
        await message.answer(
            f"👥 Список пользователей ({len(user_ids)}):\n\n"
            f"Выберите пользователя для управления:",
            reply_markup=keyboard
        )
    
    async def callback_handler(self, callback: CallbackQuery):
        """
        Handle callback queries from inline keyboards.
        
        Args:
            callback: Callback query from inline keyboard
        """
        # Get user
        user_id = callback.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        # Extract callback data
        data = callback.data
        
        logger.info(f"Callback from user {user.display_name} (ID: {user_id}): {data}")
        
        try:
            # Handle different callback types
            if data.startswith("set_model:"):
                await self.handle_set_model(callback, user)
            elif data.startswith("lang:"):
                await self.handle_set_language(callback, user)
            elif data.startswith("settings:"):
                await self.handle_settings_action(callback, user)
            elif data == "back_to_main":
                await self.handle_back_to_main(callback, user)
            elif data == "request_access":
                await self.handle_request_access(callback, user)
            elif data.startswith("grant_access:"):
                await self.handle_grant_access(callback, user)
            elif data.startswith("reject_access:"):
                await self.handle_reject_access(callback, user)
            elif data.startswith("revoke_access:"):
                await self.handle_revoke_access(callback, user)
            elif data.startswith("user_info:"):
                await self.handle_user_info(callback, user)
            elif data.startswith("user_list:"):
                await self.handle_user_list(callback, user)
            else:
                logger.warning(f"Unknown callback data: {data}")
                
            # Answer callback to stop "loading" indicator
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await callback.answer("⚠️ Произошла ошибка при обработке запроса.")
    
    async def handle_set_model(self, callback: CallbackQuery, user: User):
        """
        Handle model selection callback.
        
        Args:
            callback: Callback query
            user: User object
        """
        # Extract model name
        model_name = callback.data.split(":", 1)[1]
        
        # Update user's model
        user.model = model_name
        self.user_manager.save_user(user)
        
        logger.info(f"User {user.display_name} (ID: {user.user_id}) selected model: {model_name}")
        
        # Edit message
        await callback.message.edit_text(
            f"✅ Выбрана модель: {hcode(model_name)}\n\n"
            f"Теперь все суммаризации будут выполняться с использованием этой модели."
        )
        
        # Send new message with main keyboard
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        await callback.message.answer(
            "Модель успешно изменена! Теперь можете отправить видео для суммаризации.",
            reply_markup=keyboard
        )
    
    async def handle_set_language(self, callback: CallbackQuery, user: User):
        """
        Handle language selection callback.
        
        Args:
            callback: Callback query
            user: User object
        """
        # Extract languages
        langs_str = callback.data.split(":", 1)[1]
        langs = langs_str.split(",")
        
        # Update user's languages
        user.languages = langs
        self.user_manager.save_user(user)
        
        logger.info(f"User {user.display_name} (ID: {user.user_id}) selected languages: {langs}")
        
        # Edit message
        await callback.message.edit_text(
            f"✅ Выбраны языки: {hcode(', '.join(langs))}\n\n"
            f"Теперь бот будет искать субтитры на этих языках в первую очередь."
        )
        
        # Send new message with main keyboard
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        await callback.message.answer(
            "Язык субтитров успешно изменен! Теперь можете отправить видео для суммаризации.",
            reply_markup=keyboard
        )
    
    async def handle_settings_action(self, callback: CallbackQuery, user: User):
        """
        Handle settings actions.
        
        Args:
            callback: Callback query
            user: User object
        """
        # Extract action
        action = callback.data.split(":", 1)[1]
        
        if action == "reset":
            # Reset user settings
            user.model = None
            user.languages = DEFAULT_LANGUAGES.copy()
            self.user_manager.save_user(user)
            
            logger.info(f"User {user.display_name} (ID: {user.user_id}) reset settings")
            
            # Edit message
            await callback.message.edit_text("✅ Настройки сброшены до значений по умолчанию.")
            
            # Send new message with main keyboard
            keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
            await callback.message.answer(
                "Настройки сброшены! Теперь используются значения по умолчанию.",
                reply_markup=keyboard
            )
            
        elif action == "about":
            # Show about information
            await callback.message.edit_text(
                "ℹ️ О боте YouTube Summarizer\n\n"
                "Этот бот позволяет получать аналитические обзоры YouTube видео с использованием AI.\n\n"
                "💡 Возможности:\n"
                "- Аналитика видео на основе их аудио-контента\n"
                "- Интеллектуальная обработка с помощью AI\n"
                "- Поддержка различных языков\n"
                "- Выбор модели AI для оптимальных результатов\n\n"
                "🛠 Технологии:\n"
                "- Python\n"
                "- YouTube Transcript API\n"
                "- OpenAI API\n"
                "- Telegram Bot API\n"
            )
            
            # Send new message with main keyboard
            keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
            await callback.message.answer(
                "Используйте кнопки ниже для настройки или отправьте YouTube ссылку:",
                reply_markup=keyboard
            )
    
    async def handle_back_to_main(self, callback: CallbackQuery, user: User):
        """
        Handle back to main button.
        
        Args:
            callback: Callback query
            user: User object
        """
        # Delete current message
        await callback.message.delete()
        
        # Send new message with main keyboard
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        await callback.message.answer(
            "Вернулись в главное меню. Отправьте YouTube ссылку или выберите действие:",
            reply_markup=keyboard
        )

    async def handle_request_access(self, callback: CallbackQuery, user: User):
        """
        Handle access request from a user.
        
        Args:
            callback: Callback query
            user: User object
        """
        # Mark user as requesting access
        self.user_manager.request_access(user)
        
        logger.info(f"User {user.display_name} (ID: {user.user_id}) requested access")
        
        # Notify admin about access request
        admin_id = ADMIN_USER_ID
        if admin_id and admin_id > 0:
            # Prepare user data for admin notification
            user_data = {
                "user_id": user.user_id,
                "user_name": user.display_name,
                "username": user.username or "Нет имени пользователя",
                "request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Generate notification message
            admin_notification = await self.ai_agent.generate_admin_notification(user_data)
            
            # Create keyboard for admin
            keyboard = create_admin_notification_keyboard(user.user_id)
            
            # Send notification to admin
            try:
                await self.bot.send_message(
                    admin_id,
                    admin_notification,
                    reply_markup=keyboard
                )
                logger.info(f"Sent access request notification to admin for user {user.user_id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")
        
        # Edit message to confirm request
        await callback.message.edit_text(
            "✅ Ваш запрос на доступ отправлен администратору.\n\n"
            "Пожалуйста, ожидайте ответа. Вы получите уведомление, когда доступ будет предоставлен."
        )
    
    async def handle_grant_access(self, callback: CallbackQuery, user: User):
        """
        Handle granting access to a user (admin only).
        
        Args:
            callback: Callback query
            user: User object
        """
        # Only admins can grant access
        if not user.is_admin:
            logger.warning(f"Non-admin user {user.display_name} (ID: {user.user_id}) tried to grant access")
            await callback.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        # Extract data
        _, target_user_id_str, requests_str = callback.data.split(":", 2)
        target_user_id = int(target_user_id_str)
        requests = int(requests_str)
        
        # Grant access
        success = self.user_manager.grant_access(target_user_id, requests)
        
        if success:
            target_user = self.user_manager.get_user(target_user_id)
            
            # Log action
            logger.info(f"Admin {user.display_name} (ID: {user.user_id}) granted access to user {target_user_id} with {requests} requests")
            
            # Notify target user
            requests_text = "безлимитный доступ" if requests == UNLIMITED_REQUESTS else f"{requests} запрос(-ов)"
            try:
                await self.bot.send_message(
                    target_user_id,
                    f"🎉 Вам предоставлен доступ к боту!\n\n"
                    f"Вы получили {requests_text}. Теперь вы можете отправлять ссылки на YouTube видео для суммаризации.",
                    reply_markup=create_main_keyboard()
                )
                logger.info(f"Sent access granted notification to user {target_user_id}")
            except Exception as e:
                logger.error(f"Failed to send access granted notification to user {target_user_id}: {e}")
            
            # Edit message to confirm action
            await callback.message.edit_text(
                f"✅ Доступ предоставлен пользователю {target_user.display_name} (ID: {target_user_id}).\n\n"
                f"Предоставлено запросов: {requests_text}."
            )
        else:
            logger.warning(f"Failed to grant access to user {target_user_id}")
            await callback.message.edit_text(f"❌ Не удалось предоставить доступ пользователю {target_user_id}.")
    
    async def handle_reject_access(self, callback: CallbackQuery, user: User):
        """
        Handle rejecting access to a user (admin only).
        
        Args:
            callback: Callback query
            user: User object
        """
        # Only admins can reject access
        if not user.is_admin:
            logger.warning(f"Non-admin user {user.display_name} (ID: {user.user_id}) tried to reject access")
            await callback.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        # Extract data
        _, target_user_id_str = callback.data.split(":", 1)
        target_user_id = int(target_user_id_str)
        
        # Revoke access
        success = self.user_manager.revoke_access(target_user_id)
        
        if success:
            target_user = self.user_manager.get_user(target_user_id)
            
            # Log action
            logger.info(f"Admin {user.display_name} (ID: {user.user_id}) rejected access for user {target_user_id}")
            
            # Notify target user
            try:
                await self.bot.send_message(
                    target_user_id,
                    "❌ Ваш запрос на доступ к боту был отклонен администратором."
                )
                logger.info(f"Sent access rejected notification to user {target_user_id}")
            except Exception as e:
                logger.error(f"Failed to send access rejected notification to user {target_user_id}: {e}")
            
            # Edit message to confirm action
            await callback.message.edit_text(
                f"✅ Доступ отклонен для пользователя {target_user.display_name} (ID: {target_user_id})."
            )
        else:
            logger.warning(f"Failed to reject access for user {target_user_id}")
            await callback.message.edit_text(f"❌ Не удалось отклонить доступ для пользователя {target_user_id}.")
    
    async def handle_revoke_access(self, callback: CallbackQuery, user: User):
        """
        Handle revoking access from a user (admin only).
        
        Args:
            callback: Callback query
            user: User object
        """
        # Only admins can revoke access
        if not user.is_admin:
            logger.warning(f"Non-admin user {user.display_name} (ID: {user.user_id}) tried to revoke access")
            await callback.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        # Extract data
        _, target_user_id_str = callback.data.split(":", 1)
        target_user_id = int(target_user_id_str)
        
        # Revoke access
        success = self.user_manager.revoke_access(target_user_id)
        
        if success:
            target_user = self.user_manager.get_user(target_user_id)
            
            # Log action
            logger.info(f"Admin {user.display_name} (ID: {user.user_id}) revoked access from user {target_user_id}")
            
            # Notify target user
            try:
                await self.bot.send_message(
                    target_user_id,
                    "⚠️ Ваш доступ к боту был отозван администратором."
                )
                logger.info(f"Sent access revoked notification to user {target_user_id}")
            except Exception as e:
                logger.error(f"Failed to send access revoked notification to user {target_user_id}: {e}")
            
            # Edit message to confirm action
            await callback.message.edit_text(
                f"✅ Доступ отозван у пользователя {target_user.display_name} (ID: {target_user_id})."
            )
            
            # Show user management keyboard
            keyboard = create_user_management_keyboard(target_user_id)
            await callback.message.answer(
                f"Управление пользователем {target_user.display_name} (ID: {target_user_id}):",
                reply_markup=keyboard
            )
        else:
            logger.warning(f"Failed to revoke access from user {target_user_id}")
            await callback.message.edit_text(f"❌ Не удалось отозвать доступ у пользователя {target_user_id}.")

    async def handle_user_info(self, callback: CallbackQuery, user: User):
        """
        Handle user info callback (admin only).
        
        Args:
            callback: Callback query
            user: User object
        """
        # Only admins can view user info
        if not user.is_admin:
            logger.warning(f"Non-admin user {user.display_name} (ID: {user.user_id}) tried to view user info")
            await callback.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        # Extract data
        _, target_user_id_str = callback.data.split(":", 1)
        target_user_id = int(target_user_id_str)
        
        # Get target user
        target_user = self.user_manager.get_user(target_user_id)
        
        if target_user:
            # Format user info
            requests_text = "безлимитно" if target_user.has_unlimited_requests else str(target_user.remaining_requests)
            status_text = "✅ Доступ разрешен" if target_user.has_access() else "❌ Доступ запрещен"
            
            # Create message
            user_info = (
                f"👤 Информация о пользователе:\n\n"
                f"ID: {hcode(str(target_user.user_id))}\n"
                f"Имя: {target_user.display_name}\n"
                f"Username: {hcode(target_user.username or 'Не указан')}\n"
                f"Статус: {status_text}\n"
                f"Запросов: {requests_text}\n"
                f"Модель: {hcode(target_user.model or 'По умолчанию')}\n"
                f"Языки: {hcode(', '.join(target_user.languages))}\n"
                f"Создан: {target_user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Обновлен: {target_user.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            
            # Create keyboard
            keyboard = create_user_management_keyboard(target_user_id)
            
            # Edit message
            await callback.message.edit_text(
                user_info,
                reply_markup=keyboard
            )
        else:
            logger.warning(f"User {target_user_id} not found")
            await callback.message.edit_text(f"❌ Пользователь с ID {target_user_id} не найден.")
    
    async def handle_user_list(self, callback: CallbackQuery, user: User):
        """
        Handle user list pagination callback (admin only).
        
        Args:
            callback: Callback query
            user: User object
        """
        # Only admins can view user list
        if not user.is_admin:
            logger.warning(f"Non-admin user {user.display_name} (ID: {user.user_id}) tried to view user list")
            await callback.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        # Extract data
        _, page_str = callback.data.split(":", 1)
        page = int(page_str)
        
        # Get all users
        users = self.user_manager.get_all_users()
        user_ids = [u.user_id for u in users if u.user_id != user.user_id]  # Exclude current admin
        
        if not user_ids:
            await callback.message.edit_text("👥 Нет зарегистрированных пользователей.")
            return
        
        # Create keyboard with pagination
        keyboard = create_user_list_keyboard(user_ids, page)
        
        # Edit message
        await callback.message.edit_text(
            f"👥 Список пользователей ({len(user_ids)}):\n\n"
            f"Выберите пользователя для управления:",
            reply_markup=keyboard
        )
    
    async def handle_unknown_message(self, message: Message):
        """
        Handle messages that don't match any other handler.
        
        Args:
            message: Message to handle
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        # Get message text
        text = message.text or ""
        
        logger.info(f"Unknown message from user {user.display_name} (ID: {user_id}): {text[:50]}...")
        
        # Generate response
        response = await self.ai_agent.handle_unknown_message(text)
        
        # Send response with keyboard
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        await message.answer(response, reply_markup=keyboard)

    async def process_youtube_link(self, message: Message):
        """
        Process YouTube link and generate summary.
        
        Args:
            message: Message with YouTube link
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        # Check if user has access
        if not user.has_access():
            logger.warning(f"User {user.display_name} (ID: {user_id}) tried to use bot without access")
            
            # Send access request keyboard
            keyboard = create_access_request_keyboard()
            await message.answer(
                "⛔ У вас нет доступа к боту.\n\n"
                "Для получения доступа нажмите кнопку ниже:",
                reply_markup=keyboard
            )
            return
        
        # Extract YouTube URL from message
        match = re.search(YOUTUBE_REGEX, message.text)
        youtube_url = match.group(0)
        
        logger.info(f"User {user.display_name} (ID: {user_id}) sent YouTube link: {youtube_url}")
        
        # Get user's settings
        model_name = user.model or self.summarizer.model
        languages = user.languages
        
        logger.info(f"Using model {model_name} and languages {languages} for user {user.display_name}")
        
        # Send processing message
        processing_msg = await message.answer("⏳ Анализирую видео, это может занять некоторое время...")
        
        try:
            # Use request
            if not user.is_admin and not user.has_unlimited_requests:
                user.use_request()
                self.user_manager.save_user(user)
                logger.info(f"User {user.display_name} (ID: {user_id}) used a request, remaining: {user.remaining_requests}")
            
            # Get video info and transcript
            await processing_msg.edit_text("⏳ Получаю информацию о видео...")
            
            title, transcript = await self.youtube_processor.process_video(youtube_url, languages)
            
            if not title or not transcript:
                # Generate error response
                error_text = await self.ai_agent.generate_error_response(youtube_url)
                
                # Delete processing message
                await processing_msg.delete()
                
                # Send error message with keyboard
                keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
                await message.reply(error_text, reply_markup=keyboard)
                return
            
            # Check transcript length
            transcript_length = len(transcript)
            if transcript_length > 5000:
                await processing_msg.edit_text(
                    f"⏳ Обрабатываю контент видео... Создаю краткий обзор с моделью {model_name}, "
                    f"это может занять некоторое время..."
                )
            else:
                await processing_msg.edit_text(
                    f"⏳ Создаю краткий обзор видео с помощью модели {model_name}..."
                )
            
            # Summarize text with selected model
            logger.info(f"Starting analytical processing for user {user.display_name} with model {model_name}")
            summary = await self.summarizer.summarize(text=transcript, title=title, model=model_name)
            
            # Clean up title and summary
            clean_title = re.sub(r'\s*\([Чч]асть \d+ из \d+\)\s*', '', title)
            
            # Enhanced cleaning of part references and URLs
            clean_summary = summary
            # Remove part X of Y references
            clean_summary = re.sub(r'(?i)([чЧ]асть|part) \d+ из \d+', '', clean_summary)
            clean_summary = re.sub(r'(?i)\(([чЧ]асть|part) \d+/\d+\)', '', clean_summary)
            # Remove any markdown links to YouTube
            clean_summary = re.sub(r'\[.*?\]\(https?://(?:www\.)?youtu(?:be\.com|\.be).*?\)', '', clean_summary)
            # Remove direct YouTube URLs
            clean_summary = re.sub(r'https?://(?:www\.)?youtu(?:be\.com|\.be)/\S+', '', clean_summary)
            # Remove "source:" or "источник:" references
            clean_summary = re.sub(r'(?i)(?:источник|source):\s*\[.*?\](?:\(.*?\))?', '', clean_summary)
            # Clean up any double line breaks created by the removals
            clean_summary = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_summary)
            
            # Send result
            logger.info(f"Sending analysis result to user {user.display_name}")
            
            # Format result
            result_text = f"🎬 {hbold(clean_title)}\n\n{clean_summary}"
            
            # Handle case where result is too long for one message
            keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
            
            if len(result_text) <= MAX_MESSAGE_LENGTH:
                # Send as single message
                await message.reply(result_text, reply_markup=keyboard)
            else:
                # Send title first
                await message.reply(f"🎬 {hbold(clean_title)}")
                
                # Split summary into parts
                logger.info(f"Summary too long, splitting into parts for user {user.display_name}")
                
                # Split text by paragraphs first
                paragraphs = clean_summary.split("\n\n")
                chunks = []
                current_chunk = ""
                
                for paragraph in paragraphs:
                    # If adding this paragraph would exceed limit, start a new chunk
                    if len(current_chunk) + len(paragraph) + 4 > MAX_MESSAGE_LENGTH and current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = paragraph
                    else:
                        if current_chunk:
                            current_chunk += "\n\n" + paragraph
                        else:
                            current_chunk = paragraph
                
                # Add the last chunk
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If no chunks were created, split by characters
                if not chunks:
                    chunks = [clean_summary[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(clean_summary), MAX_MESSAGE_LENGTH)]
                
                # Send each chunk
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        # Last chunk with keyboard
                        await message.reply(chunk, reply_markup=keyboard)
                    else:
                        # Intermediate chunks
                        await message.reply(chunk)
            
            # Delete processing message
            await processing_msg.delete()
            logger.info(f"Video processing for user {user.display_name} completed successfully")
            
        except Exception as e:
            error_message = f"❌ Произошла ошибка при обработке видео: {str(e)}"
            await processing_msg.edit_text(error_message)
            
            # Send keyboard in separate message
            keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
            await message.reply(
                "Попробуйте другое видео или измените настройки.",
                reply_markup=keyboard
            )
            
            logger.error(f"Error processing video for user {user.display_name}: {str(e)}", exc_info=True) 