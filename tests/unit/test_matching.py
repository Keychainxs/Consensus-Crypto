import pytest

from app.services.nlp.matching import NarrativeMatcher


class TestNarrativeMatcher:
    
    @pytest.fixture
    def sample_narratives(self):
        """Sample narratives configuration for testing."""
        return {
            "ETF_flows": {
                "asset": "BTC",
                "terms": [
                    "spot ETF",
                    "bitcoin ETF",
                    "BTC ETF",
                    "inflows",
                    "outflows",
                    "redemptions",
                    "creations",
                    "GBTC",
                    "iShares",
                    "BlackRock",
                    "Fidelity",
                    "IBIT",
                    "FBTC"
                ],
                "fuzzy_variants": [
                    "etf flow",
                    "net flow",
                    "creation units",
                    "etf inflow",
                    "etf outflow"
                ]
            }
        }
    
    @pytest.fixture
    def matcher(self, sample_narratives):
        return NarrativeMatcher(sample_narratives)
    
    def test_exact_term_matching(self, matcher):
        """Test exact term matching for ETF flows narrative."""
        text = "Bitcoin spot ETF saw massive inflows today"
        matches = matcher.match_narratives(text, "BTC")
        
        assert "ETF_flows" in matches
        assert matches["ETF_flows"]["score"] > 0.5
        assert "spot etf" in matches["ETF_flows"]["matched_terms"]
        assert "inflows" in matches["ETF_flows"]["matched_terms"]
    
    def test_fuzzy_matching(self, matcher):
        """Test fuzzy variant matching."""
        text = "The etf flow data shows strong net flows"
        matches = matcher.match_narratives(text, "BTC")
        
        assert "ETF_flows" in matches
        assert "etf flow" in matches["ETF_flows"]["matched_variants"]
        assert "net flow" in matches["ETF_flows"]["matched_variants"]
    
    def test_case_insensitive_matching(self, matcher):
        """Test case insensitive matching."""
        text = "BLACKROCK and ishares bitcoin ETF"
        matches = matcher.match_narratives(text, "BTC")
        
        assert "ETF_flows" in matches
        assert matches["ETF_flows"]["score"] > 0.3
    
    def test_no_false_positives(self, matcher):
        """Test rejection of unrelated content."""
        text = "The weather is nice today, let's go hiking"
        matches = matcher.match_narratives(text, "BTC")
        
        assert len(matches) == 0
    
    def test_homonym_rejection(self, matcher):
        """Test rejection of homonyms that might cause false positives."""
        text = "I need to create a new user flow for the application"
        matches = matcher.match_narratives(text, "BTC")
        
        # Should not match ETF_flows for generic "flow" mentions
        assert "ETF_flows" not in matches or matches["ETF_flows"]["score"] < 0.3
    
    def test_word_boundary_matching(self, matcher):
        """Test that word boundaries are respected."""
        text = "The inflation rate is growing"  # "flow" is part of "inflation"
        matches = matcher.match_narratives(text, "BTC")
        
        # Should not match because "flow" is not a complete word
        assert "ETF_flows" not in matches
    
    def test_multiple_matches_increase_score(self, matcher):
        """Test that multiple matches increase the score."""
        text1 = "Bitcoin spot ETF inflows"  # 2 matches
        text2 = "Bitcoin spot ETF inflows from BlackRock and Fidelity"  # 4 matches
        
        matches1 = matcher.match_narratives(text1, "BTC")
        matches2 = matcher.match_narratives(text2, "BTC")
        
        assert "ETF_flows" in matches1
        assert "ETF_flows" in matches2
        assert matches2["ETF_flows"]["score"] > matches1["ETF_flows"]["score"]
    
    def test_wrong_asset_no_match(self, matcher):
        """Test that narratives don't match for wrong assets."""
        text = "Bitcoin spot ETF inflows are massive"
        matches = matcher.match_narratives(text, "ETH")  # Wrong asset
        
        # Should not match because narrative is for BTC only
        assert "ETF_flows" not in matches
    
    def test_empty_text_handling(self, matcher):
        """Test handling of empty or whitespace-only text."""
        empty_matches = matcher.match_narratives("", "BTC")
        whitespace_matches = matcher.match_narratives("   \n\t  ", "BTC")
        
        assert len(empty_matches) == 0
        assert len(whitespace_matches) == 0