from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session, select

from app.api.deps import check_rate_limits, get_current_user
from app.db.session import get_session
from app.models.document import Document
from app.models.user import User
from app.schemas.narrative import (
    DriversResponse,
    DriverDocument,
    LeaderboardItem,
    LeaderboardResponse,
    NarrativeStrengthResponse,
)
from app.services.scoring.strength import StrengthCalculator

router = APIRouter()


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    window: str = Query("24h", pattern="^(1h|6h|24h|7d)$"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    _rate_check = Depends(check_rate_limits)
):
    """Get narrative strength leaderboard."""
    
    # Parse window to hours
    window_hours = {
        "1h": 1,
        "6h": 6, 
        "24h": 24,
        "7d": 168
    }[window]
    
    # Calculate time boundary
    since_time = datetime.utcnow() - timedelta(hours=window_hours)
    
    # Get documents in time window
    documents = session.exec(
        select(Document).where(
            Document.created_at >= since_time,
            Document.narrative.is_not(None),
            Document.asset.is_not(None)
        )
    ).all()
    
    # Group by narrative + asset
    narrative_groups = {}
    for doc in documents:
        key = f"{doc.narrative}_{doc.asset}"
        if key not in narrative_groups:
            narrative_groups[key] = []
        narrative_groups[key].append(doc)
    
    # Calculate metrics for each narrative
    calculator = StrengthCalculator()
    leaderboard_items = []
    
    for key, docs in narrative_groups.items():
        narrative, asset = key.rsplit("_", 1)
        metrics = calculator.calculate_metrics(docs, window_hours)
        
        leaderboard_items.append(LeaderboardItem(
            narrative=narrative,
            asset=asset,
            mentions=metrics["mentions_count"],
            unique_authors=metrics["unique_authors"],
            sentiment_mean=metrics["sentiment_mean"],
            strength=metrics["strength"],
            updated_at=datetime.utcnow()
        ))
    
    # Sort by strength descending
    leaderboard_items.sort(key=lambda x: x.strength, reverse=True)
    
    return LeaderboardResponse(
        items=leaderboard_items,
        window=window,
        updated_at=datetime.utcnow()
    )


@router.get("/strength", response_model=NarrativeStrengthResponse)
async def get_narrative_strength(
    asset: str = Query(..., pattern="^[A-Z]{2,5}$"),
    narrative: str = Query(...),
    period: str = Query("24h", pattern="^(1h|6h|24h|7d)$"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    _rate_check = Depends(check_rate_limits)
):
    """Get strength metrics for specific narrative and asset."""
    
    # Parse period to hours
    period_hours = {
        "1h": 1,
        "6h": 6,
        "24h": 24, 
        "7d": 168
    }[period]
    
    # Get documents for this narrative + asset in time window
    since_time = datetime.utcnow() - timedelta(hours=period_hours)
    
    documents = session.exec(
        select(Document).where(
            Document.narrative == narrative,
            Document.asset == asset,
            Document.created_at >= since_time
        )
    ).all()
    
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for {narrative} narrative on {asset}"
        )
    
    # Calculate strength metrics
    calculator = StrengthCalculator()
    metrics = calculator.calculate_metrics(documents, period_hours)
    
    return NarrativeStrengthResponse(
        narrative=narrative,
        asset=asset,
        period=period,
        mentions_count=metrics["mentions_count"],
        unique_authors=metrics["unique_authors"],
        sentiment_mean=metrics["sentiment_mean"],
        strength=metrics["strength"],
        strength_z_score=metrics["strength_z_score"],
        updated_at=datetime.utcnow()
    )


@router.get("/drivers", response_model=DriversResponse)
async def get_narrative_drivers(
    asset: str = Query(..., pattern="^[A-Z]{2,5}$"),
    narrative: str = Query(...),
    period: str = Query("24h", pattern="^(1h|6h|24h|7d)$"),
    limit: int = Query(5, ge=1, le=20),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    _rate_check = Depends(check_rate_limits)
):
    """Get top driving documents for a narrative."""
    
    # Parse period to hours
    period_hours = {
        "1h": 1,
        "6h": 6,
        "24h": 24,
        "7d": 168
    }[period]
    
    # Get documents for this narrative + asset
    since_time = datetime.utcnow() - timedelta(hours=period_hours)
    
    documents = session.exec(
        select(Document).where(
            Document.narrative == narrative,
            Document.asset == asset,
            Document.created_at >= since_time
        ).order_by(Document.engagement_score.desc())
        .limit(limit)
    ).all()
    
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drivers found for {narrative} narrative on {asset}"
        )
    
    # Convert to driver format
    drivers = []
    for doc in documents:
        # Create content snippet (first 200 chars)
        content_snippet = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
        
        drivers.append(DriverDocument(
            title=doc.title,
            content_snippet=content_snippet,
            source=doc.source,
            url=doc.url,
            author=doc.author,
            sentiment_score=doc.sentiment_score or 0.0,
            sentiment_label=doc.sentiment_label or "neutral",
            engagement_score=doc.engagement_score or 0.0,
            published_at=doc.published_at or doc.created_at
        ))
    
    # Get total document count for context
    total_docs = session.exec(
        select(Document).where(
            Document.narrative == narrative,
            Document.asset == asset,
            Document.created_at >= since_time
        )
    ).all()
    
    return DriversResponse(
        narrative=narrative,
        asset=asset,
        period=period,
        drivers=drivers,
        total_documents=len(total_docs)
    )