"""
Database configuration and connection management
"""

import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import asyncpg
import asyncio
from typing import Generator
from app.core.config import settings

# Database configuration
# Use the pydantic Settings which reads `backend/.env` (Settings.Config.env_file)
# Fall back to environment var or sqlite if Settings is not available for some reason
try:
    DATABASE_URL = settings.effective_database_url
except Exception:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./edos_security.db",  # SQLite fallback for local development
    )

# Create SQLAlchemy engine
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=True if os.getenv("DEBUG") == "true" else False,
    )
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=True if os.getenv("DEBUG") == "true" else False,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency injection for FastAPI
def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI routes
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Database initialization functions
async def create_database_if_not_exists():
    """
    Create the database if it doesn't exist
    """
    try:
        # Parse database URL
        import urllib.parse

        parsed = urllib.parse.urlparse(DATABASE_URL)

        db_name = parsed.path[1:]  # Remove leading slash
        host = parsed.hostname
        port = parsed.port or 5432
        user = parsed.username
        password = parsed.password

        # Connect to postgres database to create our database
        postgres_url = f"postgresql://{user}:{password}@{host}:{port}/postgres"

        conn = await asyncpg.connect(postgres_url)

        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )

        if not exists:
            # Create database
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✅ Created database: {db_name}")
        else:
            print(f"✅ Database already exists: {db_name}")

        await conn.close()

    except Exception as e:
        print(f"❌ Error creating database: {e}")
        print("⚠️ Make sure PostgreSQL is running and credentials are correct")


def create_tables():
    """
    Create all database tables
    """
    from app.models.database import Base

    try:
        Base.metadata.create_all(bind=engine)
        print("✅ All database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")


def drop_tables():
    """
    Drop all database tables (for development)
    """
    from app.models.database import Base

    try:
        Base.metadata.drop_all(bind=engine)
        print("✅ All database tables dropped successfully")
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")


# Database health check
def check_database_connection():
    """
    Check if database connection is working
    """
    try:
        with get_db_context() as db:
            db.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


# Row Level Security setup for multi-tenant architecture
def setup_rls_policies():
    """
    Set up Row Level Security policies for multi-tenant isolation
    """
    rls_queries = [
        # Enable RLS on user-specific tables
        "ALTER TABLE users ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE user_resources ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE security_alerts ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE network_traffic ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE system_logs ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE system_metrics ENABLE ROW LEVEL SECURITY;",
        # Create policies for user isolation
        """
        CREATE POLICY user_isolation_policy ON users
        FOR ALL TO authenticated_user
        USING (id = current_setting('app.current_user_id')::uuid);
        """,
        """
        CREATE POLICY resource_isolation_policy ON user_resources
        FOR ALL TO authenticated_user
        USING (user_id = current_setting('app.current_user_id')::uuid);
        """,
        """
        CREATE POLICY alert_isolation_policy ON security_alerts
        FOR ALL TO authenticated_user
        USING (user_id = current_setting('app.current_user_id')::uuid);
        """,
        """
        CREATE POLICY traffic_isolation_policy ON network_traffic
        FOR ALL TO authenticated_user
        USING (user_id = current_setting('app.current_user_id')::uuid);
        """,
        """
        CREATE POLICY logs_isolation_policy ON system_logs
        FOR ALL TO authenticated_user
        USING (user_id = current_setting('app.current_user_id')::uuid);
        """,
        """
        CREATE POLICY metrics_isolation_policy ON system_metrics
        FOR ALL TO authenticated_user
        USING (user_id = current_setting('app.current_user_id')::uuid);
        """,
    ]

    try:
        with get_db_context() as db:
            for query in rls_queries:
                try:
                    db.execute(text(query))
                except Exception as e:
                    # Policy might already exist
                    if "already exists" not in str(e).lower():
                        print(f"⚠️ RLS Policy setup warning: {e}")

            db.commit()
            print("✅ Row Level Security policies configured")
    except Exception as e:
        print(f"❌ Error setting up RLS policies: {e}")


