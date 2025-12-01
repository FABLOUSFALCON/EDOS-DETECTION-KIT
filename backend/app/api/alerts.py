"""
Alerts API endpoints for real-time threat detection
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.database import UserProfile, SecurityAlert
from ..api.supabase_auth import get_current_user, get_current_user_id
from ..realtime_manager import get_realtime_manager
import random
from pydantic import BaseModel, Field
from app.utils.pydantic_compat import model_to_dict

router = APIRouter()

router = APIRouter()

# Initialize realtime manager
realtime_manager = get_realtime_manager()

# ================================
# ML INTEGRATION SCHEMAS
# ================================


class NetworkFlowInput(BaseModel):
    """Network flow data from ML service"""

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


class MLPrediction(BaseModel):
    """ML prediction result"""

    is_attack: bool
    attack_probability: float
    benign_probability: float
    confidence: float
    model_version: str
    base_model_scores: Optional[Dict[str, float]] = None
    explanation: Optional[Dict[str, Any]] = None


class MLAlertRequest(BaseModel):
    """Request to create alerts from ML predictions"""

    resource_id: str = Field(..., description="User's resource ID")
    source_ip: str = Field(..., description="Source IP address")
    target_ip: Optional[str] = Field(None, description="Target IP (optional)")
    flow_data: NetworkFlowInput
    prediction: MLPrediction


# Sample alerts removed - now using real database


@router.get("/")
async def get_alerts(
    level: Optional[str] = Query(None, description="Filter by alert level"),
    read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(50, description="Maximum number of alerts to return"),
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all alerts with optional filtering from database"""
    try:
        # Query alerts for current user
        query = db.query(SecurityAlert).filter(SecurityAlert.user_id == current_user.id)

        # Apply filters
        if level:
            query = query.filter(SecurityAlert.severity == level.lower())

        if read is not None:
            # Map read status to alert status
            status_filter = "acknowledged" if read else "new"
            query = query.filter(SecurityAlert.status == status_filter)

        # Order by detected_at (newest first) and limit
        alerts = query.order_by(SecurityAlert.detected_at.desc()).limit(limit).all()

        # Convert to response format
        result = []
        for alert in alerts:
            result.append(
                {
                    "id": str(alert.id),
                    "level": alert.severity.upper(),
                    "message": alert.description,
                    "source": str(alert.source_ip) if alert.source_ip else "unknown",
                    "timestamp": alert.detected_at.isoformat(),
                    "time": alert.detected_at.strftime("%m/%d %H:%M"),
                    "read": alert.status == "acknowledged",
                    "title": alert.title,
                    "category": alert.category,
                    "confidence": (
                        float(alert.confidence_score)
                        if alert.confidence_score
                        else None
                    ),
                    "target_ip": str(alert.target_ip) if alert.target_ip else None,
                    "target_port": alert.target_port,
                    "detection_method": alert.detection_method,
                }
            )

        return result

    except Exception as e:
        print(f"Error fetching alerts: {e}")
        # Return empty list if there's an error
        return []


@router.post("/", response_model=dict)
async def create_alert(alert: dict):
    """Create new alert (typically called by ML model)"""
    new_alert = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow(),
        "read": False,
        **alert,
    }

    alerts_db.insert(0, new_alert)  # Insert at beginning for newest first

    # Keep only last 1000 alerts
    if len(alerts_db) > 1000:
        alerts_db[:] = alerts_db[:1000]

    return {"status": "alert_created", "id": new_alert["id"]}


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an alert as read"""
    alert = (
        db.query(SecurityAlert)
        .filter(SecurityAlert.id == alert_id, SecurityAlert.user_id == current_user.id)
        .first()
    )

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    db.commit()

    return {"message": "Alert marked as read"}


@router.delete("/{alert_id}")
async def dismiss_alert(
    alert_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss/delete specific alert"""
    # Find the alert in database
    alert = (
        db.query(SecurityAlert)
        .filter(SecurityAlert.id == alert_id, SecurityAlert.user_id == current_user.id)
        .first()
    )

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Delete the alert
    db.delete(alert)
    db.commit()

    return {"message": "Alert dismissed"}


