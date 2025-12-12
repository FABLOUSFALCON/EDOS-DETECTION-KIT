"""
Network Analysis API for real-time system monitoring
"""

from fastapi import APIRouter, HTTPException, Depends, Query
import redis.asyncio as aioredis
import json
import logging
from datetime import datetime
from typing import Dict, Any

from ..api.supabase_auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/latest")
async def get_latest_network_analysis(
    resource_id: str = Query(..., description="Resource ID to get data for"),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the latest network analysis data from Redis"""

    redis_client = None
    try:
        # Connect to Redis
        redis_client = aioredis.from_url(
            "redis://localhost:6379", decode_responses=True
        )

        # Get latest data for specific resource
        data = await redis_client.get(f"network_analysis:latest:{resource_id}")

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No network analysis data available for resource {resource_id}",
            )

        # Parse JSON data
        network_data = json.loads(data)

        logger.info(
            f"📊 Served network analysis data for resource {resource_id} to user {current_user.id}"
        )

        return {
            "success": True,
            "data": network_data,
            "retrieved_at": datetime.now().isoformat(),
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {e}")
        raise HTTPException(status_code=500, detail="Invalid data format in Redis")

    except Exception as e:
        logger.error(f"❌ Error retrieving network analysis data: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve network analysis data"
        )

    finally:
        if redis_client:
            await redis_client.close()


@router.get("/status")
async def get_network_monitor_status(
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Check if the network monitor service is running and publishing data"""

    redis_client = None
    try:
        # Connect to Redis
        redis_client = aioredis.from_url(
            "redis://localhost:6379", decode_responses=True
        )

        # Check if data exists and when it was last updated
        data = await redis_client.get("network_analysis:latest")

        if data:
            network_data = json.loads(data)
            last_update = network_data.get("lastUpdate")

            # Parse the timestamp to check if service is recent
            if last_update:
                last_update_time = datetime.fromisoformat(
                    last_update.replace("Z", "+00:00")
                )
                time_diff = (
                    datetime.now().replace(tzinfo=last_update_time.tzinfo)
                    - last_update_time
                )
                is_recent = time_diff.total_seconds() < 30  # Within last 30 seconds
            else:
                is_recent = False

            return {
                "service_running": is_recent,
                "last_update": last_update,
                "data_available": True,
                "checked_at": datetime.now().isoformat(),
            }
        else:
            return {
                "service_running": False,
                "last_update": None,
                "data_available": False,
                "checked_at": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"❌ Error checking network monitor status: {e}")
        return {
            "service_running": False,
            "last_update": None,
            "data_available": False,
            "error": str(e),
            "checked_at": datetime.now().isoformat(),
        }

    finally:
        if redis_client:
            await redis_client.close()


@router.post("/refresh")
async def refresh_network_data(
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Force refresh of network analysis data (mainly for testing)"""

    try:
        # Get the latest data
        result = await get_latest_network_analysis(current_user)

        return {
            "success": True,
            "message": "Network analysis data refreshed",
            "data": result["data"],
            "refreshed_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error refreshing network data: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh network data")
