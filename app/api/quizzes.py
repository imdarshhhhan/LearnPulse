import random
from datetime import datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# db functions
from db.sessions import getDb
from db.models import (
    Assignment,
    AuditLog,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    StudentMastery,
    StudyGroup,
    TeacherClass,
    User,
    UserRole,
)

# adaptive engine
from services.adaptive_engine import AdaptiveEngine
from services.audit_service import record_audit_action
from services.item_analysis_service import compute_item_analysis_for_material
from services.remediation_service import build_evidence_based_remediation

from api.auth import get_current_user

# schema checkpoints
from schemas.question import RequestQuestionSchema, SubmitAnswerSchema
from schemas.quiz import AssignHomeworkSchema
from services.homework_service import (
    assignment_is_for_student,
    ensure_assignment_open,
    get_student_assignment_attempts,
)
from services.notification_service import (
    create_assignment_notifications,
    reconcile_assignment_completion_notifications,
)
from services.submission_service import create_submission_key
from services.mastery_service import calculate_student_mastery, calculate_topic_mastery


router = APIRouter(prefix="/quizzes", tags=["Adaptive Assessment & Assignments"])

class AssignmentAnswer(BaseModel):
    questionId: int
    selectedOption: str = Field(..., min_length=1, max_length=1000)


class AssignmentSubmission(BaseModel):
    answers: list[AssignmentAnswer] = Field(..., min_length=1)
    submissionId: str | None = Field(
        default=None,
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9-]+$",
    )


class AssignmentProgress(BaseModel):
    answers: list[AssignmentAnswer] = Field(default_factory=list)


class AssignmentRecipients(BaseModel):
    studentIds: list[int] = Field(default_factory=list)
    groupIds: list[int] = Field(default_factory=list)
    classIds: list[int] = Field(default_factory=list)


def _requireStudent(current_user: dict) -> int:
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assignment activity is only available to students.",
        )
    return current_user["userId"]


def _requireTeacher(current_user: dict) -> int:
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This submissions page is only available to teachers.",
        )
    return current_user["userId"]


def _get_student_assignment(db: Session, assignment_id: int, student_id: int) -> Assignment:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment is None or not assignment_is_for_student(assignment, student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    return assignment


def _get_assignment_questions(db: Session, assignment: Assignment) -> list[QuestionPool]:
    return (
        db.query(QuestionPool)
        .filter(
            QuestionPool.materialId == assignment.materialId,
            QuestionPool.isApprovedAutomatically.is_(True),
        )
        .order_by(QuestionPool.id.asc())
        .all()
    )


def _validate_assignment_answers(
    questions: list[QuestionPool],
    answers: list[AssignmentAnswer],
    require_all: bool,
) -> dict[int, str]:
    answer_map = {answer.questionId: answer.selectedOption for answer in answers}
    if len(answer_map) != len(answers):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each question can only be answered once.")

    questions_by_id = {question.id: question for question in questions}
    if not set(answer_map).issubset(questions_by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An answer refers to a question outside this assignment.",
        )
    if require_all and set(questions_by_id) != set(answer_map):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submit one answer for every question in this assignment.",
        )
    for question_id, selected_option in answer_map.items():
        options = questions_by_id[question_id].optionsMatrix
        if not isinstance(options, list) or selected_option not in options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A selected option is not valid for its question.",
            )
    return answer_map


def _submission_answers_match(existing: object, submitted: dict[int, str]) -> bool:
    if not isinstance(existing, dict):
        return False
    normalized = {str(question_id): answer for question_id, answer in submitted.items()}
    return {str(question_id): answer for question_id, answer in existing.items()} == normalized


def _submission_result(attempt: QuizAttempt) -> dict:
    return {
        "attemptId": attempt.id,
        "correctAnswers": int(attempt.score),
        "totalQuestions": attempt.totalQuestions,
        "scorePercent": (
            round(attempt.score / attempt.totalQuestions * 100, 1)
            if attempt.totalQuestions
            else None
        ),
        "attemptedAt": attempt.attemptTimestamp.isoformat() if attempt.attemptTimestamp else None,
        "studentFeedbackNotes": attempt.studentFeedbackNotes,
        "remediationData": getattr(attempt, "remediationData", None),
    }


