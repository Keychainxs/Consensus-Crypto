import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CryptoPanicClient:
    """Client for CryptoPanic news API."""
    
    def __init__(self):
        settings = get_settings()
        self.api_token = settings.CRYPTOPANIC_TOKEN
        self.base_url = "https://cryptopanic.com/api/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def fetch_news(
        self, 
        currencies: List[str] = ["BTC"],
        filter_type: str = "hot",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch news from CryptoPanic API.
        
        Args:
            currencies: List of currency symbols
            filter_type: Type of filter (hot, trending, latest)
            limit: Number of articles to fetch
            
        Returns:
            List of normalized news articles
        """
        if not self.api_token:
            logger.warning("CryptoPanic API token not configured")
            return []
        
        try:
            params = {
                "auth_token": self.api_token,
                "kind": "news",
                "currencies": ",".join(currencies),
                "filter": filter_type,
                "limit": limit
            }
            
            response = await self.client.get(f"{self.base_url}/posts/", params=params)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get("results", [])
            
            normalized_articles = []
            for article in articles:
                normalized = self._normalize_article(article)
                if normalized:
                    normalized_articles.append(normalized)
            
            logger.info(f"Fetched {len(normalized_articles)} articles from CryptoPanic")
            return normalized_articles
            
        except Exception as e:
            logger.error(f"CryptoPanic API error: {e}")
            return []
    
    def _normalize_article(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize CryptoPanic article to internal format."""
        try:
            return {
                "source_id": str(article["id"]),
                "title": article.get("title", ""),
                "content": article.get("title", ""),  # CryptoPanic doesn't provide full content
                "url": article.get("url"),
                "source": "cryptopanic",
                "author": article.get("source", {}).get("domain"),
                "domain": article.get("source", {}).get("domain"),
                "published_at": datetime.fromisoformat(
                    article["published_at"].replace("Z", "+00:00")
                ),
                "engagement_score": self._calculate_engagement_score(article)
            }
        except Exception as e:
            logger.error(f"Error normalizing CryptoPanic article: {e}")
            return None
    
    def _calculate_engagement_score(self, article: Dict[str, Any]) -> float:
        """Calculate engagement score based on votes."""
        votes = article.get("votes", {})
        positive = votes.get("positive", 0)
        negative = votes.get("negative", 0)
        important = votes.get("important", 0)
        
        # Simple engagement calculation
        total_votes = positive + negative + important
        if total_votes == 0:
            return 0.0
        
        # Weight positive and important votes higher
        weighted_score = (positive * 1.0 + important * 1.5 - negative * 0.5) / total_votes
        return max(0.0, min(1.0, weighted_score))
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()