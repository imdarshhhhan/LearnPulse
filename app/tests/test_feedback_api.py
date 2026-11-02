import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.feedback import router as feedback_router
from api.quizzes import router as quizzes_router
from db.models import (
    Assignment,
    Base,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    StudentFeedback,
    User,
    UserRole,
)
from db.sessions import getDb


class FeedbackApiTests(unittest.TestCase):
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
                fullName="Feedback Student",
                usn="1AB23CS001",
                role=UserRole.STUDENT,
            )
            self.other_student = User(
                email="other@example.test",
                fullName="Other Student",
                role=UserRole.STUDENT,
            )
            self.teacher = User(
                email="teacher@example.test",
                fullName="Owning Teacher",
                role=UserRole.TEACHER,
            )
            self.other_teacher = User(
                email="other-teacher@example.test",
                fullName="Other Teacher",
                role=UserRole.TEACHER,
            )
            session.add_all(
                [self.student, self.other_student, self.teacher, self.other_teacher]
            )
            session.flush()
            material = ContentMaterial(title="Algebra", teacherId=self.teacher.id)
            session.add(material)
            session.flush()
            self.quiz = Assignment(
                title="Linear Equations Quiz",
                activityType="quiz",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=datetime.utcnow() + timedelta(days=2),
                targetStudents=[self.student],
            )
            self.homework = Assignment(
                title="Algebra Homework",
                activityType="homework",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=datetime.utcnow() + timedelta(days=2),
                targetStudents=[self.student],
            )
            session.add_all([self.quiz, self.homework])
            session.flush()
            session.add(
                QuestionPool(
                    materialId=material.id,
                    conceptTag="Algebra",
                    questionText="What is 2 + 2?",
                    optionsMatrix=["3", "4", "5", "6"],
                    correctAnswer="4",
                    sourceQuote="Source",
                )
            )
            session.commit()
            self.quiz_id = self.quiz.id
            self.homework_id = self.homework.id
            self.student_id = self.student.id
            self.student_token = _create_access_token(self.student)
            self.other_student_token = _create_access_token(self.other_student)
            self.teacher_token = _create_access_token(self.teacher)
            self.other_teacher_token = _create_access_token(self.other_teacher)

        app = FastAPI()
        app.include_router(feedback_router)
        app.include_router(quizzes_router)

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

    def test_quiz_feedback_requires_completion_and_is_persisted_for_owning_teacher(self):
        feedback_url = f"/feedback/assignments/{self.quiz_id}"
        headers = self.auth(self.student_token)
        blocked = self.client.post(
            feedback_url,
            json={"message": "Useful questions"},
            headers=headers,
        )
        self.assertEqual(blocked.status_code, 409)

        submitted = self.client.post(
            f"/quizzes/assignments/{self.quiz_id}/submit",
            json={
                "answers": [
                    {
                        "questionId": self._question_id(),
                        "selectedOption": "4",
                    }
                ],
                "submissionId": "feedback-quiz-submit-01",
            },
            headers=headers,
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)

        saved = self.client.post(
            feedback_url,
            json={
                "message": "  The explanations were helpful.  ",
                "category": "content",
                "rating": 5,
            },
            headers=headers,
        )
        self.assertEqual(saved.status_code, 201, saved.text)

        with self.session_factory() as session:
            record = session.get(StudentFeedback, saved.json()["id"])
            self.assertEqual(record.studentId, self.student_id)
            self.assertEqual(record.assignmentId, self.quiz_id)
            self.assertEqual(record.message, "The explanations were helpful.")

        persisted = self.client.get(
            feedback_url,
            headers=headers,
        ).json()["feedback"]
        self.assertEqual(persisted["message"], "The explanations were helpful.")
        self.assertEqual(persisted["rating"], 5)

        teacher_feedback = self.client.get(
            "/feedback/teacher?activityType=quiz&search=1AB23CS001",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(teacher_feedback.status_code, 200, teacher_feedback.text)
        body = teacher_feedback.json()
        self.assertEqual(len(body["feedback"]), 1)
        self.assertEqual(body["feedback"][0]["studentUsn"], "1AB23CS001")
        self.assertEqual(body["feedback"][0]["activityTitle"], "Linear Equations Quiz")
        self.assertEqual(body["feedback"][0]["rating"], 5)
        self.assertTrue(body["feedback"][0]["submittedAt"])

        denied_list = self.client.get(
            "/feedback/teacher",
            headers=self.auth(self.other_teacher_token),
        )
        self.assertEqual(denied_list.status_code, 200)
        self.assertEqual(denied_list.json()["feedback"], [])
        denied_detail = self.client.get(
            f"/feedback/teacher/{saved.json()['id']}",
            headers=self.auth(self.other_teacher_token),
        )
        self.assertEqual(denied_detail.status_code, 404)

    def test_homework_feedback_can_be_saved_before_completion_and_updated(self):
        url = f"/feedback/assignments/{self.homework_id}"
        headers = self.auth(self.student_token)
        first = self.client.post(
            url,
            json={"message": "Instructions are clear.", "category": "experience"},
            headers=headers,
        )
        self.assertEqual(first.status_code, 201, first.text)

        second = self.client.post(
            url,
            json={"message": "Updated comment.", "rating": 4},
            headers=headers,
        )
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])

        with self.session_factory() as session:
            records = session.query(StudentFeedback).filter(
                StudentFeedback.assignmentId == self.homework_id
            ).all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].message, "Updated comment.")
        self.assertEqual(records[0].rating, 4)

        filtered = self.client.get(
            "/feedback/teacher?activityType=homework",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(len(filtered.json()["feedback"]), 1)
        self.assertEqual(filtered.json()["feedback"][0]["activityType"], "homework")
        self.assertEqual(
            {activity["id"] for activity in filtered.json()["filters"]["activities"]},
            {self.quiz_id, self.homework_id},
        )

    def test_feedback_rejects_unassigned_students_invalid_payload_and_teacher_submits(self):
        unknown_assignment = self.client.post(
            "/feedback/assignments/9999",
            json={"message": "Feedback"},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(unknown_assignment.status_code, 404)

        unassigned_student = self.client.post(
            f"/feedback/assignments/{self.homework_id}",
            json={"message": "Feedback"},
            headers=self.auth(self.other_student_token),
        )
        self.assertEqual(unassigned_student.status_code, 404)

        invalid_rating = self.client.post(
            f"/feedback/assignments/{self.homework_id}",
            json={"message": "Feedback", "rating": 6},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(invalid_rating.status_code, 422)

        forbidden_role = self.client.post(
            f"/feedback/assignments/{self.homework_id}",
            json={"message": "Feedback"},
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(forbidden_role.status_code, 403)

    def _question_id(self):
        with self.session_factory() as session:
            return session.query(QuestionPool.id).filter(
                QuestionPool.materialId == self.quiz.materialId
            ).scalar()


if __name__ == "__main__":
    unittest.main()
