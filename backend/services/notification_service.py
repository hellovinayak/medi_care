"""In-app notification service.

This is the alternative notification mechanism (different from email)
used for doctor summary reports as required by Scenario 2.
"""

from sqlalchemy.orm import Session
from database.models import Notification, Patient
from datetime import datetime


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "info"
) -> Notification:
    """Create an in-app notification."""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    print(f"🔔 [NOTIFICATION] To user #{user_id}: {title}")
    return notification


def get_user_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50
) -> list:
    """Get notifications for a user."""
    query = db.query(Notification).filter(Notification.user_id == user_id)

    if unread_only:
        query = query.filter(Notification.is_read == False)

    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()

    return [{
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "type": n.notification_type,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None
    } for n in notifications]


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark a notification as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()

    if notification:
        notification.is_read = True
        db.commit()
        return True
    return False


def get_unread_count(db: Session, user_id: int) -> int:
    """Get count of unread notifications."""
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()
