from datetime import datetime

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from db.models import (
    Assignment,
    Notification,
    NotificationType,
    QuizAttempt,
    TeacherClass,
    User,
    UserRole,
)


def _assignment_recipients(db: Session, assignment: Assignment) -> set[int]:
    if not assignment.targetStudents and not assignment.targetGroups and not assignment.targetClasses:
        return {
            user_id
            for (user_id,) in db.query(User.id)
            .filter(User.role == UserRole.STUDENT)
            .all()
        }

    recipient_ids = {
        student.id
        for student in assignment.targetStudents
        if student.role == UserRole.STUDENT
    }
    recipient_ids.update(
        member.id
        for group in assignment.targetGroups
        for member in group.members
        if member.role == UserRole.STUDENT
    )
    recipient_ids.update(
        member.id
        for teacher_class in assignment.targetClasses
        for member in teacher_class.members
        if member.role == UserRole.STUDENT
    )
    return recipient_ids


def create_assignment_notifications(db: Session, assignment: Assignment) -> None:
    recipient_ids = _assignment_recipients(db, assignment)
    if not recipient_ids:
        return

    now = datetime.utcnow()
    events = [
        (
            "assignment",
            NotificationType.ASSIGNMENT,
            f"New homework: {assignment.title}",
            f"{assignment.creator.fullName} assigned you new homework.",
        )
    ]
    if assignment.availableWindowStart and assignment.availableWindowStart > now:
        events.append(
            (
                "scheduled_quiz",
                NotificationType.QUIZ,
                f"Quiz scheduled: {assignment.title}",
                f"This quiz will be available on {assignment.availableWindowStart.isoformat()}.",
            )
        )

    source_types = [event[0] for event in events]
    existing = {
        (notification.recipientId, notification.sourceType)
        for notification in db.query(Notification)
        .filter(
            Notification.recipientId.in_(recipient_ids),
            Notification.sourceId == assignment.id,
            Notification.sourceType.in_(source_types),
        )
        .all()
    }
    notifications = []
    for recipient_id in recipient_ids:
        for source_type, notification_type, title, message in events:
            if (recipient_id, source_type) in existing:
                continue
            notifications.append(
                Notification(
                    recipientId=recipient_id,
                    notificationType=notification_type,
                    title=title,
                    messageBody=message,
                    relatedUrl=f"/assignments/{assignment.id}",
                    sourceType=source_type,
                    sourceId=assignment.id,
                    isRead=False,
                )
            )
    db.add_all(notifications)


def _completion_audiences(db: Session, assignment: Assignment) -> list[tuple[str, str, set[int]]]:
    audiences: list[tuple[str, str, set[int]]] = []
    for teacher_class in sorted(assignment.targetClasses, key=lambda item: item.id):
        student_ids = {
            member.id for member in teacher_class.members if member.role == UserRole.STUDENT
        }
        audiences.append(
            (f"class:{teacher_class.id}", teacher_class.name, student_ids)
        )

    for group in sorted(assignment.targetGroups, key=lambda item: item.id):
        student_ids = {member.id for member in group.members if member.role == UserRole.STUDENT}
        audiences.append((f"group:{group.id}", group.name, student_ids))

    direct_student_ids = {
        student.id for student in assignment.targetStudents if student.role == UserRole.STUDENT
    }
    if direct_student_ids:
        audiences.append(("students", "Selected students", direct_student_ids))

    if not audiences and not assignment.targetStudents and not assignment.targetGroups and not assignment.targetClasses:
        student_ids = {
            user_id
            for (user_id,) in db.query(User.id)
            .filter(User.role == UserRole.STUDENT)
            .all()
        }
        audiences.append(("all-students", "All students", student_ids))
    return audiences


def reconcile_assignment_completion_notifications(
    db: Session,
    assignment: Assignment,
) -> None:
    locked_assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment.id)
        .with_for_update()
        .first()
    )
    if locked_assignment is None:
        return

    audiences = _completion_audiences(db, locked_assignment)
    active_sources: set[str] = set()
    for audience_key, audience_name, eligible_student_ids in audiences:
        source_type = f"teacher_completion:{audience_key}"
        active_sources.add(source_type)
        if not eligible_student_ids:
            eligible_count = 0
            submitted_count = 0
        else:
            eligible_count = len(eligible_student_ids)
            submitted_count = (
                db.query(func.count(distinct(QuizAttempt.studentId)))
                .filter(
                    QuizAttempt.assignmentId == locked_assignment.id,
                    QuizAttempt.studentId.in_(eligible_student_ids),
                    QuizAttempt.isSubmitted.is_(True),
                    QuizAttempt.totalQuestions > 0,
                )
                .scalar()
                or 0
            )

        notification = (
            db.query(Notification)
            .filter(
                Notification.recipientId == locked_assignment.teacherId,
                Notification.sourceType == source_type,
                Notification.sourceId == locked_assignment.id,
            )
            .first()
        )
        if eligible_count == 0 or submitted_count < eligible_count:
            if notification is not None:
                db.delete(notification)
            continue

        activity_label = "Quiz" if locked_assignment.activityType == "quiz" else "Homework"
        activity_word = activity_label.lower()
        audience_word = "student" if eligible_count == 1 else "students"
        message = (
            f"All {eligible_count} {audience_word} in {audience_name} have submitted "
            f"{activity_label} {locked_assignment.title}."
        )
        related_url = f"/teacher/submissions?activityId={locked_assignment.id}"
        if notification is None:
            notification = Notification(
                recipientId=locked_assignment.teacherId,
                notificationType=(
                    NotificationType.QUIZ
                    if locked_assignment.activityType == "quiz"
                    else NotificationType.ASSIGNMENT
                ),
                sourceType=source_type,
                sourceId=locked_assignment.id,
                isRead=False,
            )
            db.add(notification)
        notification.title = f"{activity_label} completed"
        notification.messageBody = message
        notification.relatedUrl = related_url
        notification.activityType = activity_word
        notification.audienceName = audience_name
        notification.eligibleCount = eligible_count
        notification.submittedCount = submitted_count

    stale_notifications = (
        db.query(Notification)
        .filter(
            Notification.recipientId == locked_assignment.teacherId,
            Notification.sourceId == locked_assignment.id,
            Notification.sourceType.like("teacher_completion:%"),
        )
        .all()
    )
    for notification in stale_notifications:
        if notification.sourceType not in active_sources:
            db.delete(notification)
