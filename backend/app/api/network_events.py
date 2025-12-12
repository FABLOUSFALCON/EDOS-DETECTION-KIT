"""
Network Events API for Threat Map
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from ..services.network_processor import network_processor, simulate_ml_events
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network-events", tags=["network-events"])


class NetworkEventRequest(BaseModel):
    ip: str
    is_attack: bool
    confidence: float
    timestamp: Optional[str] = None


@router.post("/publish")
async def publish_network_event(event: NetworkEventRequest):
    """Publish a network event to the ML stream (for testing)"""
    try:
        import redis.asyncio as redis
        from datetime import datetime

        redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )

        event_data = {
            "ip": event.ip,
            "is_attack": str(event.is_attack).lower(),
            "confidence": str(event.confidence),
            "timestamp": event.timestamp or datetime.utcnow().isoformat(),
        }

        message_id = await redis_client.xadd("ml:network_events", event_data)
        await redis_client.close()

        logger.info(f"📡 Published network event: {event_data}")

        return {"status": "published", "message_id": message_id, "event": event_data}

    except Exception as e:
        logger.error(f"❌ Error publishing network event: {e}")
        raise HTTPException(status_code=500, detail=f"Publishing error: {str(e)}")


@router.get("/stream-info")
async def get_stream_info():
    """Get information about the network events stream"""
    try:
        return await network_processor.get_stream_info()
    except Exception as e:
        logger.error(f"❌ Error getting stream info: {e}")
        raise HTTPException(status_code=500, detail=f"Stream info error: {str(e)}")


@router.post("/start-processor")
async def start_network_processor(background_tasks: BackgroundTasks):
    """Start the network event processor"""
    try:
        if not network_processor.running:
            background_tasks.add_task(network_processor.start_processing)
            return {"status": "started", "message": "Network event processor started"}
        else:
            return {
                "status": "already_running",
                "message": "Network event processor is already running",
            }
    except Exception as e:
        logger.error(f"❌ Error starting processor: {e}")
        raise HTTPException(status_code=500, detail=f"Processor start error: {str(e)}")


@router.post("/stop-processor")
async def stop_network_processor():
    """Stop the network event processor"""
    try:
        await network_processor.stop_processing()
        return {"status": "stopped", "message": "Network event processor stopped"}
    except Exception as e:
        logger.error(f"❌ Error stopping processor: {e}")
        raise HTTPException(status_code=500, detail=f"Processor stop error: {str(e)}")


@router.post("/simulate-events")
async def start_event_simulation(background_tasks: BackgroundTasks):
    """Start simulating ML network events for testing"""
    try:
        background_tasks.add_task(simulate_ml_events)
        return {"status": "started", "message": "Event simulation started"}
    except Exception as e:
        logger.error(f"❌ Error starting simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


@router.get("/recent-events")
async def get_recent_events(limit: int = 50):
    """Get recent network events from the stream"""
    try:
        import redis.asyncio as redis

        redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )

        # Get recent events from the stream
        events = await redis_client.xrevrange("ml:network_events", count=limit)
        await redis_client.close()

        # Format events for response
        formatted_events = []
        for event_id, fields in events:
            formatted_events.append(
                {
                    "id": event_id,
                    "timestamp": fields.get("timestamp"),
                    "ip": fields.get("ip"),
                    "is_attack": fields.get("is_attack", "false").lower() == "true",
                    "confidence": float(fields.get("confidence", 0.0)),
                }
            )

        return {"events": formatted_events, "count": len(formatted_events)}

    except Exception as e:
        logger.error(f"❌ Error getting recent events: {e}")
        raise HTTPException(status_code=500, detail=f"Events retrieval error: {str(e)}")
