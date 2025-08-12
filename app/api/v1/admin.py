import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import require_admin
from app.core.security import generate_api_key, hash_api_key
from app.db.session import get_session
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.auth import APIKeyCreate, APIKeyListResponse, APIKeyResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Create a new API key (admin only)."""
    
    # Generate new API key
    raw_key = generate_api_key()
    
    # Create API key record
    api_key = APIKey(
        name=key_data.name,
        hashed_key=hash_api_key(raw_key),
        user_id=current_user.id,
        scopes=json.dumps(key_data.scopes),
        rate_limit_per_hour=key_data.rate_limit_per_hour,
        is_active=True
    )
    
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    
    logger.info(f"API key created: {key_data.name} by {current_user.email}")
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,  # Only returned on creation
        scopes=key_data.scopes,
        is_active=api_key.is_active,
        usage_count=api_key.usage_count,
        last_used=api_key.last_used,
        created_at=api_key.created_at
    )


@router.get("/api-keys", response_model=List[APIKeyListResponse])
async def list_api_keys(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """List all API keys (admin only)."""
    
    api_keys = session.exec(select(APIKey)).all()
    
    return [
        APIKeyListResponse(
            id=key.id,
            name=key.name,
            scopes=json.loads(key.scopes) if key.scopes else [],
            is_active=key.is_active,
            usage_count=key.usage_count,
            last_used=key.last_used,
            created_at=key.created_at
        )
        for key in api_keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Revoke an API key (admin only)."""
    
    api_key = session.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    session.add(api_key)
    session.commit()
    
    logger.info(f"API key revoked: {api_key.name} by {current_user.email}")
    
    return {"status": "API key revoked", "key_id": key_id}


@router.get("/api-keys/{key_id}", response_model=APIKeyListResponse)
async def get_api_key(
    key_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get API key details (admin only)."""
    
    api_key = session.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return APIKeyListResponse(
        id=api_key.id,
        name=api_key.name,
        scopes=json.loads(api_key.scopes) if api_key.scopes else [],
        is_active=api_key.is_active,
        usage_count=api_key.usage_count,
        last_used=api_key.last_used,
        created_at=api_key.created_at
    )