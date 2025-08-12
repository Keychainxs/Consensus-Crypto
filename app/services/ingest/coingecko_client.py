import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CoinGeckoClient:
    """Client for CoinGecko API."""
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.COINGECKO_BASE
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_price_data(self, coin_id: str = "bitcoin") -> Optional[Dict[str, Any]]:
        """
        Get current price data for a cryptocurrency.
        
        Args:
            coin_id: CoinGecko coin ID
            
        Returns:
            Price data or None if error
        """
        try:
            params = {
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true"
            }
            
            response = await self.client.get(f"{self.base_url}/simple/price", params=params)
            response.raise_for_status()
            
            data = response.json()
            price_info = data.get(coin_id, {})
            
            if price_info:
                normalized = {
                    "asset": "BTC",  # Map coin_id to our asset format
                    "price_usd": price_info.get("usd"),
                    "change_24h": price_info.get("usd_24h_change"),
                    "volume_24h": price_info.get("usd_24h_vol"),
                    "market_cap": price_info.get("usd_market_cap"),
                    "timestamp": datetime.utcnow(),
                    "source": "coingecko"
                }
                
                logger.info(f"Fetched price data for {coin_id}: ${price_info.get('usd')}")
                return normalized
            
        except Exception as e:
            logger.error(f"CoinGecko API error: {e}")
        
        return None
    
    async def get_market_data(self, coin_id: str = "bitcoin", days: int = 1) -> List[Dict[str, Any]]:
        """
        Get historical market data.
        
        Args:
            coin_id: CoinGecko coin ID
            days: Number of days of historical data
            
        Returns:
            List of market data points
        """
        try:
            params = {
                "vs_currency": "usd",
                "days": days,
                "interval": "hourly" if days <= 1 else "daily"
            }
            
            response = await self.client.get(
                f"{self.base_url}/coins/{coin_id}/market_chart",
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])
            
            market_data = []
            for i, (timestamp, price) in enumerate(prices):
                volume = volumes[i][1] if i < len(volumes) else 0
                
                market_data.append({
                    "asset": "BTC",
                    "price_usd": price,
                    "volume_usd": volume,
                    "timestamp": datetime.fromtimestamp(timestamp / 1000),
                    "source": "coingecko"
                })
            
            logger.info(f"Fetched {len(market_data)} market data points for {coin_id}")
            return market_data
            
        except Exception as e:
            logger.error(f"CoinGecko market data error: {e}")
            return []
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()