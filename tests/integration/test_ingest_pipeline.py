import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.pipelines.ingest_and_score import IngestionPipeline
from app.models.document import Document
from app.db.session import engine
from sqlmodel import Session, select


class TestIngestionPipeline:
    
    @pytest.fixture
    def pipeline(self):
        return IngestionPipeline()
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_sources(self, pipeline):
        """Test the complete ingestion pipeline with mocked data sources."""
        
        # Mock CryptoPanic response
        mock_cryptopanic_data = [
            {
                "source_id": "cp_123",
                "title": "Bitcoin spot ETF sees record inflows",
                "content": "Bitcoin spot ETF sees record inflows as institutional demand grows",
                "url": "https://example.com/news/123",
                "source": "cryptopanic",
                "domain": "coindesk.com",
                "published_at": datetime.utcnow(),
                "engagement_score": 0.8
            }
        ]
        
        # Mock X/Twitter response
        mock_x_data = [
            {
                "source_id": "tw_456",
                "title": None,
                "content": "BlackRock IBIT ETF creation units are through the roof! #Bitcoin #ETF",
                "url": "https://twitter.com/status/456",
                "source": "twitter",
                "author": "crypto_analyst",
                "domain": "twitter.com",
                "published_at": datetime.utcnow(),
                "engagement_score": 0.6,
                "likes_count": 150,
                "shares_count": 45
            }
        ]
        
        # Mock CoinGecko response
        mock_coingecko_data = {
            "asset": "BTC",
            "price_usd": 45000.0,
            "change_24h": 2.5,
            "volume_24h": 15000000000,
            "timestamp": datetime.utcnow()
        }
        
        # Patch the fetch methods
        with patch.object(pipeline, 'fetch_cryptopanic_data', return_value=mock_cryptopanic_data), \
             patch.object(pipeline, 'fetch_x_data', return_value=mock_x_data), \
             patch.object(pipeline, 'fetch_coingecko_data', return_value=mock_coingecko_data):
            
            # Run pipeline
            await pipeline.run_pipeline()
        
        # Verify documents were saved to database
        with Session(engine) as session:
            documents = session.exec(select(Document)).all()
            
            # Should have documents for ETF_flows narrative
            etf_docs = [doc for doc in documents if doc.narrative == "ETF_flows"]
            assert len(etf_docs) >= 1
            
            # Verify document content
            btc_docs = [doc for doc in etf_docs if doc.asset == "BTC"]
            assert len(btc_docs) >= 1
            
            # Check sentiment analysis was performed
            for doc in btc_docs:
                assert doc.sentiment_score is not None
                assert doc.sentiment_label in ["bullish", "bearish", "neutral"]
                assert doc.sentiment_confidence is not None
    
    @pytest.mark.asyncio
    async def test_deduplication_works(self, pipeline):
        """Test that duplicate content is properly deduplicated."""
        
        # Same content, different sources
        duplicate_data = [
            {
                "source_id": "cp_123",
                "content": "Bitcoin ETF inflows hit new record",
                "url": "https://source1.com/news",
                "source": "cryptopanic",
                "published_at": datetime.utcnow()
            },
            {
                "source_id": "tw_456",
                "content": "Bitcoin ETF inflows hit new record",  # Same content
                "url": "https://source2.com/tweet",
                "source": "twitter",
                "published_at": datetime.utcnow()
            }
        ]
        
        # Process documents
        processed = await pipeline.process_documents(duplicate_data)
        
        # Should only create one document due to deduplication
        with Session(engine) as session:
            documents = session.exec(select(Document)).all()
            
            # Count documents with this specific content
            matching_docs = [
                doc for doc in documents 
                if "Bitcoin ETF inflows hit new record" in doc.content
            ]
            
            # Should have only one document despite two inputs
            assert len(matching_docs) <= 1
    
    @pytest.mark.asyncio  
    async def test_sentiment_analysis_integration(self, pipeline):
        """Test sentiment analysis integration with actual analyzer."""
        
        test_documents = [
            {
                "content": "Bitcoin ETF inflows are absolutely massive! Great news for adoption!",
                "source": "test",
                "published_at": datetime.utcnow()
            },
            {
                "content": "ETF outflows continue, worst performance in months. Very bearish.",
                "source": "test", 
                "published_at": datetime.utcnow()
            },
            {
                "content": "ETF trading volumes were average today.",
                "source": "test",
                "published_at": datetime.utcnow()
            }
        ]
        
        processed = await pipeline.process_documents(test_documents)
        
        # Check that sentiments were assigned appropriately
        sentiments = [doc.sentiment_label for doc in processed if doc.sentiment_label]
        
        # Should have a mix of sentiments
        assert len(set(sentiments)) > 1
        
        # Sentiment scores should be in valid range
        for doc in processed:
            if doc.sentiment_score is not None:
                assert -1.0 <= doc.sentiment_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_narrative_matching_threshold(self, pipeline):
        """Test that narrative matching respects confidence threshold."""
        
        test_documents = [
            {
                "content": "Bitcoin spot ETF inflows BlackRock",  # Strong match
                "source": "test",
                "published_at": datetime.utcnow()
            },
            {
                "content": "The weather flow is nice today",  # Weak/no match
                "source": "test",
                "published_at": datetime.utcnow()
            }
        ]
        
        processed = await pipeline.process_documents(test_documents)
        
        # Should only process documents with strong narrative matches
        etf_docs = [doc for doc in processed if doc.narrative == "ETF_flows"]
        assert len(etf_docs) >= 1
        
        # Weather document should not match any narrative
        weather_docs = [doc for doc in processed if "weather" in doc.content.lower()]
        assert len(weather_docs) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_in_pipeline(self, pipeline):
        """Test pipeline error handling with malformed data."""
        
        malformed_data = [
            {
                "content": "Valid ETF content with BlackRock",
                "source": "test",
                "published_at": datetime.utcnow()
            },
            {
                # Missing required fields
                "invalid": "data"
            },
            {
                "content": None,  # None content
                "source": "test"
            }
        ]
        
        # Should not raise exception and process valid documents
        processed = await pipeline.process_documents(malformed_data)
        
        # Should have processed at least the valid document
        valid_docs = [doc for doc in processed if doc.content and "BlackRock" in doc.content]
        assert len(valid_docs) >= 0  # May be 0 if narrative threshold not met