from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db.models import (
    Assignment,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    StudentSavedQuiz,
    StudyGroup,
    TeacherClass,
    User,
)


def assignment_is_for_student(assignment: Assignment, student_id: int) -> bool:
    has_individual_targets = bool(assignment.targetStudents)
    has_group_targets = bool(assignment.targetGroups)
    has_class_targets = bool(assignment.targetClasses)
    if not has_individual_targets and not has_group_targets and not has_class_targets:
        return True

    if any(student.id == student_id for student in assignment.targetStudents):
        return True
    if any(
        any(member.id == student_id for member in teacher_class.members)
        for teacher_class in assignment.targetClasses
    ):
        return True
    return any(
        any(member.id == student_id for member in group.members)
        for group in assignment.targetGroups
    )


def assignment_status(
    assignment: Assignment,
    attempts: list[QuizAttempt],
    now: datetime,
) -> str:
    if any(attempt.isSubmitted for attempt in attempts):
        return "completed"
    if assignment.availableWindowStart and assignment.availableWindowStart > now:
        return "upcoming"
    if assignment.dueDate + timedelta(days=1) <= now:
        return "overdue"
    if any(attempt.answers for attempt in attempts):
        return "in_progress"
    return "pending"


def student_homework(db: Session, student_id: int) -> list[dict]:
    assignments = (
        db.query(Assignment)
        .filter(
            (Assignment.targetStudents.any(User.id == student_id))
            | (Assignment.targetGroups.any(StudyGroup.members.any(User.id == student_id)))
            | (Assignment.targetClasses.any(TeacherClass.members.any(User.id == student_id)))
            | (
                ~Assignment.targetStudents.any()
                & ~Assignment.targetGroups.any()
                & ~Assignment.targetClasses.any()
            )
        )
        .order_by(Assignment.dueDate.asc(), Assignment.createdAt.desc())
        .all()
    )
    if not assignments:
        return []

    assignment_ids = [assignment.id for assignment in assignments]
    material_ids = {assignment.materialId for assignment in assignments}
    quiz_material_ids = {
        material_id
        for (material_id,) in db.query(QuestionPool.materialId)
        .filter(
            QuestionPool.materialId.in_(material_ids),
            QuestionPool.isApprovedAutomatically.is_(True),
        )
        .distinct()
        .all()
    }
    saved_assignment_ids = {
        assignment_id
        for (assignment_id,) in db.query(StudentSavedQuiz.assignmentId)
        .filter(
            StudentSavedQuiz.studentId == student_id,
            StudentSavedQuiz.assignmentId.in_(assignment_ids),
        )
        .all()
    }
    attempts_by_assignment: dict[int, list[QuizAttempt]] = {}
    for attempt in (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.studentId == student_id,
            QuizAttempt.assignmentId.in_(assignment_ids),
        )
        .order_by(QuizAttempt.attemptTimestamp.desc())
        .all()
    ):
        attempts_by_assignment.setdefault(attempt.assignmentId, []).append(attempt)

    now = datetime.utcnow()
    results = []
    for assignment in assignments:
        attempts = attempts_by_assignment.get(assignment.id, [])
        submitted = [attempt for attempt in attempts if attempt.isSubmitted]
        best_score = max(
            (attempt.score / attempt.totalQuestions * 100 for attempt in submitted if attempt.totalQuestions),
            default=None,
        )
        material = db.get(ContentMaterial, assignment.materialId)
        results.append(
            {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "materialTitle": material.title if material else "Study material",
                "teacherName": assignment.creator.fullName if assignment.creator else "Your teacher",
                "assignedAt": assignment.createdAt.isoformat() if assignment.createdAt else None,
                "availableFrom": (
                    assignment.availableWindowStart.isoformat()
                    if assignment.availableWindowStart
                    else None
                ),
                "dueDate": assignment.dueDate.isoformat() if assignment.dueDate else None,
                "status": assignment_status(assignment, attempts, now),
                "hasQuiz": assignment.materialId in quiz_material_ids,
                "isSaved": assignment.id in saved_assignment_ids,
                "bestScorePercent": round(best_score, 1) if best_score is not None else None,
                "submissionCount": len(submitted),
                "submittedAt": (
                    submitted[0].attemptTimestamp.isoformat()
                    if submitted and submitted[0].attemptTimestamp
                    else None
                ),
            }
        )
    return results


def get_student_assignment_attempts(
    db: Session,
    assignment_id: int,
    student_id: int,
) -> list[QuizAttempt]:
    return (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.assignmentId == assignment_id,
            QuizAttempt.studentId == student_id,
        )
        .order_by(QuizAttempt.attemptTimestamp.desc())
        .all()
    )


def ensure_assignment_open(assignment: Assignment, now: datetime | None = None) -> None:
    current_time = now or datetime.utcnow()
    if assignment.availableWindowStart and assignment.availableWindowStart > current_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This homework is not available yet.",
        )
    if assignment.dueDate + timedelta(days=1) <= current_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The due date for this homework has passed.",
        )
