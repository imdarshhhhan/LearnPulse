from collections import defaultdict
from sqlalchemy.orm import Session

from db.models import ContentMaterial, QuestionPool, QuizAttempt


def build_evidence_based_remediation(
    db: Session,
    attempt: QuizAttempt,
    questions: list[QuestionPool],
) -> dict:
    submitted_answers = attempt.answers if isinstance(attempt.answers, dict) else {}
    questions_by_id = {q.id: q for q in questions}

    question_breakdown = []
    concept_stats = defaultdict(lambda: {"total": 0, "correct": 0, "mistakes": []})
    study_recommendations = []

    for q in questions:
        selected = str(submitted_answers.get(str(q.id)) or submitted_answers.get(q.id) or "").strip()
        correct = str(q.correctAnswer).strip()
        is_correct = selected.casefold() == correct.casefold()

        concept = q.conceptTag or "General"
        concept_stats[concept]["total"] += 1
        if is_correct:
            concept_stats[concept]["correct"] += 1
        else:
            concept_stats[concept]["mistakes"].append(q.questionText)

        page_ref = getattr(q, "sourcePage", None) or 1
        source_quote = getattr(q, "sourceQuote", "") or ""
        explanation = getattr(q, "explanation", "") or f"Supported by the uploaded material: {source_quote}"

        question_breakdown.append({
            "questionId": q.id,
            "questionText": q.questionText,
            "selectedOption": selected,
            "correctAnswer": correct,
            "isCorrect": is_correct,
            "explanation": explanation,
            "sourceQuote": source_quote,
            "sourcePage": page_ref,
            "conceptTag": concept,
            "subtopic": getattr(q, "subtopic", concept),
            "difficulty": q.difficulty,
            "cognitiveLevel": q.cognitiveLevel,
        })

    concepts_needing_revision = []
    strong_concepts = []

    for concept, stats in concept_stats.items():
        accuracy = round(stats["correct"] / stats["total"] * 100, 1)
        if accuracy < 75.0:
            concepts_needing_revision.append({
                "concept": concept,
                "accuracyPercent": accuracy,
                "mistakesCount": stats["total"] - stats["correct"],
                "totalConceptQuestions": stats["total"],
            })
        else:
            strong_concepts.append({
                "concept": concept,
                "accuracyPercent": accuracy,
            })

    # Pull material information for section recommendations
    material = None
    if questions and questions[0].materialId:
        material = db.query(ContentMaterial).filter(ContentMaterial.id == questions[0].materialId).first()

    material_title = material.title if material else "Course Material"

    for weak in concepts_needing_revision:
        concept_name = weak["concept"]
        relevant_quotes = [
            q["sourceQuote"]
            for q in question_breakdown
            if q["conceptTag"] == concept_name and not q["isCorrect"] and q["sourceQuote"]
        ]
        pages_to_review = list(dict.fromkeys(
            q["sourcePage"]
            for q in question_breakdown
            if q["conceptTag"] == concept_name and not q["isCorrect"]
        ))
        page_str = ", ".join(f"Page {p}" for p in pages_to_review) if pages_to_review else "All Sections"

        study_recommendations.append({
            "concept": concept_name,
            "recommendedSection": f"{material_title} — Focus on {concept_name} ({page_str})",
            "keyExcerptsToReview": relevant_quotes[:3],
            "actionGuidance": f"Review the grounded notes on '{concept_name}' before launching the adaptive practice quiz.",
        })

    summary_note = (
        f"Scored {int(attempt.score)}/{attempt.totalQuestions} ({round(attempt.score / max(1, attempt.totalQuestions) * 100, 1)}%). "
        + (
            f"Focus revision on: {', '.join(c['concept'] for c in concepts_needing_revision)}."
            if concepts_needing_revision
            else "Mastery demonstrated across all evaluated concepts."
        )
    )

    remediation_payload = {
        "attemptId": attempt.id,
        "score": attempt.score,
        "totalQuestions": attempt.totalQuestions,
        "scorePercent": round(attempt.score / max(1, attempt.totalQuestions) * 100, 1),
        "summary": summary_note,
        "questionBreakdown": question_breakdown,
        "conceptsNeedingRevision": concepts_needing_revision,
        "strongConcepts": strong_concepts,
        "studyRecommendations": study_recommendations,
        "nextSteps": {
            "canGeneratePracticeQuiz": len(concepts_needing_revision) > 0,
            "targetConcepts": [c["concept"] for c in concepts_needing_revision],
            "message": "Launch a targeted adaptive quiz on these concepts to strengthen your mastery.",
        },
    }

    attempt.studentFeedbackNotes = summary_note
    attempt.remediationData = remediation_payload
    return remediation_payload
