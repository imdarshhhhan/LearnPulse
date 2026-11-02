from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.sessions import getDb
from services.saved_quiz_service import (
    list_student_saved_quizzes,
    remove_student_saved_quiz,
    save_student_quiz,
)

router = APIRouter(prefix="/saved-quizzes", tags=["Student Saved Quizzes"])


def _require_student(current_user: dict) -> int:
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Saved quizzes are only available to student accounts.",
        )
    return current_user["userId"]


@router.get("")
def list_saved_quizzes(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _require_student(current_user)
    return {
        "studentId": student_id,
        "profile": current_user,
        "quizzes": list_student_saved_quizzes(db, student_id),
    }


@router.post("/{assignment_id}", status_code=status.HTTP_201_CREATED)
def save_quiz(
    assignment_id: int,
    response: Response,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _require_student(current_user)
    saved_quiz, created = save_student_quiz(db, student_id, assignment_id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {
        "id": saved_quiz.id,
        "assignmentId": saved_quiz.assignmentId,
        "savedAt": saved_quiz.savedAt.isoformat() if saved_quiz.savedAt else None,
        "saved": True,
    }


@router.delete("/{assignment_id}")
def remove_saved_quiz(
    assignment_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _require_student(current_user)
    if not remove_student_saved_quiz(db, student_id, assignment_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved quiz not found.",
        )
    return {"removed": True}
