from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.sessions import getDb
from services.homework_service import student_homework

router = APIRouter(prefix="/homework", tags=["Student Homework"])


@router.get("/assignments")
def list_student_homework(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Homework is only available to student accounts.",
        )

    assignments = student_homework(db, current_user["userId"])
    return {
        "studentId": current_user["userId"],
        "profile": current_user,
        "assignments": assignments,
        "count": len(assignments),
    }
