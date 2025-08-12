import pytest
from datetime import datetime, timedelta

from app.services.scoring.strength import StrengthCalculator
from app.models.document import Document


class TestStrengthCalculator:
    
    @pytest.fixture
    def calculator(self):
        return StrengthCalculator()
    
    def test_strength_calculation_basic(self, calculator):
        """Test basic strength calculation with mock data."""
        now = datetime.utcnow()
        documents = [
            Document(
                id=1,
                content="Bitcoin ETF inflows hit record high",
                content_hash="hash1",
                sentiment_score=0.8,
                author="analyst1",
                source="cryptopanic",
                asset="BTC",
                narrative="ETF_flows",
                created_at=now - timedelta(hours=1)
            ),
            Document(
                id=2,
                content="BlackRock sees massive ETF demand",
                content_hash="hash2",
                sentiment_score=0.9,
                author="analyst2", 
                source="twitter",
                asset="BTC",
                narrative="ETF_flows",
                created_at=now - timedelta(hours=2)
            ),
            Document(
                id=3,
                content="IBIT creation units spike",
                content_hash="hash3",
                sentiment_score=0.7,
                author="analyst1",  # Same author as first
                source="news",
                asset="BTC", 
                narrative="ETF_flows",
                created_at=now - timedelta(hours=3)
            )
        ]
        
        metrics = calculator.calculate_metrics(documents, window_hours=24)
        
        assert metrics["mentions_count"] == 3
        assert metrics["unique_authors"] == 2  # analyst1, analyst2
        assert abs(metrics["sentiment_mean"] - 0.8) < 0.1  # (0.8+0.9+0.7)/3
        assert metrics["strength"] > 0  # Should be positive for good metrics
    
    def test_empty_documents_handling(self, calculator):
        """Test handling of empty document list."""
        metrics = calculator.calculate_metrics([], window_hours=24)
        
        assert metrics["mentions_count"] == 0
        assert metrics["unique_authors"] == 0
        assert metrics["sentiment_mean"] == 0.0
        assert metrics["strength"] == 0.0
    
    def test_documents_without_sentiment(self, calculator):
        """Test handling of documents without sentiment scores."""
        documents = [
            Document(
                id=1,
                content="Test content",
                content_hash="hash1",
                sentiment_score=None,  # No sentiment
                author="author1",
                source="test",
                asset="BTC",
                narrative="ETF_flows",
                created_at=datetime.utcnow()
            )
        ]
        
        metrics = calculator.calculate_metrics(documents)
        
        assert metrics["mentions_count"] == 1
        assert metrics["unique_authors"] == 1
        assert metrics["sentiment_mean"] == 0.0  # No valid sentiment scores
    
    def test_documents_without_authors(self, calculator):
        """Test handling of documents without authors."""
        documents = [
            Document(
                id=1,
                content="Test content 1",
                content_hash="hash1",
                sentiment_score=0.5,
                author=None,  # No author
                source="test",
                asset="BTC",
                narrative="ETF_flows",
                created_at=datetime.utcnow()
            ),
            Document(
                id=2,
                content="Test content 2",
                content_hash="hash2",
                sentiment_score=0.6,
                author="",  # Empty author
                source="test",
                asset="BTC",
                narrative="ETF_flows",
                created_at=datetime.utcnow()
            )
        ]
        
        metrics = calculator.calculate_metrics(documents)
        
        assert metrics["mentions_count"] == 2
        assert metrics["unique_authors"] == 0  # No valid authors
    
    def test_z_score_calculation(self, calculator):
        """Test z-score normalization."""
        # Mock historical data for z-score calculation
        historical_mentions = [5, 10, 15, 20, 25]  # mean=15, std~7.9
        
        z_score = calculator._calculate_z_score(30, historical_mentions)
        
        assert z_score > 1.5  # Should be > 1.5 standard deviations
        
        # Test edge case with no variation
        z_score_flat = calculator._calculate_z_score(10, [10, 10, 10, 10])
        assert z_score_flat == 0.0
    
    def test_z_score_insufficient_data(self, calculator):
        """Test z-score calculation with insufficient historical data."""
        # Less than 2 data points
        z_score = calculator._calculate_z_score(10, [5])
        assert z_score == 0.0
        
        # Empty historical data
        z_score_empty = calculator._calculate_z_score(10, [])
        assert z_score_empty == 0.0
    
    def test_simple_strength_formula(self, calculator):
        """Test the simple strength calculation formula."""
        # Test with maximum values
        strength_max = calculator._calculate_simple_strength(10, 5, 1.0)
        assert strength_max == 1.0
        
        # Test with minimum values
        strength_min = calculator._calculate_simple_strength(0, 0, -1.0)
        assert strength_min == 0.0
        
        # Test with moderate values
        strength_mod = calculator._calculate_simple_strength(5, 3, 0.5)
        assert 0.0 <= strength_mod <= 1.0
    
    def test_group_docs_by_day(self, calculator):
        """Test grouping documents by day."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        documents = [
            Document(
                id=1, content="test1", content_hash="hash1", 
                source="test", asset="BTC", narrative="test",
                created_at=now
            ),
            Document(
                id=2, content="test2", content_hash="hash2",
                source="test", asset="BTC", narrative="test", 
                created_at=now.replace(hour=10)  # Same day, different hour
            ),
            Document(
                id=3, content="test3", content_hash="hash3",
                source="test", asset="BTC", narrative="test",
                created_at=yesterday
            ),
            Document(
                id=4, content="test4", content_hash="hash4",
                source="test", asset="BTC", narrative="test",
                created_at=two_days_ago
            )
        ]
        
        grouped = calculator._group_docs_by_day(documents)
        
        assert len(grouped) == 3  # 3 different days
        
        # Find the group with 2 documents (same day)
        group_sizes = [len(group) for group in grouped]
        assert 2 in group_sizes  # Two documents from the same day
        assert group_sizes.count(1) == 2  # Two groups with single documents