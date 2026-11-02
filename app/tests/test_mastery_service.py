import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Assignment, Base, ContentMaterial, QuestionPool, QuizAttempt, User, UserRole
from services.mastery_service import calculate_topic_mastery


class MasteryServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        self.teacher = User(
            email="teacher@example.test",
            fullName="Teacher",
            role=UserRole.TEACHER,
        )
        self.student = User(
            email="student@example.test",
            fullName="Student",
            role=UserRole.STUDENT,
            usn="1AB23CS001",
        )
        self.session.add_all([self.teacher, self.student])
        self.session.flush()
        self.material = ContentMaterial(title="Biology", teacher=self.teacher)
        self.session.add(self.material)
        self.session.flush()
        self.questions = []
        for difficulty in ("easy", "medium", "difficult"):
            question = QuestionPool(
                materialId=self.material.id,
                conceptTag="Cell biology",
                questionText=f"{difficulty} question",
                optionsMatrix=["A", "B", "C", "D"],
                correctAnswer="A",
                sourceQuote="A source",
                difficulty=difficulty,
            )
            self.session.add(question)
            self.questions.append(question)
        self.session.flush()
        self.assignment = Assignment(
            title="Cell quiz",
            materialId=self.material.id,
            teacherId=self.teacher.id,
            dueDate=datetime.utcnow() + timedelta(days=2),
        )
        self.session.add(self.assignment)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def add_attempt(self, answers, timestamp, is_submitted=True):
        attempt = QuizAttempt(
            studentId=self.student.id,
            assignmentId=self.assignment.id,
            score=sum(
                answer == question.correctAnswer
                for question_id, answer in answers.items()
                for question in self.questions
                if question.id == int(question_id)
            ),
            totalQuestions=len(answers),
            answers=answers,
            isSubmitted=is_submitted,
            attemptTimestamp=timestamp,
        )
        self.session.add(attempt)
        self.session.commit()
        return attempt

    def test_weighted_accuracy_and_difficulty_error_counts(self):
        now = datetime.utcnow()
        attempt = self.add_attempt(
            {
                self.questions[0].id: "A",
                self.questions[1].id: "B",
                self.questions[2].id: "B",
            },
            now,
        )
        result = calculate_topic_mastery(self.session, [attempt])
        topic = result["topics"][self.student.id][0]
        self.assertEqual(topic["sampleSize"], 3)
        self.assertEqual(topic["correctAnswers"], 1)
        self.assertEqual(topic["incorrectAnswers"], 2)
        self.assertEqual(topic["errorCounts"], {"easy": 0, "medium": 1, "difficult": 1})
        self.assertEqual(topic["masteryPercent"], 22.2)
        self.assertEqual(topic["attemptCount"], 1)

    def test_correct_and_incorrect_responses_at_every_difficulty(self):
        correct = self.add_attempt(
            {question.id: "A" for question in self.questions},
            datetime.utcnow(),
        )
        correct_topic = calculate_topic_mastery(self.session, [correct])["topics"][self.student.id][0]
        self.assertEqual(correct_topic["masteryPercent"], 100)

        corrected = self.add_attempt(
            {question.id: "B" for question in self.questions},
            datetime.utcnow() + timedelta(minutes=1),
        )
        incorrect_topic = calculate_topic_mastery(
            self.session,
            [correct, corrected],
        )["topics"][self.student.id][0]
        self.assertEqual(incorrect_topic["errorCounts"], {"easy": 1, "medium": 1, "difficult": 1})
        self.assertEqual(incorrect_topic["masteryPercent"], 50)
        self.assertEqual(incorrect_topic["sampleSize"], 6)

    def test_aggregates_assessments_recalculates_corrections_and_is_idempotent(self):
        first = self.add_attempt(
            {self.questions[0].id: "A"},
            datetime.utcnow(),
        )
        second = self.add_attempt(
            {self.questions[2].id: "B"},
            datetime.utcnow() + timedelta(days=1),
        )
        once = calculate_topic_mastery(self.session, [first, second])
        repeated = calculate_topic_mastery(self.session, [first, second])
        first_result = once["topics"][self.student.id][0]
        second_result = repeated["topics"][self.student.id][0]
        self.assertEqual(first_result["sampleSize"], 2)
        self.assertEqual(second_result["sampleSize"], 2)
        self.assertEqual(first_result["masteryPercent"], 33.3)
        self.assertEqual(
            [point["masteryPercent"] for point in once["history"]],
            [100, 33.3],
        )

        first.answers = {str(self.questions[0].id): "B"}
        self.session.commit()
        corrected = calculate_topic_mastery(self.session, [first, second])["topics"][self.student.id][0]
        self.assertEqual(corrected["sampleSize"], 2)
        self.assertEqual(corrected["masteryPercent"], 0)
        self.assertEqual(corrected["errorCounts"], {"easy": 1, "medium": 0, "difficult": 1})

    def test_no_attempts_and_unsubmitted_progress_have_no_mastery(self):
        self.assertEqual(calculate_topic_mastery(self.session, [])["topics"], {})
        progress = self.add_attempt(
            {self.questions[0].id: "A"},
            datetime.utcnow(),
            is_submitted=False,
        )
        self.assertEqual(calculate_topic_mastery(self.session, [progress])["topics"], {})


if __name__ == "__main__":
    unittest.main()
