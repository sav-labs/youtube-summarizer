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
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    help_button = KeyboardButton(text='❓ Помощь')
    models_button = KeyboardButton(text='🔄 Выбрать модель')
    language_button = KeyboardButton(text='🌐 Выбрать язык')
    settings_button = KeyboardButton(text='⚙️ Настройки')
    
    keyboard.add(help_button, models_button)
    keyboard.add(language_button, settings_button)
    
    return keyboard

def create_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Creates the admin keyboard with additional admin commands.
    
    Returns:
        ReplyKeyboardMarkup: Admin keyboard
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    help_button = KeyboardButton(text='❓ Помощь')
    models_button = KeyboardButton(text='🔄 Выбрать модель')
    language_button = KeyboardButton(text='🌐 Выбрать язык')
    settings_button = KeyboardButton(text='⚙️ Настройки')
    users_button = KeyboardButton(text='👥 Пользователи')
    
    keyboard.add(help_button, models_button)
    keyboard.add(language_button, settings_button)
    keyboard.add(users_button)
    
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
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup(row_width=1)
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
        
        # Add button
        keyboard.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"set_model:{model}"
        ))
    
    # Add back button
    keyboard.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    
    return keyboard

def create_language_keyboard() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for language selection.
    
    Returns:
        InlineKeyboardMarkup: Language selection keyboard
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
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
    
    # Add buttons to keyboard
    keyboard.add(ru_en_button)
    keyboard.add(ru_button, en_button)
    keyboard.add(de_button, fr_button)
    keyboard.add(es_button, it_button)
    keyboard.add(back_button)
    
    return keyboard

def create_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for settings.
    
    Returns:
        InlineKeyboardMarkup: Settings keyboard
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Settings options
    reset_button = InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="settings:reset")
    about_button = InlineKeyboardButton(text="ℹ️ О боте", callback_data="settings:about")
    
    # Back button
    back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    
    # Add buttons to keyboard
    keyboard.add(reset_button, about_button, back_button)
    
    return keyboard

def create_access_request_keyboard() -> InlineKeyboardMarkup:
    """
    Creates a keyboard for requesting access.
    
    Returns:
        InlineKeyboardMarkup: Access request keyboard
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Access request button
    request_button = InlineKeyboardButton(text="🔑 Запросить доступ", callback_data="request_access")
    
    # Add button to keyboard
    keyboard.add(request_button)
    
    return keyboard

def create_admin_notification_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for admin to approve/reject access request.
    
    Args:
        user_id: ID of the user requesting access
        
    Returns:
        InlineKeyboardMarkup: Admin notification keyboard
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
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
    
    # Add buttons to keyboard
    keyboard.add(grant_unlimited)
    keyboard.add(grant_one, grant_three)
    keyboard.add(grant_five, reject_button)
    
    return keyboard

def create_user_list_keyboard(user_ids: List[int], page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for user list with pagination.
    
    Args:
        user_ids: List of user IDs
        page: Current page number
        page_size: Number of users per page
        
    Returns:
        InlineKeyboardMarkup: User list keyboard
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Calculate pagination
    total_pages = (len(user_ids) - 1) // page_size + 1
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(user_ids))
    current_page_users = user_ids[start_idx:end_idx]
    
    # Add user buttons
    for user_id in current_page_users:
        keyboard.add(InlineKeyboardButton(
            text=f"👤 Пользователь {user_id}", 
            callback_data=f"user_info:{user_id}"
        ))
    
    # Add pagination buttons
    pagination_row = []
    
    if page > 0:
        pagination_row.append(InlineKeyboardButton(
            text="◀️ Пред.",
            callback_data=f"user_list:{page-1}"
        ))
    
    pagination_row.append(InlineKeyboardButton(
        text=f"📄 {page+1}/{total_pages}",
        callback_data="noop"
    ))
    
    if page < total_pages - 1:
        pagination_row.append(InlineKeyboardButton(
            text="След. ▶️",
            callback_data=f"user_list:{page+1}"
        ))
    
    # Add pagination row
    keyboard.row(*pagination_row)
    
    # Add back button
    keyboard.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    
    return keyboard

def create_user_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Creates a keyboard for user management.
    
    Args:
        user_id: User ID
        
    Returns:
        InlineKeyboardMarkup: User management keyboard
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # User management options
    grant_unlimited = InlineKeyboardButton(
        text="♾️ Безлимит", 
        callback_data=f"grant_access:{user_id}:-1"
    )
    
    grant_one = InlineKeyboardButton(
        text="1️⃣ 1 запрос", 
        callback_data=f"grant_access:{user_id}:1"
    )
    
    grant_five = InlineKeyboardButton(
        text="5️⃣ 5 запросов", 
        callback_data=f"grant_access:{user_id}:5"
    )
    
    grant_ten = InlineKeyboardButton(
        text="🔟 10 запросов", 
        callback_data=f"grant_access:{user_id}:10"
    )
    
    revoke_button = InlineKeyboardButton(
        text="🚫 Отозвать доступ", 
        callback_data=f"revoke_access:{user_id}"
    )
    
    back_button = InlineKeyboardButton(
        text="⬅️ Назад к списку", 
        callback_data=f"user_list:0"
    )
    
    # Add buttons to keyboard
    keyboard.add(grant_unlimited, grant_one)
    keyboard.add(grant_five, grant_ten)
    keyboard.add(revoke_button)
    keyboard.add(back_button)
    
    return keyboard 