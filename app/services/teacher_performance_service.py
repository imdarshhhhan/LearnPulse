from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import (
    Assignment,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    StudyGroup,
    TeacherClass,
    User,
)
from services.mastery_service import (
    PRACTICE_MASTERY_THRESHOLD,
    calculate_topic_mastery,
)


def _assignment_roster(assignment: Assignment, teacher_class: TeacherClass) -> set[int]:
    class_student_ids = {student.id for student in teacher_class.members}
    class_target_ids = {item.id for item in assignment.targetClasses}
    if class_target_ids and teacher_class.id not in class_target_ids:
        return set()
    if teacher_class.id in class_target_ids:
        return class_student_ids
    if not assignment.targetStudents and not assignment.targetGroups:
        return class_student_ids

    explicit_student_ids = {student.id for student in assignment.targetStudents}
    group_student_ids = {
        member.id
        for group in assignment.targetGroups
        for member in group.members
    }
    return class_student_ids.intersection(explicit_student_ids | group_student_ids)


def _topic_matches(
    assignment: Assignment,
    material_title: str,
    questions_by_material: dict[int, list[QuestionPool]],
    topic_filter: str | None,
) -> bool:
    if not topic_filter:
        return True
    normalized = topic_filter.strip().casefold()
    return normalized in material_title.casefold() or any(
        normalized in question.conceptTag.casefold()
        for question in questions_by_material.get(assignment.materialId, [])
    )


def _latest_submitted(attempts: list[QuizAttempt]) -> QuizAttempt | None:
    submitted = [attempt for attempt in attempts if attempt.isSubmitted]
    return max(
        submitted,
        key=lambda attempt: (attempt.attemptTimestamp or datetime.min, attempt.id),
        default=None,
    )


def _score_percent(attempt: QuizAttempt | None) -> float | None:
    if attempt is None or not attempt.totalQuestions:
        return None
    return round(attempt.score / attempt.totalQuestions * 100, 1)


def _attempt_data(attempt: QuizAttempt) -> dict:
    score_percent = _score_percent(attempt) if attempt.isSubmitted else None
    return {
        "id": attempt.id,
        "status": "submitted" if attempt.isSubmitted else "in_progress",
        "score": attempt.score if attempt.isSubmitted else None,
        "totalQuestions": attempt.totalQuestions if attempt.isSubmitted else None,
        "scorePercent": score_percent,
        "attemptedAt": attempt.attemptTimestamp.isoformat() if attempt.attemptTimestamp else None,
    }


def _class_assessments(
    db: Session,
    teacher_class: TeacherClass,
    topic_filter: str | None = None,
    assessment_id: int | None = None,
) -> tuple[list[Assignment], dict[int, set[int]], dict[int, str], dict[int, list[QuestionPool]]]:
    assignments = (
        db.query(Assignment)
        .filter(Assignment.teacherId == teacher_class.teacherId)
        .order_by(Assignment.createdAt.asc(), Assignment.id.asc())
        .all()
    )
    material_ids = {assignment.materialId for assignment in assignments}
    materials = (
        db.query(ContentMaterial)
        .filter(ContentMaterial.id.in_(material_ids))
        .all()
        if material_ids
        else []
    )
    material_titles = {material.id: material.title for material in materials}
    questions = (
        db.query(QuestionPool)
        .filter(QuestionPool.materialId.in_(material_ids))
        .all()
        if material_ids
        else []
    )
    questions_by_material: dict[int, list[QuestionPool]] = defaultdict(list)
    for question in questions:
        questions_by_material[question.materialId].append(question)

    relevant: list[Assignment] = []
    rosters: dict[int, set[int]] = {}
    for assignment in assignments:
        roster = _assignment_roster(assignment, teacher_class)
        if not roster:
            continue
        if assessment_id is not None and assignment.id != assessment_id:
            continue
        if not _topic_matches(
            assignment,
            material_titles.get(assignment.materialId, ""),
            questions_by_material,
            topic_filter,
        ):
            continue
        relevant.append(assignment)
        rosters[assignment.id] = roster

    return relevant, rosters, material_titles, questions_by_material


