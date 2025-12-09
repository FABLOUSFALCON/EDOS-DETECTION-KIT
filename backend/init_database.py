#!/usr/bin/env python3
"""
Database initialization script for EDoS Security Dashboard
Recreates database with updated schema
"""

import os
import sys
import uuid
import logging
from datetime import datetime

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, UserProfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize database with updated schema"""

    # Override to use SQLite for this initialization
    sqlite_url = "sqlite:///./edos_security.db"

    # Remove existing database file if it exists
    db_file = "./edos_security.db"
    if os.path.exists(db_file):
        logger.info(f"🗑️  Removing existing database: {db_file}")
        os.remove(db_file)

    # Create new database engine
    logger.info("🔧 Creating database engine...")
    engine = create_engine(
        sqlite_url,
        echo=True,  # Show SQL queries
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    logger.info("📊 Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Create a test user
        logger.info("👤 Creating test user...")
        test_user = UserProfile(
            id=uuid.UUID(
                "550e8400-e29b-41d4-a716-446655440000"
            ),  # Fixed UUID for testing
            email="test@edos.local",
            username="testuser",
            first_name="Test",
            last_name="User",
            role="analyst",
            department="Security",
            is_active=True,
            email_verified=True,
        )

        db.add(test_user)
        db.commit()

        logger.info("✅ Database initialization completed!")
        logger.info(f"📋 Test user created: {test_user.email} (ID: {test_user.id})")

    except Exception as e:
        logger.error(f"❌ Error during database initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🧪 EDoS Database Initialization")
    print("=" * 50)
    init_database()
