"""
New Clean Alerts API - Works with Real Database Schema
High-Performance API with Pagination, Bulk Operations, Search & Filtering
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy import text, and_, desc
from sqlalchemy.orm import Session
from app.database import get_db
from ..api.supabase_auth import get_current_user
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["New Alerts API"])

# Alert severity levels
SEVERITY_LEVELS = ["info", "low", "medium", "high", "critical"]

# Alert status options
ALERT_STATUS = ["new", "acknowledged", "investigating", "resolved", "false_positive"]


# Pydantic models for request validation
class BulkUpdateRequest(BaseModel):
    alert_ids: List[str]
    status: Optional[str] = None
    acknowledged_by: Optional[str] = None


class AlertFilters(BaseModel):
    severity: Optional[List[str]] = None
    status: Optional[List[str]] = None
    search: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    source_ip: Optional[str] = None


@router.get("/")
async def get_alerts(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, le=100, ge=1, description="Items per page"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    sort_by: str = Query("detected_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
):
    """Get security alerts with advanced filtering, search, sorting, and pagination"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Calculate offset
        offset = (page - 1) * limit

        # Base query for counting total results
        count_query = """
            SELECT COUNT(*)
            FROM security_alerts sa
            LEFT JOIN alert_categories ac ON sa.category_id = ac.id
            WHERE sa.user_id = :user_id
        """

        # Base query for fetching data
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
                sa.acknowledged_at,
                sa.resolved_at,
                ac.name as category_name,
                ac.color_code as category_color
            FROM security_alerts sa
            LEFT JOIN alert_categories ac ON sa.category_id = ac.id
            WHERE sa.user_id = :user_id
        """

        params = {"user_id": user_id}

        # Build WHERE conditions
        where_conditions = []

        # Resource filter - if provided, filter by specific resource
        if resource_id:
            where_conditions.append("sa.resource_id = :resource_id")
            params["resource_id"] = resource_id

        # Severity filter
        if severity and severity in SEVERITY_LEVELS:
            where_conditions.append("sa.severity = :severity")
            params["severity"] = severity

        # Status filter
        if status and status in ALERT_STATUS:
            where_conditions.append("sa.status = :status")
            params["status"] = status

        # Search filter (searches in title and description)
        if search:
            where_conditions.append(
                "(LOWER(sa.title) LIKE LOWER(:search) OR LOWER(sa.description) LIKE LOWER(:search))"
            )
            params["search"] = f"%{search}%"

        # Date range filters
        if date_from:
            where_conditions.append("DATE(sa.detected_at) >= :date_from")
            params["date_from"] = date_from

        if date_to:
            where_conditions.append("DATE(sa.detected_at) <= :date_to")
            params["date_to"] = date_to

        # Add WHERE conditions to queries
        if where_conditions:
            where_clause = " AND " + " AND ".join(where_conditions)
            count_query += where_clause
            base_query += where_clause

        # Get total count
        total_count = db.execute(text(count_query), params).scalar()

        # Add ORDER BY
        valid_sort_fields = [
            "detected_at",
            "created_at",
            "severity",
            "status",
            "title",
            "confidence_score",
        ]
        if sort_by not in valid_sort_fields:
            sort_by = "detected_at"

        sort_direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        # Custom sorting for severity (critical > high > medium > low > info)
        if sort_by == "severity":
            severity_order = "CASE sa.severity WHEN 'critical' THEN 5 WHEN 'high' THEN 4 WHEN 'medium' THEN 3 WHEN 'low' THEN 2 WHEN 'info' THEN 1 ELSE 0 END"
            base_query += (
                f" ORDER BY {severity_order} {sort_direction}, sa.detected_at DESC"
            )
        else:
            base_query += f" ORDER BY sa.{sort_by} {sort_direction}"

        # Add pagination
        base_query += " LIMIT :limit OFFSET :offset"
        params.update({"limit": limit, "offset": offset})

        # Execute data query
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
                "acknowledged_at": row[15].isoformat() if row[15] else None,
                "resolved_at": row[16].isoformat() if row[16] else None,
                "category": {
                    "name": row[17] if row[17] else "Unknown",
                    "color": row[18] if row[18] else "#808080",
                },
            }
            alerts.append(alert)

        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit
        has_next = page < total_pages
        has_prev = page > 1

        return {
            "alerts": alerts,
            "pagination": {
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": limit,
                "has_next": has_next,
                "has_prev": has_prev,
            },
        }

    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}")


@router.get("/stats")
async def get_alert_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
):
    """Get alert statistics"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Build resource filter if provided
        resource_filter = ""
        params = {"user_id": user_id}
        if resource_id:
            resource_filter = " AND resource_id = :resource_id"
            params["resource_id"] = resource_id

        # Get counts by severity
        severity_stats = db.execute(
            text(
                f"""
            SELECT severity, COUNT(*) as count
            FROM security_alerts
            WHERE status != 'resolved' AND user_id = :user_id{resource_filter}
            GROUP BY severity
        """
            ),
            params,
        ).fetchall()

        # Get recent alerts count (last 24 hours)
        recent_count = db.execute(
            text(
                f"""
            SELECT COUNT(*) as count
            FROM security_alerts 
            WHERE created_at >= NOW() - INTERVAL '24 hours' AND user_id = :user_id{resource_filter}
        """
            ),
            params,
        ).fetchone()[0]

        # Get unresolved alerts count
        unresolved_count = db.execute(
            text(
                f"""
            SELECT COUNT(*) as count
            FROM security_alerts
            WHERE status NOT IN ('resolved', 'false_positive') AND user_id = :user_id{resource_filter}
        """
            ),
            params,
        ).fetchone()[0]

        # Get unread alerts count (new status)
        unread_count = db.execute(
            text(
                f"""
            SELECT COUNT(*) as count
            FROM security_alerts
            WHERE status = 'new' AND user_id = :user_id{resource_filter}
        """
            ),
            params
        ).fetchone()[0]

        severity_breakdown = {}
        for row in severity_stats:
            severity_breakdown[row[0]] = row[1]

        return {
            "total_unresolved": unresolved_count,
            "total_unread": unread_count,
            "recent_24h": recent_count,
            "severity_breakdown": severity_breakdown,
        }

    except Exception as e:
        logger.error(f"Error fetching alert stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch alert stats: {str(e)}"
        )


