from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Column, Text

from app.models.base import BaseModel


class Document(BaseModel, table=True):
    """Document model for storing ingested content."""
    
    # Content
    title: Optional[str] = Field(default=None, max_length=500)
    content: str = Field(sa_column=Column(Text))
    url: Optional[str] = Field(default=None, max_length=1000)
    content_hash: str = Field(unique=True, index=True, max_length=64)  # For deduplication
    
    # Source metadata
    source: str = Field(index=True, max_length=50)  # cryptopanic, twitter, coingecko
    source_id: Optional[str] = Field(default=None, max_length=100)  # External ID
    author: Optional[str] = Field(default=None, index=True, max_length=255)
    domain: Optional[str] = Field(default=None, index=True, max_length=255)
    
    # Classification
    asset: str = Field(index=True, max_length=10)  # BTC, ETH, etc.
    narrative: str = Field(index=True, max_length=50)  # ETF_flows, etc.
    
    # Sentiment analysis
    sentiment_score: Optional[float] = Field(default=None)  # -1 to 1
    sentiment_label: Optional[str] = Field(default=None, max_length=20)  # bullish, bearish, neutral
    sentiment_confidence: Optional[float] = Field(default=None)
    
    # Engagement metrics
    engagement_score: Optional[float] = Field(default=0.0)
    likes_count: Optional[int] = Field(default=0)
    shares_count: Optional[int] = Field(default=0)
    comments_count: Optional[int] = Field(default=0)
    
    published_at: Optional[datetime] = Field(default=None, index=True)