import json
import uuid
import datetime
import logging
from typing import Optional

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

REDIS_STREAM = "ml:predictions"
NETWORK_EVENTS_STREAM = "ml:network_events"


async def publish_prediction(
    prediction: dict,
    client_id: str,
    resource_id: str,
    flow_meta: Optional[dict] = None,
    message_id: Optional[str] = None,
) -> Optional[str]:
    """Publish a single prediction message to Redis Streams.

    - `prediction` should be a serializable dict (prediction details)
    - `flow_meta` is a very small dict with only necessary fields (src_ip, dst_ip, dst_port, timestamp)
    - returns the Redis entry id or None on failure
    """
    try:
        redis = aioredis.from_url(settings.REDIS_URL)

        msg = {
            "message_id": message_id or str(uuid.uuid4()),
            "timestamp": (flow_meta or {}).get("timestamp")
            or datetime.datetime.utcnow().isoformat(),
            "client_id": client_id,
            "resource_id": resource_id,
            # Keep flow metadata minimal to save bandwidth/storage
            "flow_meta": flow_meta or {},
            "prediction": prediction,
            "source": "beast_mode_api",
        }

        # XADD with a single field `msg` containing JSON for simplicity
        entry_id = await redis.xadd(REDIS_STREAM, {"msg": json.dumps(msg)})
        # set a short TTL on a processed key namespace? not here
        logger.debug(f"Published prediction to stream {REDIS_STREAM} id={entry_id}")
        await redis.close()
        return entry_id

    except Exception as e:
        logger.exception(f"Failed to publish prediction to Redis: {e}")
        return None


async def publish_batch_results(
    batch_results: dict,
    client_id: str,
    resource_id: str,
    message_id: Optional[str] = None,
) -> Optional[str]:
    """Publish complete batch processing results to Redis Streams.

    - `batch_results` should contain predictions and statistics from batch processing
    - returns the Redis entry id or None on failure
    """
    try:
        redis = aioredis.from_url(settings.REDIS_URL)

        msg = {
            "message_id": message_id or str(uuid.uuid4()),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "client_id": client_id,
            "resource_id": resource_id,
            "batch_results": batch_results,
            "source": "beast_mode_batch_api",
        }

        # XADD with a single field `msg` containing JSON for simplicity
        entry_id = await redis.xadd(REDIS_STREAM, {"msg": json.dumps(msg)})
        logger.debug(f"Published batch results to stream {REDIS_STREAM} id={entry_id}")
        await redis.close()
        return entry_id

    except Exception as e:
        logger.exception(f"Failed to publish batch results to Redis: {e}")
        return None


async def publish_network_event(
    source_ip: str,
    is_attack: bool,
    confidence: float,
    flow_meta: Optional[dict] = None,
) -> Optional[str]:
    """Publish network event to dedicated threat map stream.

    - `source_ip` is the IP address that generated the traffic
    - `is_attack` indicates if this is classified as an attack
    - `confidence` is the ML model confidence score (0.0-1.0)
    - `flow_meta` contains additional flow metadata
    - returns the Redis entry id or None on failure
    """
    try:
        redis = aioredis.from_url(settings.REDIS_URL)

        event = {
            "ip": source_ip,
            "is_attack": str(is_attack).lower(),
            "confidence": str(confidence),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "flow_meta": flow_meta or {},
        }

        # Publish to dedicated network events stream for threat map
        entry_id = await redis.xadd(NETWORK_EVENTS_STREAM, event)
        logger.debug(
            f"Published network event to stream {NETWORK_EVENTS_STREAM} id={entry_id}"
        )
        await redis.close()
        return entry_id

    except Exception as e:
        logger.exception(f"Failed to publish network event to Redis: {e}")
        return None
