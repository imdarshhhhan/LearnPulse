from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import (
    Assignment,
    ContentMaterial,
    QuizAttempt,
    QuestionPool,
    StudentSavedQuiz,
    User,
)
from services.homework_service import assignment_is_for_student
from fastapi import HTTPException, status


def save_student_quiz(
    db: Session,
    student_id: int,
    assignment_id: int,
) -> tuple[StudentSavedQuiz, bool]:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment is None or not assignment_is_for_student(assignment, student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    has_questions = (
        db.query(QuestionPool.id)
        .filter(
            QuestionPool.materialId == assignment.materialId,
            QuestionPool.isApprovedAutomatically.is_(True),
        )
        .first()
    )
    if has_questions is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assignment does not contain an approved quiz.",
        )

    existing = (
        db.query(StudentSavedQuiz)
        .filter(
            StudentSavedQuiz.studentId == student_id,
            StudentSavedQuiz.assignmentId == assignment_id,
        )
        .first()
    )
    if existing is not None:
        return existing, False

    saved_quiz = StudentSavedQuiz(studentId=student_id, assignmentId=assignment_id)
    db.add(saved_quiz)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(StudentSavedQuiz)
            .filter(
                StudentSavedQuiz.studentId == student_id,
                StudentSavedQuiz.assignmentId == assignment_id,
            )
            .first()
        )
        if existing is None:
            raise
        return existing, False
    db.refresh(saved_quiz)
    return saved_quiz, True


def list_student_saved_quizzes(db: Session, student_id: int) -> list[dict]:
    saved_rows = (
        db.query(StudentSavedQuiz, Assignment, ContentMaterial, User.fullName)
        .join(Assignment, StudentSavedQuiz.assignmentId == Assignment.id)
        .join(ContentMaterial, Assignment.materialId == ContentMaterial.id)
        .join(User, Assignment.teacherId == User.id)
        .filter(StudentSavedQuiz.studentId == student_id)
        .order_by(StudentSavedQuiz.savedAt.desc())
        .all()
    )
    if not saved_rows:
        return []

    assignment_ids = [saved.assignmentId for saved, _, _, _ in saved_rows]
    submitted_attempts = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.studentId == student_id,
            QuizAttempt.assignmentId.in_(assignment_ids),
            QuizAttempt.isSubmitted.is_(True),
            QuizAttempt.totalQuestions > 0,
        )
        .all()
    )
    best_scores: dict[int, float] = {}
    for attempt in submitted_attempts:
        score = attempt.score / attempt.totalQuestions * 100
        best_scores[attempt.assignmentId] = max(
            best_scores.get(attempt.assignmentId, 0),
            score,
        )

    question_counts = dict(
        db.query(QuestionPool.materialId, func.count(QuestionPool.id))
        .filter(
            QuestionPool.materialId.in_([assignment.materialId for _, assignment, _, _ in saved_rows]),
            QuestionPool.isApprovedAutomatically.is_(True),
        )
        .group_by(QuestionPool.materialId)
        .all()
    )
    return [
        {
            "id": saved.id,
            "assignmentId": assignment.id,
            "title": assignment.title,
            "topic": material.title,
            "teacherName": teacher_name,
            "savedAt": saved.savedAt.isoformat() if saved.savedAt else None,
            "dueDate": assignment.dueDate.isoformat() if assignment.dueDate else None,
            "questionCount": question_counts.get(material.id, 0),
            "bestScorePercent": (
                round(best_scores[assignment.id], 1)
                if assignment.id in best_scores
                else None
            ),
        }
        for saved, assignment, material, teacher_name in saved_rows
    ]


def remove_student_saved_quiz(
    db: Session,
    student_id: int,
    assignment_id: int,
) -> bool:
    saved_quiz = (
        db.query(StudentSavedQuiz)
        .filter(
            StudentSavedQuiz.studentId == student_id,
            StudentSavedQuiz.assignmentId == assignment_id,
        )
        .first()
    )
    if saved_quiz is None:
        return False
    db.delete(saved_quiz)
    db.commit()
    return True