@router.put("/mark-all-read")
async def mark_all_alerts_read(
    current_user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Mark all alerts as read"""
    # Update all unread alerts for current user
    updated_count = (
        db.query(SecurityAlert)
        .filter(SecurityAlert.user_id == current_user.id, SecurityAlert.status == "new")
        .update({"status": "acknowledged"})
    )

    db.commit()
    return {"message": f"Marked {updated_count} alerts as read"}


@router.get("/stats")
async def get_alert_stats(
    current_user: UserProfile = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get alert statistics"""
    # Get all alerts for current user
    alerts = (
        db.query(SecurityAlert).filter(SecurityAlert.user_id == current_user.id).all()
    )

    total_alerts = len(alerts)
    unread_alerts = len([a for a in alerts if a.status == "new"])

    # Count by severity level
    level_counts = {}
    for alert in alerts:
        level = alert.severity.upper()
        level_counts[level] = level_counts.get(level, 0) + 1

    # Recent alerts (last 24 hours)
    from datetime import timezone

    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_alerts = len([a for a in alerts if a.detected_at > recent_cutoff])

    return {
        "total_alerts": total_alerts,
        "unread_alerts": unread_alerts,
        "recent_alerts_24h": recent_alerts,
        "level_breakdown": level_counts,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/generate-test-data")
async def generate_test_alerts(
    count: int = 20,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate test alerts for development/demo purposes"""
    created_alerts = []

    for _ in range(count):
        # Create simple test alert data
        severity_options = ["low", "medium", "high", "critical"]
        attack_types = ["ddos", "malware", "brute_force", "sql_injection", "phishing"]

        attack_type = random.choice(attack_types)
        severity = random.choice(severity_options)

        # Create database record
        db_alert = SecurityAlert(
            user_id=current_user.id,
            type=attack_type,
            category="network",
            severity=severity,
            title=f"Security Alert - {attack_type.replace('_', ' ').title()}",
            description=f"Test {attack_type} alert generated for demonstration",
            source_ip="192.168.1." + str(random.randint(1, 254)),
            target_ip="10.0.0." + str(random.randint(1, 254)),
            target_port=random.randint(80, 9999),
            detection_method="ml_analysis",
            confidence_score=random.uniform(0.75, 0.99),
            status="new",
            detected_at=datetime.utcnow() - timedelta(hours=random.randint(0, 48)),
        )

        db.add(db_alert)
        created_alerts.append(
            {
                "id": str(db_alert.id),
                "severity": db_alert.severity,
                "title": db_alert.title,
                "detected_at": db_alert.detected_at.isoformat(),
            }
        )

    db.commit()

    return {"message": f"Generated {count} test alerts", "alerts": created_alerts}


# ================================
# ML INTEGRATION ENDPOINTS
# ================================


@router.post("/ml-prediction")
async def create_alert_from_ml(
    ml_request: MLAlertRequest,
    background_tasks: BackgroundTasks,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create security alert from ML prediction
    This is the key endpoint that receives ML predictions and converts them to database alerts
    """
    try:
        # Only create alerts for detected attacks
        if not ml_request.prediction.is_attack:
            return {
                "message": "No attack detected, no alert created",
                "prediction": model_to_dict(ml_request.prediction),
            }

        # Calculate severity based on ML confidence and attack probability
        severity = _calculate_severity(
            ml_request.prediction.confidence, ml_request.prediction.attack_probability
        )

        # Determine attack type from network characteristics
        attack_type = _determine_attack_type(
            ml_request.flow_data.dst_port,
            ml_request.flow_data,
            ml_request.prediction,
        )

        # Create database alert
        db_alert = SecurityAlert(
            user_id=current_user.id,
            resource_id=ml_request.resource_id,
            type=attack_type,
            category="network",
            severity=severity,
            title=f"ML-Detected {attack_type.replace('_', ' ').title()} Attack",
            description=_generate_alert_description(
                ml_request.source_ip, ml_request.prediction, ml_request.flow_data
            ),
            source_ip=ml_request.source_ip,
            target_ip=ml_request.target_ip,
            target_port=ml_request.flow_data.dst_port,
            detection_method=ml_request.prediction.model_version,
            confidence_score=ml_request.prediction.confidence
            * 100,  # Convert to percentage
            status="new",
            raw_data={
                "ml_prediction": model_to_dict(ml_request.prediction),
                "flow_data": model_to_dict(ml_request.flow_data),
                "processed_at": datetime.utcnow().isoformat(),
            },
            detected_at=datetime.utcnow(),
        )

        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)

        # Send real-time alert via WebSocket
        background_tasks.add_task(
            _broadcast_new_alert, alert=db_alert, user_id=current_user.id
        )

        return {
            "message": "Alert created from ML prediction",
            "alert_id": str(db_alert.id),
            "severity": db_alert.severity,
            "confidence": ml_request.prediction.confidence,
            "attack_type": attack_type,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating ML alert: {str(e)}"
        )


@router.post("/batch-ml-predictions")
async def create_batch_alerts_from_ml(
    predictions: List[MLAlertRequest],
    background_tasks: BackgroundTasks,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create multiple alerts from batch ML predictions
    Optimized for high-volume ML processing
    """
    try:
        alerts_created = 0
        attack_predictions = []

        # Filter only attack predictions
        for prediction_request in predictions:
            if prediction_request.prediction.is_attack:
                attack_predictions.append(prediction_request)

        # Create alerts for attack predictions
        created_alerts = []
        for ml_request in attack_predictions:
            severity = _calculate_severity(
                ml_request.prediction.confidence,
                ml_request.prediction.attack_probability,
            )
            attack_type = _determine_attack_type(
                ml_request.flow_data.dst_port,
                ml_request.flow_data,
                ml_request.prediction,
            )

            db_alert = SecurityAlert(
                user_id=current_user.id,
                resource_id=ml_request.resource_id,
                type=attack_type,
                category="network",
                severity=severity,
                title=f"ML-Detected {attack_type.replace('_', ' ').title()} Attack",
                description=_generate_alert_description(
                    ml_request.source_ip, ml_request.prediction, ml_request.flow_data
                ),
                source_ip=ml_request.source_ip,
                target_ip=ml_request.target_ip,
                target_port=ml_request.flow_data.dst_port,
                detection_method=ml_request.prediction.model_version,
                confidence_score=ml_request.prediction.confidence * 100,
                status="new",
                raw_data={
                    "ml_prediction": model_to_dict(ml_request.prediction),
                    "flow_data": model_to_dict(ml_request.flow_data),
                    "processed_at": datetime.utcnow().isoformat(),
                },
                detected_at=datetime.utcnow(),
            )

            db.add(db_alert)
            created_alerts.append(db_alert)
            alerts_created += 1

        db.commit()

        # Queue real-time broadcasts
        for alert in created_alerts:
            background_tasks.add_task(
                _broadcast_new_alert, alert=alert, user_id=current_user.id
            )

        return {
            "message": f"Processed {len(predictions)} predictions, created {alerts_created} alerts",
            "total_predictions": len(predictions),
            "attack_predictions": len(attack_predictions),
            "alerts_created": alerts_created,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating batch ML alerts: {str(e)}"
        )


# ================================
# ML HELPER FUNCTIONS
# ================================


def _calculate_severity(confidence: float, attack_probability: float) -> str:
    """Calculate alert severity based on ML metrics"""
    if confidence >= 0.9 and attack_probability >= 0.8:
        return "critical"
    elif confidence >= 0.8 and attack_probability >= 0.6:
        return "high"
    elif confidence >= 0.6 and attack_probability >= 0.4:
        return "medium"
    else:
        return "low"


def _determine_attack_type(
    dst_port: int, flow_data: NetworkFlowInput, prediction: MLPrediction
) -> str:
    """Determine attack type from network flow characteristics"""
    # Port-based classification
    if dst_port in [80, 443, 8080, 8443]:
        return "web_attack"
    elif dst_port in [22, 2222]:
        return "ssh_attack"
    elif dst_port in [21]:
        return "ftp_attack"
    elif dst_port in [53]:
        return "dns_attack"
    elif dst_port in [25, 587, 465]:
        return "email_attack"

    # Flow-based classification
    packet_rate = flow_data.flow_pkts_s
    flow_duration = flow_data.flow_duration

    if packet_rate > 100:
        return "ddos"
    elif flow_duration > 300:
        return "persistent_threat"
    elif flow_data.psh_flag_cnt > 10:
        return "data_exfiltration"
    else:
        return "network_intrusion"


def _generate_alert_description(
    source_ip: str, prediction: MLPrediction, flow_data: NetworkFlowInput
) -> str:
    """Generate human-readable alert description"""
    return (
        f"Machine learning model detected suspicious network activity from {source_ip} "
        f"targeting port {flow_data.dst_port}. "
        f"Confidence: {prediction.confidence:.1%}, "
        f"Attack Probability: {prediction.attack_probability:.1%}. "
        f"Flow characteristics: {flow_data.tot_fwd_pkts} forward packets, "
        f"{flow_data.flow_duration:.1f}s duration."
    )


async def _broadcast_new_alert(alert: SecurityAlert, user_id: str):
    """Broadcast new alert via WebSocket to connected clients"""
    try:
        alert_data = {
            "type": "new_alert",
            "data": {
                "id": str(alert.id),
                "severity": alert.severity,
                "title": alert.title,
                "description": alert.description,
                "source_ip": str(alert.source_ip) if alert.source_ip else None,
                "target_port": alert.target_port,
                "confidence": (
                    float(alert.confidence_score) if alert.confidence_score else 0
                ),
                "detected_at": alert.detected_at.isoformat(),
                "status": alert.status,
                "attack_type": alert.type,
            },
        }

        # Broadcast to user-specific channel
        await realtime_manager.broadcast_to_topic(f"alerts_user_{user_id}", alert_data)

        # Also broadcast to general alerts channel
        await realtime_manager.broadcast_to_topic("alerts", alert_data)

    except Exception as e:
        print(f"Error broadcasting alert: {e}")
