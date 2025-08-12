import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter()
rate_limiter = RateLimiter()
logger = logging.getLogger(__name__)


async def verify_captcha(captcha_token: str) -> bool:
    """Verify captcha token with Turnstile/hCaptcha."""
    settings = get_settings()
    
    if not settings.CAPTCHA_SECRET:
        # Skip captcha in development
        return captcha_token == "TEST_OK"
    
    try:
        if settings.CAPTCHA_PROVIDER == "turnstile":
            url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        else:  # hcaptcha
            url = "https://hcaptcha.com/siteverify"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data={
                "secret": settings.CAPTCHA_SECRET,
                "response": captcha_token
            })
            result = response.json()
            return result.get("success", False)
    except Exception as e:
        logger.error(f"Captcha verification error: {e}")
        return False


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    response: Response,
    request: Request,
    session: Session = Depends(get_session)
):
    """User login with captcha verification."""
    # Rate limiting for auth endpoints
    await rate_limiter.check_auth_rate_limit(request)
    
    # Verify captcha
    if not await verify_captcha(user_data.captcha_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid captcha"
        )
    
    # Find user
    user = session.exec(select(User).where(User.email == user_data.email)).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for {user_data.email} from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )
    
    # Create tokens
    token_data = {"sub": user.email, "scopes": ["read:narratives"]}
    if user.is_admin:
        token_data["scopes"].append("admin:all")
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user.email})
    
    # Set httpOnly cookies
    settings = get_settings()
    is_secure = settings.ENV != "dev"
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="none" if is_secure else "lax",
        max_age=15 * 60  # 15 minutes
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="none" if is_secure else "lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Update last login
    user.last_login = datetime.utcnow()
    session.add(user)
    session.commit()
    
    logger.info(f"User {user.email} logged in from {request.client.host}")
    
    return TokenResponse(
        access_token=access_token,
        expires_in=15 * 60
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response
):
    """Refresh access token using refresh token from cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )
    
    try:
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Create new access token
        token_data = {"sub": email, "scopes": ["read:narratives"]}
        access_token = create_access_token(token_data)
        
        # Set new access token cookie
        settings = get_settings()
        is_secure = settings.ENV != "dev"
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=is_secure,
            samesite="none" if is_secure else "lax",
            max_age=15 * 60
        )
        
        return {"status": "token_refreshed"}
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"status": "logged_out"}


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    request: Request,
    session: Session = Depends(get_session)
):
    """Register new user (admin only in Week 1)."""
    # Rate limiting for auth endpoints
    await rate_limiter.check_auth_rate_limit(request)
    
    # Check if user already exists
    existing_user = session.exec(select(User).where(User.email == user_data.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        is_admin=user_data.is_admin,
        is_active=True
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    logger.info(f"New user registered: {user.email}")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        last_login=user.last_login,
        created_at=user.created_at
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    request: Request,
    session: Session = Depends(get_session)
):
    """Get current user information from cookie or Authorization header."""
    from app.api.deps import get_current_user
    
    # Try to get user from cookie first
    access_token = request.cookies.get("access_token")
    user = None
    
    if access_token:
        try:
            payload = verify_token(access_token)
            email = payload.get("sub")
            if email:
                user = session.exec(select(User).where(User.email == email)).first()
        except Exception:
            pass
    
    # Fall back to Authorization header
    if not user:
        user = await get_current_user(request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        last_login=user.last_login,
        created_at=user.created_at
    )