# Database migration functions
def seed_initial_data():
    """
    Seed database with initial data
    """
    from app.models.database import CloudProvider, ResourceType

    try:
        with get_db_context() as db:
            # Check if data already exists
            existing_providers = db.query(CloudProvider).count()
            if existing_providers > 0:
                print("✅ Initial data already exists")
                return

            # Create cloud providers
            aws = CloudProvider(
                name="aws",
                display_name="Amazon Web Services",
                api_endpoint="https://aws.amazon.com",
                is_active=True,
            )

            azure = CloudProvider(
                name="azure",
                display_name="Microsoft Azure",
                api_endpoint="https://management.azure.com",
                is_active=True,
            )

            gcp = CloudProvider(
                name="gcp",
                display_name="Google Cloud Platform",
                api_endpoint="https://cloud.google.com",
                is_active=True,
            )

            db.add_all([aws, azure, gcp])
            db.flush()  # Get IDs

            # Create resource types
            resource_types = [
                # AWS
                ResourceType(
                    provider_id=aws.id,
                    name="ec2",
                    display_name="EC2 Instance",
                    category="compute",
                    icon="server",
                ),
                ResourceType(
                    provider_id=aws.id,
                    name="rds",
                    display_name="RDS Database",
                    category="database",
                    icon="database",
                ),
                ResourceType(
                    provider_id=aws.id,
                    name="s3",
                    display_name="S3 Bucket",
                    category="storage",
                    icon="hard-drive",
                ),
                ResourceType(
                    provider_id=aws.id,
                    name="lambda",
                    display_name="Lambda Function",
                    category="compute",
                    icon="zap",
                ),
                # Azure
                ResourceType(
                    provider_id=azure.id,
                    name="vm",
                    display_name="Virtual Machine",
                    category="compute",
                    icon="server",
                ),
                ResourceType(
                    provider_id=azure.id,
                    name="sql",
                    display_name="SQL Database",
                    category="database",
                    icon="database",
                ),
                ResourceType(
                    provider_id=azure.id,
                    name="storage",
                    display_name="Storage Account",
                    category="storage",
                    icon="hard-drive",
                ),
                ResourceType(
                    provider_id=azure.id,
                    name="function",
                    display_name="Azure Function",
                    category="compute",
                    icon="zap",
                ),
                # GCP
                ResourceType(
                    provider_id=gcp.id,
                    name="compute",
                    display_name="Compute Engine",
                    category="compute",
                    icon="server",
                ),
                ResourceType(
                    provider_id=gcp.id,
                    name="cloudsql",
                    display_name="Cloud SQL",
                    category="database",
                    icon="database",
                ),
                ResourceType(
                    provider_id=gcp.id,
                    name="storage",
                    display_name="Cloud Storage",
                    category="storage",
                    icon="hard-drive",
                ),
                ResourceType(
                    provider_id=gcp.id,
                    name="functions",
                    display_name="Cloud Functions",
                    category="compute",
                    icon="zap",
                ),
            ]

            db.add_all(resource_types)
            db.commit()

            print("✅ Initial data seeded successfully")

    except Exception as e:
        print(f"❌ Error seeding initial data: {e}")


# Database initialization script
async def initialize_database():
    """
    Complete database initialization
    """
    print("🚀 Initializing database...")

    # Create database if it doesn't exist
    await create_database_if_not_exists()

    # Create tables
    create_tables()

    # Setup RLS policies (skipping for now - requires role configuration)
    # setup_rls_policies()

    # Seed initial data
    seed_initial_data()

    # Check connection
    if check_database_connection():
        print("✅ Database initialization completed successfully!")
        return True
    else:
        print("❌ Database initialization failed!")
        return False


# Development utilities
def reset_database():
    """
    Reset database for development (drops and recreates everything)
    """
    print("⚠️ Resetting database (this will delete all data)...")
    drop_tables()
    asyncio.run(initialize_database())


if __name__ == "__main__":
    # Run database initialization
    asyncio.run(initialize_database())
