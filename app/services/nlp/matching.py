import re
import yaml
from pathlib import Path
from typing import Any, Dict, List

from app.core.logging import get_logger

logger = get_logger(__name__)


class NarrativeMatcher:
    """Matcher for narratives using regex and fuzzy matching."""
    
    def __init__(self, narratives_config: Dict[str, Any]):
        self.narratives = narratives_config
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        self.patterns = {}
        
        for narrative_name, config in self.narratives.items():
            patterns = []
            
            # Exact terms
            for term in config.get("terms", []):
                # Word boundary matching to avoid partial matches
                pattern = r'\b' + re.escape(term.lower()) + r'\b'
                patterns.append(pattern)
            
            # Fuzzy variants  
            for variant in config.get("fuzzy_variants", []):
                pattern = r'\b' + re.escape(variant.lower()) + r'\b'
                patterns.append(pattern)
            
            # Combine all patterns for this narrative
            if patterns:
                combined_pattern = '|'.join(patterns)
                self.patterns[narrative_name] = re.compile(combined_pattern, re.IGNORECASE)
    
    def match_narratives(self, text: str, asset: str) -> Dict[str, Dict[str, Any]]:
        """
        Match text against narrative patterns.
        
        Args:
            text: Text to analyze
            asset: Asset symbol (BTC, ETH, etc.)
            
        Returns:
            Dict of matched narratives with scores and matched terms
        """
        matches = {}
        text_lower = text.lower()
        
        for narrative_name, config in self.narratives.items():
            # Check if this narrative applies to the asset
            if config.get("asset") != asset:
                continue
            
            if narrative_name not in self.patterns:
                continue
            
            pattern = self.patterns[narrative_name]
            found_matches = pattern.findall(text_lower)
            
            if found_matches:
                # Calculate match score based on number and quality of matches
                unique_matches = set(found_matches)
                
                # Score based on coverage and match density
                term_coverage = len(unique_matches) / max(len(config.get("terms", [])), 1)
                match_density = len(found_matches) / max(len(text.split()), 1)
                
                score = min(term_coverage + match_density, 1.0)
                
                # Separate exact terms from fuzzy variants
                exact_terms = []
                fuzzy_variants = []
                
                config_terms_lower = [term.lower() for term in config.get("terms", [])]
                config_variants_lower = [variant.lower() for variant in config.get("fuzzy_variants", [])]
                
                for match in unique_matches:
                    if match in config_terms_lower:
                        exact_terms.append(match)
                    elif match in config_variants_lower:
                        fuzzy_variants.append(match)
                
                matches[narrative_name] = {
                    "score": score,
                    "matched_terms": exact_terms,
                    "matched_variants": fuzzy_variants,
                    "total_matches": len(found_matches)
                }
        
        return matches


def load_narratives() -> Dict[str, Any]:
    """Load narratives configuration from YAML file."""
    config_path = Path(__file__).parent.parent.parent / "lexicon" / "narratives.yaml"
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config.get("narratives", {})
    except Exception as e:
        logger.error(f"Failed to load narratives config: {e}")
        return {}