from collections import defaultdict
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from db.models import Assignment, QuestionPool, QuizAttempt


DIFFICULTY_WEIGHTS = {"easy": 1.0, "medium": 1.5, "difficult": 2.0}
RECENT_RESPONSE_LIMIT = 5
PRACTICE_MASTERY_THRESHOLD = 60.0


def _response_date(attempt: QuizAttempt) -> datetime:
    return attempt.attemptTimestamp or datetime.min


def _question_id(value: object) -> int | None:
    try:
        question_id = int(value)
    except (TypeError, ValueError):
        return None
    return question_id if question_id > 0 else None


def calculate_topic_mastery(
    db: Session,
    attempts: Iterable[QuizAttempt],
    topic_filter: str | None = None,
) -> dict:
    """Calculate weighted mastery from submitted, question-level persisted answers.

    Weights are easy=1.0, medium=1.5, difficult=2.0. Each correct answer adds
    its weight to the numerator; all answered questions contribute weight to the
    denominator. The result is rounded to one decimal percentage point.
    """
    submitted_attempts = [attempt for attempt in attempts if attempt.isSubmitted]
    if not submitted_attempts:
        return {"topics": {}, "history": []}

    question_ids = {
        question_id
        for attempt in submitted_attempts
        if isinstance(attempt.answers, dict)
        for raw_id in attempt.answers
        if (question_id := _question_id(raw_id)) is not None
    }
    if not question_ids:
        return {"topics": {}, "history": []}

    questions = (
        db.query(QuestionPool)
        .filter(QuestionPool.id.in_(question_ids))
        .all()
    )
    questions_by_id = {question.id: question for question in questions}
    assignment_ids = {
        attempt.assignmentId
        for attempt in submitted_attempts
        if attempt.assignmentId is not None
    }
    assignments = (
        db.query(Assignment)
        .filter(Assignment.id.in_(assignment_ids))
        .all()
        if assignment_ids
        else []
    )
    material_by_assignment = {
        assignment.id: assignment.materialId for assignment in assignments
    }

    normalized_topic = topic_filter.strip().casefold() if topic_filter else ""
    grouped: dict[tuple[int, str], list[tuple[QuizAttempt, QuestionPool, bool]]] = defaultdict(list)
    for attempt in submitted_attempts:
        if not isinstance(attempt.answers, dict):
            continue
        expected_material_id = material_by_assignment.get(attempt.assignmentId)
        for raw_id, answer in attempt.answers.items():
            question_id = _question_id(raw_id)
            question = questions_by_id.get(question_id) if question_id is not None else None
            if question is None or not isinstance(answer, str):
                continue
            if expected_material_id is not None and question.materialId != expected_material_id:
                continue
            if normalized_topic and normalized_topic not in question.conceptTag.casefold():
                continue
            difficulty = question.difficulty
            if difficulty not in DIFFICULTY_WEIGHTS:
                raise ValueError(
                    f"Question {question.id} has unsupported difficulty {difficulty!r}."
                )
            is_correct = answer.strip().casefold() == question.correctAnswer.strip().casefold()
            grouped[(attempt.studentId, question.conceptTag)].append(
                (attempt, question, is_correct)
            )

    topic_results: dict[int, list[dict]] = defaultdict(list)
    history: list[dict] = []
    for (student_id, topic), responses in grouped.items():
        responses.sort(
            key=lambda response: (
                _response_date(response[0]),
                response[0].id,
                response[1].id,
            )
        )
        attempted = 0
        correct = 0
        error_counts = {"easy": 0, "medium": 0, "difficult": 0}
        weighted_total = 0.0
        weighted_correct = 0.0
        attempt_ids: set[int] = set()
        assessment_dates: set[str] = set()
        recent: list[tuple[float, float]] = []
        responses_by_attempt: dict[int, list[tuple[QuizAttempt, QuestionPool, bool]]] = defaultdict(list)
        for response in responses:
            responses_by_attempt[response[0].id].append(response)
        for attempt_id, attempt_responses in sorted(
            responses_by_attempt.items(),
            key=lambda item: (
                _response_date(item[1][0][0]),
                item[0],
            ),
        ):
            attempt_date = (
                attempt_responses[0][0].attemptTimestamp.isoformat()
                if attempt_responses[0][0].attemptTimestamp
                else None
            )
            for attempt, question, is_correct in attempt_responses:
                weight = DIFFICULTY_WEIGHTS[question.difficulty]
                attempted += 1
                attempt_ids.add(attempt.id)
                weighted_total += weight
                if is_correct:
                    correct += 1
                    weighted_correct += weight
                else:
                    error_counts[question.difficulty] += 1
                recent.append((weight, weight if is_correct else 0.0))
                if attempt_date:
                    assessment_dates.add(attempt_date)
            history.append(
                {
                    "studentId": student_id,
                    "topic": topic,
                    "attemptId": attempt_id,
                    "date": attempt_date,
                    "masteryPercent": round(weighted_correct / weighted_total * 100, 1),
                    "sampleSize": attempted,
                }
            )

        recent_responses = recent[-RECENT_RESPONSE_LIMIT:]
        recent_weight = sum(weight for weight, _ in recent_responses)
        recent_correct_weight = sum(value for _, value in recent_responses)
        latest_date = max(assessment_dates) if assessment_dates else None
        topic_results[student_id].append(
            {
                "topic": topic,
                "totalQuestionsAttempted": attempted,
                "sampleSize": attempted,
                "correctAnswers": correct,
                "incorrectAnswers": attempted - correct,
                "errorCounts": error_counts,
                "weightedAccuracy": round(weighted_correct / weighted_total, 4),
                "masteryPercent": round(weighted_correct / weighted_total * 100, 1),
                "attemptCount": len(attempt_ids),
                "assessmentDates": sorted(assessment_dates),
                "lastUpdated": latest_date,
                "recentPerformancePercent": round(
                    recent_correct_weight / recent_weight * 100,
                    1,
                ),
            }
        )

    for student_topics in topic_results.values():
        student_topics.sort(key=lambda item: (item["masteryPercent"], item["topic"].casefold()))
    history.sort(key=lambda item: (item["date"] or "", item["studentId"], item["topic"].casefold()))
    return {"topics": topic_results, "history": history}


def calculate_student_mastery(db: Session, student_id: int) -> list[dict]:
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.studentId == student_id, QuizAttempt.isSubmitted.is_(True))
        .order_by(QuizAttempt.attemptTimestamp.asc(), QuizAttempt.id.asc())
        .all()
    )
    return calculate_topic_mastery(db, attempts)["topics"].get(student_id, [])
