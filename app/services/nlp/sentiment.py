import hashlib
import logging
import sqlite3
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Financial sentiment analyzer with caching."""
    
    def __init__(self, model_name: str = "ProsusAI/finbert", use_cache: bool = True):
        self.model_name = model_name
        self.use_cache = use_cache
        self.cache_db = "sentiment_cache.db" if use_cache else None
        self._pipeline = None
        
        if self.use_cache:
            self._init_cache()
    
    def _init_cache(self) -> None:
        """Initialize SQLite cache for sentiment results."""
        if not self.cache_db:
            return
            
        conn = sqlite3.connect(self.cache_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_cache (
                content_hash TEXT PRIMARY KEY,
                sentiment_label TEXT,
                confidence REAL,
                raw_label TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def _get_pipeline(self):
        """Lazy load the sentiment analysis pipeline."""
        if self._pipeline is None:
            try:
                from transformers import pipeline
                import torch
                
                device = 0 if torch.cuda.is_available() else -1
                self._pipeline = pipeline(
                    "text-classification",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    device=device
                )
                logger.info(f"Loaded sentiment model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to load sentiment model: {e}, using mock")
                self._pipeline = self._create_mock_pipeline()
        
        return self._pipeline
    
    def _create_mock_pipeline(self):
        """Create a mock pipeline for testing when model isn't available."""
        def mock_analyze(text: str):
            # Simple keyword-based sentiment for testing
            text_lower = text.lower()
            bullish_words = ["bullish", "pump", "moon", "up", "gain", "profit", "buy", "inflow", "record", "massive"]
            bearish_words = ["bearish", "dump", "crash", "down", "loss", "sell", "fear", "outflow", "decline"]
            
            bullish_count = sum(1 for word in bullish_words if word in text_lower)
            bearish_count = sum(1 for word in bearish_words if word in text_lower)
            
            if bullish_count > bearish_count:
                return [{"label": "POSITIVE", "score": 0.8}]
            elif bearish_count > bullish_count:
                return [{"label": "NEGATIVE", "score": 0.8}]
            else:
                return [{"label": "NEUTRAL", "score": 0.6}]
        
        return mock_analyze
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached sentiment result."""
        if not self.use_cache or not self.cache_db:
            return None
        
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.execute(
                "SELECT sentiment_label, confidence, raw_label FROM sentiment_cache WHERE content_hash = ?",
                (cache_key,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "sentiment": result[0],
                    "confidence": result[1],
                    "raw_label": result[2]
                }
        except Exception as e:
            logger.error(f"Cache read error: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache sentiment result."""
        if not self.use_cache or not self.cache_db:
            return
        
        try:
            conn = sqlite3.connect(self.cache_db)
            conn.execute(
                "INSERT OR REPLACE INTO sentiment_cache (content_hash, sentiment_label, confidence, raw_label) VALUES (?, ?, ?, ?)",
                (cache_key, result["sentiment"], result["confidence"], result["raw_label"])
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Cache write error: {e}")
    
    def _analyze_with_model(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment using the loaded model."""
        pipeline_func = self._get_pipeline()
        
        # Truncate text to avoid token limits
        max_length = 512
        if len(text) > max_length:
            text = text[:max_length]
        
        try:
            result = pipeline_func(text)[0]
            return result
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {"label": "NEUTRAL", "score": 0.5}
    
    def _map_sentiment_label(self, raw_label: str, confidence: float) -> str:
        """Map model output to standardized sentiment labels."""
        label_map = {
            "POSITIVE": "bullish",
            "NEGATIVE": "bearish", 
            "NEUTRAL": "neutral",
            "LABEL_0": "bearish",  # Some models use numeric labels
            "LABEL_1": "neutral",
            "LABEL_2": "bullish"
        }
        
        return label_map.get(raw_label.upper(), "neutral")
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        
        Returns:
            Dict with sentiment, confidence, and raw_label
        """
        cache_key = self._get_cache_key(text)
        
        # Check cache first
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        
        # Analyze with model
        raw_result = self._analyze_with_model(text)
        
        # Map to standardized format
        result = {
            "sentiment": self._map_sentiment_label(raw_result["label"], raw_result["score"]),
            "confidence": raw_result["score"],
            "raw_label": raw_result["label"]
        }
        
        # Cache result
        self._cache_result(cache_key, result)
        
        return result