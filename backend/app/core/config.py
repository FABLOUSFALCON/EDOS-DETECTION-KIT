"""
Configuration settings for the EDoS Security Dashboard
"""

from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "EDoS Security Dashboard"
    VERSION: str = "1.0.0"

    # Environment
    ENVIRONMENT: str = "development"

    # Security
    SECRET_KEY: str = "edos-security-dashboard-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    ALGORITHM: str = "HS256"

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./edos_security.db"

    # Supabase Configuration (for production)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # Redis (for caching)
    REDIS_URL: str = "redis://localhost:6379"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # WebSocket
    WS_MAX_CONNECTIONS: int = 100
    WEBSOCKET_HOST: str = "0.0.0.0"
    # Changed default backend port to avoid local conflicts during development
    WEBSOCKET_PORT: int = 23335

    # Data Generation
    GENERATE_SAMPLE_DATA: bool = True
    DATA_GENERATION_INTERVAL: int = 3  # seconds
    # Debug / engine echo
    DEBUG: bool = False

    @property
    def use_supabase(self) -> bool:
        """Check if Supabase is configured and should be used"""
        return (
            self.SUPABASE_URL is not None
            and self.SUPABASE_KEY is not None
            and self.ENVIRONMENT in ["production", "staging"]
        )

    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL based on configuration"""
        if self.use_supabase:
            # Extract database URL from Supabase URL if not explicitly provided
            if "postgresql://" in self.DATABASE_URL:
                return self.DATABASE_URL
            # Construct from Supabase URL
            project_ref = self.SUPABASE_URL.split("//")[1].split(".")[0]
            return f"postgresql://postgres:password@db.{project_ref}.supabase.co:5432/postgres"
        return self.DATABASE_URL

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
