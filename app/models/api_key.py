from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class APIKey(BaseModel, table=True):
    """API key model for machine authentication."""
    name: str = Field(max_length=255)
    hashed_key: str = Field(unique=True, index=True, max_length=255)
    user_id: int = Field(foreign_key="user.id")
    scopes: str = Field(default="read:narratives", max_length=500)  # JSON string of scopes
    is_active: bool = Field(default=True)
    last_used: Optional[datetime] = Field(default=None)
    usage_count: int = Field(default=0)
    rate_limit_per_hour: int = Field(default=1000)
    
    # Relationships
    user: Optional["User"] = Relationship(back_populates="api_keys")