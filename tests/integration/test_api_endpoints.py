import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from datetime import datetime, timedelta

from app.main import app
from app.models.document import Document
from app.models.user import User
from app.models.api_key import APIKey
from app.core.security import get_password_hash, create_access_token, generate_api_key, hash_api_key
from app.db.session import get_session


@pytest.fixture
def test_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test session."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def client(test_session):
    """Create a test client with dependency overrides."""
    def get_test_session():
        return test_session
    
    app.dependency_overrides[get_session] = get_test_session
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_admin=True,
        is_active=True
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def test_api_key(test_session, test_user):
    """Create a test API key."""
    raw_key = generate_api_key()
    api_key = APIKey(
        name="Test Key",
        hashed_key=hash_api_key(raw_key),
        user_id=test_user.id,
        scopes='["read:narratives"]',
        is_active=True
    )
    test_session.add(api_key)
    test_session.commit()
    test_session.refresh(api_key)
    return api_key, raw_key


class TestHealthEndpoint:
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestAuthenticationEndpoints:
    
    def test_login_with_valid_credentials(self, client, test_user):
        """Test login with valid credentials and mocked captcha."""
        with pytest.mock.patch('app.api.v1.auth.verify_captcha', return_value=True):
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword",
                "captcha_token": "TEST_OK"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            
            # Check cookies were set
            assert "access_token" in response.cookies
            assert "refresh_token" in response.cookies
    
    def test_login_with_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials."""
        with pytest.mock.patch('app.api.v1.auth.verify_captcha', return_value=True):
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com", 
                "password": "wrongpassword",
                "captcha_token": "TEST_OK"
            })
            
            assert response.status_code == 401
    
    def test_login_without_captcha(self, client, test_user):
        """Test login without captcha token."""
        with pytest.mock.patch('app.api.v1.auth.verify_captcha', return_value=False):
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword",
                "captcha_token": "INVALID"
            })
            
            assert response.status_code == 400
            assert "captcha" in response.json()["detail"].lower()
    
    def test_logout_endpoint(self, client):
        """Test logout endpoint."""
        response = client.post("/api/v1/auth/logout")
        
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"


class TestNarrativeEndpoints:
    
    def test_leaderboard_requires_auth(self, client):
        """Test that leaderboard endpoint requires authentication."""
        response = client.get("/api/v1/narratives/leaderboard")
        assert response.status_code == 401
    
    def test_leaderboard_with_jwt_auth(self, client, test_user):
        """Test leaderboard access with JWT authentication."""
        # Create access token
        token = create_access_token({"sub": test_user.email, "scopes": ["read:narratives"]})
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/narratives/leaderboard?window=24h", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "window" in data
        assert "updated_at" in data
    
    def test_leaderboard_with_api_key_auth(self, client, test_api_key):
        """Test leaderboard access with API key authentication."""
        api_key, raw_key = test_api_key
        
        headers = {"Authorization": f"Bearer {raw_key}"}
        response = client.get("/api/v1/narratives/leaderboard?window=24h", headers=headers)
        
        assert response.status_code == 200
    
    def test_narrative_strength_endpoint(self, client, test_user, test_session):
        """Test narrative strength endpoint with test data."""
        # Create test documents
        now = datetime.utcnow()
        test_docs = [
            Document(
                content="Bitcoin ETF inflows hit record high",
                content_hash="hash1",
                source="test",
                asset="BTC",
                narrative="ETF_flows",
                sentiment_score=0.8,
                sentiment_label="bullish",
                author="test_author",
                created_at=now - timedelta(hours=1)
            ),
            Document(
                content="BlackRock sees massive ETF demand",
                content_hash="hash2", 
                source="test",
                asset="BTC",
                narrative="ETF_flows",
                sentiment_score=0.9,
                sentiment_label="bullish",
                author="test_author2",
                created_at=now - timedelta(hours=2)
            )
        ]
        
        for doc in test_docs:
            test_session.add(doc)
        test_session.commit()
        
        # Test strength endpoint
        token = create_access_token({"sub": test_user.email, "scopes": ["read:narratives"]})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(
            "/api/v1/narratives/strength?asset=BTC&narrative=ETF_flows&period=24h",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["narrative"] == "ETF_flows"
        assert data["asset"] == "BTC"
        assert data["mentions_count"] == 2
        assert data["unique_authors"] == 2
        assert data["strength"] > 0
    
    def test_narrative_drivers_endpoint(self, client, test_user, test_session):
        """Test narrative drivers endpoint."""
        # Create test document with high engagement
        test_doc = Document(
            content="BREAKING: Bitcoin spot ETF sees record $500M inflows today!",
            content_hash="driver_hash",
            source="cryptopanic",
            asset="BTC",
            narrative="ETF_flows",
            sentiment_score=0.9,
            sentiment_label="bullish",
            engagement_score=0.95,
            url="https://example.com/news",
            author="crypto_news",
            created_at=datetime.utcnow()
        )
        
        test_session.add(test_doc)
        test_session.commit()
        
        # Test drivers endpoint
        token = create_access_token({"sub": test_user.email, "scopes": ["read:narratives"]})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(
            "/api/v1/narratives/drivers?asset=BTC&narrative=ETF_flows&period=24h&limit=5",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["narrative"] == "ETF_flows"
        assert data["asset"] == "BTC"
        assert len(data["drivers"]) >= 1
        
        # Check driver structure
        driver = data["drivers"][0]
        assert "content_snippet" in driver
        assert "sentiment_label" in driver
        assert "engagement_score" in driver


class TestAdminEndpoints:
    
    def test_admin_api_key_creation(self, client, test_user):
        """Test admin API key creation endpoint."""
        token = create_access_token({
            "sub": test_user.email, 
            "scopes": ["read:narratives", "admin:all"]
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post("/api/v1/admin/api-keys", 
            headers=headers,
            json={
                "name": "Test API Key",
                "scopes": ["read:narratives"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "key" in data  # Raw key only returned on creation
        assert data["name"] == "Test API Key"
        assert "cns_" in data["key"]
    
    def test_non_admin_cannot_create_api_keys(self, client, test_session):
        """Test that non-admin users cannot create API keys."""
        # Create non-admin user
        user = User(
            email="nonadmin@example.com",
            hashed_password=get_password_hash("password"),
            is_admin=False,
            is_active=True
        )
        test_session.add(user)
        test_session.commit()
        
        token = create_access_token({"sub": user.email, "scopes": ["read:narratives"]})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post("/api/v1/admin/api-keys",
            headers=headers,
            json={
                "name": "Unauthorized Key",
                "scopes": ["read:narratives"]
            }
        )
        
        assert response.status_code == 403


class TestCORSHeaders:
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set."""
        response = client.options("/api/v1/narratives/leaderboard", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        # CORS preflight should be handled
        assert response.status_code == 200


class TestSecurityHeaders:
    
    def test_security_headers_present(self, client):
        """Test that security headers are set."""
        response = client.get("/health")
        
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "X-Request-ID" in response.headers
        
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"