@router.get("/assignments/{assignment_id}")
def getStudentAssignment(
    assignment_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _requireStudent(current_user)
    assignment = _get_student_assignment(db, assignment_id, student_id)
    questions = _get_assignment_questions(db, assignment)
    material = db.query(ContentMaterial).filter(ContentMaterial.id == assignment.materialId).first()
    teacher = db.query(User).filter(User.id == assignment.teacherId).first()
    attempts = get_student_assignment_attempts(db, assignment_id, student_id)
    progress = next((attempt for attempt in attempts if not attempt.isSubmitted), None)
    submitted_attempts = [attempt for attempt in attempts if attempt.isSubmitted]
    submitted_attempt = submitted_attempts[-1] if submitted_attempts else None

    max_attempts = getattr(assignment, "maxAttempts", 1) or 1
    attempts_used = len(submitted_attempts)
    attempts_remaining = max(0, max_attempts - attempts_used)

    now = datetime.utcnow()
    unavailable_reason = (
        "not_yet_available"
        if assignment.availableWindowStart and assignment.availableWindowStart > now
        else "due_date_passed"
        if assignment.dueDate + timedelta(days=1) <= now
        else "max_attempts_reached"
        if attempts_remaining <= 0 and progress is None
        else None
    )

    time_limit = getattr(assignment, "timeLimitMinutes", None)
    if progress and progress.startedAt and time_limit:
        elapsed = (now - progress.startedAt).total_seconds()
        remaining_seconds = max(0, int(time_limit * 60 - elapsed))
        is_expired = remaining_seconds <= 0
    elif time_limit:
        remaining_seconds = int(time_limit * 60)
        is_expired = False
    else:
        remaining_seconds = None
        is_expired = False

    return {
        "id": assignment.id,
        "title": assignment.title,
        "activityType": assignment.activityType,
        "description": assignment.description,
        "materialTitle": material.title if material else "Study material",
        "teacherName": teacher.fullName if teacher else "Your teacher",
        "dueDate": assignment.dueDate.isoformat() if assignment.dueDate else None,
        "availableFrom": (
            assignment.availableWindowStart.isoformat()
            if assignment.availableWindowStart
            else None
        ),
        "timeLimitMinutes": time_limit,
        "remainingSeconds": remaining_seconds,
        "isExpired": is_expired,
        "maxAttempts": max_attempts,
        "attemptsUsed": attempts_used,
        "attemptsRemaining": attempts_remaining,
        "progressAnswers": progress.answers if progress and progress.answers else {},
        "submittedResult": (
            _submission_result(submitted_attempt) if submitted_attempt else None
        ),
        "canSubmit": unavailable_reason is None and not is_expired,
        "unavailableReason": unavailable_reason,
        "questions": [
            {
                "id": question.id,
                "conceptTag": question.conceptTag,
                "subtopic": getattr(question, "subtopic", question.conceptTag),
                "cognitiveLevel": question.cognitiveLevel,
                "difficulty": question.difficulty,
                "questionType": getattr(question, "questionType", "mcq"),
                "questionText": question.questionText,
                "options": (
                    (progress.optionOrders or {}).get(str(question.id))
                    if progress and getattr(progress, "optionOrders", None) and str(question.id) in progress.optionOrders
                    else question.optionsMatrix
                ),
            }
            for question in questions
        ],
    }


@router.put("/assignments/{assignment_id}/progress")
def saveStudentAssignmentProgress(
    assignment_id: int,
    payload: AssignmentProgress,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _requireStudent(current_user)
    assignment = _get_student_assignment(db, assignment_id, student_id)
    ensure_assignment_open(assignment)
    questions = _get_assignment_questions(db, assignment)
    answers = _validate_assignment_answers(questions, payload.answers, require_all=False)
    attempts = get_student_assignment_attempts(db, assignment_id, student_id)
    attempt = next((item for item in attempts if not item.isSubmitted), None)
    if attempt is None:
        attempt = QuizAttempt(
            studentId=student_id,
            assignmentId=assignment.id,
            score=0,
            totalQuestions=len(questions),
            answers={},
            isSubmitted=False,
        )
        db.add(attempt)
    attempt.answers = answers
    db.commit()
    return {"status": "saved", "answeredQuestions": len(answers)}


@router.post("/assignments/{assignment_id}/submit")
def submitStudentAssignment(
    assignment_id: int,
    payload: AssignmentSubmission,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _requireStudent(current_user)
    assignment = _get_student_assignment(db, assignment_id, student_id)
    ensure_assignment_open(assignment)
    questions = _get_assignment_questions(db, assignment)
    submitted_answers = _validate_assignment_answers(questions, payload.answers, require_all=True)
    questions_by_id = {question.id: question for question in questions}
    serialized_answers = {
        str(question_id): answer for question_id, answer in submitted_answers.items()
    }
    submission_key = create_submission_key(
        student_id,
        f"assignment:{assignment.id}",
        payload.submissionId,
        serialized_answers,
    )
    existing_attempt = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.submissionKey == submission_key)
        .first()
    )
    if existing_attempt is not None:
        if (
            existing_attempt.studentId != student_id
            or existing_attempt.assignmentId != assignment.id
            or not _submission_answers_match(existing_attempt.answers, submitted_answers)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This submission identifier has already been used.",
            )
        return _submission_result(existing_attempt)

    correct_answers = 0
    for question_id, selected_option in submitted_answers.items():
        question = questions_by_id[question_id]
        if selected_option.strip().casefold() == question.correctAnswer.strip().casefold():
            correct_answers += 1

    attempts = get_student_assignment_attempts(db, assignment_id, student_id)
    attempt = next((item for item in attempts if not item.isSubmitted), None)
    if attempt is None:
        attempt = QuizAttempt(studentId=student_id, assignmentId=assignment.id)
        db.add(attempt)
    attempt.score = correct_answers
    attempt.totalQuestions = len(submitted_answers)
    attempt.answers = submitted_answers
    attempt.isSubmitted = True
    attempt.submissionKey = submission_key

    try:
        build_evidence_based_remediation(
            db,
            attempt,
            [questions_by_id[qid] for qid in submitted_answers.keys() if qid in questions_by_id],
        )
    except Exception:
        pass

    for qid, sel in submitted_answers.items():
        q = questions_by_id.get(qid)
        if q:
            is_corr = sel.strip().casefold() == q.correctAnswer.strip().casefold()
            try:
                AdaptiveEngine.updateItemDiffMetric(db, q.id, is_corr)
                AdaptiveEngine.updateStudentMastery(
                    db,
                    student_id,
                    q.conceptTag,
                    q.difficulty_index_p or 0.5,
                    is_corr,
                )
            except Exception:
                pass
    try:
        db.flush()
        reconcile_assignment_completion_notifications(db, assignment)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing_attempt = (
            db.query(QuizAttempt)
            .filter(QuizAttempt.submissionKey == submission_key)
            .first()
        )
        if (
            existing_attempt is not None
            and existing_attempt.studentId == student_id
            and existing_attempt.assignmentId == assignment.id
            and _submission_answers_match(existing_attempt.answers, submitted_answers)
        ):
            return _submission_result(existing_attempt)
        raise exc
    db.refresh(attempt)
    return _submission_result(attempt)


@router.get("/teacher/submissions")
def listTeacherSubmissions(
    activity_id: int | None = Query(default=None, alias="activityId", gt=0),
    student_id: int | None = Query(default=None, alias="studentId", gt=0),
    submission_status: Literal["submitted", "in_progress"] | None = Query(
        default=None,
        alias="status",
    ),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _requireTeacher(current_user)
    attempts_query = (
        db.query(
            QuizAttempt,
            User.id,
            User.fullName,
            User.usn,
            Assignment.id,
            Assignment.title,
        )
        .join(Assignment, QuizAttempt.assignmentId == Assignment.id)
        .join(User, QuizAttempt.studentId == User.id)
        .filter(Assignment.teacherId == teacher_id)
    )
    if activity_id is not None:
        attempts_query = attempts_query.filter(Assignment.id == activity_id)
    if student_id is not None:
        attempts_query = attempts_query.filter(QuizAttempt.studentId == student_id)
    if submission_status is not None:
        attempts_query = attempts_query.filter(
            QuizAttempt.isSubmitted.is_(submission_status == "submitted")
        )

    submissions = []
    for attempt, attempt_student_id, student_name, student_usn, assignment_id, assignment_title in (
        attempts_query.order_by(QuizAttempt.attemptTimestamp.desc()).all()
    ):
        submissions.append(
            {
                "id": attempt.id,
                "studentId": attempt_student_id,
                "studentName": student_name,
                "studentUsn": student_usn,
                "activityId": assignment_id,
                "activityTitle": assignment_title,
                "submittedAt": (
                    attempt.attemptTimestamp.isoformat()
                    if attempt.attemptTimestamp
                    else None
                ),
                "status": "submitted" if attempt.isSubmitted else "in_progress",
                "score": attempt.score if attempt.isSubmitted else None,
                "totalQuestions": attempt.totalQuestions if attempt.isSubmitted else None,
                "scorePercent": (
                    round(attempt.score / attempt.totalQuestions * 100, 1)
                    if attempt.isSubmitted and attempt.totalQuestions
                    else None
                ),
            }
        )

    activities = (
        db.query(Assignment.id, Assignment.title)
        .filter(Assignment.teacherId == teacher_id)
        .order_by(Assignment.title.asc(), Assignment.id.asc())
        .all()
    )
    students = (
        db.query(User.id, User.fullName, User.usn)
        .join(QuizAttempt, QuizAttempt.studentId == User.id)
        .join(Assignment, QuizAttempt.assignmentId == Assignment.id)
        .filter(Assignment.teacherId == teacher_id)
        .distinct()
        .order_by(User.fullName.asc(), User.id.asc())
        .all()
    )
    return {
        "profile": current_user,
        "submissions": submissions,
        "filters": {
            "activities": [{"id": item_id, "title": title} for item_id, title in activities],
            "students": [
                {"id": item_id, "fullName": name, "usn": usn}
                for item_id, name, usn in students
            ],
        },
    }


@router.get("/teacher/submissions/{attempt_id}")
def readTeacherSubmission(
    attempt_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _requireTeacher(current_user)
    result = (
        db.query(QuizAttempt, Assignment, User)
        .join(Assignment, QuizAttempt.assignmentId == Assignment.id)
        .join(User, QuizAttempt.studentId == User.id)
        .filter(
            QuizAttempt.id == attempt_id,
            Assignment.teacherId == teacher_id,
        )
        .first()
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    attempt, assignment, student = result
    questions = _get_assignment_questions(db, assignment)
    raw_answers = attempt.answers if isinstance(attempt.answers, dict) else {}
    answers = []
    for question in questions:
        selected_option = raw_answers.get(
            str(question.id),
            raw_answers.get(question.id),
        )
        answers.append(
            {
                "questionId": question.id,
                "conceptTag": question.conceptTag,
                "difficulty": question.difficulty,
                "questionText": question.questionText,
                "selectedOption": selected_option,
                "correctAnswer": question.correctAnswer,
                "isCorrect": (
                    selected_option.strip().casefold()
                    == question.correctAnswer.strip().casefold()
                    if isinstance(selected_option, str)
                    else False
                ),
            }
        )

    return {
        "profile": current_user,
        "id": attempt.id,
        "studentId": student.id,
        "studentName": student.fullName,
        "studentUsn": student.usn,
        "activityId": assignment.id,
        "activityTitle": assignment.title,
        "submittedAt": (
            attempt.attemptTimestamp.isoformat()
            if attempt.attemptTimestamp
            else None
        ),
        "status": "submitted" if attempt.isSubmitted else "in_progress",
        "score": attempt.score if attempt.isSubmitted else None,
        "totalQuestions": attempt.totalQuestions if attempt.isSubmitted else None,
        "scorePercent": (
            round(attempt.score / attempt.totalQuestions * 100, 1)
            if attempt.isSubmitted and attempt.totalQuestions
            else None
        ),
        "answers": answers,
    }


@router.post("/next-question", status_code=status.HTTP_200_OK)
def fetchAdaptiveQuestion(
    payload: RequestQuestionSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user)
):
    #feature 4  : Adaptive engine
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adaptive questions are only available to students.",
        )
    studentId = current_user.get("userId")
    
    # item response theory 
    adaptiveQuestion = AdaptiveEngine.selectNextAdtvQ(db, studentId, payload.conceptTag)
    
    if not adaptiveQuestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient item variants matching this concept tag inside the question bank."
        )

    return {
        "questionId": adaptiveQuestion.id,
        "questionText": adaptiveQuestion.questionText,
        "optionsMatrix": adaptiveQuestion.optionsMatrix,
        "cognitiveLevel": adaptiveQuestion.cognitiveLevel,
        "difficulty": adaptiveQuestion.difficulty,
    }


def _adaptive_answer_result(
    db: Session,
    question: QuestionPool,
    attempt: QuizAttempt,
    student_id: int,
) -> dict:
    is_correct = attempt.score == 1
    mastery = next(
        (
            item
            for item in calculate_student_mastery(db, student_id)
            if item["topic"] == question.conceptTag
        ),
        None,
    )
    if mastery is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The submitted answer could not be included in mastery calculations.",
        )
    return {
        "attemptId": attempt.id,
        "evaluationStatus": "correct" if is_correct else "incorrect",
        "correctAnswerKey": question.correctAnswer,
        "remediationQuote": question.sourceQuote,
        "updatedStudentMastery": mastery["weightedAccuracy"],
        "masteryPercent": mastery["masteryPercent"],
        "sampleSize": mastery["sampleSize"],
        "updatedItemDifficultyMetric": round(question.difficulty_index_p, 4),
    }


