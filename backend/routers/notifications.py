"""Notification routes - in-app notification management."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Patient
from routers.auth import get_current_user
from services.notification_service import (
    get_user_notifications,
    mark_notification_read,
    get_unread_count
)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
def get_notifications(
    unread_only: bool = False,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notifications for the current user."""
    notifications = get_user_notifications(db, current_user.id, unread_only)
    unread = get_unread_count(db, current_user.id)

    return {
        "notifications": notifications,
        "unread_count": unread
    }


@router.post("/mark-read/{notification_id}")
def mark_read(
    notification_id: int,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    success = mark_notification_read(db, notification_id, current_user.id)
    if not success:
        return {"success": False, "error": "Notification not found"}

    return {"success": True}


@router.get("/unread-count")
def unread_count(
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unread notification count."""
    count = get_unread_count(db, current_user.id)
    return {"unread_count": count}
