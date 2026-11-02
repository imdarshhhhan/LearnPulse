from datetime import datetime
from sqlalchemy.orm import Session

from db.models import AuditLog


def record_audit_action(
    db: Session,
    user_id: int,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    log_entry = AuditLog(
        userId=user_id,
        action=action,
        targetType=target_type,
        targetId=target_id,
        details=details or {},
        createdAt=datetime.utcnow(),
    )
    db.add(log_entry)
    return log_entry
