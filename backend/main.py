"""
EDoS Security Dashboard Backend
A comprehensive FastAPI backend for real-time cybersecurity monitoring
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid


# Helper function for datetime serialization
def serialize_datetime_dict(data) -> Dict[str, Any]:
    """Recursively convert datetime objects to ISO strings for JSON serialization"""
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {key: serialize_datetime_dict(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_datetime_dict(item) for item in data]
    elif hasattr(data, "model_dump"):
        return serialize_datetime_dict(data.model_dump())
    elif hasattr(data, "dict"):
        return serialize_datetime_dict(data.dict())
    else:
        return data


from app.core.config import settings
from app.api import (
    alerts,
    network,
    resources,
    metrics,
    logs,
    settings_api,
    supabase_auth,
    websockets,
    live_monitoring,
    alerts_new,
)
from app.realtime_manager import get_realtime_manager
from app.supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize managers
realtime_manager = get_realtime_manager()
supabase_client = get_supabase_client()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting EDoS Security Dashboard Backend")

    # Log configuration
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Using Supabase: {settings.use_supabase}")
    logger.info(f"Database URL: {settings.effective_database_url[:50]}...")

    # Initialize database
    logger.info("🗄️ Initializing database...")
    try:
        if settings.use_supabase:
            logger.info("🔗 Using Supabase for database operations")
            # Initialize Supabase real-time subscriptions
            await setup_supabase_subscriptions()
        else:
            logger.info("📁 Using local SQLite database")
            from app.database import initialize_database, check_database_connection

            # Check if database is available
            if check_database_connection():
                logger.info("✅ Database connection established")
            else:
                # Try to initialize database
                success = await initialize_database()
                if success:
                    logger.info("✅ Database initialized successfully")
                else:
                    logger.warning("⚠️ Database initialization failed, using mock data")
    except Exception as e:
        logger.warning(
            f"⚠️ Database initialization error: {e}, falling back to mock data"
        )

    # Start ML processor for Redis stream processing
    logger.info("🤖 Starting ML processor for alerts generation...")
    try:
        from app.services.ml_processor import start_ml_processor

        ml_processor_task = asyncio.create_task(start_ml_processor())
        logger.info("✅ ML processor started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start ML processor: {e}")
        ml_processor_task = None

    # Start real-time monitoring for Supabase changes (instead of dummy data generation)
    if settings.use_supabase:
        background_task = asyncio.create_task(monitor_supabase_changes())
    else:
        logger.info("⚠️ Real-time monitoring disabled - Supabase not configured")

    yield

    # Shutdown
    logger.info("🛑 Shutting down EDoS Security Dashboard Backend")
    if "background_task" in locals():
        background_task.cancel()
    if "ml_processor_task" in locals() and ml_processor_task:
        ml_processor_task.cancel()


async def setup_supabase_subscriptions():
    """Setup Supabase real-time subscriptions for database changes"""
    if not settings.use_supabase:
        return

    try:
        logger.info("🔔 Setting up Supabase real-time subscriptions...")

        # Note: Supabase Python SDK real-time subscriptions have limited support
        # For now, we'll rely on our own real-time data generation
        # Real-time subscriptions work better with the JavaScript SDK

        logger.info("✅ Real-time data generation active (using background tasks)")

    except Exception as e:
        logger.error(f"❌ Supabase subscriptions not available in Python SDK: {e}")


# Create FastAPI app
app = FastAPI(
    title="EDoS Security Dashboard API",
    description="A comprehensive cybersecurity monitoring and threat detection API with real-time capabilities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware - Configuration based on environment
cors_origins = settings.BACKEND_CORS_ORIGINS.copy()
if settings.ENVIRONMENT == "development":
    cors_origins.extend(
        [
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:4000",
            "http://127.0.0.1:4000",
        ]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Include API routers
app.include_router(supabase_auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(alerts_new.router, prefix="/api/alerts-new", tags=["New Alerts API"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(resources.router, prefix="/api/resources", tags=["Resources"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(websockets.router, prefix="/ws", tags=["WebSockets"])
app.include_router(
    live_monitoring.router, prefix="/api/ml", tags=["ML Live Monitoring"]
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint with detailed system information"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "edos-security-dashboard",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "database": "supabase" if settings.use_supabase else "sqlite",
        "realtime_connections": realtime_manager.get_connection_stats(),
    }


# Remove the old WebSocket endpoints - these are now in websockets.py


# Real-time monitoring for Supabase changes
async def monitor_supabase_changes():
    """Monitor Supabase for real database changes and broadcast to connected clients"""
    logger.info("🔄 Starting Supabase real-time monitoring")

    while True:
        try:
            # In a real implementation, this would:
            # 1. Listen to Supabase real-time subscriptions
            # 2. Query for recent alerts, logs, metrics from the database
            # 3. Broadcast only real data to WebSocket clients

            # For now, we'll poll the database periodically for new data
            # This is better than generating dummy data

            # Check for new alerts from the last minute
            try:
                response = (
                    supabase_client.table("security_alerts")
                    .select("*")
                    .gte(
                        "detected_at",
                        (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
                    )
                    .execute()
                )

                if response.data:
                    for alert in response.data:
                        await realtime_manager.broadcast_to_topic(
                            "alerts", {"type": "new_alert", "data": alert}
                        )
                        # Also broadcast to user-specific channel if user_id exists
                        if alert.get("user_id"):
                            await realtime_manager.broadcast_to_topic(
                                f"alerts_user_{alert['user_id']}",
                                {"type": "new_alert", "data": alert},
                            )

            except Exception as e:
                logger.debug(f"No new alerts or error fetching: {e}")

            # Check for new logs
            try:
                response = (
                    supabase_client.table("system_logs")
                    .select("*")
                    .gte(
                        "timestamp",
                        (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
                    )
                    .execute()
                )

                if response.data:
                    for log in response.data:
                        await realtime_manager.broadcast_to_topic(
                            "logs", {"type": "new_log", "data": log}
                        )

            except Exception as e:
                logger.debug(f"No new logs or error fetching: {e}")

            # For metrics, we can still generate some real-time system metrics
            # since these are about the actual system performance
            current_time = datetime.utcnow()
            system_metrics = {
                "timestamp": current_time.isoformat(),
                "cpu_usage": 45.0,  # In production, get from actual system
                "memory_usage": 68.0,  # In production, get from actual system
                "network_io": 156.7,  # In production, get from actual system
                "active_connections": len(realtime_manager.get_connection_stats()),
            }

            await realtime_manager.broadcast_to_topic(
                "metrics", {"type": "metrics_update", "data": system_metrics}
            )

            # Wait before next check (every 30 seconds for real data)
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Error in Supabase monitoring: {e}")
            await asyncio.sleep(10)  # Wait longer on error


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "EDoS Security Dashboard API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "database": "supabase" if settings.use_supabase else "sqlite",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "websockets": {
            "alerts": "/ws/alerts",
            "alerts_user": "/ws/alerts/{user_id}",
            "metrics": "/ws/metrics",
            "network": "/ws/network",
            "logs": "/ws/logs",
            "resources": "/ws/resources",
        },
        "realtime_stats": realtime_manager.get_connection_stats(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.WEBSOCKET_HOST,
        port=settings.WEBSOCKET_PORT,
        reload=True,
        log_level="info",
    )
