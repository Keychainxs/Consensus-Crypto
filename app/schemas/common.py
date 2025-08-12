from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standard success response."""
    message: str
    data: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: List[Dict[str, Any]]
    total: int
    page: int
    size: int
    has_next: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime