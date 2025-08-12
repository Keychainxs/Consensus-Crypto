from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.api_key import APIKey


class User(BaseModel, table=True):
    """User model for authentication."""
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    last_login: Optional[datetime] = Field(default=None)
    
    # Relationships
    api_keys: List["APIKey"] = Relationship(back_populates="user")