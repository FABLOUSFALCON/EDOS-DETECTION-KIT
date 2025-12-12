"""
Development Database Setup Script
Ensures consistent user IDs between Supabase and local database
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import uuid
import json

logger = logging.getLogger(__name__)

# Development constants for consistent IDs
DEV_USER_ID = "21c9dde7-a586-44af-9f67-11f13b9ddd28"  # Your actual Supabase user ID
DEV_CLIENT_ID = "client_dev_001"
DEV_RESOURCE_IDS = ["res_001", "res_002", "res_003"]


async def setup_dev_user():
    """Setup development user in local database"""
    try:
        # Use direct database URL for setup
        database_url = "postgresql://postgres:password@localhost:5432/edos_security"
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Check if dev user exists
        existing_user = db.execute(
            text("SELECT id FROM user_profiles WHERE id = :user_id"),
            {"user_id": DEV_USER_ID},
        ).fetchone()

        if not existing_user:
            # Create dev user
            db.execute(
                text(
                    """
                    INSERT INTO user_profiles (id, email, full_name, role, created_at, updated_at)
                    VALUES (:id, :email, :name, :role, NOW(), NOW())
                """
                ),
                {
                    "id": DEV_USER_ID,
                    "email": "dev@example.com",
                    "name": "Development User",
                    "role": "admin",
                },
            )
            db.commit()
            logger.info(f"✅ Created development user: {DEV_USER_ID}")
        else:
            logger.info(f"👤 Development user already exists: {DEV_USER_ID}")

        # Setup development resources
        for resource_id in DEV_RESOURCE_IDS:
            existing_resource = db.execute(
                text("SELECT id FROM resources WHERE id = :resource_id"),
                {"resource_id": resource_id},
            ).fetchone()

            if not existing_resource:
                # Create resource table if it doesn't exist
                db.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS resources (
                        id VARCHAR(50) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        type VARCHAR(50) NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        client_id VARCHAR(50),
                        user_id VARCHAR(36),
                        location VARCHAR(100),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """
                    )
                )

                # Insert dev resource
                resource_data = get_dev_resource_data(resource_id)
                db.execute(
                    text(
                        """
                        INSERT INTO resources (id, name, type, status, client_id, user_id, location, metadata)
                        VALUES (:id, :name, :type, :status, :client_id, :user_id, :location, :metadata)
                        ON CONFLICT (id) DO NOTHING
                    """
                    ),
                    resource_data,
                )
                logger.info(f"🏗️ Created development resource: {resource_id}")

        db.commit()
        db.close()
        logger.info("✅ Development database setup complete")

    except Exception as e:
        logger.error(f"❌ Error setting up dev database: {e}")
        raise


def get_dev_resource_data(resource_id: str) -> dict:
    """Get development resource data"""
    resource_configs = {
        "res_001": {
            "name": "Production Server",
            "type": "server",
            "location": "US-East-1",
        },
        "res_002": {
            "name": "Development Environment",
            "type": "cloud",
            "location": "US-West-2",
        },
        "res_003": {
            "name": "Docker Cluster",
            "type": "container",
            "location": "EU-Central-1",
        },
    }

    config = resource_configs.get(
        resource_id,
        {"name": f"Resource {resource_id}", "type": "server", "location": "Unknown"},
    )

    return {
        "id": resource_id,
        "name": config["name"],
        "type": config["type"],
        "status": "online",
        "client_id": DEV_CLIENT_ID,
        "user_id": DEV_USER_ID,
        "location": config["location"],
        "metadata": '{"fingerprint": "dev-fingerprint", "cic_ready": true, "backend_ready": true}',
    }


async def setup_dev_redis_data():
    """Setup development data in Redis"""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        print("⚠️  Redis not available, skipping Redis setup")
        return

    try:
        redis_client = aioredis.from_url(
            "redis://localhost:6379", decode_responses=True
        )
        await redis_client.ping()

        # Setup sample network analysis data for each resource
        for resource_id in DEV_RESOURCE_IDS:
            sample_data = {
                "timestamp": "2025-12-09T12:00:00Z",
                "resource_id": resource_id,
                "client_id": DEV_CLIENT_ID,
                "networkSpeeds": [
                    {
                        "timestamp": "2025-12-09T12:00:00Z",
                        "upload": 10.5,
                        "download": 25.3,
                    },
                ],
                "connectionStats": {"active": 15, "total": 100, "failed": 2},
                "threatAnalysis": {"level": "medium", "threats": 3, "blocked": 5},
            }

            key = f"network_analysis:latest:{resource_id}"
            await redis_client.set(key, json.dumps(sample_data))
            logger.info(f"📊 Setup Redis data for resource: {resource_id}")

        await redis_client.close()
        logger.info("✅ Development Redis setup complete")

    except Exception as e:
        logger.error(f"❌ Error setting up Redis: {e}")


if __name__ == "__main__":
    import json

    asyncio.run(setup_dev_user())
    asyncio.run(setup_dev_redis_data())
    print("🚀 Development environment setup complete!")
    print(f"👤 User ID: {DEV_USER_ID}")
    print(f"🏢 Client ID: {DEV_CLIENT_ID}")
    print(f"🏗️ Resources: {', '.join(DEV_RESOURCE_IDS)}")
