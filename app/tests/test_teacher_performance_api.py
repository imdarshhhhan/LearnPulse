import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.teacher_performance import router
from db.models import (
    Assignment,
    Base,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    TeacherClass,
    User,
    UserRole,
)
from db.sessions import getDb


class TeacherPerformanceApiTests(unittest.TestCase):
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
            other_teacher = User(
                email="other@example.test",
                fullName="Other Teacher",
                role=UserRole.TEACHER,
            )
            first_student = User(
                email="first@example.test",
                fullName="First Student",
                role=UserRole.STUDENT,
                usn="1AB23CS001",
            )
            second_student = User(
                email="second@example.test",
                fullName="Second Student",
                role=UserRole.STUDENT,
                usn="1AB23CS002",
            )
            missing_student = User(
                email="missing@example.test",
                fullName="No Attempt",
                role=UserRole.STUDENT,
                usn="1AB23CS003",
            )
            session.add_all(
                [teacher, other_teacher, first_student, second_student, missing_student]
            )
            session.flush()
            teacher_class = TeacherClass(name="Biology", teacher=teacher, members=[
                first_student,
                second_student,
                missing_student,
            ])
            other_class = TeacherClass(name="Other class", teacher=other_teacher, members=[
                first_student,
            ])
            session.add_all([teacher_class, other_class])
            material = ContentMaterial(title="Cell biology", teacher=teacher)
            other_material = ContentMaterial(title="Physics", teacher=other_teacher)
            session.add_all([material, other_material])
            session.flush()
            assignment = Assignment(
                title="Cell test",
                materialId=material.id,
                creator=teacher,
                dueDate=datetime.utcnow() + timedelta(days=2),
                targetClasses=[teacher_class],
            )
            unauthorized_assignment = Assignment(
                title="Other teacher test",
                materialId=other_material.id,
                creator=other_teacher,
                dueDate=datetime.utcnow() + timedelta(days=2),
                targetStudents=[first_student],
            )
            session.add_all([assignment, unauthorized_assignment])
            session.flush()
            first_question = QuestionPool(
                materialId=material.id,
                conceptTag="Cell structure",
                questionText="Question one",
                optionsMatrix=["A", "B", "C", "D"],
                correctAnswer="A",
                sourceQuote="Source one",
            )
            second_question = QuestionPool(
                materialId=material.id,
                conceptTag="Cell structure",
                questionText="Question two",
                optionsMatrix=["A", "B", "C", "D"],
                correctAnswer="B",
                sourceQuote="Source two",
            )
            session.add_all([first_question, second_question])
            session.flush()
            session.add_all(
                [
                    QuizAttempt(
                        student=first_student,
                        assignment=assignment,
                        score=2,
                        totalQuestions=2,
                        answers={first_question.id: "A", second_question.id: "B"},
                        isSubmitted=True,
                    ),
                    QuizAttempt(
                        student=second_student,
                        assignment=assignment,
                        score=1,
                        totalQuestions=2,
                        answers={first_question.id: "A", second_question.id: "A"},
                        isSubmitted=True,
                    ),
                ]
            )
            session.commit()
            self.teacher_id = teacher.id
            self.class_id = teacher_class.id
            self.other_class_id = other_class.id
            self.first_student_id = first_student.id
            self.second_student_id = second_student.id
            self.missing_student_id = missing_student.id
            self.teacher_token = _create_access_token(teacher)
            self.other_teacher_token = _create_access_token(other_teacher)
            self.student_token = _create_access_token(first_student)

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

    def test_class_summary_uses_real_submissions_and_distinguishes_missing(self):
        response = self.client.get(
            f"/teacher/performance/classes/{self.class_id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["totalStudents"], 3)
        self.assertEqual(body["classAveragePercent"], 75)
        self.assertEqual(body["topPerformer"]["usn"], "1AB23CS001")
        self.assertEqual(body["lowestPerformer"]["usn"], "1AB23CS002")
        self.assertEqual(body["assessmentOpportunities"], 3)
        self.assertEqual(body["completedOpportunities"], 2)
        self.assertAlmostEqual(body["completionPercent"], 66.7)
        self.assertEqual(body["assessments"][0]["averageScorePercent"], 75)

    def test_student_detail_includes_question_responses_and_missing_assessment(self):
        detail = self.client.get(
            f"/teacher/performance/classes/{self.class_id}/students/{self.second_student_id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(body["student"]["usn"], "1AB23CS002")
        self.assertEqual(body["averageScorePercent"], 50)
        self.assertEqual(body["questionStats"], {"attempted": 2, "correct": 1, "incorrect": 1})
        self.assertEqual(body["assessments"][0]["status"], "submitted")

        missing = self.client.get(
            f"/teacher/performance/classes/{self.class_id}/students/{self.missing_student_id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(missing.status_code, 200, missing.text)
        missing_assessment = missing.json()["assessments"][0]
        self.assertEqual(missing_assessment["status"], "not_started")
        self.assertIsNone(missing_assessment["scorePercent"])

    def test_class_and_student_access_are_scoped_to_teacher_class(self):
        inaccessible_class = self.client.get(
            f"/teacher/performance/classes/{self.other_class_id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(inaccessible_class.status_code, 404)

        not_in_class = self.client.get(
            f"/teacher/performance/classes/{self.class_id}/students/{self.first_student_id + 999}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(not_in_class.status_code, 404)

        forbidden = self.client.get(
            f"/teacher/performance/classes/{self.class_id}",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(forbidden.status_code, 403)

        hidden = self.client.get(
            f"/teacher/performance/classes/{self.class_id}",
            headers=self.auth(self.other_teacher_token),
        )
        self.assertEqual(hidden.status_code, 404)


if __name__ == "__main__":
    unittest.main()
