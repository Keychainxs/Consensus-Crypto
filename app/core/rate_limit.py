import time
from typing import Optional

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    def __init__(self):
        settings = get_settings()
        self.redis_client = redis.from_url(settings.RATE_LIMIT_REDIS_URL)
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window: int,
        request: Request
    ) -> bool:
        """
        Check if request is within rate limit using sliding window.
        
        Args:
            key: Rate limit key (e.g., IP address, user ID)
            limit: Number of requests allowed
            window: Time window in seconds
            request: FastAPI request object
        
        Returns:
            True if within limit, raises HTTPException if exceeded
        """
        current_time = int(time.time())
        window_start = current_time - window
        
        try:
            # Use sliding window with Redis sorted sets
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Count requests in window
            pipe.zcard(key)
            
            # Set expiry for the key
            pipe.expire(key, window)
            
            results = await pipe.execute()
            request_count = results[2]
            
            if request_count > limit:
                # Log rate limit violation
                logger.warning(
                    f"Rate limit exceeded for {key}: {request_count}/{limit} "
                    f"requests in {window}s window. IP: {request.client.host}"
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {window} seconds.",
                    headers={"Retry-After": str(window)}
                )
            
            return True
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # In case of Redis failure, allow the request (fail open)
            return True
    
    async def check_ip_rate_limit(self, request: Request) -> bool:
        """Check global IP rate limit."""
        ip = request.client.host
        return await self.check_rate_limit(f"ip:{ip}", 100, 3600, request)  # 100/hour
    
    async def check_auth_rate_limit(self, request: Request) -> bool:
        """Check authentication rate limit."""
        ip = request.client.host
        return await self.check_rate_limit(f"auth:{ip}", 10, 900, request)  # 10/15min
    
    async def check_api_key_rate_limit(self, api_key: str, request: Request) -> bool:
        """Check API key rate limit."""
        return await self.check_rate_limit(f"api_key:{api_key}", 1000, 3600, request)  # 1000/hour