"""
User model for the YouTube Summarizer Bot.
Represents a user of the bot with their settings and access permissions.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from src.config.settings import DEFAULT_LANGUAGES, DEFAULT_USER_REQUESTS, UNLIMITED_REQUESTS

@dataclass
class User:
    """
    Represents a user of the YouTube Summarizer Bot.
    Stores user settings and access permissions.
    """
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool = False
    is_approved: bool = False
    model: Optional[str] = None
    languages: List[str] = field(default_factory=lambda: DEFAULT_LANGUAGES.copy())
    remaining_requests: int = DEFAULT_USER_REQUESTS
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def display_name(self) -> str:
        """Returns the display name of the user (first name + last name or username)"""
        if self.first_name:
            if self.last_name:
                return f"{self.first_name} {self.last_name}"
            return self.first_name
        elif self.username:
            return self.username
        return str(self.user_id)
    
    @property
    def has_unlimited_requests(self) -> bool:
        """Returns True if the user has unlimited requests"""
        return self.remaining_requests == UNLIMITED_REQUESTS or self.is_admin
    
    def has_access(self) -> bool:
        """Returns True if the user is allowed to use the bot"""
        return self.is_admin or self.is_approved and (self.has_unlimited_requests or self.remaining_requests > 0)
    
    def use_request(self) -> bool:
        """
        Decrements the remaining requests count.
        Returns True if the operation was successful, False if the user has no requests left.
        """
        if self.has_unlimited_requests:
            return True
        
        if self.remaining_requests <= 0:
            return False
        
        self.remaining_requests -= 1
        self.updated_at = datetime.now()
        return True
    
    def grant_access(self, requests: int = UNLIMITED_REQUESTS) -> None:
        """Grants access to the user with the specified number of requests"""
        self.is_approved = True
        self.remaining_requests = requests
        self.updated_at = datetime.now()
    
    def revoke_access(self) -> None:
        """Revokes access from the user"""
        self.is_approved = False
        self.remaining_requests = 0
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Converts the user to a dictionary for storage"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "is_admin": self.is_admin,
            "is_approved": self.is_approved,
            "model": self.model,
            "languages": self.languages,
            "remaining_requests": self.remaining_requests,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Creates a user from a dictionary"""
        # Handle datetime conversion
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            data["created_at"] = datetime.fromisoformat(created_at)
        
        updated_at = data.get("updated_at")
        if updated_at and isinstance(updated_at, str):
            data["updated_at"] = datetime.fromisoformat(updated_at)
        
        return cls(**data) 