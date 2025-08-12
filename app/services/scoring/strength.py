import statistics
from datetime import datetime, timedelta
from typing import Dict, List

from app.models.document import Document
from app.core.logging import get_logger

logger = get_logger(__name__)


class StrengthCalculator:
    """Calculator for narrative strength metrics."""
    
    def __init__(self):
        self.window_lookback_days = 7  # For z-score calculation
    
    def calculate_metrics(self, documents: List[Document], window_hours: int = 24) -> Dict[str, float]:
        """
        Calculate narrative strength metrics for a set of documents.
        
        Args:
            documents: List of documents in the time window
            window_hours: Time window in hours
            
        Returns:
            Dict with calculated metrics
        """
        if not documents:
            return {
                "mentions_count": 0,
                "unique_authors": 0,
                "sentiment_mean": 0.0,
                "strength": 0.0,
                "strength_z_score": 0.0
            }
        
        # Basic metrics
        mentions_count = len(documents)
        unique_authors = len(set(doc.author for doc in documents if doc.author))
        
        # Sentiment metrics
        sentiment_scores = [doc.sentiment_score for doc in documents if doc.sentiment_score is not None]
        sentiment_mean = statistics.mean(sentiment_scores) if sentiment_scores else 0.0
        
        # Calculate composite strength
        strength = self._calculate_simple_strength(mentions_count, unique_authors, sentiment_mean)
        
        return {
            "mentions_count": mentions_count,
            "unique_authors": unique_authors,
            "sentiment_mean": sentiment_mean,
            "strength": strength,
            "strength_z_score": 0.0  # TODO: Implement with historical data
        }
    
    def _calculate_simple_strength(self, mentions: int, authors: int, sentiment: float) -> float:
        """
        Calculate simple strength score.
        
        Formula: weighted combination of normalized metrics
        """
        # Normalize metrics (simple linear scaling for Week 1)
        mentions_norm = min(mentions / 10.0, 1.0)  # Cap at 10 mentions = 1.0
        authors_norm = min(authors / 5.0, 1.0)     # Cap at 5 authors = 1.0
        sentiment_norm = max((sentiment + 1) / 2.0, 0.0)  # Convert -1,1 to 0,1
        
        # Weighted combination
        strength = (
            mentions_norm * 0.4 +    # 40% weight on volume
            authors_norm * 0.3 +     # 30% weight on diversity
            sentiment_norm * 0.3     # 30% weight on sentiment
        )
        
        return min(strength, 1.0)
    
    def calculate_strength_with_history(
        self, 
        current_docs: List[Document],
        historical_docs: List[Document],
        narrative: str,
        asset: str
    ) -> Dict[str, float]:
        """
        Calculate strength with z-score normalization against historical data.
        """
        current_metrics = self.calculate_metrics(current_docs)
        
        if not historical_docs:
            return current_metrics
        
        # Calculate historical baseline metrics by day
        historical_by_day = self._group_docs_by_day(historical_docs)
        
        historical_mentions = [len(docs) for docs in historical_by_day]
        historical_authors = [len(set(doc.author for doc in docs if doc.author)) for docs in historical_by_day]
        historical_sentiment = []
        
        for docs in historical_by_day:
            sentiments = [doc.sentiment_score for doc in docs if doc.sentiment_score is not None]
            if sentiments:
                historical_sentiment.append(statistics.mean(sentiments))
            else:
                historical_sentiment.append(0.0)
        
        # Calculate z-scores
        mentions_z = self._calculate_z_score(current_metrics["mentions_count"], historical_mentions)
        authors_z = self._calculate_z_score(current_metrics["unique_authors"], historical_authors)
        sentiment_z = self._calculate_z_score(current_metrics["sentiment_mean"], historical_sentiment)
        
        # Composite z-score strength
        strength_z = (mentions_z + authors_z + sentiment_z) / 3.0
        
        current_metrics.update({
            "strength_z_score": strength_z,
            "mentions_z": mentions_z,
            "authors_z": authors_z,
            "sentiment_z": sentiment_z
        })
        
        return current_metrics
    
    def _group_docs_by_day(self, documents: List[Document]) -> List[List[Document]]:
        """Group documents by day for historical analysis."""
        by_day = {}
        
        for doc in documents:
            day_key = doc.created_at.date()
            if day_key not in by_day:
                by_day[day_key] = []
            by_day[day_key].append(doc)
        
        return list(by_day.values())
    
    def _calculate_z_score(self, current_value: float, historical_values: List[float]) -> float:
        """Calculate z-score for current value against historical values."""
        if len(historical_values) < 2:
            return 0.0
        
        mean_val = statistics.mean(historical_values)
        
        try:
            std_val = statistics.stdev(historical_values)
            if std_val == 0:
                return 0.0
            return (current_value - mean_val) / std_val
        except statistics.StatisticsError:
            return 0.0