@router.post("/submit-answer", status_code=status.HTTP_200_OK)
def evaluateStudentSubmission(
    payload: SubmitAnswerSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user)
):
    studentId = current_user.get("userId")
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts can submit answers.",
        )

    # fetching row from PostgreSQL
    targetQuestion = db.query(QuestionPool).filter(QuestionPool.id == payload.questionId).first()
    if not targetQuestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Targeted assessment item reference not found."
        )
    if (
        not isinstance(targetQuestion.optionsMatrix, list)
        or payload.chosenOption not in targetQuestion.optionsMatrix
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A selected option is not valid for this question.",
        )
    isCorrect = targetQuestion.correctAnswer.strip().lower() == payload.chosenOption.strip().lower()
    serialized_answer = {str(targetQuestion.id): payload.chosenOption}
    submission_key = create_submission_key(
        studentId,
        f"question:{targetQuestion.id}",
        payload.submissionId,
        serialized_answer,
    )
    existing_attempt = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.submissionKey == submission_key)
        .first()
    )
    if existing_attempt is not None:
        if (
            existing_attempt.studentId != studentId
            or existing_attempt.assignmentId is not None
            or not _submission_answers_match(existing_attempt.answers, {
                targetQuestion.id: payload.chosenOption
            })
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This submission identifier has already been used.",
            )
        return _adaptive_answer_result(db, targetQuestion, existing_attempt, studentId)

    adaptive_attempt = QuizAttempt(
        studentId=studentId,
        assignmentId=None,
        score=1 if isCorrect else 0,
        totalQuestions=1,
        answers=serialized_answer,
        isSubmitted=True,
        submissionKey=submission_key,
    )
    db.add(adaptive_attempt)
    targetQuestion.totalAttemptsLogged = (targetQuestion.totalAttemptsLogged or 0) + 1
    if isCorrect:
        targetQuestion.correctAttemptsLogged = (targetQuestion.correctAttemptsLogged or 0) + 1
    targetQuestion.difficulty_index_p = (
        targetQuestion.correctAttemptsLogged / targetQuestion.totalAttemptsLogged
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_attempt = (
            db.query(QuizAttempt)
            .filter(QuizAttempt.submissionKey == submission_key)
            .first()
        )
        if (
            existing_attempt is not None
            and existing_attempt.studentId == studentId
            and existing_attempt.assignmentId is None
            and _submission_answers_match(existing_attempt.answers, {
                targetQuestion.id: payload.chosenOption
            })
        ):
            return _adaptive_answer_result(db, targetQuestion, existing_attempt, studentId)
        raise
    db.refresh(adaptive_attempt)

    return _adaptive_answer_result(db, targetQuestion, adaptive_attempt, studentId)


@router.post("/assign", status_code=status.HTTP_201_CREATED)
def assignHomeworkActivity(
    payload: AssignHomeworkSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user)
):
    """
    [FEATURE - TEACHER: ASSIGN AN ACTIVITY / HOMEWORK]
    Links a lesson material item to a due date window constraint.
    """
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: This operation requires teacher account permissions."
        )

    teacher_id = current_user["userId"]
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Homework title is required.")
    material = (
        db.query(ContentMaterial)
        .filter(
            ContentMaterial.id == payload.materialId,
            ContentMaterial.teacherId == teacher_id,
        )
        .first()
    )
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study material not found.",
        )
    student_ids = set(payload.studentIds)
    group_ids = set(payload.groupIds)
    class_ids = set(payload.classIds)
    if not student_ids and not group_ids and not class_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one student, group, or class for this assignment.",
        )
    students = (
        db.query(User)
        .filter(User.id.in_(student_ids), User.role == UserRole.STUDENT)
        .all()
        if student_ids
        else []
    )
    if len(students) != len(student_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected recipients are not students.",
        )

    groups = (
        db.query(StudyGroup)
        .filter(StudyGroup.id.in_(group_ids), StudyGroup.creatorId == teacher_id)
        .all()
        if group_ids
        else []
    )
    if len(groups) != len(group_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected groups are not managed by this teacher.",
        )

    classes = (
        db.query(TeacherClass)
        .filter(TeacherClass.id.in_(class_ids), TeacherClass.teacherId == teacher_id)
        .all()
        if class_ids
        else []
    )
    if len(classes) != len(class_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected classes are not managed by this teacher.",
        )

    available_from = payload.availableFrom
    if payload.dueDate < datetime.now(timezone.utc).date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The due date must be today or later.",
        )
    if available_from and available_from.tzinfo:
        available_from = available_from.astimezone(timezone.utc).replace(tzinfo=None)
    due_at = datetime.combine(payload.dueDate, time.min)
    if available_from and available_from >= due_at + timedelta(days=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The availability date must be before the homework due date closes.",
        )

    newAssignment = Assignment(
        title=title,
        description=payload.description.strip() if payload.description else None,
        activityType=payload.activityType,
        materialId=payload.materialId,
        teacherId=teacher_id,
        dueDate=due_at,
        availableWindowStart=available_from or datetime.utcnow(),
        timeLimitMinutes=payload.timeLimitMinutes,
        maxAttempts=payload.maxAttempts if payload.maxAttempts else 1,
        randomizeQuestions=payload.randomizeQuestions if payload.randomizeQuestions is not None else True,
        randomizeOptions=payload.randomizeOptions if payload.randomizeOptions is not None else True,
        poolQuestionCount=payload.poolQuestionCount,
        targetStudents=students,
        targetGroups=groups,
        targetClasses=classes,
    )
    
    db.add(newAssignment)
    db.flush()
    create_assignment_notifications(db, newAssignment)
    record_audit_action(
        db,
        teacher_id,
        "CREATE_ASSIGNMENT",
        "assignment",
        newAssignment.id,
        {
            "title": title,
            "activityType": payload.activityType,
            "dueDate": due_at.isoformat(),
            "timeLimitMinutes": payload.timeLimitMinutes,
            "maxAttempts": payload.maxAttempts,
        },
    )
    db.commit()
    db.refresh(newAssignment)

    return {
        "status": "success",
        "assignmentId": newAssignment.id,
        "title": newAssignment.title,
        "windowClosedAt": newAssignment.dueDate.isoformat()
    }


