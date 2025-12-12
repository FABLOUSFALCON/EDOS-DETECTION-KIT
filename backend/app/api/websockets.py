"""
WebSocket endpoints for real-time data streaming
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import json
import asyncio
import logging
from datetime import datetime

from ..api.supabase_auth import verify_token
from ..realtime_manager import get_realtime_manager
from ..services.data_generator import DataGenerator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/alerts/{user_id}")
async def websocket_alerts(
    websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)
):
    """WebSocket endpoint for real-time alerts"""

    # Verify authentication
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        # Verify the token
        token_data = await verify_token_ws(token)
        if token_data["user_id"] != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return

    except Exception as e:
        await websocket.close(code=4001, reason="Invalid token")
        return

    realtime_manager = get_realtime_manager()
    data_generator = DataGenerator()

    try:
        # Connect to real-time manager
        await realtime_manager.connect(websocket, "alerts", user_id)
        logger.info(f"User {user_id} connected to alerts WebSocket")

        # Send initial alerts
        initial_alerts = data_generator.generate_alerts(count=5, user_id=user_id)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "initial_alerts",
                    "data": initial_alerts,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Start streaming real-time alerts
        alert_task = asyncio.create_task(
            stream_alerts(websocket, user_id, data_generator)
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (like resource selection)
                message = await websocket.receive_text()
                data = json.loads(message)

                if data.get("type") == "resource_selected":
                    # Update user's selected resource for targeted alerts
                    resource_id = data.get("resource_id")
                    logger.info(f"User {user_id} selected resource {resource_id}")

                    # Send resource-specific alerts
                    resource_alerts = data_generator.generate_resource_alerts(
                        resource_id=resource_id, user_id=user_id, count=3
                    )
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "resource_alerts",
                                "data": resource_alerts,
                                "resource_id": resource_id,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from alerts WebSocket")
    except Exception as e:
        logger.error(f"Error in alerts WebSocket for user {user_id}: {e}")
    finally:
        # Clean up
        await realtime_manager.disconnect(websocket, "alerts", user_id)
        if "alert_task" in locals():
            alert_task.cancel()


@router.websocket("/metrics/{user_id}")
async def websocket_metrics(
    websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)
):
    """WebSocket endpoint for real-time metrics"""

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        token_data = await verify_token_ws(token)
        if token_data["user_id"] != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except:
        await websocket.close(code=4001, reason="Invalid token")
        return

    realtime_manager = get_realtime_manager()
    data_generator = DataGenerator()

    try:
        await realtime_manager.connect(websocket, "metrics", user_id)
        logger.info(f"User {user_id} connected to metrics WebSocket")

        # Stream real-time metrics
        while True:
            metrics = data_generator.generate_metrics(user_id=user_id)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "metrics_update",
                        "data": metrics,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            await asyncio.sleep(5)  # Update every 5 seconds

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from metrics WebSocket")
    finally:
        await realtime_manager.disconnect(websocket, "metrics", user_id)


@router.websocket("/network/{user_id}")
async def websocket_network(
    websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)
):
    """WebSocket endpoint for real-time network data"""

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        token_data = await verify_token_ws(token)
        if token_data["user_id"] != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except:
        await websocket.close(code=4001, reason="Invalid token")
        return

    realtime_manager = get_realtime_manager()
    data_generator = DataGenerator()

    try:
        await realtime_manager.connect(websocket, "network", user_id)
        logger.info(f"User {user_id} connected to network WebSocket")

        # Stream real-time network data
        while True:
            network_data = data_generator.generate_network_activity(user_id=user_id)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "network_update",
                        "data": network_data,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            await asyncio.sleep(2)  # Update every 2 seconds

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from network WebSocket")
    finally:
        await realtime_manager.disconnect(websocket, "network", user_id)


async def verify_token_ws(token: str) -> dict:
    """Verify token for WebSocket connections"""
    import jwt
    import os

    SUPABASE_JWT_SECRET = os.getenv(
        "SUPABASE_JWT_SECRET", "your-jwt-secret-from-supabase"
    )

    payload = jwt.decode(
        token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False}
    )

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


async def stream_alerts(
    websocket: WebSocket, user_id: str, data_generator: DataGenerator
):
    """Background task to stream alerts to user"""
    try:
        while True:
            # Generate new alert for this user
            new_alert = data_generator.generate_single_alert(user_id=user_id)

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "new_alert",
                        "data": new_alert,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            # Random interval between 10-30 seconds
            import random

            await asyncio.sleep(random.randint(10, 30))

    except asyncio.CancelledError:
        logger.info(f"Alert streaming cancelled for user {user_id}")
    except Exception as e:
        logger.error(f"Error streaming alerts for user {user_id}: {e}")


# ============================================================================
# ML PREDICTIONS STREAMING WEBSOCKET (NO AUTH REQUIRED FOR MONITOR)
# ============================================================================

import redis.asyncio as redis
from typing import List


class MLConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"ML WebSocket connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"ML WebSocket disconnected. Total connections: {len(self.active_connections)}"
        )

    async def broadcast(self, message: str):
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to ML WebSocket: {e}")
                disconnected_connections.append(connection)

        # Clean up disconnected connections
        for conn in disconnected_connections:
            self.disconnect(conn)


ml_manager = MLConnectionManager()


class RedisStreamListener:
    def __init__(self):
        self.redis_client = None
        self.is_listening = False

    async def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url("redis://localhost:6379/0")
            await self.redis_client.ping()
            logger.info("Connected to Redis for ML WebSocket streaming")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis for ML streaming: {e}")
            return False

    async def listen_to_stream(self):
        """Listen to Redis stream and broadcast to all connected WebSocket clients"""
        if not self.redis_client:
            if not await self.connect_redis():
                return

        self.is_listening = True
        logger.info("Starting Redis stream listener for ML WebSocket broadcasting")

        try:
            # Read from the stream starting from the latest messages
            last_id = "$"  # Start from latest

            while self.is_listening and ml_manager.active_connections:
                try:
                    # Read new messages from Redis stream
                    messages = await self.redis_client.xread(
                        {"ml:predictions": last_id},
                        count=10,
                        block=1000,  # Block for 1 second
                    )

                    if messages:
                        for stream_name, stream_messages in messages:
                            for message_id, fields in stream_messages:
                                try:
                                    # Parse the Redis message
                                    message_data = {}
                                    for key, value in fields.items():
                                        key_str = (
                                            key.decode()
                                            if isinstance(key, bytes)
                                            else key
                                        )
                                        value_str = (
                                            value.decode()
                                            if isinstance(value, bytes)
                                            else value
                                        )

                                        if key_str in ["predictions", "statistics"]:
                                            # Parse JSON fields
                                            message_data[key_str] = json.loads(
                                                value_str
                                            )
                                        else:
                                            message_data[key_str] = value_str

                                    # Add message metadata
                                    message_data["message_id"] = (
                                        message_id.decode()
                                        if isinstance(message_id, bytes)
                                        else message_id
                                    )

                                    # Broadcast to all connected WebSocket clients
                                    await ml_manager.broadcast(json.dumps(message_data))
                                    logger.debug(
                                        f"Broadcasted ML prediction to {len(ml_manager.active_connections)} clients"
                                    )

                                    # Update last_id for next read
                                    last_id = message_id

                                except Exception as e:
                                    logger.error(f"Error processing Redis message: {e}")

                    # If no active connections, pause the listener
                    if not ml_manager.active_connections:
                        logger.info(
                            "No active ML WebSocket connections, pausing Redis listener"
                        )
                        await asyncio.sleep(5)

                except Exception as e:
                    logger.error(f"Error reading from Redis stream: {e}")
                    await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Redis stream listener error: {e}")
        finally:
            self.is_listening = False
            if self.redis_client:
                await self.redis_client.close()
            logger.info("Redis stream listener stopped")

    async def stop_listening(self):
        """Stop the Redis stream listener"""
        self.is_listening = False


# Global Redis listener instance for ML predictions
ml_redis_listener = RedisStreamListener()


@router.websocket("/ml/live")
async def websocket_ml_predictions(websocket: WebSocket):
    """WebSocket endpoint for real-time ML prediction streaming - NO AUTH REQUIRED"""
    await ml_manager.connect(websocket)

    # Start Redis listener if not already running and we have connections
    if not ml_redis_listener.is_listening and ml_manager.active_connections:
        logger.info("Starting Redis stream listener for new ML WebSocket connection")
        # Start the Redis listener in the background
        asyncio.create_task(ml_redis_listener.listen_to_stream())

    try:
        # Send initial connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_status",
                    "status": "connected",
                    "message": "WebSocket connected to ML prediction stream",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Keep the connection alive
        while True:
            try:
                # Wait for messages from client (like heartbeat)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Echo back any received messages
                try:
                    client_message = json.loads(data)
                    if client_message.get("type") == "ping":
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "timestamp": client_message.get("timestamp"),
                                    "server_timestamp": datetime.now().isoformat(),
                                }
                            )
                        )
                except json.JSONDecodeError:
                    # Ignore non-JSON messages
                    pass

            except asyncio.TimeoutError:
                # Send periodic heartbeat to keep connection alive
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.now().isoformat(),
                            "active_connections": len(ml_manager.active_connections),
                        }
                    )
                )

    except WebSocketDisconnect:
        ml_manager.disconnect(websocket)
        logger.info("ML WebSocket disconnected")
    except Exception as e:
        logger.error(f"ML WebSocket error: {e}")
        ml_manager.disconnect(websocket)


@router.websocket("/network-analysis")
async def websocket_network_analysis(websocket: WebSocket):
    """WebSocket endpoint for real-time network analysis data"""
    import redis.asyncio as aioredis

    await websocket.accept()
    logger.info("🌐 Network analysis WebSocket connected")

    # Connect to Redis
    redis_client = None
    try:
        redis_client = aioredis.from_url(
            "redis://localhost:6379", decode_responses=True
        )
        await redis_client.ping()
        logger.info("✅ Connected to Redis for network analysis")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        await websocket.close(code=4000, reason="Redis connection failed")
        return

    try:
        while True:
            try:
                # Check if WebSocket is still connected before sending
                if websocket.client_state.name == "DISCONNECTED":
                    logger.info(
                        "🔌 Network analysis WebSocket disconnected, breaking loop"
                    )
                    break

                # Get latest network analysis data from Redis
                data = await redis_client.get("network_analysis:latest")

                if data:
                    # Parse and send the data
                    network_data = json.loads(data)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "network_analysis",
                                "data": network_data,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )
                    logger.debug("📡 Sent network analysis data to WebSocket")
                else:
                    # Send empty data if no Redis data available
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "network_analysis",
                                "data": None,
                                "error": "No data available",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )

                # Wait 2 seconds before next update (same as the Python service)
                await asyncio.sleep(2)

            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error: {e}")
                if websocket.client_state.name != "DISCONNECTED":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "message": "Invalid data format",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"❌ Error in network analysis loop: {e}")
                # Don't try to send if connection is closed
                if "send" not in str(e) and "close" not in str(e):
                    await asyncio.sleep(5)
                else:
                    logger.info("🔌 WebSocket connection closed, breaking loop")
                    break

    except WebSocketDisconnect:
        logger.info("🔌 Network analysis WebSocket disconnected")
    except Exception as e:
        logger.error(f"💥 Network analysis WebSocket error: {e}")
    finally:
        if redis_client:
            await redis_client.close()
            logger.info("🔒 Redis connection closed")


@router.websocket("/threat_map/{resource_id}")
async def websocket_threat_map(websocket: WebSocket, resource_id: str):
    """WebSocket endpoint for resource-specific real-time threat map updates"""

    from ..core.websocket_manager import websocket_manager

    try:
        # Connect to resource-specific channel
        resource_channel = f"threat_map_{resource_id}"
        await websocket_manager.connect(websocket, resource_channel)
        logger.info(
            f"🌍 Client connected to threat map WebSocket for resource: {resource_id}"
        )

        # Send initial connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_established",
                    "message": "Connected to threat map updates",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any incoming messages from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle different message types if needed
                if message.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        )
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"❌ Error handling threat map message: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"🌍 Threat map WebSocket disconnected for resource: {resource_id}")
    except Exception as e:
        logger.error(f"💥 Threat map WebSocket error for resource {resource_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket, resource_channel)
        logger.info(
            f"🌍 Threat map WebSocket connection closed for resource: {resource_id}"
        )
