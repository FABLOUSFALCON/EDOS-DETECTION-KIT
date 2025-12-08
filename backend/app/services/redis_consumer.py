import asyncio
import json
import logging
import time
from typing import Any, Dict

import redis.asyncio as aioredis
from app.core.config import settings
from app.database import get_db_context
from app.models.database import SecurityAlert, UserResource
from datetime import datetime
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)

STREAM_KEY = "ml:predictions"
CONSUMER_GROUP = "ml_consumers"
DLQ_STREAM = "ml:predictions:dlq"
CONSUMER_NAME_PREFIX = "alerts_worker"
PROCESS_TTL_SECONDS = 24 * 60 * 60  # processed id TTL
MAX_RETRIES = 5
READ_COUNT = 100
BLOCK_MS = 5000
CLAIM_MIN_IDLE_MS = 0  # For dev: claim pending entries immediately on startup (ms)


async def ensure_group(redis: aioredis.Redis):
    try:
        # Create group starting from 0 (oldest) if not exists
        await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="$", mkstream=True)
        logger.info(f"Created consumer group {CONSUMER_GROUP} on {STREAM_KEY}")
    except Exception as e:
        # If group exists, ignore
        if "BUSYGROUP" in str(e) or "exists" in str(e).lower():
            logger.debug("Consumer group already exists")
        else:
            logger.warning(f"Could not create consumer group: {e}")


