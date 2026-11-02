import unittest
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.homework import router as homework_router
from api.quizzes import router as quizzes_router
from db.models import (
    Assignment,
    Base,
    ContentMaterial,
    QuestionPool,
    StudyGroup,
    User,
    UserRole,
)
from db.sessions import getDb


class StudentHomeworkApiTests(unittest.TestCase):
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

            material = ContentMaterial(title="Algebra", teacherId=self.teacher.id)
            group = StudyGroup(
                name="Algebra group",
                uniqueGroupCode="QZ-HOMEWORK",
                creatorId=self.teacher.id,
                members=[self.student],
            )
            session.add_all([material, group])
            session.flush()
            now = datetime.utcnow()
            self.personal_assignment = Assignment(
                title="Individual equations",
                description="Complete the equations.",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=now + timedelta(days=2),
                targetStudents=[self.student],
            )
            self.group_assignment = Assignment(
                title="Group equations",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=now + timedelta(days=2),
                targetGroups=[group],
            )
            self.other_assignment = Assignment(
                title="Other student homework",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=now + timedelta(days=2),
                targetStudents=[self.other_student],
            )
            self.upcoming_assignment = Assignment(
                title="Scheduled homework",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=now + timedelta(days=3),
                availableWindowStart=now + timedelta(days=1),
                targetStudents=[self.student],
            )
            self.overdue_assignment = Assignment(
                title="Past due homework",
                materialId=material.id,
                teacherId=self.teacher.id,
                dueDate=now - timedelta(days=2),
                targetStudents=[self.student],
            )
            session.add_all(
                [
                    self.personal_assignment,
                    self.group_assignment,
                    self.other_assignment,
                    self.upcoming_assignment,
                    self.overdue_assignment,
                    QuestionPool(
                        materialId=material.id,
                        conceptTag="Algebra",
                        questionText="What is 2 + 2?",
                        optionsMatrix=["3", "4", "5", "6"],
                        correctAnswer="4",
                        sourceQuote="Sample source",
                    ),
                    QuestionPool(
                        materialId=material.id,
                        conceptTag="Algebra",
                        questionText="What is 3 + 3?",
                        optionsMatrix=["5", "6", "7", "8"],
                        correctAnswer="6",
                        sourceQuote="Sample source",
                    ),
                ]
            )
            session.commit()
            self.student_id = self.student.id
            self.personal_assignment_id = self.personal_assignment.id
            self.group_assignment_id = self.group_assignment.id
            self.other_assignment_id = self.other_assignment.id
            self.upcoming_assignment_id = self.upcoming_assignment.id
            self.overdue_assignment_id = self.overdue_assignment.id
            self.group_id = group.id
            self.material_id = material.id
            self.question_ids = [
                question.id
                for question in session.query(QuestionPool)
                .filter(QuestionPool.materialId == material.id)
                .order_by(QuestionPool.id)
                .all()
            ]
            self.student_token = _create_access_token(self.student)
            self.other_student_token = _create_access_token(self.other_student)
            self.teacher_token = _create_access_token(self.teacher)

        app = FastAPI()
        app.include_router(homework_router)
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

    def test_student_only_sees_individual_and_member_group_assignments(self):
        response = self.client.get(
            "/homework/assignments",
            headers=self.auth(self.student_token),
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        listed_ids = {item["id"] for item in body["assignments"]}
        self.assertEqual(body["studentId"], self.student_id)
        self.assertIn(self.personal_assignment_id, listed_ids)
        self.assertIn(self.group_assignment_id, listed_ids)
        self.assertNotIn(self.other_assignment_id, listed_ids)
        self.assertEqual(
            next(item for item in body["assignments"] if item["id"] == self.personal_assignment_id)["description"],
            "Complete the equations.",
        )
        self.assertEqual(
            next(item for item in body["assignments"] if item["id"] == self.upcoming_assignment_id)["status"],
            "upcoming",
        )
        self.assertEqual(
            next(item for item in body["assignments"] if item["id"] == self.overdue_assignment_id)["status"],
            "overdue",
        )

    def test_other_student_cannot_read_or_submit_targeted_homework(self):
        headers = self.auth(self.other_student_token)
        self.assertEqual(
            self.client.get(
                f"/quizzes/assignments/{self.personal_assignment_id}",
                headers=headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/quizzes/assignments/{self.personal_assignment_id}/submit",
                json={"answers": [{"questionId": self.question_ids[0], "selectedOption": "4"}]},
                headers=headers,
            ).status_code,
            404,
        )

    def test_progress_persists_and_submission_marks_homework_complete(self):
        headers = self.auth(self.student_token)
        progress_response = self.client.put(
            f"/quizzes/assignments/{self.personal_assignment_id}/progress",
            json={"answers": [{"questionId": self.question_ids[0], "selectedOption": "4"}]},
            headers=headers,
        )
        self.assertEqual(progress_response.status_code, 200, progress_response.text)
        self.assertEqual(progress_response.json()["answeredQuestions"], 1)

        details = self.client.get(
            f"/quizzes/assignments/{self.personal_assignment_id}",
            headers=headers,
        )
        self.assertEqual(details.status_code, 200, details.text)
        self.assertEqual(details.json()["progressAnswers"], {str(self.question_ids[0]): "4"})

        listed = self.client.get("/homework/assignments", headers=headers).json()["assignments"]
        status_by_id = {item["id"]: item["status"] for item in listed}
        self.assertEqual(status_by_id[self.personal_assignment_id], "in_progress")

        submitted = self.client.post(
            f"/quizzes/assignments/{self.personal_assignment_id}/submit",
            json={
                "answers": [
                    {"questionId": self.question_ids[0], "selectedOption": "4"},
                    {"questionId": self.question_ids[1], "selectedOption": "5"},
                ]
            },
            headers=headers,
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["scorePercent"], 50)
        listed = self.client.get("/homework/assignments", headers=headers).json()["assignments"]
        completed = next(item for item in listed if item["id"] == self.personal_assignment_id)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["bestScorePercent"], 50)

    def test_backend_rejects_submission_after_due_date_and_before_availability(self):
        headers = self.auth(self.student_token)
        before_available = self.client.post(
            f"/quizzes/assignments/{self.upcoming_assignment_id}/submit",
            json={"answers": [{"questionId": self.question_ids[0], "selectedOption": "4"}]},
            headers=headers,
        )
        self.assertEqual(before_available.status_code, 409)

        overdue = self.client.post(
            f"/quizzes/assignments/{self.overdue_assignment_id}/submit",
            json={"answers": [{"questionId": self.question_ids[0], "selectedOption": "4"}]},
            headers=headers,
        )
        self.assertEqual(overdue.status_code, 409)

    def test_teacher_can_create_individual_and_group_targeted_homework(self):
        response = self.client.post(
            "/quizzes/assign",
            json={
                "title": "New homework",
                "description": "Review the topic.",
                "materialId": self.material_id,
                "dueDate": (date.today() + timedelta(days=4)).isoformat(),
                "studentIds": [self.student_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        assignment_id = response.json()["assignmentId"]
        self.assertEqual(
            self.client.get(
                f"/quizzes/assignments/{assignment_id}",
                headers=self.auth(self.student_token),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/quizzes/assignments/{assignment_id}",
                headers=self.auth(self.other_student_token),
            ).status_code,
            404,
        )

        group_response = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Group homework",
                "materialId": self.material_id,
                "dueDate": (date.today() + timedelta(days=4)).isoformat(),
                "groupIds": [self.group_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(group_response.status_code, 201, group_response.text)
        group_assignment_id = group_response.json()["assignmentId"]
        self.assertEqual(
            self.client.get(
                f"/quizzes/assignments/{group_assignment_id}",
                headers=self.auth(self.student_token),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/quizzes/assignments/{group_assignment_id}",
                headers=self.auth(self.other_student_token),
            ).status_code,
            404,
        )

    def test_teacher_only_can_assign_homework_and_student_list(self):
        denied_assignment = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Invalid role",
                "materialId": self.material_id,
                "dueDate": (date.today() + timedelta(days=1)).isoformat(),
            },
            headers=self.auth(self.student_token),
        )
        self.assertEqual(denied_assignment.status_code, 403)
        self.assertEqual(
            self.client.get("/homework/assignments", headers=self.auth(self.teacher_token)).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
