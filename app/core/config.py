from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "dev"
    DATABASE_URL: str = "sqlite:///./data.db"
    
    # JWT Configuration
    JWT_PRIVATE_KEY_PATH: str = "keys/jwtRS256.key"
    JWT_PUBLIC_KEY_PATH: str = "keys/jwtRS256.key.pub"
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Redis
    RATE_LIMIT_REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Captcha
    CAPTCHA_PROVIDER: str = "turnstile"  # or "hcaptcha"
    CAPTCHA_SECRET: str = ""
    
    # External APIs
    CRYPTOPANIC_TOKEN: str = ""
    X_BEARER_TOKEN: str = ""
    COINGECKO_BASE: str = "https://api.coingecko.com/api/v3"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()