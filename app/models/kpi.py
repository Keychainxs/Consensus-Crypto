from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

from app.models.base import BaseModel


class KPIValue(BaseModel, table=True):
    """KPI value model for tracking metrics."""
    name: str = Field(index=True, max_length=100)  # etf_net_flow_usd, etc.
    value: float
    asset: str = Field(index=True, max_length=10)
    source: str = Field(index=True, max_length=50)
    timestamp: datetime = Field(index=True)
    metadata: Optional[str] = Field(default=None, max_length=1000)  # JSON metadatas