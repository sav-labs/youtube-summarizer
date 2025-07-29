"""
Keyboards module for the YouTube Summarizer Bot.
Contains functions to create various bot keyboards.
"""
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from typing import List, Optional

def create_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Creates the main keyboard with command buttons.
    
    Returns:
        ReplyKeyboardMarkup: Main keyboard
    """
    help_button = KeyboardButton(text='❓ Помощь')
    models_button = KeyboardButton(text='🔄 Выбрать модель')
    language_button = KeyboardButton(text='🌐 Выбрать язык')
    settings_button = KeyboardButton(text='⚙️ Настройки')
    
    # In Aiogram 3.x, we need to create a keyboard with a list of lists of buttons
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [help_button, models_button],
            [language_button, settings_button]
        ],
        resize_keyboard=True
    )
    
    return keyboard

def create_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Creates the admin keyboard with additional admin commands.
    
    Returns:
        ReplyKeyboardMarkup: Admin keyboard
    """
    help_button = KeyboardButton(text='❓ Помощь')
    models_button = KeyboardButton(text='🔄 Выбрать модель')
    language_button = KeyboardButton(text='🌐 Выбрать язык')
    settings_button = KeyboardButton(text='⚙️ Настройки')
    users_button = KeyboardButton(text='👥 Пользователи')
    
    # In Aiogram 3.x, we need to create a keyboard with a list of lists of buttons
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [help_button, models_button],
            [language_button, settings_button],
            [users_button]
        ],
        resize_keyboard=True
    )
    
    return keyboard

def create_models_keyboard(models: List[str], current_model: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for model selection.
    
    Args:
        models: List of available models
        current_model: Currently selected model
        
    Returns:
        InlineKeyboardMarkup: Model selection keyboard
    """
    # Model categories for sorting
    model_categories = {
        "gpt-4.5": 1,
        "gpt-4o": 2,
        "gpt-4o-mini": 3,
        "gpt-4": 4,
        "gpt-4-turbo": 5,
        "gpt-3.5-turbo-16k": 6,
        "gpt-3.5-turbo": 7
    }
    
    # Sort models by category
    sorted_models = sorted(models, key=lambda x: (
        next((i for prefix, i in model_categories.items() if x.startswith(prefix)), 99),
        x
    ))
    
    # Create buttons for models
    keyboard_buttons = []
    added_models = set()
    
    for model in sorted_models:
        # Skip if already added (absolute duplicates)
        if model in added_models:
            continue
            
        # Add to processed list
        added_models.add(model)
        
        # Mark current model
        is_current = (model == current_model)
        button_text = f"{model} ✓" if is_current else model
        
        # Add button to the list
        keyboard_buttons.append([
            InlineKeyboardButton(text=button_text, callback_data=f"set_model:{model}")
        ])
    
    # Add back button
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    
    # Create the keyboard with the buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    return keyboard

def create_language_keyboard() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for language selection.
    
    Returns:
        InlineKeyboardMarkup: Language selection keyboard
    """
    # Default option (Russian + English)
    ru_en_button = InlineKeyboardButton(
        text="🇷🇺🇬🇧 Русский+Английский (по умолчанию)", 
        callback_data="lang:ru,en"
    )
    
    # Language options
    ru_button = InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")
    en_button = InlineKeyboardButton(text="🇬🇧 Английский", callback_data="lang:en")
    de_button = InlineKeyboardButton(text="🇩🇪 Немецкий", callback_data="lang:de")
    fr_button = InlineKeyboardButton(text="🇫🇷 Французский", callback_data="lang:fr")
    es_button = InlineKeyboardButton(text="🇪🇸 Испанский", callback_data="lang:es")
    it_button = InlineKeyboardButton(text="🇮🇹 Итальянский", callback_data="lang:it")
    
    # Back button
    back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    
    # Create keyboard with buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [ru_en_button],
        [ru_button, en_button],
        [de_button, fr_button],
        [es_button, it_button],
        [back_button]
    ])
    
    return keyboard

