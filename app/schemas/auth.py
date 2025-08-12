from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str = Field(min_length=6, max_length=255)
    captcha_token: str = Field(min_length=1, max_length=1000)


class UserRegister(BaseModel):
    """User registration request (admin only)."""
    email: EmailStr
    password: str = Field(min_length=6, max_length=255)
    is_admin: bool = False


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User response."""
    id: int
    email: str
    is_active: bool
    is_admin: bool
    last_login: Optional[datetime]
    created_at: datetime


class APIKeyCreate(BaseModel):
    """API key creation request."""
    name: str = Field(min_length=1, max_length=255)
    scopes: List[str] = Field(default=["read:narratives"])
    rate_limit_per_hour: int = Field(default=1000, ge=1, le=10000)


class APIKeyResponse(BaseModel):
    """API key response."""
    id: int
    name: str
    key: Optional[str] = None  # Only returned on creation
    scopes: List[str]
    is_active: bool
    usage_count: int
    last_used: Optional[datetime]
    created_at: datetime


class APIKeyListResponse(BaseModel):
    """API key list response."""
    id: int
    name: str
    scopes: List[str]
    is_active: bool
    usage_count: int
    last_used: Optional[datetime]
    created_at: datetime