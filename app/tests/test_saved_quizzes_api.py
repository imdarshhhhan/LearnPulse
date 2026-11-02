import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.quizzes import router as quizzes_router
from api.saved_quizzes import router as saved_quizzes_router
from db.models import (
    Assignment,
    Base,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    StudentSavedQuiz,
    User,
    UserRole,
)
from db.sessions import getDb


class SavedQuizzesApiTests(unittest.TestCase):
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
            self.other_student = User(
                email="other@example.test",
                fullName="Other Student",
                role=UserRole.STUDENT,
            )
            self.teacher = User(
                email="teacher@example.test",
                fullName="Teacher",
                role=UserRole.TEACHER,
            )
            session.add_all([self.student, self.other_student, self.teacher])
            session.flush()

            material = ContentMaterial(title="Geometry", teacherId=self.teacher.id)
            no_quiz_material = ContentMaterial(title="Reading", teacherId=self.teacher.id)
            session.add_all([material, no_quiz_material])
            session.flush()
            self.assignment = Assignment(
                title="Triangles quiz",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=datetime.utcnow() + timedelta(days=3),
                targetStudents=[self.student],
            )
            self.no_quiz_assignment = Assignment(
                title="Unapproved quiz",
                materialId=no_quiz_material.id,
                teacherId=self.teacher.id,
                dueDate=datetime.utcnow() + timedelta(days=3),
                targetStudents=[self.student],
            )
            session.add_all(
                [
                    self.assignment,
                    self.no_quiz_assignment,
                    QuestionPool(
                        materialId=material.id,
                        conceptTag="Triangles",
                        questionText="How many sides does a triangle have?",
                        optionsMatrix=["2", "3", "4", "5"],
                        correctAnswer="3",
                        sourceQuote="Sample source",
                    ),
                    QuizAttempt(
                        studentId=self.student.id,
                        assignment=self.assignment,
                        score=1,
                        totalQuestions=1,
                    ),
                ]
            )
            session.commit()
            self.assignment_id = self.assignment.id
            self.no_quiz_assignment_id = self.no_quiz_assignment.id
            self.student_id = self.student.id
            self.student_token = _create_access_token(self.student)
            self.other_student_token = _create_access_token(self.other_student)
            self.teacher_token = _create_access_token(self.teacher)

        app = FastAPI()
        app.include_router(saved_quizzes_router)
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

    def test_save_list_duplicate_prevention_and_removal_persist(self):
        headers = self.auth(self.student_token)
        initial = self.client.get("/saved-quizzes", headers=headers)
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertEqual(initial.json()["quizzes"], [])

        first = self.client.post(
            f"/saved-quizzes/{self.assignment_id}",
            headers=headers,
        )
        self.assertEqual(first.status_code, 201, first.text)
        duplicate = self.client.post(
            f"/saved-quizzes/{self.assignment_id}",
            headers=headers,
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(first.json()["id"], duplicate.json()["id"])

        listed = self.client.get("/saved-quizzes", headers=headers).json()
        self.assertEqual(len(listed["quizzes"]), 1)
        quiz = listed["quizzes"][0]
        self.assertEqual(quiz["assignmentId"], self.assignment_id)
        self.assertEqual(quiz["title"], "Triangles quiz")
        self.assertEqual(quiz["topic"], "Geometry")
        self.assertEqual(quiz["bestScorePercent"], 100)
        self.assertEqual(
            self.client.get(
                f"/quizzes/assignments/{self.assignment_id}",
                headers=headers,
            ).status_code,
            200,
        )

        with self.session_factory() as session:
            self.assertEqual(session.query(StudentSavedQuiz).count(), 1)
            renewed_token = _create_access_token(session.get(User, self.student_id))
        self.assertEqual(
            len(
                self.client.get(
                    "/saved-quizzes",
                    headers=self.auth(renewed_token),
                ).json()["quizzes"]
            ),
            1,
        )

        removed = self.client.delete(
            f"/saved-quizzes/{self.assignment_id}",
            headers=headers,
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertTrue(removed.json()["removed"])
        self.assertEqual(
            self.client.get("/saved-quizzes", headers=headers).json()["quizzes"],
            [],
        )

    def test_owner_access_and_quiz_reference_validation(self):
        student_headers = self.auth(self.student_token)
        other_headers = self.auth(self.other_student_token)
        self.assertEqual(
            self.client.post(
                f"/saved-quizzes/{self.assignment_id}",
                headers=other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/saved-quizzes/{self.assignment_id}",
                headers=other_headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/saved-quizzes/{self.no_quiz_assignment_id}",
                headers=student_headers,
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.get(
                "/saved-quizzes",
                headers=self.auth(self.teacher_token),
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
