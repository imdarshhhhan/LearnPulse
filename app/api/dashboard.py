from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import (
    Assignment,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    User,
)
from db.sessions import getDb
from services.mastery_service import calculate_student_mastery
from services.homework_service import student_homework

router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


def _requireRole(currentUser: dict, role: str) -> None:
    """Server-side role gate. The frontend redirect is only a convenience."""
    if currentUser["role"] != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This dashboard is only available to {role} accounts.",
        )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/teacher")
def readTeacherDashboard(
    db: Session = Depends(getDb),
    currentUser: dict = Depends(get_current_user),
):
    _requireRole(currentUser, "teacher")
    teacherId = currentUser["userId"]

    materials = (
        db.query(ContentMaterial)
        .filter(ContentMaterial.teacherId == teacherId)
        .order_by(ContentMaterial.createdAt.desc())
        .all()
    )
    materialIds = [m.id for m in materials]
    materialTitles = {m.id: m.title for m in materials}

    questionCounts = dict(
        db.query(QuestionPool.materialId, func.count(QuestionPool.id))
        .filter(QuestionPool.materialId.in_(materialIds))
        .group_by(QuestionPool.materialId)
        .all()
    )

    assignments = (
        db.query(Assignment)
        .filter(Assignment.teacherId == teacherId)
        .order_by(Assignment.dueDate.desc())
        .all()
    )
    attemptCounts = dict(
        db.query(QuizAttempt.assignmentId, func.count(QuizAttempt.id))
        .filter(QuizAttempt.assignmentId.in_([a.id for a in assignments]))
        .group_by(QuizAttempt.assignmentId)
        .all()
    )

    return {
        "profile": currentUser,
        "stats": {
            "materials": len(materials),
            "assignments": len(assignments),
            "questionsInBank": sum(questionCounts.values()),
            "submissions": sum(attemptCounts.values()),
        },
        "materials": [
            {
                "id": m.id,
                "title": m.title,
                "createdAt": _iso(m.createdAt),
                "questionCount": questionCounts.get(m.id, 0),
            }
            for m in materials
        ],
        "assignments": [
            {
                "id": a.id,
                "title": a.title,
                "materialTitle": materialTitles.get(a.materialId, "Unknown material"),
                "dueDate": _iso(a.dueDate),
                "submissions": attemptCounts.get(a.id, 0),
            }
            for a in assignments
        ],
    }


@router.get("/student")
def readStudentDashboard(
    db: Session = Depends(getDb),
    currentUser: dict = Depends(get_current_user),
):
    _requireRole(currentUser, "student")
    studentId = currentUser["userId"]

    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.studentId == studentId, QuizAttempt.isSubmitted.is_(True))
        .order_by(QuizAttempt.attemptTimestamp.desc())
        .all()
    )
    assignmentItems = student_homework(db, studentId)
    assignmentTitles = {assignment["id"]: assignment["title"] for assignment in assignmentItems}

    mastery = calculate_student_mastery(db, studentId)

    scored = [a for a in attempts if a.totalQuestions]
    averageScore = (
        round(sum(a.score / a.totalQuestions * 100 for a in scored) / len(scored), 1)
        if scored
        else None
    )

    return {
        "profile": currentUser,
        "stats": {
            "openAssignments": sum(
                1
                for assignment in assignmentItems
                if assignment["status"] in {"upcoming", "pending", "in_progress"}
            ),
            "completedAssignments": sum(
                1 for a in assignmentItems if a["status"] == "completed"
            ),
            "averageScorePercent": averageScore,
            "conceptsTracked": len(mastery),
        },
        "assignments": assignmentItems,
        "mastery": [
            {
                "conceptTag": m["topic"],
                "masteryPercent": m["masteryPercent"],
                "sampleSize": m["sampleSize"],
                "correctAnswers": m["correctAnswers"],
                "incorrectAnswers": m["incorrectAnswers"],
                "difficultyErrors": m["errorCounts"],
                "recentPerformancePercent": m["recentPerformancePercent"],
                "lastUpdated": m["lastUpdated"],
            }
            for m in mastery
        ],
        "recentAttempts": [
            {
                "id": a.id,
                "assignmentTitle": assignmentTitles.get(a.assignmentId, "Practice quiz"),
                "scorePercent": (
                    round(a.score / a.totalQuestions * 100, 1) if a.totalQuestions else 0
                ),
                "attemptedAt": _iso(a.attemptTimestamp),
            }
            for a in attempts[:5]
        ],
    }