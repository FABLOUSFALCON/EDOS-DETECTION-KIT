"""
Live ML Monitoring API for EDoS Security Dashboard
Real-time streaming of ML predictions from Redis
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import asyncio
import json
import redis.asyncio as aioredis
from datetime import datetime
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ================================
# SCHEMAS
# ================================


class MLPrediction(BaseModel):
    """Individual ML prediction result"""

    is_attack: bool
    attack_probability: float
    benign_probability: float
    confidence: float
    model_version: str
    attack_type: Optional[str] = None


class BatchStatistics(BaseModel):
    """Batch processing statistics"""

    total_flows: int
    attack_predictions: int
    benign_predictions: int
    processing_time_ms: float
    throughput_flows_per_sec: float
    average_confidence: float


class LiveBatchResult(BaseModel):
    """Complete batch result from Redis stream"""

    message_id: str
    timestamp: str
    client_id: str
    resource_id: str
    source: str
    predictions: List[MLPrediction]
    statistics: BatchStatistics


class LiveMonitoringResponse(BaseModel):
    """Response for live monitoring endpoint"""

    total_entries: int
    latest_batches: List[LiveBatchResult]
    threat_summary: Dict[str, Any]


# ================================
# REDIS STREAM UTILITIES
# ================================


async def get_redis_connection():
    """Get Redis connection"""
    try:
        redis = aioredis.from_url(settings.REDIS_URL or "redis://localhost:6379")
        return redis
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise HTTPException(status_code=503, detail="Redis connection failed")


async def parse_redis_entry(
    entry_id: str, fields: Dict[bytes, bytes]
) -> Optional[LiveBatchResult]:
    """Parse a Redis stream entry into a LiveBatchResult"""
    try:
        # Decode the message
        msg_data = json.loads(fields[b"msg"].decode())

        # Skip if not a batch result
        if "batch_results" not in msg_data:
            return None

        batch_data = msg_data["batch_results"]

        # Parse predictions
        predictions = []
        for pred in batch_data.get("predictions", []):
            predictions.append(MLPrediction(**pred))

        # Parse statistics
        stats = BatchStatistics(**batch_data["statistics"])

        return LiveBatchResult(
            message_id=msg_data.get("message_id", ""),
            timestamp=msg_data.get("timestamp", ""),
            client_id=msg_data.get("client_id", ""),
            resource_id=msg_data.get("resource_id", ""),
            source=msg_data.get("source", ""),
            predictions=predictions,
            statistics=stats,
        )

    except Exception as e:
        logger.warning(f"Failed to parse Redis entry {entry_id}: {e}")
        return None


# ================================
# API ENDPOINTS
# ================================


@router.get("/live/latest", response_model=LiveMonitoringResponse)
async def get_latest_predictions(limit: int = 10):
    """Get the latest ML prediction batches from Redis stream"""

    redis = await get_redis_connection()

    try:
        # Get stream info
        stream_length = await redis.xlen("ml:predictions")

        # Get latest entries
        raw_entries = await redis.xrevrange("ml:predictions", count=limit)

        # Parse entries
        batches = []
        total_attacks = 0
        total_flows = 0

        for entry_id, fields in raw_entries:
            parsed = await parse_redis_entry(entry_id.decode(), fields)
            if parsed:
                batches.append(parsed)
                total_attacks += parsed.statistics.attack_predictions
                total_flows += parsed.statistics.total_flows

        # Calculate threat summary
        attack_rate = (total_attacks / total_flows * 100) if total_flows > 0 else 0
        threat_level = (
            "CRITICAL"
            if attack_rate >= 80
            else (
                "HIGH"
                if attack_rate >= 50
                else (
                    "MEDIUM"
                    if attack_rate >= 20
                    else "LOW" if attack_rate > 0 else "NORMAL"
                )
            )
        )

        threat_summary = {
            "total_flows_monitored": total_flows,
            "total_attacks_detected": total_attacks,
            "attack_rate_percent": round(attack_rate, 2),
            "threat_level": threat_level,
            "active_clients": len(set(b.client_id for b in batches)),
            "active_resources": len(set(b.resource_id for b in batches)),
            "last_update": datetime.utcnow().isoformat(),
        }

        return LiveMonitoringResponse(
            total_entries=stream_length,
            latest_batches=batches,
            threat_summary=threat_summary,
        )

    finally:
        await redis.aclose()


@router.get("/live/stream")
async def stream_predictions():
    """Server-Sent Events stream of real-time ML predictions"""

    async def generate_events():
        redis = await get_redis_connection()
        last_id = "$"  # Start from new messages

        try:
            while True:
                try:
                    # Read new entries with blocking
                    entries = await redis.xread(
                        {"ml:predictions": last_id},
                        count=1,
                        block=5000,  # 5 second timeout
                    )

                    if entries:
                        stream_name, messages = entries[0]
                        for entry_id, fields in messages:
                            # Parse the entry
                            parsed = await parse_redis_entry(entry_id.decode(), fields)
                            if parsed:
                                # Send as SSE
                                event_data = {
                                    "type": "new_batch",
                                    "data": parsed.dict(),
                                }
                                yield f"data: {json.dumps(event_data)}\n\n"

                            last_id = entry_id.decode()

                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

                except asyncio.TimeoutError:
                    # Send heartbeat on timeout
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    await asyncio.sleep(1)

        finally:
            await redis.aclose()

    return StreamingResponse(
        generate_events(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/live/stats")
async def get_live_stats():
    """Get current live monitoring statistics"""

    redis = await get_redis_connection()

    try:
        # Get stream info
        stream_length = await redis.xlen("ml:predictions")

        # Get last 100 entries to calculate recent stats
        recent_entries = await redis.xrevrange("ml:predictions", count=100)

        recent_attacks = 0
        recent_flows = 0
        clients = set()
        resources = set()

        for entry_id, fields in recent_entries:
            try:
                msg_data = json.loads(fields[b"msg"].decode())
                if "batch_results" in msg_data:
                    batch = msg_data["batch_results"]
                    stats = batch.get("statistics", {})
                    recent_attacks += stats.get("attack_predictions", 0)
                    recent_flows += stats.get("total_flows", 0)
                    clients.add(msg_data.get("client_id", "unknown"))
                    resources.add(msg_data.get("resource_id", "unknown"))
            except:
                continue

        return {
            "stream_length": stream_length,
            "recent_flows": recent_flows,
            "recent_attacks": recent_attacks,
            "recent_attack_rate": round(
                (recent_attacks / recent_flows * 100) if recent_flows > 0 else 0, 2
            ),
            "active_clients": len(clients),
            "active_resources": len(resources),
            "clients": list(clients),
            "resources": list(resources),
            "timestamp": datetime.utcnow().isoformat(),
        }

    finally:
        await redis.aclose()
