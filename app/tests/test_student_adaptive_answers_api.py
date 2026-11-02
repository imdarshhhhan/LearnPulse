import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.quizzes import router
from db.models import Base, ContentMaterial, QuestionPool, QuizAttempt, User, UserRole
from db.sessions import getDb


class StudentAdaptiveAnswersApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as session:
            teacher = User(
                email="teacher@example.test",
                fullName="Teacher",
                role=UserRole.TEACHER,
            )
            student = User(
                email="student@example.test",
                fullName="Student",
                role=UserRole.STUDENT,
                usn="1AB23CS001",
            )
            session.add_all([teacher, student])
            session.flush()
            material = ContentMaterial(title="Ecology", teacher=teacher)
            session.add(material)
            session.flush()
            self.question = QuestionPool(
                materialId=material.id,
                conceptTag="Ecosystems",
                questionText="Question",
                optionsMatrix=["Correct", "Wrong", "Other", "Choice"],
                correctAnswer="Correct",
                sourceQuote="Source",
                difficulty="difficult",
            )
            session.add(self.question)
            session.commit()
            self.question_id = self.question.id
            self.student_id = student.id
            self.student_token = _create_access_token(student)
            self.teacher_token = _create_access_token(teacher)

        app = FastAPI()
        app.include_router(router)

        def override_db():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[getDb] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def submit(self, answer, token=None, submission_id=None):
        payload = {
            "questionId": self.question_id,
            "chosenOption": answer,
            "conceptTag": "untrusted topic label",
        }
        if submission_id is not None:
            payload["submissionId"] = submission_id
        return self.client.post(
            "/quizzes/submit-answer",
            headers=self.auth(token or self.student_token),
            json=payload,
        )

    def test_responses_are_persisted_and_mastery_uses_question_difficulty(self):
        correct = self.submit("Correct")
        self.assertEqual(correct.status_code, 200, correct.text)
        self.assertEqual(correct.json()["masteryPercent"], 100)
        self.assertEqual(correct.json()["sampleSize"], 1)

        incorrect = self.submit("Wrong")
        self.assertEqual(incorrect.status_code, 200, incorrect.text)
        self.assertEqual(incorrect.json()["masteryPercent"], 50)
        self.assertEqual(incorrect.json()["sampleSize"], 2)

        with self.session_factory() as session:
            attempts = session.query(QuizAttempt).filter(
                QuizAttempt.studentId == self.student_id,
                QuizAttempt.assignmentId.is_(None),
            ).all()
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(attempt.answers for attempt in attempts))

    def test_repeated_submission_is_idempotent_and_conflicting_reuse_is_rejected(self):
        first = self.submit("Correct", submission_id="submission-unique-001")
        repeated = self.submit("Correct", submission_id="submission-unique-001")
        conflict = self.submit("Wrong", submission_id="submission-unique-001")

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(first.json()["attemptId"], repeated.json()["attemptId"])
        self.assertEqual(conflict.status_code, 409, conflict.text)

        with self.session_factory() as session:
            attempts = session.query(QuizAttempt).filter(
                QuizAttempt.studentId == self.student_id,
                QuizAttempt.assignmentId.is_(None),
            ).all()
            question = session.get(QuestionPool, self.question_id)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(question.totalAttemptsLogged, 1)
        self.assertEqual(question.correctAttemptsLogged, 1)

    def test_invalid_option_and_teacher_role_are_rejected(self):
        invalid = self.submit("not an option")
        self.assertEqual(invalid.status_code, 400)

        teacher = self.submit("Correct", token=self.teacher_token)
        self.assertEqual(teacher.status_code, 403)


if __name__ == "__main__":
    unittest.main()
