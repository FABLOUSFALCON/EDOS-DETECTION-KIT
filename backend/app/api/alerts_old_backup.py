"""
Real-time Security Alerts API - Production Version
Only serves real alerts from Redis ML predictions stored in database
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from ..database import get_db
from ..models.database import UserProfile, SecurityAlert
from ..api.supabase_auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_alerts(
    level: Optional[str] = Query(
        None, description="Filter by alert level (info, low, medium, high, critical)"
    ),
    read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(50, description="Maximum number of alerts to return"),
    offset: int = Query(0, description="Pagination offset"),
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get security alerts from database (generated from Redis ML predictions)"""
    try:
        # Query alerts for current user
        query = db.query(SecurityAlert).filter(SecurityAlert.user_id == current_user.id)

        # Apply filters
        if level:
            query = query.filter(SecurityAlert.severity == level.lower())

        if read is not None:
            # Map read status to alert status
            if read:
                query = query.filter(
                    SecurityAlert.status.in_(["acknowledged", "resolved"])
                )
            else:
                query = query.filter(SecurityAlert.status == "new")

        # Order by detected_at (newest first), apply pagination
        alerts = (
            query.order_by(desc(SecurityAlert.detected_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Convert to response format matching frontend expectations
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
                    "read": alert.status in ["acknowledged", "resolved"],
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
                    "severity": alert.severity,
                    "status": alert.status,
                    "detected_at": alert.detected_at.isoformat(),
                    "attack_type": alert.type,
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")


@router.get("/stats")
async def get_alert_stats(
    hours: int = Query(24, description="Hours to look back for stats"),
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get alert statistics for dashboard"""
    try:
        # Time range for recent alerts
        time_threshold = datetime.utcnow() - timedelta(hours=hours)

        # Total alerts
        total_alerts = (
            db.query(SecurityAlert)
            .filter(SecurityAlert.user_id == current_user.id)
            .count()
        )

        # Unread alerts
        unread_alerts = (
            db.query(SecurityAlert)
            .filter(
                SecurityAlert.user_id == current_user.id, SecurityAlert.status == "new"
            )
            .count()
        )

        # Recent alerts
        recent_alerts = (
            db.query(SecurityAlert)
            .filter(
                SecurityAlert.user_id == current_user.id,
                SecurityAlert.detected_at >= time_threshold,
            )
            .count()
        )

        # Severity breakdown
        severity_breakdown = {}
        severity_counts = (
            db.query(SecurityAlert.severity, func.count(SecurityAlert.id))
            .filter(SecurityAlert.user_id == current_user.id)
            .group_by(SecurityAlert.severity)
            .all()
        )

        for severity, count in severity_counts:
            severity_breakdown[severity.upper()] = count

        return {
            "total_alerts": total_alerts,
            "unread_alerts": unread_alerts,
            f"recent_alerts_{hours}h": recent_alerts,
            "level_breakdown": severity_breakdown,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching alert stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alert statistics")


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an alert as read/acknowledged"""
    try:
        alert = (
            db.query(SecurityAlert)
            .filter(
                SecurityAlert.id == alert_id, SecurityAlert.user_id == current_user.id
            )
            .first()
        )

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        db.commit()

        return {"message": "Alert marked as read", "id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark alert as read")


@router.patch("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_notes: Optional[str] = None,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an alert as resolved"""
    try:
        alert = (
            db.query(SecurityAlert)
            .filter(
                SecurityAlert.id == alert_id, SecurityAlert.user_id == current_user.id
            )
            .first()
        )

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        if resolution_notes:
            alert.resolution_notes = resolution_notes
        db.commit()

        return {"message": "Alert resolved", "id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an alert (use sparingly - prefer resolve)"""
    try:
        alert = (
            db.query(SecurityAlert)
            .filter(
                SecurityAlert.id == alert_id, SecurityAlert.user_id == current_user.id
            )
            .first()
        )

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        db.delete(alert)
        db.commit()

        return {"message": "Alert deleted", "id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete alert")


@router.get("/recent")
async def get_recent_alerts(
    limit: int = Query(10, description="Number of recent alerts to return"),
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get most recent alerts for notifications/dashboard"""
    try:
        alerts = (
            db.query(SecurityAlert)
            .filter(SecurityAlert.user_id == current_user.id)
            .order_by(desc(SecurityAlert.detected_at))
            .limit(limit)
            .all()
        )

        result = []
        for alert in alerts:
            result.append(
                {
                    "id": str(alert.id),
                    "title": alert.title,
                    "severity": alert.severity,
                    "detected_at": alert.detected_at.isoformat(),
                    "status": alert.status,
                    "source_ip": str(alert.source_ip) if alert.source_ip else None,
                    "target_port": alert.target_port,
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error fetching recent alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent alerts")
