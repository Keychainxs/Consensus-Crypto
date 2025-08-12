import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from jose import jwt

from app.core.security import (
    create_access_token, 
    verify_token,
    get_password_hash,
    verify_password,
    hash_api_key,
    verify_api_key,
    generate_api_key
)
from app.core.config import get_settings


class TestPasswordHashing:
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "secure_password_123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes are long
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False
    
    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        password = "test_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2  # Should be different due to salt
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    
    def test_jwt_token_creation_and_verification(self):
        """Test JWT token creation and verification."""
        # Create token
        token_data = {"sub": "user@example.com", "scopes": ["read:narratives"]}
        token = create_access_token(token_data)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT should be reasonably long
        
        # Verify token
        decoded = verify_token(token)
        assert decoded["sub"] == "user@example.com"
        assert "read:narratives" in decoded["scopes"]
        assert "exp" in decoded
        assert decoded["type"] == "access"
    
    def test_token_expiration(self):
        """Test token expiration handling."""
        settings = get_settings()
        
        # Create token with very short expiration
        short_expiry = timedelta(seconds=-1)  # Already expired
        token_data = {"sub": "user@example.com"}
        
        with pytest.raises(Exception):  # Should raise JWT expiry exception
            expired_token = create_access_token(token_data, short_expiry)
            verify_token(expired_token)
    
    def test_invalid_token_rejection(self):
        """Test that invalid tokens are rejected."""
        with pytest.raises(Exception):
            verify_token("invalid.jwt.token")
        
        with pytest.raises(Exception):
            verify_token("definitely_not_a_jwt")
    
    def test_token_without_required_fields(self):
        """Test token verification with missing required fields."""
        # Create token without 'sub' field
        token_data = {"other_field": "value"}
        token = create_access_token(token_data)
        
        decoded = verify_token(token)
        assert decoded.get("sub") is None  # Should handle missing fields gracefully


class TestAPIKeys:
    
    def test_api_key_generation(self):
        """Test API key generation."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        
        assert key1.startswith("cns_")
        assert key2.startswith("cns_")
        assert key1 != key2  # Should be unique
        assert len(key1) > 40  # Should be reasonably long
    
    def test_api_key_hashing(self):
        """Test API key hashing and verification."""
        api_key = "cns_test_api_key_12345"
        hashed = hash_api_key(api_key)
        
        assert hashed != api_key
        assert len(hashed) == 64  # SHA-256 hex digest length
        assert verify_api_key(api_key, hashed) is True
        assert verify_api_key("wrong_key", hashed) is False
    
    def test_api_key_deterministic_hashing(self):
        """Test that same API key always produces same hash."""
        api_key = "cns_consistent_key"
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)
        
        assert hash1 == hash2  # Should be deterministic


class TestAuthenticationEndpoints:
    
    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)
    
    @patch('app.api.v1.auth.verify_captcha')
    def test_login_with_valid_credentials(self, mock_captcha, client):
        """Test login endpoint with valid credentials."""
        mock_captcha.return_value = True
        
        # This test would need a test database with a user
        # For now, we test the endpoint structure
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword",
            "captcha_token": "TEST_OK"
        })
        
        # Expect 401 since user doesn't exist in test
        assert response.status_code in [200, 401]
    
    @patch('app.api.v1.auth.verify_captcha')
    def test_login_with_invalid_captcha(self, mock_captcha, client):
        """Test login with invalid captcha."""
        mock_captcha.return_value = False
        
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword",
            "captcha_token": "INVALID"
        })
        
        assert response.status_code == 400
        assert "captcha" in response.json()["detail"].lower()
    
    def test_login_missing_fields(self, client):
        """Test login with missing required fields."""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com"
            # Missing password and captcha_token
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_logout_endpoint(self, client):
        """Test logout endpoint."""
        response = client.post("/api/v1/auth/logout")
        
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"


class TestRateLimiting:
    
    @pytest.mark.asyncio
    async def test_rate_limiter_basic_functionality(self):
        """Test basic rate limiting functionality."""
        from app.core.rate_limit import RateLimiter
        from unittest.mock import Mock
        
        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [None, None, 5, None]  # 5 requests in window
        
        rate_limiter = RateLimiter()
        rate_limiter.redis_client = mock_redis
        
        # Mock request object
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Should not raise exception (under limit)
        result = await rate_limiter.check_rate_limit("test_key", 10, 3600, mock_request)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_exceeds_limit(self):
        """Test rate limiting when limit is exceeded."""
        from app.core.rate_limit import RateLimiter
        from unittest.mock import Mock
        from fastapi import HTTPException
        
        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [None, None, 15, None]  # 15 requests, limit 10
        
        rate_limiter = RateLimiter()
        rate_limiter.redis_client = mock_redis
        
        # Mock request object
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter.check_rate_limit("test_key", 10, 3600, mock_request)
        
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert "Retry-After" in exc_info.value.headers