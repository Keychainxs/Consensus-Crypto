import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class KPIAdapter(ABC):
    """Abstract base class for KPI data adapters."""
    
    @abstractmethod
    async def fetch_kpi_value(self, kpi_name: str, asset: str, timeframe: str) -> Optional[float]:
        """Fetch a single KPI value."""
        pass
    
    @abstractmethod
    async def fetch_kpi_history(self, kpi_name: str, asset: str, days: int) -> List[Dict[str, Any]]:
        """Fetch historical KPI values."""
        pass


class StubETFAdapter(KPIAdapter):
    """Stub adapter for ETF flow data (Week 1 implementation)."""
    
    async def fetch_kpi_value(self, kpi_name: str, asset: str, timeframe: str) -> Optional[float]:
        """Return mock ETF flow data."""
        if kpi_name == "etf_net_flow_usd" and asset == "BTC":
            # Mock positive flows for demo
            base_flow = 100_000_000  # $100M base
            variation = random.uniform(-0.3, 0.5)  # -30% to +50% variation
            return base_flow * (1 + variation)
        
        return None
    
    async def fetch_kpi_history(self, kpi_name: str, asset: str, days: int) -> List[Dict[str, Any]]:
        """Return mock historical ETF flow data."""
        if kpi_name != "etf_net_flow_usd" or asset != "BTC":
            return []
        
        history = []
        base_date = datetime.utcnow() - timedelta(days=days)
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            
            # Generate realistic-looking flow data
            # Trend component (slight positive bias)
            trend = 50_000_000 + (i * 2_000_000)
            
            # Weekly pattern (higher flows on weekdays)
            weekly_factor = 1.2 if date.weekday() < 5 else 0.8
            
            # Random variation
            random_factor = random.uniform(-0.4, 0.6)
            
            flow_value = trend * weekly_factor * (1 + random_factor)
            
            history.append({
                "timestamp": date,
                "value": flow_value,
                "asset": asset,
                "kpi_name": kpi_name,
                "source": "stub_etf_api"
            })
        
        return history


class KPIManager:
    """Manages KPI data fetching from various adapters."""
    
    def __init__(self):
        self.adapters = {
            "stub_etf_api": StubETFAdapter()
        }
    
    async def get_kpi_value(self, kpi_name: str, asset: str, source: str, timeframe: str = "24h") -> Optional[float]:
        """Get current KPI value from specified source."""
        adapter = self.adapters.get(source)
        if not adapter:
            logger.error(f"Unknown KPI source: {source}")
            return None
        
        try:
            value = await adapter.fetch_kpi_value(kpi_name, asset, timeframe)
            logger.info(f"Fetched KPI {kpi_name} for {asset}: {value}")
            return value
        except Exception as e:
            logger.error(f"Error fetching KPI {kpi_name}: {e}")
            return None
    
    async def get_kpi_history(self, kpi_name: str, asset: str, source: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get historical KPI values."""
        adapter = self.adapters.get(source)
        if not adapter:
            logger.error(f"Unknown KPI source: {source}")
            return []
        
        try:
            history = await adapter.fetch_kpi_history(kpi_name, asset, days)
            logger.info(f"Fetched {len(history)} historical KPI values for {kpi_name}")
            return history
        except Exception as e:
            logger.error(f"Error fetching KPI history {kpi_name}: {e}")
            return []