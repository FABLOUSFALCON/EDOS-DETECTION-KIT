"""
ML Integration API for EDoS Security Dashboard
Receives predictions from ML service and converts them to alerts
"""

from fastapi import APIRouter
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

router = APIRouter()
realtime_manager = get_realtime_manager()

# ================================
# ML PREDICTION SCHEMAS
# ================================


class NetworkFlowData(BaseModel):
    """Network flow data from ML service"""

    dst_port: int
    flow_duration: float
    """
    Minimal ML integration proxy endpoints

    This module provides lightweight proxy endpoints to the ML service for
    testing and developer use. It uses `model_to_dict()` to serialize Pydantic
    models in a way compatible with both Pydantic v1 and v2.
    """

    from datetime import datetime

    from fastapi import APIRouter, HTTPException, Depends
    import httpx
    from typing import Any
    from pydantic import BaseModel

    from sqlalchemy.orm import Session

    from ..database import get_db
    from ..models.database import UserProfile
    from ..api.supabase_auth import get_current_user
    from app.utils.pydantic_compat import model_to_dict

    router = APIRouter()

    class NetworkFlowData(BaseModel):
        dst_port: int
        flow_duration: float
        tot_fwd_pkts: int
        tot_bwd_pkts: int
        fwd_pkt_len_max: int
        fwd_pkt_len_min: int
        bwd_pkt_len_max: int
        bwd_pkt_len_mean: float
        flow_byts_s: float
        flow_pkts_s: float
        flow_iat_mean: float
        flow_iat_std: float
        flow_iat_max: float
        fwd_iat_std: float
        bwd_pkts_s: float
        psh_flag_cnt: int
        ack_flag_cnt: int
        init_fwd_win_byts: int
        init_bwd_win_byts: int
        fwd_seg_size_min: int

    @router.post("/ml/predict")
    async def proxy_ml_prediction(
        flow_data: NetworkFlowData,
        current_user: UserProfile = Depends(get_current_user),
    ):
        """Proxy a single flow to the ML service and return its response.

        Uses `model_to_dict()` for robust serialization.
        """
        try:
            ml_url = "http://localhost:23334/predict"
            async with httpx.AsyncClient() as client:
                payload = model_to_dict(flow_data)
                response = await client.post(ml_url, json=payload, timeout=15.0)
                response.raise_for_status()

            ml_prediction = response.json()

            return {
                "prediction": ml_prediction,
                "user_id": str(current_user.id),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, detail=f"ML service unavailable: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

    @router.post("/ml/predict-batch")
    async def proxy_ml_batch_prediction(
        flows: list[NetworkFlowData],
        current_user: UserProfile = Depends(get_current_user),
    ):
        """Proxy a batch of flows to the ML service and return the batch response."""
        try:
            ml_url = "http://localhost:23334/predict/batch"
            async with httpx.AsyncClient() as client:
                payload = {"flows": [model_to_dict(f) for f in flows]}
                response = await client.post(ml_url, json=payload, timeout=30.0)
                response.raise_for_status()

            batch_prediction = response.json()

            return {
                "predictions": batch_prediction,
                "user_id": str(current_user.id),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, detail=f"ML service unavailable: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")
