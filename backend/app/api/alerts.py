"""
Alerts API endpoints for real-time threat detection
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.database import User, SecurityAlert
from ..api.auth import get_current_user
from ..services.data_generator import DataGenerator
import random

router = APIRouter()

# Initialize with some sample alerts
router = APIRouter()

# Sample alerts removed - now using real database


@router.get("/", response_model=List[dict])
async def get_alerts(
    level: Optional[str] = Query(None, description="Filter by alert level"),
    read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(50, description="Maximum number of alerts to return"),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
async def dismiss_alert(alert_id: str, current_user: User = Depends(get_current_user)):
    """Dismiss/delete specific alert"""
    global alerts_db
    alerts_db = [alert for alert in alerts_db if alert["id"] != alert_id]
    return {"message": "Alert dismissed"}


@router.put("/mark-all-read")
async def mark_all_alerts_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all alerts as read"""
    # Update all unread alerts for current user
    updated_count = db.query(SecurityAlert).filter(
        SecurityAlert.user_id == current_user.id,
        SecurityAlert.status == 'new'
    ).update({"status": "acknowledged"})
    
    db.commit()
    return {"message": f"Marked {updated_count} alerts as read"}


@router.get("/stats")
async def get_alert_stats(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Get alert statistics"""
    # Get all alerts for current user
    alerts = db.query(SecurityAlert).filter(SecurityAlert.user_id == current_user.id).all()
    
    total_alerts = len(alerts)
    unread_alerts = len([a for a in alerts if a.status == 'new'])

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate test alerts for development/demo purposes"""
    generator = DataGenerator()
    created_alerts = []

    for _ in range(count):
        # Generate alert data
        alert_data = generator.generate_alert()

        # Create database record
        db_alert = SecurityAlert(
            user_id=current_user.id,
            type=(
                alert_data.alert_type
                if hasattr(alert_data, "alert_type")
                else "general"
            ),
            category="network",
            severity=(
                alert_data.level.lower() if hasattr(alert_data, "level") else "medium"
            ),
            title=f"Security Alert - {alert_data.alert_type if hasattr(alert_data, 'alert_type') else 'General'}",
            description=(
                alert_data.message
                if hasattr(alert_data, "message")
                else "Test alert generated for demonstration"
            ),
            source_ip=(
                alert_data.source_ip
                if hasattr(alert_data, "source_ip")
                else "192.168.1." + str(random.randint(1, 254))
            ),
            target_ip=(
                alert_data.destination_ip
                if hasattr(alert_data, "destination_ip")
                else "10.0.0." + str(random.randint(1, 254))
            ),
            target_port=(
                alert_data.destination_port
                if hasattr(alert_data, "destination_port")
                else random.randint(80, 9999)
            ),
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
