from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import TeacherClass, User, UserRole
from db.sessions import getDb
from services.teacher_performance_service import (
    get_class_performance,
    get_student_performance,
)


router = APIRouter(prefix="/teacher/performance", tags=["Teacher Performance"])


def _require_teacher(current_user: dict) -> int:
    if current_user.get("role") != UserRole.TEACHER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Performance data is only available to teachers.",
        )
    return current_user["userId"]


def _get_owned_class(db: Session, class_id: int, teacher_id: int) -> TeacherClass:
    teacher_class = (
        db.query(TeacherClass)
        .filter(TeacherClass.id == class_id, TeacherClass.teacherId == teacher_id)
        .first()
    )
    if teacher_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    return teacher_class


@router.get("/classes")
def list_performance_classes(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    classes = (
        db.query(TeacherClass)
        .filter(TeacherClass.teacherId == teacher_id)
        .order_by(TeacherClass.name.asc(), TeacherClass.id.asc())
        .all()
    )
    return {
        "classes": [
            {"id": teacher_class.id, "name": teacher_class.name, "subject": teacher_class.subject}
            for teacher_class in classes
        ]
    }


@router.get("/classes/{class_id}")
def read_class_performance(
    class_id: int = Path(..., gt=0),
    topic: str | None = Query(default=None, max_length=120),
    assessment_id: int | None = Query(default=None, alias="assessmentId", gt=0),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_class = _get_owned_class(db, class_id, _require_teacher(current_user))
    return {
        "profile": current_user,
        **get_class_performance(db, teacher_class, topic, assessment_id),
    }


@router.get("/classes/{class_id}/students/{student_id}")
def read_student_performance(
    class_id: int = Path(..., gt=0),
    student_id: int = Path(..., gt=0),
    topic: str | None = Query(default=None, max_length=120),
    assessment_id: int | None = Query(default=None, alias="assessmentId", gt=0),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_class = _get_owned_class(db, class_id, _require_teacher(current_user))
    if not any(member.id == student_id for member in teacher_class.members):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student performance not found.",
        )
    student = (
        db.query(User)
        .filter(User.id == student_id, User.role == UserRole.STUDENT)
        .first()
    )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student performance not found.",
        )
    return {
        "profile": current_user,
        **get_student_performance(db, teacher_class, student, topic, assessment_id),
    }