@router.put("/assignments/{assignment_id}/recipients")
def updateAssignmentRecipients(
    assignment_id: int,
    payload: AssignmentRecipients,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _requireTeacher(current_user)
    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id, Assignment.teacherId == teacher_id)
        .first()
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    student_ids = set(payload.studentIds)
    group_ids = set(payload.groupIds)
    class_ids = set(payload.classIds)
    if not student_ids and not group_ids and not class_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one student, group, or class for this assignment.",
        )

    students = (
        db.query(User)
        .filter(User.id.in_(student_ids), User.role == UserRole.STUDENT)
        .all()
        if student_ids
        else []
    )
    groups = (
        db.query(StudyGroup)
        .filter(StudyGroup.id.in_(group_ids), StudyGroup.creatorId == teacher_id)
        .all()
        if group_ids
        else []
    )
    classes = (
        db.query(TeacherClass)
        .filter(TeacherClass.id.in_(class_ids), TeacherClass.teacherId == teacher_id)
        .all()
        if class_ids
        else []
    )
    if len(students) != len(student_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more selected recipients are not students.")
    if len(groups) != len(group_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more selected groups are not managed by this teacher.")
    if len(classes) != len(class_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more selected classes are not managed by this teacher.")

    assignment.targetStudents = students
    assignment.targetGroups = groups
    assignment.targetClasses = classes
    db.flush()
    create_assignment_notifications(db, assignment)
    reconcile_assignment_completion_notifications(db, assignment)
    db.commit()
    recipient_ids = {
        student.id for student in assignment.targetStudents
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
    return {
        "assignmentId": assignment.id,
        "studentCount": len(recipient_ids),
        "recipientsUpdated": True,
    }


@router.get("/assignment-recipients")
def listHomeworkRecipients(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires teacher account permissions.",
        )
    students = (
        db.query(User)
        .filter(User.role == UserRole.STUDENT)
        .order_by(User.fullName.asc())
        .all()
    )
    groups = (
        db.query(StudyGroup)
        .filter(StudyGroup.creatorId == current_user["userId"])
        .order_by(StudyGroup.name.asc())
        .all()
    )
    classes = (
        db.query(TeacherClass)
        .filter(TeacherClass.teacherId == current_user["userId"])
        .order_by(TeacherClass.name.asc())
        .all()
    )
    return {
        "students": [
            {"id": student.id, "fullName": student.fullName, "usn": student.usn}
            for student in students
        ],
        "groups": [{"id": group.id, "name": group.name} for group in groups],
        "classes": [{"id": teacher_class.id, "name": teacher_class.name} for teacher_class in classes],
    }


# ─── REMEDIATION & EVIDENCE-BASED FEEDBACK (FEATURE 6) ───
@router.get("/attempts/{attempt_id}/remediation")
def getAttemptRemediation(
    attempt_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    attempt = db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt record not found.")

    user_id = current_user.get("userId")
    user_role = current_user.get("role")

    if user_role == "student" and attempt.studentId != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized to view this remediation.")

    if not getattr(attempt, "remediationData", None) and attempt.answers and isinstance(attempt.answers, dict):
        q_ids = [int(qid) for qid in attempt.answers.keys() if str(qid).isdigit()]
        questions = db.query(QuestionPool).filter(QuestionPool.id.in_(q_ids)).all()
        if questions:
            build_evidence_based_remediation(db, attempt, questions)
            db.commit()
            db.refresh(attempt)

    return {
        "attemptId": attempt.id,
        "studentId": attempt.studentId,
        "score": attempt.score,
        "totalQuestions": attempt.totalQuestions,
        "scorePercent": round(attempt.score / max(1, attempt.totalQuestions) * 100, 1),
        "studentFeedbackNotes": attempt.studentFeedbackNotes,
        "remediationData": getattr(attempt, "remediationData", None),
    }


# ─── GENUINE ADAPTIVE ASSESSMENT (FEATURE 4) ───
class PracticeQuizGenerateSchema(BaseModel):
    materialId: int | None = None
    numQuestions: int = Field(default=5, ge=1, le=20)


@router.post("/practice/generate")
def generateAdaptivePracticeQuiz(
    payload: PracticeQuizGenerateSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _requireStudent(current_user)
    questions = AdaptiveEngine.generate_adaptive_practice_quiz(
        db,
        student_id=student_id,
        material_id=payload.materialId,
        num_questions=payload.numQuestions,
    )
    if not questions:
        raise HTTPException(
            status_code=404,
            detail="No questions available for adaptive practice in this pool.",
        )
    return {
        "status": "success",
        "totalQuestions": len(questions),
        "questions": questions,
    }


class PracticeAnswerSchema(BaseModel):
    questionId: int
    selectedOption: str


class PracticeSubmissionSchema(BaseModel):
    answers: list[PracticeAnswerSchema]


@router.post("/practice/submit")
def submitAdaptivePracticeQuiz(
    payload: PracticeSubmissionSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _requireStudent(current_user)
    if not payload.answers:
        raise HTTPException(status_code=400, detail="No answers provided.")

    q_ids = [a.questionId for a in payload.answers]
    questions = db.query(QuestionPool).filter(QuestionPool.id.in_(q_ids)).all()
    questions_by_id = {q.id: q for q in questions}

    submitted_map = {a.questionId: a.selectedOption for a in payload.answers}
    correct_count = 0

    for a in payload.answers:
        q = questions_by_id.get(a.questionId)
        if q:
            is_corr = a.selectedOption.strip().casefold() == q.correctAnswer.strip().casefold()
            if is_corr:
                correct_count += 1
            AdaptiveEngine.updateItemDiffMetric(db, q.id, is_corr)
            AdaptiveEngine.updateStudentMastery(
                db,
                student_id,
                q.conceptTag,
                q.difficulty_index_p or 0.5,
                is_corr,
            )

    attempt = QuizAttempt(
        studentId=student_id,
        assignmentId=None,
        score=correct_count,
        totalQuestions=len(payload.answers),
        answers={str(k): v for k, v in submitted_map.items()},
        isSubmitted=True,
    )
    db.add(attempt)
    db.flush()

    remediation = build_evidence_based_remediation(db, attempt, questions)
    db.commit()
    db.refresh(attempt)

    return {
        "attemptId": attempt.id,
        "score": correct_count,
        "totalQuestions": len(payload.answers),
        "scorePercent": round(correct_count / len(payload.answers) * 100, 1),
        "remediation": remediation,
    }


# ─── QUESTION & DISTRACTOR ANALYSIS (FEATURE 5) ───
@router.get("/materials/{material_id}/item-analysis")
def getMaterialItemAnalysis(
    material_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    _requireTeacher(current_user)
    material = db.query(ContentMaterial).filter(ContentMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found.")
    return compute_item_analysis_for_material(db, material_id)


# ─── AUDIT TRAIL OF TEACHER ACTIONS (FEATURE 7) ───
@router.get("/teacher/audit-logs")
def getTeacherAuditLogs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _requireTeacher(current_user)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.userId == teacher_id)
        .order_by(AuditLog.createdAt.desc())
        .limit(limit)
        .all()
    )
    return {
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "targetType": log.targetType,
                "targetId": log.targetId,
                "details": log.details,
                "createdAt": log.createdAt.isoformat(),
            }
            for log in logs
        ]
    }


# ─── USEFUL ANALYTICS: MASTERY TRENDS & HEATMAP (FEATURE 8) ───
@router.get("/student/mastery-trends")
def getStudentMasteryTrends(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    student_id = _requireStudent(current_user)
    masteries = db.query(StudentMastery).filter(StudentMastery.studentId == student_id).all()
    trends = []
    for m in masteries:
        trends.append({
            "conceptTag": m.conceptTag,
            "masteryScore": round(m.masteryScore * 100, 1),
            "attemptsCount": getattr(m, "attemptsCount", 0) or 0,
            "lastUpdated": m.lastUpdated.isoformat() if m.lastUpdated else None,
            "history": getattr(m, "history", []) or [],
        })
    return {"studentId": student_id, "trends": trends}


@router.get("/teacher/heatmap/{class_id}")
def getTeacherClassHeatmap(
    class_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _requireTeacher(current_user)
    teacher_class = (
        db.query(TeacherClass)
        .filter(TeacherClass.id == class_id, TeacherClass.teacherId == teacher_id)
        .first()
    )
    if not teacher_class:
        raise HTTPException(status_code=404, detail="Class not found or unauthorized.")

    members = teacher_class.members
    student_ids = [s.id for s in members]

    masteries = (
        db.query(StudentMastery)
        .filter(StudentMastery.studentId.in_(student_ids))
        .all()
        if student_ids
        else []
    )

    concepts = sorted(list(dict.fromkeys(m.conceptTag for m in masteries)))
    grid = []

    for s in members:
        row = {
            "studentId": s.id,
            "studentName": s.fullName,
            "usn": s.usn,
            "concepts": {},
        }
        student_mst = {m.conceptTag: m for m in masteries if m.studentId == s.id}
        for c in concepts:
            rec = student_mst.get(c)
            if rec:
                score = round(rec.masteryScore * 100, 1)
                status_label = "Strong" if score >= 80 else ("Developing" if score >= 50 else "Struggling")
                row["concepts"][c] = {
                    "score": score,
                    "status": status_label,
                    "attempts": getattr(rec, "attemptsCount", 0) or 0,
                }
            else:
                row["concepts"][c] = {
                    "score": None,
                    "status": "Not Attempted",
                    "attempts": 0,
                }
        grid.append(row)

    return {
        "classId": class_id,
        "className": teacher_class.name,
        "concepts": concepts,
        "studentHeatmap": grid,
    }

