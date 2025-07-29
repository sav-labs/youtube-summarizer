"""
User Manager for the YouTube Summarizer Bot.
Handles user data storage and retrieval.
"""
import json
import os
from typing import Dict, List, Optional, Any
from src.models.user import User
from src.config.settings import ADMIN_USER_ID
import logging

class UserManager:
    """
    Manages user data for the YouTube Summarizer Bot.
    Handles persistence, retrieval, and operations on user data.
    """
    def __init__(self, data_file: str = "user_data.json", logger: Optional[logging.Logger] = None):
        """
        Initializes the UserManager.
        
        Args:
            data_file: Path to the JSON file for user data storage
            logger: Logger instance
        """
        self.data_file = data_file
        self.logger = logger or logging.getLogger(__name__)
        self.users: Dict[int, User] = {}
        self._load_users()
        self._ensure_admin()
    
    def _ensure_admin(self) -> None:
        """Ensures the admin user exists"""
        if ADMIN_USER_ID and ADMIN_USER_ID > 0:
            admin = self.get_user(ADMIN_USER_ID)
            if admin:
                # Make sure admin has admin rights
                if not admin.is_admin:
                    admin.is_admin = True
                    admin.is_approved = True
                    self.save_user(admin)
                    self.logger.info(f"Updated user {ADMIN_USER_ID} to admin status")
            else:
                # Create admin user if it doesn't exist
                admin = User(
                    user_id=ADMIN_USER_ID,
                    is_admin=True,
                    is_approved=True
                )
                self.save_user(admin)
                self.logger.info(f"Created admin user with ID {ADMIN_USER_ID}")
    
    def _load_users(self) -> None:
        """Loads users from the data file"""
        if not os.path.exists(self.data_file):
            self.logger.info(f"User data file {self.data_file} not found, starting with empty user list")
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            users_loaded = 0
            for user_data in data.values():
                user = User.from_dict(user_data)
                self.users[user.user_id] = user
                users_loaded += 1
            
            self.logger.info(f"Loaded {users_loaded} users from {self.data_file}")
            
            # Auto-migrate: Save users to update file structure with new fields
            if users_loaded > 0:
                self._save_users()
                self.logger.info("Auto-migrated users data to current format")
                
        except Exception as e:
            self.logger.error(f"Error loading users from {self.data_file}: {e}")
    
    def _save_users(self) -> None:
        """Saves users to the data file"""
        try:
            data = {str(user_id): user.to_dict() for user_id, user in self.users.items()}
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Saved {len(self.users)} users to {self.data_file}")
        except Exception as e:
            self.logger.error(f"Error saving users to {self.data_file}: {e}")
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Gets a user by their ID"""
        return self.users.get(user_id)
    
    def get_or_create_user(self, user_id: int, **kwargs: Any) -> User:
        """Gets a user by their ID or creates a new one if it doesn't exist"""
        user = self.get_user(user_id)
        if not user:
            user = User(user_id=user_id, **kwargs)
            
            # If this is the admin user, grant admin privileges
            if user_id == ADMIN_USER_ID:
                user.is_admin = True
                user.is_approved = True
            
            self.users[user_id] = user
            self._save_users()
            self.logger.info(f"Created new user with ID {user_id}")
        return user
    
    def save_user(self, user: User) -> None:
        """Saves a user to the database"""
        self.users[user.user_id] = user
        self._save_users()
    
    def get_all_users(self) -> List[User]:
        """Returns a list of all users"""
        return list(self.users.values())
    
    def get_admin_users(self) -> List[User]:
        """Returns a list of admin users"""
        return [user for user in self.users.values() if user.is_admin]
    
    def request_access(self, user: User) -> None:
        """Marks a user as requesting access"""
        user.is_approved = False
        self.save_user(user)
    
    def grant_access(self, user_id: int, requests: int) -> bool:
        """
        Grants access to a user with the specified number of requests.
        Returns True if successful, False if the user doesn't exist.
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        user.grant_access(requests)
        self.save_user(user)
        return True
    
    def revoke_access(self, user_id: int) -> bool:
        """
        Revokes access from a user.
        Returns True if successful, False if the user doesn't exist.
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        user.revoke_access()
        self.save_user(user)
        return True 