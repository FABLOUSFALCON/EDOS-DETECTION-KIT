import json
import uuid
import datetime
import logging
from typing import Optional

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

REDIS_STREAM = "ml:predictions"


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
