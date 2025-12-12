"""
Real-time Network Event Processor for Threat Map
Consumes ML network events and provides geolocation data
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import redis.asyncio as redis
from fastapi import WebSocket
from ..core.websocket_manager import websocket_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetworkEventProcessor:
    def __init__(self):
        self.redis_client = None
        self.running = False
        self.event_stream = "ml:network_events"
        self.consumer_group = "threat_map_group"
        self.consumer_name = "threat_map_consumer"

    async def initialize(self):
        """Initialize Redis connection and consumer group"""
        try:
            self.redis_client = redis.Redis(
                host="localhost", port=6379, db=0, decode_responses=True
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Redis connection established for network events")

            # Create consumer group if it doesn't exist
            try:
                await self.redis_client.xgroup_create(
                    self.event_stream, self.consumer_group, id="0", mkstream=True
                )
                logger.info(f"✅ Created consumer group: {self.consumer_group}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    logger.info(
                        f"📦 Consumer group already exists: {self.consumer_group}"
                    )
                else:
                    raise e

        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            raise e

    async def start_processing(self):
        """Start processing network events from Redis stream"""
        if not self.redis_client:
            await self.initialize()

        self.running = True
        logger.info(
            f"🚀 Starting network event processor for stream: {self.event_stream}"
        )

        while self.running:
            try:
                # Read events from the stream
                events = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.event_stream: ">"},
                    count=10,
                    block=1000,  # Block for 1 second
                )

                for stream, messages in events:
                    for message_id, fields in messages:
                        await self.process_network_event(message_id, fields)

            except Exception as e:
                logger.error(f"❌ Error processing network events: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def process_network_event(self, message_id: str, fields: Dict[str, str]):
        """Process individual network event and broadcast to threat map"""
        try:
            # Parse event data including client/resource context
            event_data = json.loads(fields.get("msg", "{}"))

            client_id = event_data.get("client_id", "unknown")
            resource_id = event_data.get("resource_id", "default")

            ip = fields.get("ip") or event_data.get("ip")
            is_attack = fields.get(
                "is_attack", "false"
            ).lower() == "true" or event_data.get("is_attack", False)
            confidence = float(
                fields.get("confidence", 0.0) or event_data.get("confidence", 0.0)
            )
            timestamp = fields.get("timestamp") or event_data.get(
                "timestamp", datetime.utcnow().isoformat()
            )

            logger.info(
                f"📡 Processing network event: IP={ip}, Attack={is_attack}, Confidence={confidence}, Resource={resource_id}"
            )

            if not ip:
                logger.warning("⚠️ Skipping event with missing IP")
                await self.acknowledge_message(message_id)
                return

            # Get location data (this would integrate with your geolocation service)
            location_data = await self.get_ip_location(ip)

            # Determine threat severity based on confidence
            severity = self.calculate_severity(confidence, is_attack)

            # Create threat map update
            threat_update = {
                "type": "threat_update",
                "data": {
                    "ip": ip,
                    "country": location_data.get("country", "Unknown"),
                    "lat": location_data.get("lat", 0),
                    "lng": location_data.get("lon", 0),
                    "is_attack": is_attack,
                    "severity": severity,
                    "confidence": confidence,
                    "timestamp": timestamp,
                    "city": location_data.get("city", "Unknown"),
                    "isp": location_data.get("isp", "Unknown"),
                    "client_id": client_id,
                    "resource_id": resource_id,
                },
            }

            # Broadcast to resource-specific WebSocket channel
            resource_channel = f"threat_map_{resource_id}"
            await websocket_manager.broadcast_to_room(resource_channel, threat_update)
            logger.info(
                f"📤 Broadcasted threat update for IP: {ip} to resource {resource_id}"
            )

            # Acknowledge message processing
            await self.acknowledge_message(message_id)

        except Exception as e:
            logger.error(f"❌ Error processing network event {message_id}: {e}")
            # Don't acknowledge failed messages so they can be retried

    async def get_ip_location(self, ip: str) -> Dict[str, Any]:
        """Get IP geolocation data (integrate with your geolocation service)"""
        try:
            # This would integrate with your existing geolocation service
            # For now, return mock data based on IP ranges

            if ip.startswith("185."):
                return {
                    "country": "Russia",
                    "lat": 55.7558,
                    "lon": 37.6176,
                    "city": "Moscow",
                    "isp": "Unknown",
                }
            elif ip.startswith("103."):
                return {
                    "country": "China",
                    "lat": 39.9042,
                    "lon": 116.4074,
                    "city": "Beijing",
                    "isp": "Unknown",
                }
            elif ip.startswith("175."):
                return {
                    "country": "North Korea",
                    "lat": 39.0392,
                    "lon": 125.7625,
                    "city": "Pyongyang",
                    "isp": "Unknown",
                }
            elif ip.startswith("5."):
                return {
                    "country": "Iran",
                    "lat": 35.6892,
                    "lon": 51.3890,
                    "city": "Tehran",
                    "isp": "Unknown",
                }
            else:
                return {
                    "country": "Unknown",
                    "lat": 0,
                    "lon": 0,
                    "city": "Unknown",
                    "isp": "Unknown",
                }

        except Exception as e:
            logger.error(f"❌ Geolocation error for IP {ip}: {e}")
            return {
                "country": "Unknown",
                "lat": 0,
                "lon": 0,
                "city": "Unknown",
                "isp": "Unknown",
            }

    def calculate_severity(self, confidence: float, is_attack: bool) -> str:
        """Calculate threat severity based on ML confidence and attack status"""
        if not is_attack:
            return "low"

        if confidence >= 0.9:
            return "critical"
        elif confidence >= 0.7:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        else:
            return "low"

    async def acknowledge_message(self, message_id: str):
        """Acknowledge processed message"""
        try:
            await self.redis_client.xack(
                self.event_stream, self.consumer_group, message_id
            )
        except Exception as e:
            logger.error(f"❌ Error acknowledging message {message_id}: {e}")

    async def stop_processing(self):
        """Stop the network event processor"""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()
        logger.info("🛑 Network event processor stopped")

    async def get_stream_info(self) -> Dict[str, Any]:
        """Get information about the network events stream"""
        try:
            if not self.redis_client:
                return {"status": "disconnected"}

            # Get stream info
            stream_info = await self.redis_client.xinfo_stream(self.event_stream)

            # Get consumer group info
            try:
                groups_info = await self.redis_client.xinfo_groups(self.event_stream)
                group_info = next(
                    (g for g in groups_info if g["name"] == self.consumer_group), {}
                )
            except:
                group_info = {}

            return {
                "status": "connected",
                "stream_length": stream_info.get("length", 0),
                "last_entry": stream_info.get("last-generated-id", "N/A"),
                "consumer_group": self.consumer_group,
                "pending_messages": group_info.get("pending", 0),
                "consumers": group_info.get("consumers", 0),
            }

        except Exception as e:
            logger.error(f"❌ Error getting stream info: {e}")
            return {"status": "error", "error": str(e)}


# Global instance
network_processor = NetworkEventProcessor()


# Function to simulate ML events for testing
async def simulate_ml_events():
    """Simulate ML network events for testing the threat map"""
    try:
        redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )

        test_events = [
            {
                "ip": "185.220.101.42",
                "is_attack": "true",
                "confidence": "0.95",
            },  # Russia - Critical
            {
                "ip": "103.208.220.122",
                "is_attack": "true",
                "confidence": "0.82",
            },  # China - High
            {
                "ip": "175.45.176.83",
                "is_attack": "true",
                "confidence": "0.91",
            },  # North Korea - Critical
            {
                "ip": "5.63.151.52",
                "is_attack": "true",
                "confidence": "0.75",
            },  # Iran - High
            {
                "ip": "192.168.1.100",
                "is_attack": "false",
                "confidence": "0.12",
            },  # Local - Low
        ]

        for event in test_events:
            event["timestamp"] = datetime.utcnow().isoformat()

            await redis_client.xadd("ml:network_events", event)
            logger.info(f"📝 Simulated event: {event}")

            await asyncio.sleep(2)  # 2 second intervals

    except Exception as e:
        logger.error(f"❌ Simulation error: {e}")
    finally:
        await redis_client.close()