async def process_message(redis: aioredis.Redis, entry_id: str, msg: Dict[str, Any]):
    """Process a single ML prediction message."""
    # Normalize and decode payload
    raw_fields = msg
    payload = None
    if isinstance(msg, dict):
        payload = msg.get("msg") if "msg" in msg else msg.get(b"msg")

    if payload is None and isinstance(msg, dict) and len(msg) > 0:
        payload = next(iter(msg.values()))

    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode()
        except Exception:
            payload = str(payload)

    if payload is None:
        logger.warning(f"No payload found for entry {entry_id}; moving to DLQ")
        await redis.xadd(
            DLQ_STREAM, {"msg": json.dumps({"raw_fields": str(raw_fields)})}
        )
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        return

    try:
        obj = json.loads(payload)
    except Exception as e:
        logger.exception(f"Failed to parse JSON for entry {entry_id}: {e}")
        await redis.xadd(DLQ_STREAM, {"msg": json.dumps({"raw": str(payload)})})
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        return

    message_id = obj.get("message_id")
    client_id = obj.get("client_id")
    resource_id = obj.get("resource_id")
    prediction = obj.get("prediction")
    flow_meta = obj.get("flow_meta") or obj.get("flow") or {}

    # Validate required fields
    if not message_id or not client_id or not resource_id or not prediction:
        logger.warning(f"Missing required fields in message {entry_id}; sending to DLQ")
        await redis.xadd(DLQ_STREAM, {"msg": json.dumps(obj)})
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        return

    # Idempotency check
    processed_key = f"ml:processed:{message_id}"
    try:
        was_set = await redis.set(processed_key, "1", nx=True, ex=PROCESS_TTL_SECONDS)
    except Exception:
        was_set = True

    if not was_set:
        logger.debug(f"Message {message_id} already processed; acking entry {entry_id}")
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        return

    # Determine if attack
    try:
        is_attack = bool(prediction.get("is_attack"))
    except Exception:
        is_attack = False

    # Attempt ORM lookup first; if it fails, fallback to raw SQL lookup
    user_id = None
    res = None
    try:
        with get_db_context() as db:
            res = (
                db.query(UserResource)
                .filter(UserResource.resource_id == resource_id)
                .first()
            )
            if res:
                user_id = getattr(res, "user_id", None)
    except Exception as orm_err:
        logger.debug(f"ORM lookup failed for resource_id={resource_id}: {orm_err}")
        # fallback to raw SQL
        try:
            with get_db_context() as db:
                row = db.execute(
                    text(
                        "SELECT id, user_id FROM cloud_resources WHERE identifier = :ident LIMIT 1"
                    ),
                    {"ident": resource_id},
                ).first()
                if row:
                    resource_db_id = row[0]
                    user_id = row[1]
                else:
                    user_id = None
        except Exception as raw_err:
            logger.exception(
                f"Raw SQL lookup failed for resource_id={resource_id}: {raw_err}"
            )
            user_id = None

    if not user_id:
        logger.warning(
            f"Unknown resource_id {resource_id} for message {message_id} - acking and dropping"
        )
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        return

    # If attack -> persist alert (try ORM then raw SQL)
    if is_attack:
        try:
            # Try ORM-based insert if models align
            with get_db_context() as db:
                # NEW INVERTED LOGIC SEVERITY CALCULATION
                # Lower attack_probability = higher confidence it's an attack
                severity = "low"
                try:
                    conf = float(prediction.get("confidence", 0.0))
                    attack_prob = float(prediction.get("attack_probability", 1.0))
                    
                    # Inverted logic: LOW attack_probability indicates HIGH attack confidence
                    # Convert to attack confidence: lower prob = higher confidence
                    attack_confidence = 1.0 - attack_prob
                    
                    if attack_confidence >= 0.8 and conf >= 0.8:  # Very high confidence
                        severity = "critical"
                    elif attack_confidence >= 0.6 and conf >= 0.6:  # High confidence
                        severity = "high"
                    elif attack_confidence >= 0.4 and conf >= 0.4:  # Medium confidence
                        severity = "medium"
                    else:
                        severity = "low"
                except Exception:
                    severity = "medium"  # Default to medium for attacks

                alert = SecurityAlert(
                    user_id=user_id,
                    resource_id=res.id if res else None,
                    type=prediction.get("attack_type") or "ml_detected",
                    category="network",
                    severity=severity,
                    title=f"ML-Detected Attack ({prediction.get('model_version')})",
                    description=(
                        f"ML detected attack with confidence {prediction.get('confidence')} and probability {prediction.get('attack_probability')}"
                    ),
                    source_ip=flow_meta.get("src_ip"),
                    target_ip=flow_meta.get("dst_ip"),
                    target_port=flow_meta.get("dst_port"),
                    detection_method=prediction.get("model_version"),
                    confidence_score=(float(prediction.get("confidence", 0.0)) * 100),
                    status="new",
                    raw_data={
                        "message_id": message_id,
                        "prediction": prediction,
                        "flow_meta": flow_meta,
                        "received_at": datetime.utcnow().isoformat(),
                    },
                    detected_at=datetime.utcnow(),
                )

                db.add(alert)
                db.commit()
                db.refresh(alert)

                # broadcast
                try:
                    from app.realtime_manager import get_realtime_manager

                    rm = get_realtime_manager()
                    alert_data = {
                        "type": "new_alert",
                        "data": {
                            "id": str(alert.id),
                            "severity": alert.severity,
                            "title": alert.title,
                            "description": alert.description,
                            "source_ip": (
                                str(alert.source_ip) if alert.source_ip else None
                            ),
                            "target_port": alert.target_port,
                            "confidence": (
                                float(alert.confidence_score)
                                if alert.confidence_score
                                else 0
                            ),
                            "detected_at": alert.detected_at.isoformat(),
                            "status": alert.status,
                            "attack_type": alert.type,
                        },
                    }
                    await rm.broadcast_to_topic(f"alerts_user_{user_id}", alert_data)
                    await rm.broadcast_to_topic("alerts", alert_data)
                except Exception:
                    logger.debug("Failed to broadcast alert after DB insert")

        except Exception as orm_insert_err:
            logger.debug(
                f"ORM insert failed, falling back to raw SQL insert: {orm_insert_err}"
            )
            try:
                with get_db_context() as db:
                    insert_sql = text(
                        "INSERT INTO security_alerts (id, user_id, resource_id, category_id, severity, title, description, source_ip, target_ip, target_port, detection_method, confidence_score, status, raw_data, detected_at, created_at, updated_at) VALUES (uuid_generate_v4(), :user_id, :resource_db_id, NULL, :severity, :title, :description, :source_ip, :target_ip, :target_port, :detection_method, :confidence_score, 'new', CAST(:raw_data AS jsonb), NOW(), NOW(), NOW()) RETURNING id"
                    )

                    raw_data_json = json.dumps(
                        {
                            "message_id": message_id,
                            "prediction": prediction,
                            "flow_meta": flow_meta,
                            "received_at": datetime.utcnow().isoformat(),
                        }
                    )

                    # NEW INVERTED LOGIC SEVERITY CALCULATION (Raw SQL)
                    severity = "low"
                    try:
                        conf = float(prediction.get("confidence", 0.0))
                        attack_prob = float(prediction.get("attack_probability", 1.0))
                        
                        # Inverted logic: LOW attack_probability indicates HIGH attack confidence
                        attack_confidence = 1.0 - attack_prob
                        
                        if attack_confidence >= 0.8 and conf >= 0.8:
                            severity = "critical"
                        elif attack_confidence >= 0.6 and conf >= 0.6:
                            severity = "high"
                        elif attack_confidence >= 0.4 and conf >= 0.4:
                            severity = "medium"
                        else:
                            severity = "low"
                    except Exception:
                        severity = "medium"
                            severity = "medium"
                    except Exception:
                        severity = "low"

                    res_sql = db.execute(
                        insert_sql,
                        {
                            "user_id": user_id,
                            "resource_db_id": (
                                resource_db_id if "resource_db_id" in locals() else None
                            ),
                            "severity": severity,
                            "title": f"ML-Detected Attack ({prediction.get('model_version')})",
                            "description": f"ML detected attack with confidence {prediction.get('confidence')} and probability {prediction.get('attack_probability')}",
                            "source_ip": flow_meta.get("src_ip"),
                            "target_ip": flow_meta.get("dst_ip"),
                            "target_port": flow_meta.get("dst_port"),
                            "detection_method": prediction.get("model_version"),
                            "confidence_score": float(
                                prediction.get("confidence", 0.0)
                            ),
                            "raw_data": raw_data_json,
                        },
                    )
                    db.commit()
                    alert_row = res_sql.first()
                    alert_id = alert_row[0] if alert_row else None

                    try:
                        from app.realtime_manager import get_realtime_manager

                        rm = get_realtime_manager()
                        alert_data = {
                            "type": "new_alert",
                            "data": {
                                "id": str(alert_id) if alert_id else None,
                                "severity": severity,
                                "title": f"ML-Detected Attack ({prediction.get('model_version')})",
                                "description": f"ML detected attack with confidence {prediction.get('confidence')} and probability {prediction.get('attack_probability')}",
                                "source_ip": flow_meta.get("src_ip"),
                                "target_port": flow_meta.get("dst_port"),
                                "confidence": float(prediction.get("confidence", 0.0)),
                                "detected_at": datetime.utcnow().isoformat(),
                                "status": "new",
                                "attack_type": prediction.get("attack_type"),
                            },
                        }
                        await rm.broadcast_to_topic(
                            f"alerts_user_{user_id}", alert_data
                        )
                        await rm.broadcast_to_topic("alerts", alert_data)
                    except Exception:
                        logger.debug("Failed to broadcast alert after raw SQL insert")

            except Exception as raw_insert_err:
                logger.exception(
                    f"Failed to insert alert via raw SQL: {raw_insert_err}"
                )
                await redis.xadd(DLQ_STREAM, {"msg": json.dumps(obj)})
                await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
                return

    # Acknowledge the processed entry
    try:
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
    except Exception:
        logger.warning(f"Failed to xack entry {entry_id}")