@router.post("/bulk-update")
async def bulk_update_alerts(
    request: BulkUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk update multiple alerts"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        if not request.alert_ids:
            raise HTTPException(status_code=400, detail="No alert IDs provided")

        if len(request.alert_ids) > 1000:
            raise HTTPException(status_code=400, detail="Too many alerts (max 1000)")

        # Validate alerts exist AND belong to user
        placeholders = ",".join([f":id_{i}" for i in range(len(request.alert_ids))])
        id_params = {
            f"id_{i}": alert_id for i, alert_id in enumerate(request.alert_ids)
        }
        id_params["user_id"] = user_id

        count_check = db.execute(
            text(
                f"SELECT COUNT(*) FROM security_alerts WHERE id IN ({placeholders}) AND user_id = :user_id"
            ),
            id_params,
        ).scalar()

        if count_check != len(request.alert_ids):
            raise HTTPException(
                status_code=404, detail="Some alerts not found or access denied"
            )

        # Build update query
        update_fields = []
        params = id_params.copy()

        if request.status:
            if request.status not in ALERT_STATUS:
                raise HTTPException(
                    status_code=400, detail=f"Invalid status: {request.status}"
                )
            update_fields.append("status = :status")
            params["status"] = request.status

        if request.acknowledged_by:
            update_fields.append("acknowledged_by = :ack_by")
            update_fields.append("acknowledged_at = NOW()")
            params["ack_by"] = request.acknowledged_by

        if request.status == "resolved":
            update_fields.append("resolved_at = NOW()")
        elif (
            request.status == "acknowledged"
            and "acknowledged_at = NOW()" not in update_fields
        ):
            update_fields.append("acknowledged_at = NOW()")

        if not update_fields:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        # Execute bulk update
        update_sql = f"""
            UPDATE security_alerts 
            SET {', '.join(update_fields)}, updated_at = NOW() 
            WHERE id IN ({placeholders}) AND user_id = :user_id
        """

        result = db.execute(text(update_sql), params)
        db.commit()

        return {
            "message": f"Successfully updated {result.rowcount} alerts",
            "updated_count": result.rowcount,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk update: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {str(e)}")


@router.post("/mark-all-read")
async def mark_all_alerts_read(
    filters: Optional[AlertFilters] = Body(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all alerts as read (acknowledged) for a user with optional filters"""
    try:
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Base update query
        base_query = """
            UPDATE security_alerts 
            SET status = 'acknowledged', acknowledged_at = NOW(), updated_at = NOW()
            WHERE user_id = :user_id AND status = 'new'
        """

        params = {"user_id": user_id}

        # Apply filters if provided
        if filters:
            conditions = []

            if filters.severity:
                severity_placeholders = ",".join(
                    [f":sev_{i}" for i in range(len(filters.severity))]
                )
                conditions.append(f"severity IN ({severity_placeholders})")
                for i, sev in enumerate(filters.severity):
                    params[f"sev_{i}"] = sev

            if filters.date_from:
                conditions.append("DATE(detected_at) >= :date_from")
                params["date_from"] = filters.date_from

            if filters.date_to:
                conditions.append("DATE(detected_at) <= :date_to")
                params["date_to"] = filters.date_to

            if conditions:
                base_query += " AND " + " AND ".join(conditions)

        result = db.execute(text(base_query), params)
        db.commit()

        return {
            "message": f"Marked {result.rowcount} alerts as read",
            "updated_count": result.rowcount,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error marking all as read: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to mark alerts as read: {str(e)}"
        )


@router.get("/search")
async def search_alerts(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, le=50),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
):
    """Advanced search across alert fields"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Build resource filter if provided
        resource_filter = ""
        if resource_id:
            resource_filter = " AND sa.resource_id = :resource_id"

        search_query = f"""
            SELECT 
                sa.id, sa.title, sa.description, sa.severity, sa.status,
                sa.source_ip, sa.target_ip, sa.detected_at,
                ac.name as category_name
            FROM security_alerts sa
            LEFT JOIN alert_categories ac ON sa.category_id = ac.id
            WHERE sa.user_id = :user_id{resource_filter} AND (
                LOWER(sa.title) LIKE LOWER(:search) OR 
                LOWER(sa.description) LIKE LOWER(:search) OR
                LOWER(sa.detection_method) LIKE LOWER(:search) OR
                CAST(sa.source_ip AS text) LIKE :search OR
                CAST(sa.target_ip AS text) LIKE :search
            )
            ORDER BY sa.detected_at DESC
            LIMIT :limit
        """

        params = {"user_id": user_id, "search": f"%{q}%", "limit": limit}

        if resource_id:
            params["resource_id"] = resource_id

        result = db.execute(text(search_query), params)

        alerts = []
        for row in result:
            alerts.append(
                {
                    "id": str(row[0]),
                    "title": row[1],
                    "description": row[2],
                    "severity": row[3],
                    "status": row[4],
                    "source_ip": str(row[5]) if row[5] else None,
                    "target_ip": str(row[6]) if row[6] else None,
                    "detected_at": row[7].isoformat() if row[7] else None,
                    "category_name": row[8],
                }
            )

        return {"alerts": alerts, "query": q}

    except Exception as e:
        logger.error(f"Error in search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/filters")
async def get_filter_options(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
):
    """Get available filter options for dropdowns"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Build resource filter if provided
        resource_filter = ""
        params = {"user_id": user_id}
        if resource_id:
            resource_filter = " AND resource_id = :resource_id"
            params["resource_id"] = resource_id

        # Get unique source IPs (top 20)
        source_ips = db.execute(
            text(
                f"""
            SELECT DISTINCT CAST(source_ip AS text) as ip, COUNT(*) as count
            FROM security_alerts 
            WHERE source_ip IS NOT NULL AND user_id = :user_id{resource_filter}
            GROUP BY source_ip
            ORDER BY count DESC
            LIMIT 20
        """
            ),
            params,
        ).fetchall()

        # Get detection methods
        detection_methods = db.execute(
            text(
                f"""
            SELECT DISTINCT detection_method, COUNT(*) as count
            FROM security_alerts
            WHERE detection_method IS NOT NULL AND user_id = :user_id{resource_filter}
            GROUP BY detection_method
            ORDER BY count DESC
        """
            ),
            params,
        ).fetchall()

        return {
            "severities": SEVERITY_LEVELS,
            "statuses": ALERT_STATUS,
            "source_ips": [{"ip": row[0], "count": row[1]} for row in source_ips],
            "detection_methods": [
                {"method": row[0], "count": row[1]} for row in detection_methods
            ],
        }

    except Exception as e:
        logger.error(f"Error getting filter options: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get filter options: {str(e)}"
        )


@router.delete("/bulk-delete")
async def bulk_delete_alerts(
    alert_ids: List[str] = Body(..., embed=True),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk delete multiple alerts (use with caution)"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        if not alert_ids:
            raise HTTPException(status_code=400, detail="No alert IDs provided")

        if len(alert_ids) > 100:
            raise HTTPException(
                status_code=400, detail="Too many alerts to delete at once (max 100)"
            )

        placeholders = ",".join([f":id_{i}" for i in range(len(alert_ids))])
        params = {f"id_{i}": alert_id for i, alert_id in enumerate(alert_ids)}
        params["user_id"] = user_id

        result = db.execute(
            text(
                f"DELETE FROM security_alerts WHERE id IN ({placeholders}) AND user_id = :user_id"
            ),
            params,
        )
        db.commit()

        return {
            "message": f"Deleted {result.rowcount} alerts",
            "deleted_count": result.rowcount,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk delete: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")


@router.post("/")
async def create_alert(
    alert_data: Dict[str, Any],
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new security alert"""
    try:
        # Get authenticated user ID - alerts are always created for the authenticated user
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Get default category (first one available)
        category_result = db.execute(
            text("SELECT id FROM alert_categories LIMIT 1")
        ).fetchone()
        category_id = category_result[0] if category_result else None

        # Prepare data with defaults
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
    alert_id: str,
    update_data: Dict[str, Any],
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update alert status"""
    try:
        # Get authenticated user ID
        user_id = (
            current_user.id
            if hasattr(current_user, "id")
            else current_user.get("user_id", "21c9dde7-a586-44af-9f67-11f13b9ddd28")
        )

        # Validate alert exists AND belongs to user
        alert_check = db.execute(
            text(
                "SELECT id FROM security_alerts WHERE id = :alert_id AND user_id = :user_id"
            ),
            {"alert_id": alert_id, "user_id": user_id},
        ).fetchone()

        if not alert_check:
            raise HTTPException(
                status_code=404, detail="Alert not found or access denied"
            )

        # Update fields
        update_fields = []
        params = {"alert_id": alert_id, "user_id": user_id}

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
        update_sql = f"UPDATE security_alerts SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = :alert_id AND user_id = :user_id"
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
async def get_alert_categories(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
