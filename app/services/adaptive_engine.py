import math
import random
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import QuestionPool, StudentMastery
from services.mastery_service import calculate_student_mastery


class AdaptiveEngine:

    @staticmethod
    def calculateMastery(
        current_mastery: float,
        question_difficulty: float,
        is_correct: bool,
    ) -> float:
        """Performance-weighted Bayesian-inspired adaptive mastery update.

        current_mastery: float in [0.0, 1.0]
        question_difficulty: empirical difficulty index P (ratio of correct answers in [0.0, 1.0])
        is_correct: boolean outcome
        """
        alpha = 0.15
        actual_difficulty = 1.0 - question_difficulty

        if is_correct:
            growth_factor = alpha * (1.0 - current_mastery) * (0.5 + actual_difficulty)
            new_mastery = current_mastery + growth_factor
        else:
            decay_factor = alpha * current_mastery * (0.5 + question_difficulty)
            new_mastery = current_mastery - decay_factor

        return max(0.0, min(1.0, round(new_mastery, 4)))

    @staticmethod
    def updateStudentMastery(
        db: Session,
        student_id: int,
        concept_tag: str,
        question_difficulty: float,
        is_correct: bool,
    ) -> float:
        mastery_record = (
            db.query(StudentMastery)
            .filter(
                StudentMastery.studentId == student_id,
                StudentMastery.conceptTag == concept_tag,
            )
            .first()
        )

        if not mastery_record:
            mastery_record = StudentMastery(
                studentId=student_id,
                conceptTag=concept_tag,
                masteryScore=0.5,
                attemptsCount=0,
                history=[],
            )
            db.add(mastery_record)
            db.flush()

        updated_score = AdaptiveEngine.calculateMastery(
            current_mastery=mastery_record.masteryScore,
            question_difficulty=question_difficulty,
            is_correct=is_correct,
        )

        mastery_record.masteryScore = updated_score
        mastery_record.attemptsCount = (getattr(mastery_record, "attemptsCount", 0) or 0) + 1
        now_iso = datetime.utcnow().isoformat()
        mastery_record.lastUpdated = datetime.utcnow()

        history_list = list(getattr(mastery_record, "history", []) or [])
        history_list.append({
            "timestamp": now_iso,
            "score": round(updated_score * 100, 1),
            "outcome": "correct" if is_correct else "incorrect",
        })
        mastery_record.history = history_list[-20:]

        db.commit()
        return updated_score

    @staticmethod
    def selectNextAdtvQ(
        db: Session,
        student_id: int,
        concept_tag: str,
    ) -> QuestionPool | None:
        topic_mastery = next(
            (
                item
                for item in calculate_student_mastery(db, student_id)
                if item["topic"] == concept_tag
            ),
            None,
        )
        student_competence = (
            topic_mastery["weightedAccuracy"] if topic_mastery else 0.5
        )

        question_candidates = (
            db.query(QuestionPool)
            .filter(
                QuestionPool.conceptTag == concept_tag,
                QuestionPool.isApprovedAutomatically.is_(True),
                QuestionPool.isArchived.is_(False),
            )
            .all()
        )

        if not question_candidates:
            return None

        target_p_index = 1.0 - student_competence
        question_candidates.sort(
            key=lambda q: abs((q.difficulty_index_p or 0.5) - target_p_index)
        )

        top_pool = question_candidates[:2]
        return random.choice(top_pool)

    @staticmethod
    def generate_adaptive_practice_quiz(
        db: Session,
        student_id: int,
        material_id: int | None = None,
        num_questions: int = 5,
    ) -> list[dict]:
        """Generates an adaptive practice session.

        Biases concept selection towards the student's weakest concepts:
        Weight W_c = (1.05 - Mastery_c)^2
        And matches question difficulty to the Zone of Proximal Development.
        """
        query = db.query(QuestionPool).filter(
            QuestionPool.isApprovedAutomatically.is_(True),
            QuestionPool.isArchived.is_(False),
        )
        if material_id:
            query = query.filter(QuestionPool.materialId == material_id)

        all_questions = query.all()
        if not all_questions:
            return []

        # Get student mastery across topics
        student_masteries = {
            item["topic"]: item["weightedAccuracy"]
            for item in calculate_student_mastery(db, student_id)
        }

        # Group questions by conceptTag
        questions_by_concept: dict[str, list[QuestionPool]] = {}
        for q in all_questions:
            questions_by_concept.setdefault(q.conceptTag, []).append(q)

        # Calculate sampling weight for each concept: higher weight for lower mastery
        concept_weights = {}
        for c in questions_by_concept:
            m = student_masteries.get(c, 0.5)
            # Inverse quadratic weight: mastery=0.2 -> weight=0.72; mastery=0.9 -> weight=0.02
            deficit = max(0.05, 1.05 - m)
            concept_weights[c] = deficit ** 2

        selected_questions: list[QuestionPool] = []
        selected_ids: set[int] = set()

        available_concepts = list(concept_weights.keys())
        total_needed = min(num_questions, len(all_questions))

        while len(selected_questions) < total_needed and available_concepts:
            # Weighted random selection of concept
            weights = [concept_weights[c] for c in available_concepts]
            total_w = sum(weights)
            if total_w <= 0:
                chosen_concept = random.choice(available_concepts)
            else:
                chosen_concept = random.choices(available_concepts, weights=weights, k=1)[0]

            pool = [q for q in questions_by_concept[chosen_concept] if q.id not in selected_ids]
            if not pool:
                available_concepts.remove(chosen_concept)
                continue

            current_m = student_masteries.get(chosen_concept, 0.5)
            target_p = 1.0 - current_m
            pool.sort(key=lambda q: abs((q.difficulty_index_p or 0.5) - target_p))

            best_match = pool[0]
            selected_questions.append(best_match)
            selected_ids.add(best_match.id)

        return [
            {
                "questionId": q.id,
                "questionText": q.questionText,
                "questionType": getattr(q, "questionType", "mcq"),
                "optionsMatrix": q.optionsMatrix,
                "conceptTag": q.conceptTag,
                "subtopic": getattr(q, "subtopic", q.conceptTag),
                "difficulty": q.difficulty,
                "cognitiveLevel": q.cognitiveLevel,
            }
            for q in selected_questions
        ]

    @staticmethod
    def updateItemDiffMetric(
        db: Session,
        question_id: int,
        is_correct: bool,
    ) -> float:
        question = db.query(QuestionPool).filter(QuestionPool.id == question_id).first()
        if not question:
            return 1.0

        question.totalAttemptsLogged = (question.totalAttemptsLogged or 0) + 1
        if is_correct:
            question.correctAttemptsLogged = (question.correctAttemptsLogged or 0) + 1

        new_p_index = question.correctAttemptsLogged / question.totalAttemptsLogged
        question.difficulty_index_p = round(new_p_index, 4)

        db.commit()
        return new_p_index
