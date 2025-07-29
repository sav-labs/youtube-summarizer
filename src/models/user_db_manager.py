"""
User Database Manager for the YouTube Summarizer Bot.
Handles user data storage and retrieval using SQLite database.
"""
import sqlite3
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.models.user import User
from src.config.settings import ADMIN_USER_ID
import logging

class UserDatabaseManager:
    """
    Manages user data for the YouTube Summarizer Bot using SQLite database.
    Handles persistence, retrieval, and operations on user data.
    """
    
    def __init__(self, db_path: str = "data/users.db", logger: Optional[logging.Logger] = None):
        """
        Initializes the UserDatabaseManager.
        
        Args:
            db_path: Path to the SQLite database file
            logger: Logger instance
        """
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self.users: Dict[int, User] = {}
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
        self._load_users()
        self._ensure_admin()
    
    def _init_database(self) -> None:
        """Initialize the database and create tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        is_admin BOOLEAN DEFAULT FALSE,
                        is_approved BOOLEAN DEFAULT FALSE,
                        model TEXT,
                        forced_model TEXT,
                        is_model_locked BOOLEAN DEFAULT FALSE,
                        languages TEXT,  -- JSON array
                        remaining_requests INTEGER DEFAULT 1,
                        created_at TEXT,
                        updated_at TEXT
                    )
                ''')
                
                conn.commit()
                self.logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
    
    def _load_users(self) -> None:
        """Load all users from database into memory"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable column access by name
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM users')
                rows = cursor.fetchall()
                
                users_loaded = 0
                for row in rows:
                    user_data = dict(row)
                    
                    # Parse JSON languages
                    user_data['languages'] = json.loads(user_data['languages']) if user_data['languages'] else ['ru', 'en']
                    
                    # Parse datetime strings
                    if user_data['created_at']:
                        user_data['created_at'] = datetime.fromisoformat(user_data['created_at'])
                    else:
                        user_data['created_at'] = datetime.now()
                    
                    if user_data['updated_at']:
                        user_data['updated_at'] = datetime.fromisoformat(user_data['updated_at'])
                    else:
                        user_data['updated_at'] = datetime.now()
                    
                    # Convert boolean fields
                    user_data['is_admin'] = bool(user_data['is_admin'])
                    user_data['is_approved'] = bool(user_data['is_approved'])
                    user_data['is_model_locked'] = bool(user_data['is_model_locked'])
                    
                    user = User(**user_data)
                    self.users[user.user_id] = user
                    users_loaded += 1
                
                self.logger.info(f"Loaded {users_loaded} users from database")
                
        except Exception as e:
            self.logger.error(f"Error loading users from database: {e}")
    
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
            self.save_user(user)
            self.logger.info(f"Created new user with ID {user_id}")
        return user
    
    def save_user(self, user: User) -> None:
        """Saves a user to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO users (
                        user_id, username, first_name, last_name, is_admin, is_approved,
                        model, forced_model, is_model_locked, languages, remaining_requests,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.user_id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.is_admin,
                    user.is_approved,
                    user.model,
                    user.forced_model,
                    user.is_model_locked,
                    json.dumps(user.languages),
                    user.remaining_requests,
                    user.created_at.isoformat(),
                    user.updated_at.isoformat()
                ))
                
                conn.commit()
                self.users[user.user_id] = user
                
        except Exception as e:
            self.logger.error(f"Error saving user {user.user_id}: {e}")
            raise
    
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
    
    def migrate_from_json(self, json_file: str) -> int:
        """
        Migrate users from old JSON file to database.
        Returns the number of users migrated.
        """
        if not os.path.exists(json_file):
            self.logger.info(f"JSON file {json_file} not found, skipping migration")
            return 0
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            migrated_count = 0
            for user_data in data.values():
                # Handle new fields for backwards compatibility
                if "forced_model" not in user_data:
                    user_data["forced_model"] = None
                
                if "is_model_locked" not in user_data:
                    user_data["is_model_locked"] = False
                
                # Handle datetime conversion
                if user_data.get("created_at") and isinstance(user_data["created_at"], str):
                    user_data["created_at"] = datetime.fromisoformat(user_data["created_at"])
                
                if user_data.get("updated_at") and isinstance(user_data["updated_at"], str):
                    user_data["updated_at"] = datetime.fromisoformat(user_data["updated_at"])
                
                user = User(**user_data)
                
                # Only migrate if user doesn't already exist in DB
                if not self.get_user(user.user_id):
                    self.save_user(user)
                    migrated_count += 1
            
            self.logger.info(f"Migrated {migrated_count} users from {json_file}")
            
            # Backup the old file
            backup_file = f"{json_file}.backup"
            os.rename(json_file, backup_file)
            self.logger.info(f"Backed up old JSON file to {backup_file}")
            
            return migrated_count
            
        except Exception as e:
            self.logger.error(f"Error migrating from JSON file {json_file}: {e}")
            return 0 