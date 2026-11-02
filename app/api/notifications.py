from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Literal

from api.auth import get_current_user
from db.models import Notification
from db.sessions import getDb

router = APIRouter(prefix="/notifications", tags=["Student Notifications"])


def _require_student(current_user: dict) -> int:
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Notifications are only available to student accounts.",
        )
    return current_user["userId"]


def _require_teacher(current_user: dict) -> int:
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher notifications are only available to teacher accounts.",
        )
    return current_user["userId"]


def _require_notification_owner(current_user: dict) -> int:
    if current_user.get("role") not in {"student", "teacher"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Notifications are not available to this account.",
        )
    return current_user["userId"]


def _unread_count(db: Session, recipient_id: int) -> int:
    return (
        db.query(func.count(Notification.id))
        .filter(
            Notification.recipientId == recipient_id,
            Notification.isRead.is_(False),
        )
        .scalar()
        or 0
    )


def _serialize(notification: Notification) -> dict:
    notification_type = notification.notificationType
    return {
        "id": notification.id,
        "title": notification.title or "Learning update",
        "message": notification.messageBody,
        "type": notification_type.value,
        "createdAt": notification.createdAt.isoformat() if notification.createdAt else None,
        "isRead": bool(notification.isRead),
        "relatedUrl": notification.relatedUrl,
        "activityType": notification.activityType,
        "audienceName": notification.audienceName,
        "eligibleCount": notification.eligibleCount,
        "submittedCount": notification.submittedCount,
    }


@router.get("")
def list_notifications(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _require_student(current_user)
    notifications = (
        db.query(Notification)
        .filter(Notification.recipientId == student_id)
        .order_by(Notification.createdAt.desc(), Notification.id.desc())
        .limit(100)
        .all()
    )
    return {
        "studentId": student_id,
        "profile": current_user,
        "notifications": [_serialize(notification) for notification in notifications],
        "unreadCount": _unread_count(db, student_id),
    }


@router.get("/teacher")
def list_teacher_notifications(
    activity_type: Literal["quiz", "homework"] | None = Query(
        default=None,
        alias="activityType",
    ),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    query = db.query(Notification).filter(
        Notification.recipientId == teacher_id,
        Notification.sourceType.like("teacher_completion:%"),
    )
    if activity_type:
        query = query.filter(Notification.activityType == activity_type)
    notifications = (
        query.order_by(Notification.createdAt.desc(), Notification.id.desc())
        .limit(500)
        .all()
    )
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.recipientId == teacher_id,
            Notification.sourceType.like("teacher_completion:%"),
            Notification.isRead.is_(False),
        )
        .scalar()
        or 0
    )
    return {
        "profile": current_user,
        "notifications": [_serialize(notification) for notification in notifications],
        "unreadCount": unread_count,
    }


@router.get("/unread-count")
def get_unread_notification_count(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    recipient_id = _require_notification_owner(current_user)
    return {"unreadCount": _unread_count(db, recipient_id)}


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    recipient_id = _require_notification_owner(current_user)
    query = db.query(Notification).filter(
        Notification.recipientId == recipient_id,
        Notification.isRead.is_(False),
    )
    if current_user.get("role") == "teacher":
        query = query.filter(Notification.sourceType.like("teacher_completion:%"))
    updated = query.update({Notification.isRead: True}, synchronize_session=False)
    db.commit()
    return {"updatedCount": updated, "unreadCount": 0}


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    recipient_id = _require_notification_owner(current_user)
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.recipientId == recipient_id,
        )
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    if not notification.isRead:
        notification.isRead = True
        db.commit()
    return {"id": notification.id, "isRead": True}