async def redis_consumer_loop(app):
    """Main loop for consuming Redis Stream entries."""
    redis = aioredis.from_url(settings.REDIS_URL)
    consumer_name = f"{CONSUMER_NAME_PREFIX}_{int(time.time())}"

    # Ensure consumer group exists
    await ensure_group(redis)

    # Try to claim pending entries older than threshold
    try:
        # XAUTOCLAIM is available in redis-py via xauto_claim
        # We'll attempt to auto-claim pending entries older than CLAIM_MIN_IDLE_MS
        try:
            claimed = await redis.xautoclaim(
                STREAM_KEY,
                CONSUMER_GROUP,
                consumer_name,
                min_idle_time=CLAIM_MIN_IDLE_MS,
                start_id="0-0",
                count=100,
            )
            # claimed returns (next_start_id, entries)
            if claimed and len(claimed) > 1:
                entries = claimed[1]
                for entry_id, fields in entries:
                    await process_message(redis, entry_id, fields)
                    await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        except Exception:
            # Fall back to not auto-claiming if method not available
            pass

        while True:
            try:
                resp = await redis.xreadgroup(
                    CONSUMER_GROUP,
                    consumer_name,
                    streams={STREAM_KEY: ">"},
                    count=READ_COUNT,
                    block=BLOCK_MS,
                )
                if not resp:
                    continue

                # resp is a list of (stream, [(id, {b'msg': b'...'}), ...])
                for stream_key, messages in resp:
                    for entry_id, fields in messages:
                        try:
                            await process_message(redis, entry_id, fields)
                        except Exception as e:
                            logger.exception(f"Processing entry {entry_id} failed: {e}")
                            # increment retry counter
                            retry_key = f"ml:retry:{entry_id}"
                            retries = await redis.incr(retry_key)
                            if retries == 1:
                                await redis.expire(retry_key, 3600)
                            if retries > MAX_RETRIES:
                                # move to DLQ
                                await redis.xadd(
                                    DLQ_STREAM,
                                    {
                                        "msg": (
                                            fields.get(b"msg")
                                            if isinstance(
                                                fields.get(b"msg"), (bytes, bytearray)
                                            )
                                            else json.dumps(fields)
                                        )
                                    },
                                )
                                await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
                                logger.warning(
                                    f"Moved entry {entry_id} to DLQ after {retries} failed attempts"
                                )
                        else:
                            # ack already done inside process_message
                            pass

            except Exception as e:
                logger.exception(f"Error reading from Redis stream: {e}")
                await asyncio.sleep(1)

    finally:
        try:
            await redis.close()
        except Exception:
            pass


async def start_consumer_task(app):
    task = asyncio.create_task(redis_consumer_loop(app))
    app.state._redis_consumer_task = task
    return task
