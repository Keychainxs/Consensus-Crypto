"""Database initialization script."""
import logging
from pathlib import Path
import sys

# Add app to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session

from app.db.session import engine, create_db_and_tables
from app.models.user import User
from app.models.api_key import APIKey
from app.core.security import get_password_hash, generate_api_key, hash_api_key

logger = logging.getLogger(__name__)


def init_database():
    """Initialize database with tables and seed data."""
    logging.basicConfig(level=logging.INFO)
    
    logger.info("Creating database tables...")
    create_db_and_tables()
    
    with Session(engine) as session:
        # Check if admin user already exists
        existing_user = session.query(User).filter(User.email == "admin@consensus.dev").first()
        if existing_user:
            logger.info("Admin user already exists")
            return
        
        # Create admin user
        logger.info("Creating admin user...")
        admin_user = User(
            email="admin@consensus.dev",
            hashed_password=get_password_hash("admin123!"),
            is_admin=True,
            is_active=True
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        
        # Create initial API key
        logger.info("Creating initial API key...")
        raw_key = generate_api_key()
        api_key = APIKey(
            name="Initial Admin Key",
            hashed_key=hash_api_key(raw_key),
            user_id=admin_user.id,
            scopes='["read:narratives", "admin:all"]',
            is_active=True
        )
        session.add(api_key)
        session.commit()
        
        logger.info("Database initialization complete!")
        logger.info(f"Admin email: admin@consensus.dev")
        logger.info(f"Admin password: admin123!")
        logger.info(f"Initial API key: {raw_key}")


if __name__ == "__main__":
    init_database()