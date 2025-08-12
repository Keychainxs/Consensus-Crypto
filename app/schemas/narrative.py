from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NarrativeStrengthResponse(BaseModel):
    """Narrative strength response."""
    narrative: str
    asset: str
    period: str
    mentions_count: int
    unique_authors: int
    sentiment_mean: float
    strength: float
    strength_z_score: float
    updated_at: datetime


class LeaderboardItem(BaseModel):
    """Leaderboard item."""
    narrative: str
    asset: str
    mentions: int
    unique_authors: int
    sentiment_mean: float
    strength: float
    updated_at: datetime


class LeaderboardResponse(BaseModel):
    """Leaderboard response."""
    items: List[LeaderboardItem]
    window: str
    updated_at: datetime


class DriverDocument(BaseModel):
    """Driver document."""
    title: Optional[str]
    content_snippet: str
    source: str
    url: Optional[str]
    author: Optional[str]
    sentiment_score: float
    sentiment_label: str
    engagement_score: float
    published_at: datetime


class DriversResponse(BaseModel):
    """Drivers response."""
    narrative: str
    asset: str
    period: str
    drivers: List[DriverDocument]
    total_documents: int


class AlertResponse(BaseModel):
    """Alert response."""
    id: int
    narrative: str
    asset: str
    alert_type: str
    strength: float
    confidence: float
    message: str
    created_at: datetime


class NarrativeQuery(BaseModel):
    """Narrative query parameters."""
    asset: str = Field(pattern=r"^[A-Z]{2,5}$")
    narrative: str = Field(min_length=1, max_length=50)
    period: str = Field(pattern=r"^(1h|6h|24h|7d)$", default="24h")


class LeaderboardQuery(BaseModel):
    """Leaderboard query parameters."""
    window: str = Field(pattern=r"^(1h|6h|24h|7d)$", default="24h")


class DriversQuery(BaseModel):
    """Drivers query parameters."""
    asset: str = Field(pattern=r"^[A-Z]{2,5}$")
    narrative: str = Field(min_length=1, max_length=50)
    period: str = Field(pattern=r"^(1h|6h|24h|7d)$", default="24h")
    limit: int = Field(default=5, ge=1, le=20)