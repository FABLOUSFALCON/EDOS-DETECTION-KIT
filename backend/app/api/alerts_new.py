"""
New Clean Alerts API - Works with Real Database Schema
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text, and_, desc
from sqlalchemy.orm import Session
from app.database import get_db
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["New Alerts API"])

# Alert severity levels
SEVERITY_LEVELS = ["info", "low", "medium", "high", "critical"]

# Alert status options
ALERT_STATUS = ["new", "acknowledged", "investigating", "resolved", "false_positive"]


@router.get("/")
async def get_alerts(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
):
    """Get security alerts with filtering and pagination"""
    try:
        # Base query
        base_query = """
            SELECT 
                sa.id,
                sa.user_id,
                sa.resource_id,
                sa.severity,
                sa.title,
                sa.description,
                sa.source_ip,
                sa.target_ip,
                sa.target_port,
                sa.detection_method,
                sa.confidence_score,
                sa.status,
                sa.raw_data,
                sa.detected_at,
                sa.created_at,
                ac.name as category_name,
                ac.color_code as category_color
            FROM security_alerts sa
            LEFT JOIN alert_categories ac ON sa.category_id = ac.id
            WHERE 1=1
        """

        params = {}

        # Add filters
        if severity:
            base_query += " AND sa.severity = :severity"
            params["severity"] = severity

        if status:
            base_query += " AND sa.status = :status"
            params["status"] = status

        if user_id:
            base_query += " AND sa.user_id = :user_id"
            params["user_id"] = user_id

        # Order by newest first
        base_query += " ORDER BY sa.detected_at DESC, sa.created_at DESC"

        # Add pagination
        base_query += " LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        # Execute query
        result = db.execute(text(base_query), params)
        alerts = []

        for row in result:
            alert = {
                "id": str(row[0]),
                "user_id": str(row[1]),
                "resource_id": str(row[2]) if row[2] else None,
                "severity": row[3],
                "title": row[4],
                "description": row[5],
                "source_ip": str(row[6]) if row[6] else None,
                "target_ip": str(row[7]) if row[7] else None,
                "target_port": row[8],
                "detection_method": row[9],
                "confidence_score": float(row[10]) if row[10] else 0.0,
                "status": row[11],
                "raw_data": row[12] if row[12] else {},
                "detected_at": row[13].isoformat() if row[13] else None,
                "created_at": row[14].isoformat() if row[14] else None,
                "category": {
                    "name": row[15] if row[15] else "Unknown",
                    "color": row[16] if row[16] else "#808080",
                },
            }
            alerts.append(alert)

        return {"alerts": alerts, "total": len(alerts)}

    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}")


@router.get("/stats")
async def get_alert_stats(db: Session = Depends(get_db)):
    """Get alert statistics"""
    try:
        # Get counts by severity
        severity_stats = db.execute(
            text(
                """
            SELECT severity, COUNT(*) as count
            FROM security_alerts
            WHERE status != 'resolved'
            GROUP BY severity
        """
            )
        ).fetchall()

        # Get recent alerts count (last 24 hours)
        recent_count = db.execute(
            text(
                """
            SELECT COUNT(*) as count
            FROM security_alerts 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """
            )
        ).fetchone()[0]

        # Get unresolved alerts count
        unresolved_count = db.execute(
            text(
                """
            SELECT COUNT(*) as count
            FROM security_alerts
            WHERE status NOT IN ('resolved', 'false_positive')
        """
            )
        ).fetchone()[0]

        severity_breakdown = {}
        for row in severity_stats:
            severity_breakdown[row[0]] = row[1]

        return {
            "total_unresolved": unresolved_count,
            "recent_24h": recent_count,
            "severity_breakdown": severity_breakdown,
        }

    except Exception as e:
        logger.error(f"Error fetching alert stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch alert stats: {str(e)}"
        )


@router.post("/")
async def create_alert(alert_data: Dict[str, Any], db: Session = Depends(get_db)):
    """Create a new security alert"""
    try:
        # Get default category (first one available)
        category_result = db.execute(
            text("SELECT id FROM alert_categories LIMIT 1")
        ).fetchone()
        category_id = category_result[0] if category_result else None

        # Prepare data with defaults
        user_id = alert_data.get("user_id", "550e8400-e29b-41d4-a716-446655440000")
        severity = alert_data.get("severity", "medium")
        title = alert_data.get("title", "Security Alert")
        description = alert_data.get("description", "Security alert detected")
        source_ip = alert_data.get("source_ip")
        target_ip = alert_data.get("target_ip")
        target_port = alert_data.get("target_port")
        detection_method = alert_data.get("detection_method", "Manual")

        # Scale confidence score to database range (0-100% -> 0-9.99)
        confidence_raw = float(alert_data.get("confidence_score", 50))
        confidence_score = min(
            confidence_raw / 10.0, 9.99
        )  # Scale down and cap at 9.99

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
            RETURNING id, created_at
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

        return {
            "id": str(result[0]),
            "created_at": result[1].isoformat(),
            "message": "Alert created successfully",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.patch("/{alert_id}")
async def update_alert_status(
    alert_id: str, update_data: Dict[str, Any], db: Session = Depends(get_db)
):
    """Update alert status"""
    try:
        # Validate alert exists
        alert_check = db.execute(
            text("SELECT id FROM security_alerts WHERE id = :alert_id"),
            {"alert_id": alert_id},
        ).fetchone()

        if not alert_check:
            raise HTTPException(status_code=404, detail="Alert not found")

        # Update fields
        update_fields = []
        params = {"alert_id": alert_id}

        if "status" in update_data:
            if update_data["status"] not in ALERT_STATUS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {ALERT_STATUS}",
                )
            update_fields.append("status = :status")
            params["status"] = update_data["status"]

        if "acknowledged_by" in update_data:
            update_fields.append("acknowledged_by = :ack_by, acknowledged_at = NOW()")
            params["ack_by"] = update_data["acknowledged_by"]

        if update_data.get("status") == "resolved":
            update_fields.append("resolved_at = NOW()")

        if not update_fields:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        # Execute update
        update_sql = f"UPDATE security_alerts SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = :alert_id"
        db.execute(text(update_sql), params)
        db.commit()

        return {"message": "Alert updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update alert: {str(e)}")


@router.get("/categories")
async def get_alert_categories(db: Session = Depends(get_db)):
    """Get available alert categories"""
    try:
        result = db.execute(
            text(
                """
            SELECT id, name, description, color_code
            FROM alert_categories 
            ORDER BY name
        """
            )
        )

        categories = []
        for row in result:
            categories.append(
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "description": row[2],
                    "color_code": row[3],
                }
            )

        return {"categories": categories}

    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch categories: {str(e)}"
        )
