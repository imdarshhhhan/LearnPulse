from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import Assignment, QuizAttempt, StudentFeedback, User, UserRole
from db.sessions import getDb
from services.homework_service import assignment_is_for_student

router = APIRouter(prefix="/feedback", tags=["Student Feedback"])


class FeedbackPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    category: Literal["content", "difficulty", "experience", "other"] | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


def _serialize_feedback(
    feedback: StudentFeedback,
    student_name: str,
    student_usn: str | None,
    assignment: Assignment,
) -> dict:
    return {
        "id": feedback.id,
        "studentId": feedback.studentId,
        "studentName": student_name,
        "studentUsn": student_usn,
        "assignmentId": assignment.id,
        "activityType": assignment.activityType,
        "activityTitle": assignment.title,
        "message": feedback.message,
        "category": feedback.category,
        "rating": feedback.rating,
        "submittedAt": feedback.createdAt.isoformat() if feedback.createdAt else None,
    }


@router.get("/assignments/{assignment_id}")
def read_student_feedback(
    assignment_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can view their assessment feedback.",
        )
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    student_id = current_user["userId"]
    if assignment is None or not assignment_is_for_student(assignment, student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    feedback = (
        db.query(StudentFeedback)
        .filter(
            StudentFeedback.assignmentId == assignment_id,
            StudentFeedback.studentId == student_id,
        )
        .first()
    )
    return {
        "feedback": (
            {
                "message": feedback.message,
                "category": feedback.category,
                "rating": feedback.rating,
                "submittedAt": feedback.createdAt.isoformat() if feedback.createdAt else None,
            }
            if feedback
            else None
        )
    }


@router.post("/assignments/{assignment_id}", status_code=status.HTTP_201_CREATED)
def submit_student_feedback(
    assignment_id: int,
    payload: FeedbackPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can submit assessment feedback.",
        )

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    student_id = current_user["userId"]
    if assignment is None or not assignment_is_for_student(assignment, student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    if assignment.activityType == "quiz":
        has_submitted_attempt = (
            db.query(QuizAttempt.id)
            .filter(
                QuizAttempt.assignmentId == assignment_id,
                QuizAttempt.studentId == student_id,
                QuizAttempt.isSubmitted.is_(True),
                QuizAttempt.totalQuestions > 0,
            )
            .first()
            is not None
        )
        if not has_submitted_attempt:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Complete the quiz before submitting feedback.",
            )

    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback message cannot be empty.",
        )

    feedback = (
        db.query(StudentFeedback)
        .filter(
            StudentFeedback.studentId == student_id,
            StudentFeedback.assignmentId == assignment_id,
        )
        .first()
    )
    if feedback is None:
        feedback = StudentFeedback(
            studentId=student_id,
            assignmentId=assignment_id,
            message=message,
            category=payload.category,
            rating=payload.rating,
        )
        db.add(feedback)
    else:
        feedback.message = message
        feedback.category = payload.category
        feedback.rating = payload.rating

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        feedback = (
            db.query(StudentFeedback)
            .filter(
                StudentFeedback.studentId == student_id,
                StudentFeedback.assignmentId == assignment_id,
            )
            .first()
        )
        if feedback is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Feedback could not be saved. Please try again.",
            )
        feedback.message = message
        feedback.category = payload.category
        feedback.rating = payload.rating
        db.commit()

    db.refresh(feedback)
    return {
        "id": feedback.id,
        "assignmentId": assignment.id,
        "submittedAt": feedback.createdAt.isoformat() if feedback.createdAt else None,
    }


def _require_teacher(current_user: dict) -> int:
    if current_user.get("role") != UserRole.TEACHER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student feedback review is only available to teachers.",
        )
    return current_user["userId"]


def _teacher_feedback_query(db: Session, teacher_id: int):
    return (
        db.query(StudentFeedback, Assignment, User)
        .join(Assignment, StudentFeedback.assignmentId == Assignment.id)
        .join(User, StudentFeedback.studentId == User.id)
        .filter(Assignment.teacherId == teacher_id)
    )


@router.get("/teacher")
def list_teacher_feedback(
    activity_type: Literal["quiz", "homework"] | None = Query(default=None, alias="activityType"),
    assignment_id: int | None = Query(default=None, alias="assignmentId", gt=0),
    search: str | None = Query(default=None, max_length=100),
    sort: Literal["newest", "oldest"] = Query(default="newest"),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    query = _teacher_feedback_query(db, teacher_id)
    if activity_type:
        query = query.filter(Assignment.activityType == activity_type)
    if assignment_id:
        query = query.filter(Assignment.id == assignment_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            StudentFeedback.message.ilike(term)
            | Assignment.title.ilike(term)
            | User.fullName.ilike(term)
            | User.usn.ilike(term)
        )

    order = StudentFeedback.createdAt.asc() if sort == "oldest" else StudentFeedback.createdAt.desc()
    rows = query.order_by(order, StudentFeedback.id.desc()).limit(500).all()
    activities = (
        db.query(Assignment.id, Assignment.title, Assignment.activityType)
        .filter(Assignment.teacherId == teacher_id)
        .order_by(Assignment.title.asc(), Assignment.id.asc())
        .all()
    )
    return {
        "profile": current_user,
        "feedback": [
            _serialize_feedback(item, student.fullName, student.usn, assignment)
            for item, assignment, student in rows
        ],
        "filters": {
            "activities": [
                {"id": item_id, "title": title, "activityType": item_type}
                for item_id, title, item_type in activities
            ]
        },
    }


@router.get("/teacher/{feedback_id}")
def read_teacher_feedback(
    feedback_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    row = (
        _teacher_feedback_query(db, teacher_id)
        .filter(StudentFeedback.id == feedback_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found.")
    feedback, assignment, student = row
    return {
        "profile": current_user,
        **_serialize_feedback(feedback, student.fullName, student.usn, assignment),
    }
