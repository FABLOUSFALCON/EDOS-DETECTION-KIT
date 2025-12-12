"""
Simple Redis ML Predictions Processor
Listens to Redis streams and creates alerts using the new alerts API
"""

import asyncio
import redis.asyncio as redis
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MLPredictionProcessor:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.running = False
        self.stream_name = "ml:predictions"
        self.consumer_group = "alerts_processor"
        self.consumer_name = "alert_consumer_1"

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis successfully")

            # Create consumer group (ignore if exists)
            try:
                await self.redis_client.xgroup_create(
                    self.stream_name, self.consumer_group, id="0", mkstream=True
                )
                logger.info(f"Created consumer group: {self.consumer_group}")
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"Consumer group {self.consumer_group} already exists")
                else:
                    raise

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    def process_prediction(self, msg_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert ML prediction from Redis message to alert data
        Only creates alerts when batch size >= 40 flows AND >40% of flows are attacks
        """
        try:
            # Check if this is a batch results message
            if "batch_results" not in msg_data:
                logger.debug("No batch_results in message")
                return None

            batch_data = msg_data["batch_results"]
            predictions = batch_data.get("predictions", [])

            if not predictions:
                logger.debug("No predictions in batch_results")
                return None

            # Calculate attack statistics for the batch
            total_flows = len(predictions)
            attack_count = sum(
                1 for pred in predictions if pred.get("is_attack", False)
            )
            attack_percentage = (
                (attack_count / total_flows) * 100 if total_flows > 0 else 0
            )

            # THRESHOLD 1: Only create alerts for batches with >= 40 flows
            if total_flows < 40:
                logger.debug(
                    f"Skipping small batch: {total_flows} flows (minimum 40 required)"
                )
                return None

            # THRESHOLD 2: Only create alerts when >40% of flows are attacks
            if attack_percentage < 40.0:
                logger.debug(
                    f"Skipping batch with low attack ratio: {attack_percentage:.1f}% ({attack_count}/{total_flows})"
                )
                return None

            # Map attack percentage to severity levels
            if attack_percentage >= 80.0:  # 80%+ = Critical
                severity = "critical"
            elif attack_percentage >= 65.0:  # 65-80% = High
                severity = "high"
            elif attack_percentage >= 50.0:  # 50-65% = Medium
                severity = "medium"
            else:  # 40-50% = Low
                severity = "low"

            # Get a sample attack prediction for details
            sample_attack = None
            for pred in predictions:
                if pred.get("is_attack", False):
                    sample_attack = pred
                    break

            if not sample_attack:
                return None

            # Extract network details from flow_meta
            flow_meta = msg_data.get("flow_meta", {})

            # Extract client information for user mapping
            client_id = msg_data.get("client_id", "unknown")

            # Map client_id to user_id (in production this would be from database)
            # For now, map to your user ID as default
            user_id_mapping = {
                "cicflow-monitor-01": "21c9dde7-a586-44af-9f67-11f13b9ddd28",  # Your user ID
                "target-server-01": "21c9dde7-a586-44af-9f67-11f13b9ddd28",  # Your user ID
                "default": "21c9dde7-a586-44af-9f67-11f13b9ddd28",  # Your user ID as fallback
            }

            alert_user_id = user_id_mapping.get(client_id, user_id_mapping["default"])

            # Create alert data
            alert_data = {
                "title": f"Batch Attack Detected ({sample_attack.get('model_version', 'Unknown')})",
                "description": f"Attack detected in {attack_percentage:.1f}% of flows ({attack_count}/{total_flows} flows)",
                "severity": severity,
                "source_ip": flow_meta.get("src_ip"),
                "target_ip": flow_meta.get("dst_ip"),
                "target_port": flow_meta.get("dst_port"),
                "detection_method": sample_attack.get("model_version", "ML Model"),
                "confidence_score": min(
                    attack_percentage, 99.9
                ),  # Use attack percentage as confidence
                "user_id": alert_user_id,  # Dynamic user mapping
                "raw_data": {
                    "batch_stats": {
                        "total_flows": total_flows,
                        "attack_count": attack_count,
                        "attack_percentage": attack_percentage,
                        "benign_count": total_flows - attack_count,
                    },
                    "sample_prediction": sample_attack,
                    "flow_meta": flow_meta,
                    "message_id": msg_data.get("message_id"),
                    "timestamp": msg_data.get("timestamp"),
                    "received_at": datetime.now().isoformat(),
                    "client_id": client_id,
                },
            }

            logger.info(
                f"🚨 ALERT CREATED: {attack_percentage:.1f}% attack ratio ({severity})"
            )
            return alert_data

        except Exception as e:
            logger.error(f"Error processing prediction: {e}")
            return None

    async def create_alert_in_db(self, alert_data: Dict[str, Any]) -> bool:
        """
        Create alert directly in database
        """
        try:
            # Get database session
            db = next(get_db())

            # Get a category (use first available)
            category_result = db.execute(
                text("SELECT id FROM alert_categories LIMIT 1")
            ).fetchone()
            category_id = category_result[0] if category_result else None

            if not category_id:
                logger.error("No alert categories found in database")
                return False

            # Prepare data
            user_id = alert_data.get("user_id", "550e8400-e29b-41d4-a716-446655440000")
            severity = alert_data.get("severity", "medium")
            title = alert_data.get("title", "ML Security Alert")
            description = alert_data.get(
                "description", "ML model detected security threat"
            )
            source_ip = alert_data.get("source_ip")
            target_ip = alert_data.get("target_ip")
            target_port = alert_data.get("target_port")
            detection_method = alert_data.get("detection_method", "ML Model")

            # Scale confidence score properly (0-100% -> 0-9.99)
            confidence_raw = float(alert_data.get("confidence_score", 50))
            confidence_score = min(confidence_raw / 10.0, 9.99)

            # Insert alert
            insert_sql = text(
                """
                INSERT INTO security_alerts 
                (user_id, category_id, severity, title, description, source_ip, target_ip, 
                 target_port, detection_method, confidence_score, status, raw_data, detected_at) 
                VALUES 
                (:user_id, :category_id, :severity, :title, :description, 
                 CAST(:source_ip AS inet), CAST(:target_ip AS inet), :target_port, 
                 :detection_method, :confidence_score, 'new', 
                 CAST(:raw_data AS jsonb), NOW())
                RETURNING id
            """
            )

            result = db.execute(
                insert_sql,
                {
                    "user_id": user_id,
                    "category_id": category_id,
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "source_ip": source_ip,
                    "target_ip": target_ip,
                    "target_port": target_port,
                    "detection_method": detection_method,
                    "confidence_score": confidence_score,
                    "raw_data": json.dumps(alert_data.get("raw_data", {})),
                },
            ).fetchone()

            db.commit()
            alert_id = result[0]
            logger.info(f"Created alert with ID: {alert_id}")
            return True

        except Exception as e:
            if "db" in locals():
                db.rollback()
            logger.error(f"Error creating alert in database: {e}")
            return False
        finally:
            if "db" in locals():
                db.close()

    async def process_redis_messages(self):
        """
        Main processing loop for Redis messages
        """
        logger.info(f"Starting to process messages from stream: {self.stream_name}")

        while self.running:
            try:
                # Read messages from Redis stream
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=10,
                    block=1000,  # 1 second timeout
                )

                if not messages:
                    continue

                # Process each message
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        try:
                            logger.info(
                                f"Processing message {msg_id}: {list(fields.keys())}"
                            )

                            # Parse message data (same format as live monitoring)
                            if "msg" in fields:
                                msg_data = json.loads(fields["msg"])
                            elif "prediction_data" in fields:
                                msg_data = json.loads(fields["prediction_data"])
                            else:
                                logger.warning("Unknown message format")
                                continue

                            # Convert to alert
                            alert_data = self.process_prediction(msg_data)

                            if alert_data:
                                # Create alert in database
                                success = await self.create_alert_in_db(alert_data)

                                if success:
                                    logger.info(
                                        "Successfully created alert from prediction"
                                    )
                                    # Acknowledge message
                                    await self.redis_client.xack(
                                        self.stream_name, self.consumer_group, msg_id
                                    )
                                else:
                                    logger.error(
                                        "Failed to create alert from prediction"
                                    )
                            else:
                                logger.info(
                                    "No threat detected, skipping alert creation"
                                )
                                # Still acknowledge the message
                                await self.redis_client.xack(
                                    self.stream_name, self.consumer_group, msg_id
                                )

                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                            # Don't acknowledge failed messages - they'll be retried

            except Exception as e:
                logger.error(f"Error in Redis processing loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def start(self):
        """Start the processor"""
        try:
            await self.connect()
            self.running = True
            logger.info("ML Prediction Processor started")
            await self.process_redis_messages()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error starting processor: {e}")
        finally:
            await self.disconnect()

    async def stop(self):
        """Stop the processor"""
        self.running = False
        await self.disconnect()


# Global processor instance
ml_processor = MLPredictionProcessor()


async def start_ml_processor():
    """Start the ML processor"""
    logger.info("Starting ML prediction processor...")
    asyncio.create_task(ml_processor.start())


async def stop_ml_processor():
    """Stop the ML processor"""
    logger.info("Stopping ML prediction processor...")
    await ml_processor.stop()


# For testing
async def test_create_sample_alert():
    """Test creating a sample alert"""
    processor = MLPredictionProcessor()

    sample_alert = {
        "title": "Test DDoS Detection",
        "description": "Test alert from ML model",
        "severity": "high",
        "source_ip": "192.168.1.100",
        "target_ip": "10.0.0.1",
        "target_port": 80,
        "detection_method": "ML Model",
        "confidence_score": 85.5,
        "raw_data": {"test": True, "timestamp": datetime.now().isoformat()},
    }

    success = await processor.create_alert_in_db(sample_alert)
    return success


if __name__ == "__main__":
    # Run test
    async def test():
        result = await test_create_sample_alert()
        print(f"Test alert creation: {'SUCCESS' if result else 'FAILED'}")

    asyncio.run(test())
