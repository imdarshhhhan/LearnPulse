import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.quizzes import router
from db.models import Assignment, Base, ContentMaterial, QuestionPool, QuizAttempt, User, UserRole
from db.sessions import getDb


class StudentAssignmentsApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        with self.session_factory() as session:
            self.student = User(
                email="student@example.test",
                fullName="Student",
                role=UserRole.STUDENT,
            )
            self.teacher = User(
                email="teacher@example.test",
                fullName="Teacher",
                role=UserRole.TEACHER,
            )
            session.add_all([self.student, self.teacher])
            session.flush()

            self.material = ContentMaterial(title="Algebra", teacherId=self.teacher.id)
            session.add(self.material)
            session.flush()
            self.assignment = Assignment(
                title="Linear equations",
                materialId=self.material.id,
                teacherId=self.teacher.id,
                dueDate=datetime.utcnow() + timedelta(days=2),
            )
            session.add(self.assignment)
            session.flush()
            self.assignment_id = self.assignment.id
            session.add_all(
                [
                    QuestionPool(
                        materialId=self.material.id,
                        conceptTag="Algebra",
                        questionText="What is 2 + 2?",
                        optionsMatrix=["3", "4", "5", "6"],
                        correctAnswer="4",
                        sourceQuote="Sample source",
                    ),
                    QuestionPool(
                        materialId=self.material.id,
                        conceptTag="Algebra",
                        questionText="What is 3 + 3?",
                        optionsMatrix=["5", "6", "7", "8"],
                        correctAnswer="6",
                        sourceQuote="Sample source",
                    ),
                ]
            )
            session.commit()
            self.question_ids = [
                question.id
                for question in session.query(QuestionPool)
                .filter(QuestionPool.materialId == self.material.id)
                .order_by(QuestionPool.id)
                .all()
            ]
            self.student_id = self.student.id
            self.student_token = _create_access_token(self.student)
            self.teacher_token = _create_access_token(self.teacher)

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

    def test_student_gets_assignment_questions_without_answer_key(self):
        response = self.client.get(
            f"/quizzes/assignments/{self.assignment_id}",
            headers=self.auth(self.student_token),
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["title"], "Linear equations")
        self.assertEqual(len(body["questions"]), 2)
        self.assertNotIn("correctAnswer", body["questions"][0])
        self.assertEqual(body["questions"][0]["options"], ["3", "4", "5", "6"])

    def test_submission_requires_all_assignment_questions_and_persists_score(self):
        partial = self.client.post(
            f"/quizzes/assignments/{self.assignment_id}/submit",
            json={"answers": [{"questionId": self.question_ids[0], "selectedOption": "4"}]},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(partial.status_code, 400)

        submitted = self.client.post(
            f"/quizzes/assignments/{self.assignment_id}/submit",
            json={
                "answers": [
                    {"questionId": self.question_ids[0], "selectedOption": "4"},
                    {"questionId": self.question_ids[1], "selectedOption": "5"},
                ]
            },
            headers=self.auth(self.student_token),
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["correctAnswers"], 1)
        self.assertEqual(submitted.json()["totalQuestions"], 2)
        self.assertEqual(submitted.json()["scorePercent"], 50)

        with self.session_factory() as session:
            attempt = session.get(QuizAttempt, submitted.json()["attemptId"])
            self.assertEqual(attempt.studentId, self.student_id)
            self.assertEqual(attempt.assignmentId, self.assignment_id)
            self.assertEqual(attempt.score, 1)
            self.assertEqual(attempt.totalQuestions, 2)

    def test_assignment_quiz_requires_a_student_session(self):
        url = f"/quizzes/assignments/{self.assignment_id}"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(
            self.client.get(url, headers=self.auth(self.teacher_token)).status_code,
            403,
        )

    def test_submission_retries_return_the_original_attempt(self):
        payload = {
            "answers": [
                {"questionId": self.question_ids[0], "selectedOption": "4"},
                {"questionId": self.question_ids[1], "selectedOption": "5"},
            ],
            "submissionId": "assignment-submission-001",
        }
        url = f"/quizzes/assignments/{self.assignment_id}/submit"
        first = self.client.post(url, json=payload, headers=self.auth(self.student_token))
        retry = self.client.post(url, json=payload, headers=self.auth(self.student_token))

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(first.json()["attemptId"], retry.json()["attemptId"])

        with self.session_factory() as session:
            attempts = session.query(QuizAttempt).filter(
                QuizAttempt.studentId == self.student_id,
                QuizAttempt.assignmentId == self.assignment_id,
            ).all()
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
