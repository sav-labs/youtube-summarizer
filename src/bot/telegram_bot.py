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
    Handles all bot interactions and user management.
    """
    def __init__(self):
        """Initialize the Telegram bot with all necessary components."""
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)
        self.dp = Dispatcher()
        self.user_manager = UserManager()
        self.youtube_processor = YouTubeProcessor()
        self.summarizer = Summarizer()
        self.ai_agent = AIAgent()
        
        # Set up command menu
        self._setup_bot_commands()
        
        # Register handlers
        self.register_handlers()
        
        logger.info("Telegram bot initialized")

    async def _setup_bot_commands(self):
        """Setup bot commands menu."""
        commands = [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="help", description="Помощь по использованию"),
            BotCommand(command="models", description="Выбрать модель"),
            BotCommand(command="language", description="Выбрать язык"),
            BotCommand(command="settings", description="Настройки")
        ]
        await self.bot.set_my_commands(commands)

    def register_handlers(self):
        """Register all message and callback handlers."""
        # Command handlers
        self.dp.message.register(self.cmd_start, commands=["start"])
        self.dp.message.register(self.cmd_help, commands=["help"])
        self.dp.message.register(self.cmd_models, commands=["models"])
        self.dp.message.register(self.cmd_language, commands=["language"])
        self.dp.message.register(self.cmd_settings, commands=["settings"])
        
        # Button handlers
        self.dp.message.register(self.cmd_help, lambda msg: msg.text == "❓ Помощь")
        self.dp.message.register(self.cmd_models, lambda msg: msg.text == "🔄 Выбрать модель")
        self.dp.message.register(self.cmd_language, lambda msg: msg.text == "🌐 Выбрать язык")
        self.dp.message.register(self.cmd_settings, lambda msg: msg.text == "⚙️ Настройки")
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
        """Start the bot polling with improved error handling and retry logic."""
        max_retries = 5
        retry_delay = 1.0
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info("Starting bot polling")
                
                # Configure polling parameters for better stability
                await self.dp.start_polling(
                    self.bot,
                    allowed_updates=["message", "callback_query"],  # Only handle messages and callbacks
                    drop_pending_updates=True,  # Skip old messages on restart
                    timeout=30,  # 30 second timeout for long polling
                    backoff_factor=2.0,  # Exponential backoff for retries
                    max_retries=3  # Internal retries for each request
                )
                
                # If we get here, polling ended normally
                logger.info("Bot polling ended")
                break
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user (KeyboardInterrupt)")
                break
                
            except Exception as e:
                error_msg = str(e).lower()
                retry_count += 1
                
                # Handle specific error types
                if "conflict" in error_msg and "getupdates" in error_msg:
                    logger.warning(f"Conflict error detected (another bot instance running): {e}")
                    if retry_count < max_retries:
                        logger.info(f"Waiting {retry_delay * 2} seconds for other instance to stop...")
                        await asyncio.sleep(retry_delay * 2)
                        retry_delay *= 2  # Increase delay for conflicts
                    continue
                    
                elif any(network_error in error_msg for network_error in [
                    "connection reset", "connection timeout", "network", 
                    "server disconnected", "timeout", "clientoserror"
                ]):
                    logger.warning(f"Network error (attempt {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 30)  # Cap delay at 30 seconds
                    continue
                    
                else:
                    # For other errors, log and retry with shorter delay
                    logger.error(f"Unexpected error (attempt {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        logger.info(f"Retrying in {min(retry_delay, 5)} seconds...")
                        await asyncio.sleep(min(retry_delay, 5))
                    continue
        
        if retry_count >= max_retries:
            logger.critical(f"Failed to start bot after {max_retries} attempts")
            raise Exception(f"Bot failed to start after {max_retries} retry attempts")
    
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
        
        # Check if user has access
        if user.has_access():
            # User has access, show main menu
            keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
            welcome_message = f"👋 Привет, {user.display_name}!\n\n"
            
            if user.is_admin:
                welcome_message += "🔧 *Административная панель*\n\n"
            
            welcome_message += (
                "🎥 Я помогу вам создать краткое содержание любого YouTube видео!\n\n"
                "📎 Просто отправьте мне ссылку на YouTube видео, и я проанализирую его содержание.\n\n"
                "⚙️ Используйте кнопки ниже для настройки бота."
            )
            
            await message.answer(welcome_message, reply_markup=keyboard)
        else:
            # User doesn't have access, show access request
            await self.show_access_request(message, user)

    async def show_access_request(self, message: Message, user):
        """Show access request interface to user."""
        access_message = (
            f"👋 Привет, {user.display_name}!\n\n"
            "🔒 Для использования бота необходимо получить доступ.\n\n"
            "📝 Нажмите кнопку ниже, чтобы отправить запрос администратору."
        )
        
        keyboard = create_access_request_keyboard()
        await message.answer(access_message, reply_markup=keyboard)

    async def cmd_help(self, message: Message):
        """
        Handle /help command and help button.
        
        Args:
            message: Telegram message with the command
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        logger.info(f"User {user.display_name} (ID: {user_id}) requested help")
        
        help_text = (
            "📖 *Руководство по использованию бота*\n\n"
            "🎥 *Основная функция:*\n"
            "Отправьте ссылку на YouTube видео, и бот создаст его краткое содержание\n\n"
            "🔧 *Доступные команды:*\n"
            "• /start - Запустить бота\n"
            "• /help - Показать эту справку\n"
            "• /models - Выбрать модель ИИ\n"
            "• /language - Выбрать язык субтитров\n"
            "• /settings - Настройки бота\n\n"
            "⚙️ *Кнопки управления:*\n"
            "• 🔄 Выбрать модель - изменить модель ИИ\n"
            "• 🌐 Выбрать язык - настроить языки субтитров\n"
            "• ⚙️ Настройки - дополнительные опции\n\n"
        )
        
        if user.is_admin:
            help_text += (
                "👑 *Административные функции:*\n"
                "• 👥 Пользователи - управление пользователями\n"
                "• Одобрение запросов доступа\n"
                "• Управление лимитами пользователей\n\n"
            )
        
        help_text += (
            "📝 *Поддерживаемые форматы ссылок:*\n"
            "• youtube.com/watch?v=...\n"
            "• youtu.be/...\n"
            "• youtube.com/shorts/...\n\n"
            "💡 *Совет:* Бот работает лучше всего с видео, у которых есть субтитры на русском или английском языке."
        )
        
        await message.answer(help_text)

    async def cmd_models(self, message: Message):
        """
        Handle /models command and models button.
        
        Args:
            message: Telegram message with the command
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        if not user.has_access():
            await message.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        try:
            models = await self.summarizer.list_available_models()
            keyboard = create_models_keyboard(models, user.model)
            
            model_text = (
                "🤖 *Выбор модели ИИ для анализа видео*\n\n"
                f"Текущая модель: *{user.model or 'По умолчанию'}*\n\n"
                "📊 *Описание моделей:*\n"
                "• GPT-4o - Самая современная модель\n"
                "• GPT-4o-mini - Быстрая и эффективная\n"
                "• GPT-4 - Высокое качество анализа\n"
                "• GPT-3.5 - Базовая модель\n\n"
                "Выберите модель из списка ниже:"
            )
            
            await message.answer(model_text, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            await message.answer("❌ Ошибка при получении списка моделей.")

    async def cmd_language(self, message: Message):
        """
        Handle /language command and language button.
        
        Args:
            message: Telegram message with the command
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        if not user.has_access():
            await message.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        keyboard = create_language_keyboard()
        
        current_langs = ", ".join(user.languages) if user.languages else "ru, en"
        
        language_text = (
            "🌐 *Выбор языков для субтитров*\n\n"
            f"Текущие языки: *{current_langs}*\n\n"
            "📝 *Как это работает:*\n"
            "Бот будет искать субтитры на выбранных языках в порядке приоритета.\n\n"
            "🎯 *Рекомендации:*\n"
            "• Для русских видео: Русский + Английский\n"
            "• Для международного контента: Английский\n"
            "• Для локального контента: соответствующий язык\n\n"
            "Выберите языки ниже:"
        )
        
        await message.answer(language_text, reply_markup=keyboard)

    async def cmd_settings(self, message: Message):
        """
        Handle /settings command and settings button.
        
        Args:
            message: Telegram message with the command
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        if not user.has_access():
            await message.answer("⛔ У вас нет доступа к этой функции.")
            return
        
        keyboard = create_settings_keyboard()
        
        # Format user info
        remaining = "♾️ Безлимит" if user.has_unlimited_requests else f"{user.remaining_requests}"
        
        settings_text = (
            "⚙️ *Настройки пользователя*\n\n"
            f"👤 *Пользователь:* {user.display_name}\n"
            f"🤖 *Модель:* {user.model or 'По умолчанию'}\n"
            f"🌐 *Языки:* {', '.join(user.languages)}\n"
            f"📊 *Осталось запросов:* {remaining}\n"
            f"📅 *Дата регистрации:* {user.created_at.strftime('%d.%m.%Y')}\n\n"
            "Выберите действие:"
        )
        
        await message.answer(settings_text, reply_markup=keyboard)

    async def list_users(self, message: types.Message):
        """
        Shows a list of all users to admin users.
        
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
        
        # Get all users except the current admin
        all_users = self.user_manager.get_all_users()
        users = [u for u in all_users if u.user_id != user_id]
        
        if not users:
            await message.answer("👥 Нет зарегистрированных пользователей.")
            return
        
        # Create keyboard with user objects
        keyboard = create_user_list_keyboard(users)
        
        # Send user list message
        await message.answer(
            f"👥 Список пользователей ({len(users)}):\n\n"
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
            elif data.startswith("user_info:"):
                await self.handle_user_info(callback, user)
            elif data.startswith("user_list:"):
                await self.handle_user_list_page(callback, user)
            elif data.startswith("revoke_access:"):
                await self.handle_revoke_access(callback, user)
            elif data == "noop":
                # No operation - for pagination indicators
                await callback.answer()
            else:
                logger.warning(f"Unknown callback data: {data}")
                await callback.answer("❌ Неизвестная команда")
                
        except Exception as e:
            logger.error(f"Error handling callback {data}: {e}")
            await callback.answer("❌ Произошла ошибка")

    async def handle_set_model(self, callback: CallbackQuery, user):
        """Handle model selection callback."""
        model = callback.data.split(":", 1)[1]
        
        # Update user model
        user.model = model
        self.user_manager.save_user(user)
        
        logger.info(f"User {user.display_name} (ID: {user.user_id}) changed model to {model}")
        
        await callback.answer(f"✅ Модель изменена на {model}")
        
        # Update the message
        try:
            models = await self.summarizer.list_available_models()
            keyboard = create_models_keyboard(models, user.model)
            
            await callback.message.edit_text(
                f"🤖 *Выбор модели ИИ для анализа видео*\n\n"
                f"Текущая модель: *{user.model}* ✅\n\n"
                f"Модель успешно изменена!",
                reply_markup=keyboard
            )
        except:
            pass

    async def handle_set_language(self, callback: CallbackQuery, user):
        """Handle language selection callback."""
        languages_str = callback.data.split(":", 1)[1]
        languages = [lang.strip() for lang in languages_str.split(",")]
        
        # Update user languages
        user.languages = languages
        self.user_manager.save_user(user)
        
        logger.info(f"User {user.display_name} (ID: {user.user_id}) changed languages to {languages}")
        
        await callback.answer(f"✅ Языки изменены на: {', '.join(languages)}")
        
        # Update the message
        keyboard = create_language_keyboard()
        await callback.message.edit_text(
            f"🌐 *Выбор языков для субтитров*\n\n"
            f"Текущие языки: *{', '.join(languages)}* ✅\n\n"
            f"Языки успешно изменены!",
            reply_markup=keyboard
        )

    async def handle_settings_action(self, callback: CallbackQuery, user):
        """Handle settings actions."""
        action = callback.data.split(":", 1)[1]
        
        if action == "reset":
            # Reset user settings to default
            user.model = None
            user.languages = ['ru', 'en']
            self.user_manager.save_user(user)
            
            await callback.answer("✅ Настройки сброшены")
            await callback.message.edit_text(
                "🔄 *Настройки сброшены*\n\n"
                "Все настройки возвращены к значениям по умолчанию."
            )
            
        elif action == "about":
            about_text = (
                "ℹ️ *О боте YouTube Summarizer*\n\n"
                "🎯 *Назначение:*\n"
                "Создание кратких аналитических обзоров YouTube видео\n\n"
                "🔧 *Технологии:*\n"
                "• OpenAI GPT для анализа\n"
                "• YouTube Transcript API для субтитров\n"
                "• Aiogram для Telegram интеграции\n\n"
                "📊 *Возможности:*\n"
                "• Поддержка нескольких языков\n"
                "• Выбор различных моделей ИИ\n"
                "• Структурированный анализ контента\n\n"
                "👨‍💻 *Разработка:* 2024"
            )
            
            await callback.message.edit_text(about_text)

    async def handle_back_to_main(self, callback: CallbackQuery, user):
        """Handle back to main menu action."""
        await callback.answer()
        
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()
        
        welcome_text = f"👋 Главное меню\n\n"
        if user.is_admin:
            welcome_text += "🔧 *Административная панель*\n\n"
        
        welcome_text += "Выберите действие:"
        
        await callback.message.edit_text(welcome_text, reply_markup=keyboard)

    async def handle_request_access(self, callback: CallbackQuery, user):
        """Handle access request from user."""
        await callback.answer("📨 Запрос отправлен администратору")
        
        # Send notification to all admins
        admins = self.user_manager.get_admin_users()
        
        for admin in admins:
            try:
                # Generate admin notification
                user_data = {
                    "user_id": user.user_id,
                    "user_name": user.display_name,
                    "username": user.username or "Не указан",
                    "request_date": datetime.now().strftime("%d.%m.%Y %H:%M")
                }
                
                notification_text = await self.ai_agent.generate_admin_notification(user_data)
                keyboard = create_admin_notification_keyboard(user.user_id)
                
                await self.bot.send_message(
                    admin.user_id,
                    notification_text,
                    reply_markup=keyboard
                )
                
            except Exception as e:
                logger.error(f"Failed to send notification to admin {admin.user_id}: {e}")
        
        # Update user message
        await callback.message.edit_text(
            "📨 *Запрос отправлен*\n\n"
            "Ваш запрос на доступ отправлен администратору.\n"
            "Ожидайте одобрения."
        )

    async def handle_grant_access(self, callback: CallbackQuery, user):
        """Handle admin granting access to user."""
        if not user.is_admin:
            await callback.answer("⛔ Недостаточно прав")
            return
        
        try:
            _, target_user_id_str, requests_str = callback.data.split(":")
            target_user_id = int(target_user_id_str)
            requests = int(requests_str)
            
            target_user = self.user_manager.get_user(target_user_id)
            if not target_user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            # Grant access
            target_user.grant_access(requests)
            self.user_manager.save_user(target_user)
            
            # Notify admin
            requests_text = "безлимитный доступ" if requests == -1 else f"{requests} запросов"
            await callback.answer(f"✅ Доступ предоставлен: {requests_text}")
            
            # Update admin message
            await callback.message.edit_text(
                f"✅ *Доступ предоставлен*\n\n"
                f"Пользователь {target_user.display_name} получил {requests_text}."
            )
            
            # Notify user about approved access
            try:
                await self.bot.send_message(
                    target_user_id,
                    f"🎉 *Доступ одобрен!*\n\n"
                    f"Вам предоставлен {requests_text}.\n"
                    f"Теперь вы можете пользоваться ботом!"
                )
            except:
                pass
            
            logger.info(f"Admin {user.display_name} granted access to user {target_user.display_name} ({requests} requests)")
            
        except Exception as e:
            logger.error(f"Error granting access: {e}")
            await callback.answer("❌ Ошибка при предоставлении доступа")

    async def handle_reject_access(self, callback: CallbackQuery, user):
        """Handle admin rejecting access request."""
        if not user.is_admin:
            await callback.answer("⛔ Недостаточно прав")
            return
        
        try:
            target_user_id = int(callback.data.split(":", 1)[1])
            target_user = self.user_manager.get_user(target_user_id)
            
            if not target_user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            await callback.answer("❌ Запрос отклонен")
            
            # Update admin message
            await callback.message.edit_text(
                f"❌ *Запрос отклонен*\n\n"
                f"Запрос пользователя {target_user.display_name} был отклонен."
            )
            
            # Notify user about rejection
            try:
                await self.bot.send_message(
                    target_user_id,
                    "❌ *Запрос отклонен*\n\n"
                    "К сожалению, ваш запрос на доступ к боту был отклонен администратором."
                )
            except:
                pass
            
            logger.info(f"Admin {user.display_name} rejected access for user {target_user.display_name}")
            
        except Exception as e:
            logger.error(f"Error rejecting access: {e}")
            await callback.answer("❌ Ошибка при отклонении запроса")

    async def handle_user_info(self, callback: CallbackQuery, user):
        """Handle user info request from admin."""
        if not user.is_admin:
            await callback.answer("⛔ Недостаточно прав")
            return
        
        try:
            target_user_id = int(callback.data.split(":", 1)[1])
            target_user = self.user_manager.get_user(target_user_id)
            
            if not target_user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            # Format user information
            remaining = "♾️ Безлимит" if target_user.has_unlimited_requests else f"{target_user.remaining_requests}"
            status = "✅ Активен" if target_user.has_access() else "❌ Нет доступа"
            
            user_info_text = (
                f"👤 *Информация о пользователе*\n\n"
                f"**ID:** {target_user.user_id}\n"
                f"**Имя:** {target_user.display_name}\n"
                f"**Username:** @{target_user.username or 'Не указан'}\n"
                f"**Статус:** {status}\n"
                f"**Админ:** {'Да' if target_user.is_admin else 'Нет'}\n"
                f"**Модель:** {target_user.model or 'По умолчанию'}\n"
                f"**Языки:** {', '.join(target_user.languages)}\n"
                f"**Осталось запросов:** {remaining}\n"
                f"**Регистрация:** {target_user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"**Последнее обновление:** {target_user.updated_at.strftime('%d.%m.%Y %H:%M')}"
            )
            
            keyboard = create_user_management_keyboard(target_user_id)
            await callback.message.edit_text(user_info_text, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error showing user info: {e}")
            await callback.answer("❌ Ошибка при получении информации")

    async def handle_user_list_page(self, callback: CallbackQuery, user):
        """Handle user list pagination."""
        if not user.is_admin:
            await callback.answer("⛔ Недостаточно прав")
            return
        
        try:
            page = int(callback.data.split(":", 1)[1])
            
            # Get all users except current admin
            all_users = self.user_manager.get_all_users()
            users = [u for u in all_users if u.user_id != user.user_id]
            
            keyboard = create_user_list_keyboard(users, page)
            
            await callback.message.edit_text(
                f"👥 Список пользователей ({len(users)}):\n\n"
                f"Выберите пользователя для управления:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error handling user list page: {e}")
            await callback.answer("❌ Ошибка при загрузке страницы")

    async def handle_revoke_access(self, callback: CallbackQuery, user):
        """Handle admin revoking user access."""
        if not user.is_admin:
            await callback.answer("⛔ Недостаточно прав")
            return
        
        try:
            target_user_id = int(callback.data.split(":", 1)[1])
            target_user = self.user_manager.get_user(target_user_id)
            
            if not target_user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            # Revoke access
            target_user.revoke_access()
            self.user_manager.save_user(target_user)
            
            await callback.answer("✅ Доступ отозван")
            
            # Notify user
            try:
                await self.bot.send_message(
                    target_user_id,
                    "🚫 *Доступ отозван*\n\n"
                    "Ваш доступ к боту был отозван администратором."
                )
            except:
                pass
            
            logger.info(f"Admin {user.display_name} revoked access for user {target_user.display_name}")
            
        except Exception as e:
            logger.error(f"Error revoking access: {e}")
            await callback.answer("❌ Ошибка при отзыве доступа")

    async def process_youtube_link(self, message: Message):
        """
        Process YouTube link sent by user.
        
        Args:
            message: Telegram message containing YouTube link
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Check if user has access
        if not user.has_access():
            await message.answer("⛔ У вас нет доступа к обработке видео. Запросите доступ у администратора.")
            return
        
        # Check if user has remaining requests
        if not user.use_request():
            await message.answer("❌ У вас закончились запросы. Обратитесь к администратору.")
            return
        
        # Save user after using request
        self.user_manager.save_user(user)
        
        url = message.text.strip()
        
        logger.info(f"User {user.display_name} (ID: {user_id}) sent YouTube link: {url}")
        logger.info(f"Using model {user.model or 'default'} and languages {user.languages} for user {user_id}")
        
        # Send "processing" message
        processing_msg = await message.answer("🔄 Обрабатываю видео, это может занять некоторое время...")
        
        try:
            # Process the video
            video_title, transcript = await self.youtube_processor.process_video(url, user.languages)
            
            if not video_title or not transcript:
                # Generate error response
                error_response = await self.ai_agent.generate_error_response(url, user.model)
                await processing_msg.edit_text(error_response)
                return
            
            # Generate summary
            summary = await self.summarizer.summarize_text(
                text=transcript,
                title=video_title,
                model=user.model
            )
            
            if not summary:
                await processing_msg.edit_text("❌ Не удалось создать анализ видео.")
                return
            
            # Format final response
            final_response = (
                f"🎥 **{video_title}**\n\n"
                f"{summary}\n\n"
                f"🔗 [Ссылка на видео]({url})"
            )
            
            # Edit the processing message with results
            await processing_msg.edit_text(final_response, disable_web_page_preview=True)
            
            logger.info(f"Successfully processed video for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error processing video for user {user_id}: {str(e)}")
            
            # Generate error response using AI
            try:
                error_response = await self.ai_agent.generate_error_response(url, user.model)
                await processing_msg.edit_text(error_response)
            except:
                await processing_msg.edit_text(
                    "❌ Произошла ошибка при обработке видео. "
                    "Пожалуйста, проверьте ссылку и попробуйте снова."
                )

    async def handle_unknown_message(self, message: Message):
        """
        Handle unknown messages (not YouTube links or commands).
        
        Args:
            message: Telegram message with unknown content
        """
        user_id = message.from_user.id
        user = self.user_manager.get_or_create_user(user_id=user_id)
        
        # Don't process if user doesn't have access
        if not user.has_access():
            await self.show_access_request(message, user)
            return
        
        text = message.text or ""
        
        logger.info(f"Unknown message from user {user.display_name} (ID: {user_id}): {text[:50]}...")
        
        try:
            # Generate response using AI
            response = await self.ai_agent.handle_unknown_message(text, user.model)
            await message.answer(response)
            
        except Exception as e:
            logger.error(f"Error handling unknown message: {e}")
            await message.answer(
                "🤖 Я умею анализировать только YouTube видео.\n\n"
                "📎 Отправьте мне ссылку на YouTube видео, и я создам его краткий анализ!"
            )