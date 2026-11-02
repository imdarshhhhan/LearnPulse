from collections import defaultdict
from sqlalchemy.orm import Session

from db.models import Assignment, ContentMaterial, QuestionPool, QuizAttempt


def compute_item_analysis_for_material(db: Session, material_id: int) -> dict:
    questions = (
        db.query(QuestionPool)
        .filter(QuestionPool.materialId == material_id, QuestionPool.isArchived.is_(False))
        .order_by(QuestionPool.id.asc())
        .all()
    )

    if not questions:
        return {"materialId": material_id, "questions": [], "summary": {}}

    assignments = db.query(Assignment).filter(Assignment.materialId == material_id).all()
    assignment_ids = [a.id for a in assignments]

    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.assignmentId.in_(assignment_ids), QuizAttempt.isSubmitted.is_(True))
        .all()
    )

    # Also include practice attempts that answered these questions
    question_ids = {q.id for q in questions}

    # Map student total scores for discrimination index partitioning
    student_scores: dict[int, list[float]] = defaultdict(list)
    for att in attempts:
        if att.totalQuestions and att.totalQuestions > 0:
            student_scores[att.studentId].append(att.score / att.totalQuestions)

    student_avg_score = {
        sid: sum(scs) / len(scs) for sid, scs in student_scores.items()
    }

    # Group students into upper 50% and lower 50%
    sorted_students = sorted(student_avg_score.items(), key=lambda x: x[1], reverse=True)
    n_students = len(sorted_students)
    upper_students = set(sid for sid, _ in sorted_students[: max(1, n_students // 2)])
    lower_students = set(sid for sid, _ in sorted_students[max(1, n_students // 2):]) if n_students > 1 else set()

    # Collect responses per question
    question_responses: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for att in attempts:
        if isinstance(att.answers, dict):
            for qid_str, selected in att.answers.items():
                try:
                    qid = int(qid_str)
                    if qid in question_ids and isinstance(selected, str):
                        question_responses[qid].append((att.studentId, selected.strip()))
                except (ValueError, TypeError):
                    continue

    analyzed_items = []
    total_health_scores = []

    for q in questions:
        responses = question_responses.get(q.id, [])
        total_attempts = len(responses)

        options = q.optionsMatrix if isinstance(q.optionsMatrix, list) else []
        correct_answer = q.correctAnswer.strip().lower()

        if total_attempts == 0:
            analyzed_items.append({
                "id": q.id,
                "questionText": q.questionText,
                "questionType": getattr(q, "questionType", "mcq"),
                "conceptTag": q.conceptTag,
                "subtopic": getattr(q, "subtopic", q.conceptTag),
                "difficulty": q.difficulty,
                "cognitiveLevel": q.cognitiveLevel,
                "correctAnswer": q.correctAnswer,
                "options": options,
                "totalAttempts": 0,
                "correctAttempts": 0,
                "difficultyIndexP": round(q.difficulty_index_p, 3),
                "difficultyRating": "Uncalibrated",
                "discriminationIndex": None,
                "discriminationRating": "Insufficient Data",
                "distractorAnalysis": [
                    {
                        "option": opt,
                        "selectionCount": 0,
                        "selectionPercent": 0.0,
                        "isCorrect": opt.strip().lower() == correct_answer,
                        "status": "CORRECT_KEY" if opt.strip().lower() == correct_answer else "UNTESTED",
                    }
                    for opt in options
                ],
                "healthStatus": "NEEDS_DATA",
                "recommendation": "Gather student attempts to calibrate item metrics.",
            })
            continue

        correct_count = sum(1 for _, ans in responses if ans.strip().lower() == correct_answer)
        p_val = round(correct_count / total_attempts, 3)

        # Upper vs Lower responses for Discrimination Index D
        upper_resp = [ans for sid, ans in responses if sid in upper_students]
        lower_resp = [ans for sid, ans in responses if sid in lower_students]

        p_upper = (
            sum(1 for a in upper_resp if a.strip().lower() == correct_answer) / len(upper_resp)
            if upper_resp
            else p_val
        )
        p_lower = (
            sum(1 for a in lower_resp if a.strip().lower() == correct_answer) / len(lower_resp)
            if lower_resp
            else p_val
        )
        discrimination = round(p_upper - p_lower, 3) if lower_resp else None

        # Option selection breakdown
        distractor_stats = []
        has_misleading_distractor = False
        has_non_functioning = False

        for opt in options:
            opt_clean = opt.strip().lower()
            opt_chosen = [ans for _, ans in responses if ans.strip().lower() == opt_clean]
            count = len(opt_chosen)
            pct = round(count / total_attempts * 100, 1)
            is_key = opt_clean == correct_answer

            opt_upper = sum(1 for sid, ans in responses if sid in upper_students and ans.strip().lower() == opt_clean)
            opt_lower = sum(1 for sid, ans in responses if sid in lower_students and ans.strip().lower() == opt_clean)

            if is_key:
                status = "CORRECT_KEY"
            elif opt_upper > opt_lower and opt_upper > 0:
                status = "AMBIGUOUS_DISTRACTOR"
                has_misleading_distractor = True
            elif pct < 5.0 and total_attempts >= 5:
                status = "NON_FUNCTIONING"
                has_non_functioning = True
            else:
                status = "FUNCTIONING_DISTRACTOR"

            distractor_stats.append({
                "option": opt,
                "selectionCount": count,
                "selectionPercent": pct,
                "upperGroupCount": opt_upper,
                "lowerGroupCount": opt_lower,
                "isCorrect": is_key,
                "status": status,
            })

        # Difficulty categorization
        if p_val >= 0.85:
            diff_rating = "Easy"
        elif p_val <= 0.35:
            diff_rating = "Hard"
        else:
            diff_rating = "Moderate"

        # Discrimination categorization
        if discrimination is None:
            disc_rating = "Insufficient Split"
        elif discrimination >= 0.35:
            disc_rating = "Strong Discriminator"
        elif discrimination >= 0.20:
            disc_rating = "Acceptable"
        elif discrimination >= 0.0:
            disc_rating = "Weak Discriminator"
        else:
            disc_rating = "Defective (Negative)"

        # Health status & recommendation
        if discrimination is not None and discrimination < 0.0:
            health = "DEFECTIVE"
            rec = "Remove or completely rewrite: lower-scoring students got this right more often than high-scorers."
        elif has_misleading_distractor:
            health = "NEEDS_REVISION"
            rec = "Revise distractor: an incorrect option is disproportionately attracting top-performing students."
        elif has_non_functioning:
            health = "MARGINAL"
            rec = "Plausibility check: one or more distractors were never chosen by students."
        elif discrimination is not None and discrimination >= 0.25 and 0.30 <= p_val <= 0.85:
            health = "EXCELLENT"
            rec = "High-quality question: excellent balance of difficulty and discrimination."
        else:
            health = "GOOD"
            rec = "Acceptable performance. Keep monitoring as more students complete attempts."

        # Update persisted fields on question
        q.difficulty_index_p = p_val
        q.totalAttemptsLogged = total_attempts
        q.correctAttemptsLogged = correct_count
        if discrimination is not None:
            q.discriminationIndex = discrimination

        analyzed_items.append({
            "id": q.id,
            "questionText": q.questionText,
            "questionType": getattr(q, "questionType", "mcq"),
            "conceptTag": q.conceptTag,
            "subtopic": getattr(q, "subtopic", q.conceptTag),
            "difficulty": q.difficulty,
            "cognitiveLevel": q.cognitiveLevel,
            "correctAnswer": q.correctAnswer,
            "options": options,
            "totalAttempts": total_attempts,
            "correctAttempts": correct_count,
            "difficultyIndexP": p_val,
            "difficultyRating": diff_rating,
            "discriminationIndex": discrimination,
            "discriminationRating": disc_rating,
            "distractorAnalysis": distractor_stats,
            "healthStatus": health,
            "recommendation": rec,
        })
        total_health_scores.append(100 if health == "EXCELLENT" else (75 if health == "GOOD" else 40))

    try:
        db.commit()
    except Exception:
        db.rollback()

    avg_health = round(sum(total_health_scores) / len(total_health_scores), 1) if total_health_scores else None

    return {
        "materialId": material_id,
        "totalQuestions": len(questions),
        "totalAttemptsLogged": sum(item["totalAttempts"] for item in analyzed_items),
        "averageItemHealth": avg_health,
        "questions": analyzed_items,
    }
