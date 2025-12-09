"""
Redis Stream Message Duplicator
Copies messages from ml:predictions to batch_results for alerts processing
"""

import asyncio
import redis.asyncio as redis
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageDuplicator:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.running = False
        self.source_stream = "ml:predictions"
        self.target_stream = "batch_results"
        self.consumer_group = "duplicator_group"
        self.consumer_name = "duplicator_1"
        self.last_processed_id = "$"  # Start from new messages only

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Duplicator connected to Redis successfully")

            # Create consumer group for source stream
            try:
                await self.redis_client.xgroup_create(
                    self.source_stream,
                    self.consumer_group,
                    id="$",  # Only process new messages
                    mkstream=True,
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
            logger.info("Duplicator disconnected from Redis")

    async def duplicate_messages(self):
        """
        Main duplication loop
        """
        logger.info(
            f"Starting message duplication: {self.source_stream} -> {self.target_stream}"
        )

        while self.running:
            try:
                # Read messages from source stream
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.source_stream: ">"},
                    count=5,  # Process in small batches
                    block=2000,  # 2 second timeout
                )

                if not messages:
                    continue

                # Process each message
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        try:
                            # Copy the message to target stream
                            await self.redis_client.xadd(self.target_stream, fields)

                            logger.debug(
                                f"Duplicated message {msg_id} to {self.target_stream}"
                            )

                            # Acknowledge message in source stream
                            await self.redis_client.xack(
                                self.source_stream, self.consumer_group, msg_id
                            )

                        except Exception as e:
                            logger.error(f"Error duplicating message {msg_id}: {e}")

            except Exception as e:
                logger.error(f"Error in duplication loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def start(self):
        """Start the duplicator"""
        try:
            await self.connect()
            self.running = True
            logger.info("Message Duplicator started")
            await self.duplicate_messages()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error starting duplicator: {e}")
        finally:
            await self.disconnect()

    async def stop(self):
        """Stop the duplicator"""
        self.running = False
        await self.disconnect()


# Global duplicator instance
message_duplicator = MessageDuplicator()


async def start_message_duplicator():
    """Start the message duplicator"""
    logger.info("Starting message duplicator...")
    asyncio.create_task(message_duplicator.start())


async def stop_message_duplicator():
    """Stop the message duplicator"""
    logger.info("Stopping message duplicator...")
    await message_duplicator.stop()


# For testing
if __name__ == "__main__":

    async def test():
        duplicator = MessageDuplicator()
        await duplicator.start()

    asyncio.run(test())