def create_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for settings.
    
    Returns:
        InlineKeyboardMarkup: Settings keyboard
    """
    # Settings options
    reset_button = InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="settings:reset")
    about_button = InlineKeyboardButton(text="ℹ️ О боте", callback_data="settings:about")
    
    # Back button
    back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    
    # Create keyboard with buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [reset_button],
        [about_button],
        [back_button]
    ])
    
    return keyboard

def create_access_request_keyboard() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for requesting access.
    
    Returns:
        InlineKeyboardMarkup: Access request keyboard
    """
    # Access request button
    request_button = InlineKeyboardButton(text="🔑 Запросить доступ", callback_data="request_access")
    
    # Create keyboard with button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [request_button]
    ])
    
    return keyboard

def create_admin_notification_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for admin to approve/reject access request.
    
    Args:
        user_id: ID of the user requesting access
        
    Returns:
        InlineKeyboardMarkup: Admin notification keyboard
    """
    # Approval options
    grant_unlimited = InlineKeyboardButton(
        text="✅ Дать безлимит", 
        callback_data=f"grant_access:{user_id}:-1"
    )
    
    grant_one = InlineKeyboardButton(
        text="1️⃣ Дать 1 запрос", 
        callback_data=f"grant_access:{user_id}:1"
    )
    
    grant_three = InlineKeyboardButton(
        text="3️⃣ Дать 3 запроса", 
        callback_data=f"grant_access:{user_id}:3"
    )
    
    grant_five = InlineKeyboardButton(
        text="5️⃣ Дать 5 запросов", 
        callback_data=f"grant_access:{user_id}:5"
    )
    
    # Reject button
    reject_button = InlineKeyboardButton(
        text="❌ Отклонить", 
        callback_data=f"reject_access:{user_id}"
    )
    
    # Create keyboard with buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [grant_unlimited],
        [grant_one, grant_three],
        [grant_five, reject_button]
    ])
    
    return keyboard

def create_user_list_keyboard(users: List, page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for user list with pagination.
    
    Args:
        users: List of User objects
        page: Current page number
        page_size: Number of users per page
        
    Returns:
        InlineKeyboardMarkup: User list keyboard
    """
    # Calculate pagination
    total_pages = (len(users) - 1) // page_size + 1
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(users))
    current_page_users = users[start_idx:end_idx]
    
    # Create buttons list
    keyboard_buttons = []
    
    # Add user buttons
    for user in current_page_users:
        # Show username or display name instead of just ID
        display_text = f"👤 {user.display_name}"
        if user.username and user.username != user.display_name:
            display_text += f" (@{user.username})"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=display_text, 
                callback_data=f"user_info:{user.user_id}"
            )
        ])
    
    # Add pagination buttons if necessary
    if total_pages > 1:
        pagination_row = []
        
        # Add "Previous" button if not on first page
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(
                    text="⬅️ Назад", 
                    callback_data=f"user_list:{page-1}"
                )
            )
        
        # Add page indicator
        pagination_row.append(
            InlineKeyboardButton(
                text=f"📄 {page+1}/{total_pages}", 
                callback_data="noop"
            )
        )
        
        # Add "Next" button if not on last page
        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton(
                    text="➡️ Вперед", 
                    callback_data=f"user_list:{page+1}"
                )
            )
        
        keyboard_buttons.append(pagination_row)
    
    # Add "Back to main" button
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")
    ])
    
    # Create keyboard with buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    return keyboard

def create_user_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for managing a specific user.
    
    Args:
        user_id: ID of the user to manage
        
    Returns:
        InlineKeyboardMarkup: User management keyboard
    """
    # Create buttons
    grant_unlimited = InlineKeyboardButton(
        text="♾️ Дать безлимитный доступ", 
        callback_data=f"grant_access:{user_id}:-1"
    )
    
    grant_requests = InlineKeyboardButton(
        text="🎯 Добавить запросы", 
        callback_data=f"grant_access:{user_id}:5"
    )
    
    revoke_access = InlineKeyboardButton(
        text="🚫 Отозвать доступ", 
        callback_data=f"revoke_access:{user_id}"
    )
    
    back_to_list = InlineKeyboardButton(
        text="📋 К списку пользователей", 
        callback_data="user_list:0"
    )
    
    back_to_main = InlineKeyboardButton(
        text="⬅️ В главное меню", 
        callback_data="back_to_main"
    )
    
    # Create keyboard with buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [grant_unlimited],
        [grant_requests],
        [revoke_access],
        [back_to_list],
        [back_to_main]
    ])
    
    return keyboard 