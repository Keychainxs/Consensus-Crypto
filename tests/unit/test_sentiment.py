import pytest
from unittest.mock import Mock, patch

from app.services.nlp.sentiment import SentimentAnalyzer


class TestSentimentAnalyzer:
    
    @pytest.fixture
    def analyzer(self):
        return SentimentAnalyzer(model_name="mock-model", use_cache=False)
    
    def test_sentiment_analysis_bullish(self, analyzer):
        """Test bullish sentiment classification."""
        # Mock the pipeline to return positive sentiment
        with patch.object(analyzer, '_get_pipeline') as mock_pipeline:
            mock_pipeline.return_value = lambda x: [{"label": "POSITIVE", "score": 0.85}]
            
            text = "Bitcoin ETF inflows are breaking records! Great news for adoption."
            result = analyzer.analyze_sentiment(text)
            
            assert result["sentiment"] == "bullish"
            assert result["confidence"] == 0.85
            assert result["raw_label"] == "POSITIVE"
    
    def test_sentiment_analysis_bearish(self, analyzer):
        """Test bearish sentiment classification."""
        with patch.object(analyzer, '_get_pipeline') as mock_pipeline:
            mock_pipeline.return_value = lambda x: [{"label": "NEGATIVE", "score": 0.90}]
            
            text = "Massive ETF outflows continue, worst performance in months"
            result = analyzer.analyze_sentiment(text)
            
            assert result["sentiment"] == "bearish"
            assert result["confidence"] == 0.90
    
    def test_sentiment_analysis_neutral(self, analyzer):
        """Test neutral sentiment classification."""
        with patch.object(analyzer, '_get_pipeline') as mock_pipeline:
            mock_pipeline.return_value = lambda x: [{"label": "NEUTRAL", "score": 0.60}]
            
            text = "ETF trading volumes were average today"
            result = analyzer.analyze_sentiment(text)
            
            assert result["sentiment"] == "neutral"
            assert result["confidence"] == 0.60
    
    def test_sentiment_caching(self):
        """Test sentiment result caching."""
        analyzer = SentimentAnalyzer(use_cache=True)
        
        with patch.object(analyzer, '_analyze_with_model') as mock_analyze:
            mock_analyze.return_value = {"label": "POSITIVE", "score": 0.8}
            
            text = "Same text for caching test"
            
            # First call should hit the model
            result1 = analyzer.analyze_sentiment(text)
            assert mock_analyze.call_count == 1
            
            # Second call should use cache
            result2 = analyzer.analyze_sentiment(text)
            assert mock_analyze.call_count == 1
            assert result1 == result2
    
    def test_mock_pipeline_keyword_based(self, analyzer):
        """Test the mock pipeline's keyword-based sentiment."""
        # Test bullish keywords
        bullish_text = "Bitcoin pump to the moon! Massive gains and profits!"
        result = analyzer.analyze_sentiment(bullish_text)
        assert result["sentiment"] == "bullish"
        
        # Test bearish keywords
        bearish_text = "Bitcoin dump and crash! Huge losses and fear in market!"
        result = analyzer.analyze_sentiment(bearish_text)
        assert result["sentiment"] == "bearish"
        
        # Test neutral text
        neutral_text = "Bitcoin price remains stable today"
        result = analyzer.analyze_sentiment(neutral_text)
        assert result["sentiment"] == "neutral"
    
    def test_label_mapping(self, analyzer):
        """Test various label formats are mapped correctly."""
        test_cases = [
            ("POSITIVE", "bullish"),
            ("NEGATIVE", "bearish"),
            ("NEUTRAL", "neutral"),
            ("LABEL_0", "bearish"),
            ("LABEL_1", "neutral"),
            ("LABEL_2", "bullish"),
            ("UNKNOWN", "neutral"),  # Unknown labels default to neutral
        ]
        
        for raw_label, expected_sentiment in test_cases:
            mapped = analyzer._map_sentiment_label(raw_label, 0.8)
            assert mapped == expected_sentiment
    
    def test_text_truncation(self, analyzer):
        """Test that long text is properly truncated."""
        with patch.object(analyzer, '_get_pipeline') as mock_pipeline:
            mock_func = Mock(return_value=[{"label": "POSITIVE", "score": 0.8}])
            mock_pipeline.return_value = mock_func
            
            # Create text longer than 512 characters
            long_text = "Bitcoin ETF " * 100  # Much longer than 512 chars
            
            analyzer.analyze_sentiment(long_text)
            
            # Check that the text passed to pipeline was truncated
            called_text = mock_func.call_args[0][0]
            assert len(called_text) <= 512
    
    def test_error_handling(self, analyzer):
        """Test error handling in sentiment analysis."""
        with patch.object(analyzer, '_get_pipeline') as mock_pipeline:
            # Mock pipeline to raise an exception
            mock_pipeline.return_value = Mock(side_effect=Exception("Model error"))
            
            result = analyzer.analyze_sentiment("Test text")
            
            # Should return neutral sentiment on error
            assert result["sentiment"] == "neutral"
            assert result["confidence"] == 0.5
            assert result["raw_label"] == "NEUTRAL"