def _class_attempts(
    db: Session,
    assignments: list[Assignment],
    student_ids: set[int],
) -> dict[tuple[int, int], list[QuizAttempt]]:
    if not assignments or not student_ids:
        return {}
    attempts = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.assignmentId.in_([assignment.id for assignment in assignments]),
            QuizAttempt.studentId.in_(student_ids),
        )
        .order_by(QuizAttempt.attemptTimestamp.asc(), QuizAttempt.id.asc())
        .all()
    )
    grouped: dict[tuple[int, int], list[QuizAttempt]] = defaultdict(list)
    for attempt in attempts:
        grouped[(attempt.assignmentId, attempt.studentId)].append(attempt)
    return grouped


def _student_summary(
    student: User,
    assignments: list[Assignment],
    rosters: dict[int, set[int]],
    attempts: dict[tuple[int, int], list[QuizAttempt]],
) -> dict:
    possible = sum(student.id in roster for roster in rosters.values())
    latest = [
        _latest_submitted(attempts.get((assignment.id, student.id), []))
        for assignment in assignments
        if student.id in rosters[assignment.id]
    ]
    scores = [score for attempt in latest if (score := _score_percent(attempt)) is not None]
    submitted = sum(attempt is not None for attempt in latest)
    participated = sum(
        bool(attempts.get((assignment.id, student.id)))
        for assignment in assignments
        if student.id in rosters[assignment.id]
    )
    return {
        "id": student.id,
        "fullName": student.fullName,
        "usn": student.usn,
        "averageScorePercent": round(sum(scores) / len(scores), 1) if scores else None,
        "submittedAssessments": submitted,
        "participatedAssessments": participated,
        "eligibleAssessments": possible,
        "masteryPercent": None,
    }


def get_class_performance(
    db: Session,
    teacher_class: TeacherClass,
    topic_filter: str | None = None,
    assessment_id: int | None = None,
) -> dict:
    students = sorted(
        teacher_class.members,
        key=lambda student: (student.fullName.casefold(), student.id),
    )
    assignments, rosters, material_titles, _ = _class_assessments(
        db,
        teacher_class,
        topic_filter,
        assessment_id,
    )
    attempts = _class_attempts(
        db,
        assignments,
        set().union(*rosters.values()) if rosters else set(),
    )
    scoped_attempts = [attempt for history in attempts.values() for attempt in history]
    mastery_by_student = calculate_topic_mastery(db, scoped_attempts, topic_filter)["topics"]

    assessments = []
    opportunity_count = 0
    participation_count = 0
    completion_count = 0
    submitted_score_values = []
    for assignment in assignments:
        roster = rosters[assignment.id]
        opportunity_count += len(roster)
        score_values = []
        participating = 0
        completed = 0
        for student_id in roster:
            history = attempts.get((assignment.id, student_id), [])
            if history:
                participating += 1
            latest = _latest_submitted(history)
            score_percent = _score_percent(latest)
            if latest is not None:
                completed += 1
                if score_percent is not None:
                    score_values.append(score_percent)
                    submitted_score_values.append(score_percent)
        participation_count += participating
        completion_count += completed
        assessments.append(
            {
                "id": assignment.id,
                "title": assignment.title,
                "subject": material_titles.get(assignment.materialId, "Assessment"),
                "date": assignment.createdAt.isoformat() if assignment.createdAt else None,
                "eligibleStudents": len(roster),
                "participatedStudents": participating,
                "completedStudents": completed,
                "averageScorePercent": (
                    round(sum(score_values) / len(score_values), 1)
                    if score_values
                    else None
                ),
                "distribution": {
                    "below50": sum(score < 50 for score in score_values),
                    "from50To69": sum(50 <= score < 70 for score in score_values),
                    "from70To89": sum(70 <= score < 90 for score in score_values),
                    "from90To100": sum(score >= 90 for score in score_values),
                },
            }
        )

    student_summaries = [
        _student_summary(student, assignments, rosters, attempts)
        for student in students
    ]
    for student_summary in student_summaries:
        topics = mastery_by_student.get(student_summary["id"], [])
        student_summary["masteryPercent"] = (
            round(sum(item["masteryPercent"] for item in topics) / len(topics), 1)
            if topics
            else None
        )
    ranked = [student for student in student_summaries if student["averageScorePercent"] is not None]
    topper = max(
        ranked,
        key=lambda student: (student["averageScorePercent"], student["fullName"].casefold()),
        default=None,
    )
    lowest = min(
        ranked,
        key=lambda student: (student["averageScorePercent"], student["fullName"].casefold()),
        default=None,
    )
    average = round(sum(submitted_score_values) / len(submitted_score_values), 1) if submitted_score_values else None

    mastery_values = [
        student["masteryPercent"]
        for student in student_summaries
        if student["masteryPercent"] is not None
    ]

    return {
        "class": {
            "id": teacher_class.id,
            "name": teacher_class.name,
            "subject": teacher_class.subject,
            "description": teacher_class.description,
        },
        "totalStudents": len(students),
        "classAveragePercent": average,
        "topPerformer": topper,
        "lowestPerformer": lowest,
        "averageMasteryPercent": (
            round(sum(mastery_values) / len(mastery_values), 1)
            if mastery_values
            else None
        ),
        "studentsWithMastery": len(mastery_values),
        "participationPercent": (
            round(participation_count / opportunity_count * 100, 1)
            if opportunity_count
            else None
        ),
        "completionPercent": (
            round(completion_count / opportunity_count * 100, 1)
            if opportunity_count
            else None
        ),
        "participatedOpportunities": participation_count,
        "completedOpportunities": completion_count,
        "assessmentOpportunities": opportunity_count,
        "assessments": assessments,
        "students": student_summaries,
    }


