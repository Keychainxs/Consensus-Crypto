from datetime import datetime
from typing import Optional, List
import json

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select

from app.db.session import get_session
from app.core.security import verify_token, verify_api_key
from app.core.rate_limit import RateLimiter
from app.models.user import User
from app.models.api_key import APIKey

security = HTTPBearer(auto_error=False)
rate_limiter = RateLimiter()


async def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session)
) -> Optional[User]:
    """Get current user from JWT token."""
    if not credentials:
        return None
    
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("sub")
        if not email:
            return None
        
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or not user.is_active:
            return None
        
        return user
    except Exception:
        return None


async def get_current_user_from_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session)
) -> Optional[User]:
    """Get current user from API key."""
    if not credentials:
        return None
    
    try:
        # API keys should start with 'cns_'
        if not credentials.credentials.startswith('cns_'):
            return None
        
        # Find API key in database
        api_keys = session.exec(select(APIKey).where(APIKey.is_active == True)).all()
        
        for api_key_record in api_keys:
            if verify_api_key(credentials.credentials, api_key_record.hashed_key):
                # Update usage tracking
                api_key_record.usage_count += 1
                api_key_record.last_used = datetime.utcnow()
                session.add(api_key_record)
                session.commit()
                
                # Get associated user
                user = session.get(User, api_key_record.user_id)
                if user and user.is_active:
                    return user
        
        return None
    except Exception:
        return None


async def get_current_user(
    user_from_token: Optional[User] = Depends(get_current_user_from_token),
    user_from_api_key: Optional[User] = Depends(get_current_user_from_api_key)
) -> User:
    """Get current user from either JWT token or API key."""
    user = user_from_token or user_from_api_key
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def check_rate_limits(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user)
) -> bool:
    """Check rate limits for authenticated requests."""
    # Global IP rate limit
    await rate_limiter.check_ip_rate_limit(request)
    
    # TODO: Add per-user/per-API-key rate limits in future iterations
    return True