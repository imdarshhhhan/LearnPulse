import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.quizzes import router
from db.models import (
    Assignment,
    Base,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    User,
    UserRole,
)
from db.sessions import getDb


class TeacherSubmissionsApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as session:
            self.teacher = User(
                email="teacher@example.test",
                fullName="Teacher",
                role=UserRole.TEACHER,
            )
            self.other_teacher = User(
                email="other-teacher@example.test",
                fullName="Other Teacher",
                role=UserRole.TEACHER,
            )
            self.student = User(
                email="student@example.test",
                fullName="Student",
                role=UserRole.STUDENT,
            )
            self.other_student = User(
                email="other-student@example.test",
                fullName="Other Student",
                role=UserRole.STUDENT,
            )
            session.add_all(
                [self.teacher, self.other_teacher, self.student, self.other_student]
            )
            session.flush()
            first_material = ContentMaterial(title="Biology", teacherId=self.teacher.id)
            second_material = ContentMaterial(title="Chemistry", teacherId=self.teacher.id)
            other_material = ContentMaterial(title="Physics", teacherId=self.other_teacher.id)
            session.add_all([first_material, second_material, other_material])
            session.flush()
            now = datetime.utcnow()
            first_assignment = Assignment(
                title="Cell quiz",
                materialId=first_material.id,
                teacherId=self.teacher.id,
                dueDate=now + timedelta(days=2),
                targetStudents=[self.student],
            )
            second_assignment = Assignment(
                title="Molecule quiz",
                materialId=second_material.id,
                teacherId=self.teacher.id,
                dueDate=now + timedelta(days=3),
                targetStudents=[self.student],
            )
            other_assignment = Assignment(
                title="Forces quiz",
                materialId=other_material.id,
                teacherId=self.other_teacher.id,
                dueDate=now + timedelta(days=2),
                targetStudents=[self.other_student],
            )
            session.add_all([first_assignment, second_assignment, other_assignment])
            session.flush()
            first_questions = [
                QuestionPool(
                    materialId=first_material.id,
                    conceptTag="Biology",
                    questionText="Which is genetic material?",
                    optionsMatrix=["DNA", "Protein", "Sugar", "Lipid"],
                    correctAnswer="DNA",
                    sourceQuote="DNA stores genetic information.",
                ),
                QuestionPool(
                    materialId=first_material.id,
                    conceptTag="Biology",
                    questionText="Where is DNA stored?",
                    optionsMatrix=["Nucleus", "Membrane", "Cell wall", "Ribosome"],
                    correctAnswer="Nucleus",
                    sourceQuote="The nucleus stores DNA.",
                ),
            ]
            second_question = QuestionPool(
                materialId=second_material.id,
                conceptTag="Chemistry",
                questionText="What is water's formula?",
                optionsMatrix=["H2O", "CO2", "O2", "NaCl"],
                correctAnswer="H2O",
                sourceQuote="Water is H2O.",
            )
            session.add_all([*first_questions, second_question])
            session.flush()
            submitted_attempt = QuizAttempt(
                studentId=self.student.id,
                assignmentId=first_assignment.id,
                score=1,
                totalQuestions=2,
                answers={
                    first_questions[0].id: "DNA",
                    first_questions[1].id: "Membrane",
                },
                isSubmitted=True,
                attemptTimestamp=now - timedelta(hours=2),
            )
            in_progress_attempt = QuizAttempt(
                studentId=self.student.id,
                assignmentId=second_assignment.id,
                score=0,
                totalQuestions=1,
                answers={second_question.id: "H2O"},
                isSubmitted=False,
                attemptTimestamp=now - timedelta(hours=1),
            )
            other_attempt = QuizAttempt(
                studentId=self.other_student.id,
                assignmentId=other_assignment.id,
                score=1,
                totalQuestions=1,
                answers={},
                isSubmitted=True,
            )
            session.add_all([submitted_attempt, in_progress_attempt, other_attempt])
            session.commit()

            self.student_id = self.student.id
            self.first_activity_id = first_assignment.id
            self.second_activity_id = second_assignment.id
            self.submitted_attempt_id = submitted_attempt.id
            self.other_attempt_id = other_attempt.id
            self.teacher_token = _create_access_token(self.teacher)
            self.other_teacher_token = _create_access_token(self.other_teacher)
            self.student_token = _create_access_token(self.student)

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

    def test_list_is_scoped_and_filters_activity_student_and_status(self):
        response = self.client.get(
            "/quizzes/teacher/submissions",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body["submissions"]), 2)
        self.assertEqual(
            {item["activityTitle"] for item in body["submissions"]},
            {"Cell quiz", "Molecule quiz"},
        )
        self.assertEqual(body["filters"]["activities"], [
            {"id": self.first_activity_id, "title": "Cell quiz"},
            {"id": self.second_activity_id, "title": "Molecule quiz"},
        ])
        self.assertEqual(body["filters"]["students"], [
            {"id": self.student_id, "fullName": "Student", "usn": None}
        ])

        filtered = self.client.get(
            "/quizzes/teacher/submissions"
            f"?activityId={self.first_activity_id}&studentId={self.student_id}&status=submitted",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual([item["id"] for item in filtered.json()["submissions"]], [self.submitted_attempt_id])
        self.assertEqual(filtered.json()["submissions"][0]["scorePercent"], 50)

        in_progress = self.client.get(
            "/quizzes/teacher/submissions?status=in_progress",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(in_progress.status_code, 200, in_progress.text)
        self.assertEqual(len(in_progress.json()["submissions"]), 1)
        self.assertEqual(in_progress.json()["submissions"][0]["scorePercent"], None)

    def test_detail_shows_answer_results_and_enforces_teacher_ownership(self):
        response = self.client.get(
            f"/quizzes/teacher/submissions/{self.submitted_attempt_id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["studentName"], "Student")
        self.assertIsNone(body["studentUsn"])
        self.assertEqual(body["activityTitle"], "Cell quiz")
        self.assertEqual(body["status"], "submitted")
        self.assertEqual(body["scorePercent"], 50)
        self.assertEqual(body["answers"][0]["selectedOption"], "DNA")
        self.assertTrue(body["answers"][0]["isCorrect"])
        self.assertEqual(body["answers"][1]["selectedOption"], "Membrane")
        self.assertFalse(body["answers"][1]["isCorrect"])

        self.assertEqual(
            self.client.get(
                f"/quizzes/teacher/submissions/{self.submitted_attempt_id}",
                headers=self.auth(self.other_teacher_token),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/quizzes/teacher/submissions/{self.submitted_attempt_id}",
                headers=self.auth(self.student_token),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/quizzes/teacher/submissions",
                headers=self.auth(self.student_token),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/quizzes/teacher/submissions").status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                f"/quizzes/teacher/submissions/{self.other_attempt_id}",
                headers=self.auth(self.teacher_token),
            ).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