def get_student_performance(
    db: Session,
    teacher_class: TeacherClass,
    student: User,
    topic_filter: str | None = None,
    assessment_id: int | None = None,
) -> dict:
    assignments, rosters, material_titles, _ = _class_assessments(
        db,
        teacher_class,
        topic_filter,
        assessment_id,
    )
    allowed_assignments = [
        assignment
        for assignment in assignments
        if student.id in rosters[assignment.id]
    ]
    attempts = _class_attempts(db, allowed_assignments, {student.id})
    mastery = calculate_topic_mastery(
        db,
        [attempt for history in attempts.values() for attempt in history],
        topic_filter,
    )
    student_topics = mastery["topics"].get(student.id, [])
    assessment_history = []
    score_history = []

    for assignment in allowed_assignments:
        history = attempts.get((assignment.id, student.id), [])
        latest_submitted = _latest_submitted(history)
        latest_attempt = history[-1] if history else None
        assessment_history.append(
            {
                "id": assignment.id,
                "title": assignment.title,
                "subject": material_titles.get(assignment.materialId, "Assessment"),
                "date": assignment.createdAt.isoformat() if assignment.createdAt else None,
                "status": "in_progress" if latest_attempt and not latest_attempt.isSubmitted
                else "submitted" if latest_submitted else "not_started",
                "score": latest_submitted.score if latest_submitted else None,
                "totalQuestions": latest_submitted.totalQuestions if latest_submitted else None,
                "scorePercent": _score_percent(latest_submitted),
                "attempts": [_attempt_data(attempt) for attempt in history],
            }
        )

        for attempt in history:
            if not attempt.isSubmitted:
                continue
            score_percent = _score_percent(attempt)
            if score_percent is not None:
                score_history.append(
                    {
                        "assessmentId": assignment.id,
                        "assessmentTitle": assignment.title,
                        "date": attempt.attemptTimestamp.isoformat() if attempt.attemptTimestamp else None,
                        "score": attempt.score,
                        "totalQuestions": attempt.totalQuestions,
                        "scorePercent": score_percent,
                    }
                )

    score_history.sort(key=lambda item: (item["date"] or "", item["assessmentId"]))
    submitted_latest = [
        item["scorePercent"]
        for item in assessment_history
        if item["scorePercent"] is not None
    ]
    return {
        "student": {
            "id": student.id,
            "fullName": student.fullName,
            "usn": student.usn,
            "email": student.email,
        },
        "class": {"id": teacher_class.id, "name": teacher_class.name},
        "averageScorePercent": (
            round(sum(submitted_latest) / len(submitted_latest), 1)
            if submitted_latest
            else None
        ),
        "scoreHistory": score_history,
        "assessments": assessment_history,
        "questionStats": {
            "attempted": sum(item["totalQuestionsAttempted"] for item in student_topics),
            "correct": sum(item["correctAnswers"] for item in student_topics),
            "incorrect": sum(item["incorrectAnswers"] for item in student_topics),
        },
        "topicPerformance": student_topics,
        "masteryHistory": [
            item for item in mastery["history"] if item["studentId"] == student.id
        ],
        "practiceTopics": [
            item["topic"]
            for item in student_topics
            if item["masteryPercent"] < PRACTICE_MASTERY_THRESHOLD
        ],
    }
