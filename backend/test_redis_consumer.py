#!/usr/bin/env python3
"""
Redis Consumer Alert Generation Test
Tests the Redis consumer functionality to generate alerts from ML predictions
"""

import os
import sys
import redis
import json
import time
import asyncio
import logging
from datetime import datetime

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.services.redis_consumer import redis_consumer_loop, ensure_group

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_redis_consumer():
    """Test the Redis consumer by sending ML predictions to Redis"""

    # Connect to Redis
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    try:
        # Test Redis connection
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.info("💡 Make sure Redis is running: redis-server")
        return

    # ML prediction test data (using inverted logic - low probability = attack)
    test_predictions = [
        {
            "flow_meta": {
                "src_ip": "203.0.113.45",
                "dst_ip": "192.168.1.100",
                "dst_port": 80,
            },
            "prediction": {
                "is_attack": True,
                "attack_probability": 0.15,  # Low probability = attack (inverted logic)
                "confidence": 0.85,
                "model_version": "edos_ml_v1.2",
                "attack_type": "ddos",
            },
            "timestamp": datetime.now().isoformat(),
        },
        {
            "flow_meta": {
                "src_ip": "198.51.100.22",
                "dst_ip": "192.168.1.200",
                "dst_port": 22,
            },
            "prediction": {
                "is_attack": True,
                "attack_probability": 0.25,  # Low probability = attack
                "confidence": 0.75,
                "model_version": "edos_ml_v1.2",
                "attack_type": "brute_force",
            },
            "timestamp": datetime.now().isoformat(),
        },
        {
            "flow_meta": {
                "src_ip": "192.0.2.100",
                "dst_ip": "192.168.1.50",
                "dst_port": 443,
            },
            "prediction": {
                "is_attack": False,
                "attack_probability": 0.85,  # High probability = normal traffic
                "confidence": 0.90,
                "model_version": "edos_ml_v1.2",
                "attack_type": "normal",
            },
            "timestamp": datetime.now().isoformat(),
        },
    ]

    # Send predictions to Redis stream
    stream_name = "ml_predictions"
    logger.info(
        f"📤 Sending {len(test_predictions)} predictions to Redis stream: {stream_name}"
    )

    for i, prediction in enumerate(test_predictions, 1):
        try:
            # Add prediction to Redis stream
            stream_id = redis_client.xadd(stream_name, prediction)
            logger.info(f"✅ Prediction {i} added to stream with ID: {stream_id}")
            logger.info(
                f"   Attack: {prediction['prediction']['is_attack']}, "
                f"Probability: {prediction['prediction']['attack_probability']}, "
                f"Type: {prediction['prediction']['attack_type']}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to add prediction {i}: {e}")

    # Wait a bit for data to be available
    time.sleep(1)

    # Check what's in the stream
    logger.info("🔍 Checking Redis stream contents...")
    try:
        stream_data = redis_client.xread({stream_name: "0-0"}, count=10)
        if stream_data:
            stream_entries = stream_data[0][1]  # [('stream_name', [(id, data), ...])]
            logger.info(f"📊 Found {len(stream_entries)} entries in stream")
            for entry_id, entry_data in stream_entries:
                logger.info(f"   Entry {entry_id}: {entry_data}")
        else:
            logger.warning("⚠️ No entries found in stream")
    except Exception as e:
        logger.error(f"❌ Failed to read stream: {e}")

    # Test the Redis consumer function directly
    logger.info("🤖 Testing Redis consumer function...")
    try:
        # This will process available messages once
        asyncio.run(redis_consumer_loop())
        logger.info("✅ Redis consumer function executed successfully")
    except Exception as e:
        logger.error(f"❌ Redis consumer function failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🧪 Redis Consumer Alert Generation Test")
    print("=" * 50)
    test_redis_consumer()
