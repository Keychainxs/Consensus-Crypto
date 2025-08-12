"""Main ingestion and scoring pipeline."""
import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.models.document import Document
from app.services.ingest.cryptopanic_client import CryptoPanicClient
from app.services.ingest.coingecko_client import CoinGeckoClient
from app.services.ingest.x_client import get_x_client
from app.services.nlp.sentiment import SentimentAnalyzer
from app.services.nlp.matching import NarrativeMatcher, load_narratives

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Main ingestion and scoring pipeline."""
    
    def __init__(self):
        self.settings = get_settings()
        self.cryptopanic = CryptoPanicClient()
        self.x_client = get_x_client()
        self.coingecko = CoinGeckoClient()
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Load narrative configuration
        narratives_config = load_narratives()
        self.narrative_matcher = NarrativeMatcher(narratives_config)
        
        self.processed_hashes = set()  # For deduplication
    
    def _generate_content_hash(self, content: str, url: str = None) -> str:
        """Generate hash for content deduplication."""
        hash_input = content
        if url:
            hash_input += url
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    async def fetch_cryptopanic_data(self) -> List[Dict[str, Any]]:
        """Fetch news from CryptoPanic."""
        try:
            articles = await self.cryptopanic.fetch_news(
                currencies=["BTC"],
                filter_type="hot",
                limit=50
            )
            logger.info(f"Fetched {len(articles)} articles from CryptoPanic")
            return articles
        except Exception as e:
            logger.error(f"Error fetching CryptoPanic data: {e}")
            return []
    
    async def fetch_x_data(self) -> List[Dict[str, Any]]:
        """Fetch tweets from X API."""
        try:
            # Search for ETF-related Bitcoin tweets
            query = "bitcoin ETF OR BTC ETF OR spot ETF bitcoin -is:retweet lang:en"
            tweets = await self.x_client.search_tweets(
                query=query,
                max_results=50
            )
            logger.info(f"Fetched {len(tweets)} tweets from X")
            return tweets
        except Exception as e:
            logger.error(f"Error fetching X data: {e}")
            return []
    
    async def fetch_coingecko_data(self) -> Dict[str, Any]:
        """Fetch price data from CoinGecko."""
        try:
            price_data = await self.coingecko.get_price_data("bitcoin")
            if price_data:
                logger.info(f"Fetched BTC price: ${price_data['price_usd']}")
            return price_data or {}
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data: {e}")
            return {}
    
    def normalize_document(self, raw_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw document to internal format."""
        content = raw_doc.get("content", "") or raw_doc.get("title", "")
        
        return {
            "title": raw_doc.get("title"),
            "content": content,
            "url": raw_doc.get("url"),
            "content_hash": self._generate_content_hash(content, raw_doc.get("url")),
            "source": raw_doc.get("source"),
            "source_id": raw_doc.get("source_id"),
            "author": raw_doc.get("author"),
            "domain": raw_doc.get("domain"),
            "engagement_score": raw_doc.get("engagement_score", 0.0),
            "likes_count": raw_doc.get("likes_count", 0),
            "shares_count": raw_doc.get("shares_count", 0),
            "comments_count": raw_doc.get("comments_count", 0),
            "published_at": raw_doc.get("published_at") or datetime.utcnow()
        }
    
    def match_narratives(self, content: str, asset: str = "BTC") -> List[str]:
        """Match content to narratives."""
        matches = self.narrative_matcher.match_narratives(content, asset)
        
        # Return narratives with score > threshold
        matched_narratives = []
        for narrative, match_data in matches.items():
            if match_data["score"] > 0.3:  # Minimum confidence threshold
                matched_narratives.append(narrative)
        
        return matched_narratives
    
    async def process_documents(self, raw_documents: List[Dict[str, Any]]) -> List[Document]:
        """Process and score documents."""
        processed_docs = []
        
        with Session(engine) as session:
            for raw_doc in raw_documents:
                try:
                    # Normalize document
                    normalized = self.normalize_document(raw_doc)
                    
                    # Skip if already processed (deduplication)
                    if normalized["content_hash"] in self.processed_hashes:
                        continue
                    
                    # Check if already exists in database
                    existing = session.exec(
                        select(Document).where(Document.content_hash == normalized["content_hash"])
                    ).first()
                    if existing:
                        continue
                    
                    # Match to narratives
                    narratives = self.match_narratives(normalized["content"])
                    
                    # Skip if no narrative matches
                    if not narratives:
                        continue
                    
                    # Analyze sentiment
                    sentiment_result = self.sentiment_analyzer.analyze_sentiment(normalized["content"])
                    
                    # Create documents for each matched narrative
                    for narrative in narratives:
                        doc = Document(
                            **normalized,
                            asset="BTC",  # Fixed for Week 1
                            narrative=narrative,
                            sentiment_score=self._sentiment_to_score(sentiment_result["sentiment"]),
                            sentiment_label=sentiment_result["sentiment"],
                            sentiment_confidence=sentiment_result["confidence"]
                        )
                        
                        processed_docs.append(doc)
                        session.add(doc)
                    
                    self.processed_hashes.add(normalized["content_hash"])
                    
                except Exception as e:
                    logger.error(f"Error processing document: {e}")
                    continue
            
            # Commit all documents
            session.commit()
            logger.info(f"Processed and saved {len(processed_docs)} documents")
        
        return processed_docs
    
    def _sentiment_to_score(self, sentiment_label: str) -> float:
        """Convert sentiment label to numeric score."""
        mapping = {
            "bullish": 0.8,
            "bearish": -0.8,
            "neutral": 0.0
        }
        return mapping.get(sentiment_label, 0.0)
    
    async def run_pipeline(self):
        """Run the complete ingestion and scoring pipeline."""
        logger.info("Starting ingestion pipeline...")
        
        try:
            # Fetch data from all sources
            tasks = [
                self.fetch_cryptopanic_data(),
                self.fetch_x_data(),
                self.fetch_coingecko_data()
            ]
            
            cryptopanic_data, x_data, coingecko_data = await asyncio.gather(*tasks)
            
            # Combine document sources
            all_documents = cryptopanic_data + x_data
            
            # Process documents
            if all_documents:
                processed_docs = await self.process_documents(all_documents)
                logger.info(f"Pipeline completed: {len(processed_docs)} documents processed")
            else:
                logger.warning("No documents to process")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        finally:
            # Clean up clients
            await self.cryptopanic.close()
            await self.x_client.close()
            await self.coingecko.close()


async def main():
    """Main entry point for the pipeline."""
    setup_logging()
    pipeline = IngestionPipeline()
    await pipeline.run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())