import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class XClientInterface(ABC):
    """Abstract interface for X/Twitter clients."""
    
    @abstractmethod
    async def search_tweets(
        self, 
        query: str, 
        max_results: int = 50,
        tweet_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for tweets."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close client connections."""
        pass


class XClient(XClientInterface):
    """Real X API v2 client."""
    
    def __init__(self):
        settings = get_settings()
        self.bearer_token = settings.X_BEARER_TOKEN
        self.base_url = "https://api.twitter.com/2"
        self.client = httpx.AsyncClient(timeout=30.0) if self.bearer_token else None
    
    async def search_tweets(
        self, 
        query: str, 
        max_results: int = 50,
        tweet_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for tweets using X API v2."""
        if not self.client or not self.bearer_token:
            logger.warning("X API not configured, falling back to stub")
            return []
        
        try:
            if tweet_fields is None:
                tweet_fields = ["created_at", "author_id", "public_metrics", "context_annotations"]
            
            params = {
                "query": query,
                "max_results": max_results,
                "tweet.fields": ",".join(tweet_fields)
            }
            
            headers = {
                "Authorization": f"Bearer {self.bearer_token}"
            }
            
            response = await self.client.get(
                f"{self.base_url}/tweets/search/recent",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            tweets = data.get("data", [])
            
            normalized_tweets = []
            for tweet in tweets:
                normalized = self._normalize_tweet(tweet)
                if normalized:
                    normalized_tweets.append(normalized)
            
            logger.info(f"Fetched {len(normalized_tweets)} tweets from X API")
            return normalized_tweets
            
        except Exception as e:
            logger.error(f"X API error: {e}")
            return []
    
    def _normalize_tweet(self, tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize X API tweet to internal format."""
        try:
            metrics = tweet.get("public_metrics", {})
            
            return {
                "source_id": tweet["id"],
                "title": None,
                "content": tweet["text"],
                "url": f"https://twitter.com/i/web/status/{tweet['id']}",
                "source": "twitter",
                "author": tweet.get("author_id"),
                "domain": "twitter.com",
                "published_at": datetime.fromisoformat(
                    tweet["created_at"].replace("Z", "+00:00")
                ),
                "likes_count": metrics.get("like_count", 0),
                "shares_count": metrics.get("retweet_count", 0),
                "comments_count": metrics.get("reply_count", 0),
                "engagement_score": self._calculate_tweet_engagement(metrics)
            }
        except Exception as e:
            logger.error(f"Error normalizing tweet: {e}")
            return None
    
    def _calculate_tweet_engagement(self, metrics: Dict[str, Any]) -> float:
        """Calculate engagement score for a tweet."""
        likes = metrics.get("like_count", 0)
        retweets = metrics.get("retweet_count", 0)
        replies = metrics.get("reply_count", 0)
        
        # Weight different engagement types
        engagement = (likes * 1.0 + retweets * 2.0 + replies * 1.5)
        
        # Normalize to 0-1 scale (logarithmic for high engagement tweets)
        if engagement == 0:
            return 0.0
        
        import math
        normalized = math.log10(engagement + 1) / 4.0  # Assumes max ~10k engagement = 1.0
        return min(1.0, normalized)
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()


class StubXClient(XClientInterface):
    """Stub implementation for testing without X API access."""
    
    async def search_tweets(
        self, 
        query: str, 
        max_results: int = 50,
        tweet_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Return stub data from fixtures."""
        try:
            stub_file = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "x_sample.json"
            with open(stub_file, 'r') as f:
                stub_tweets = json.load(f)
            
            normalized_tweets = []
            for tweet in stub_tweets[:max_results]:
                normalized = self._normalize_stub_tweet(tweet)
                if normalized:
                    normalized_tweets.append(normalized)
            
            logger.info(f"Using stub data: {len(normalized_tweets)} tweets")
            return normalized_tweets
            
        except Exception as e:
            logger.error(f"Error loading stub data: {e}")
            return []
    
    def _normalize_stub_tweet(self, tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize stub tweet data to internal format."""
        try:
            metrics = tweet.get("public_metrics", {})
            
            return {
                "source_id": tweet["id"],
                "title": None,
                "content": tweet["text"],
                "url": f"https://twitter.com/i/web/status/{tweet['id']}",
                "source": "twitter",
                "author": tweet.get("author_id"),
                "domain": "twitter.com",
                "published_at": datetime.fromisoformat(
                    tweet["created_at"].replace("Z", "+00:00")
                ),
                "likes_count": metrics.get("like_count", 0),
                "shares_count": metrics.get("retweet_count", 0),
                "comments_count": metrics.get("reply_count", 0),
                "engagement_score": self._calculate_tweet_engagement(metrics)
            }
        except Exception as e:
            logger.error(f"Error normalizing stub tweet: {e}")
            return None
    
    def _calculate_tweet_engagement(self, metrics: Dict[str, Any]) -> float:
        """Calculate engagement score for a tweet."""
        likes = metrics.get("like_count", 0)
        retweets = metrics.get("retweet_count", 0)
        replies = metrics.get("reply_count", 0)
        
        engagement = (likes * 1.0 + retweets * 2.0 + replies * 1.5)
        
        if engagement == 0:
            return 0.0
        
        import math
        normalized = math.log10(engagement + 1) / 4.0
        return min(1.0, normalized)
    
    async def close(self) -> None:
        """No-op for stub client."""
        pass


def get_x_client() -> XClientInterface:
    """Factory function to get appropriate X client."""
    settings = get_settings()
    if settings.X_BEARER_TOKEN:
        return XClient()
    else:
        logger.info("No X Bearer token configured, using stub client")
        return StubXClient()