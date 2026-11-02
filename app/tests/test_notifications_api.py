import unittest
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.notifications import router as notifications_router
from api.quizzes import router as quizzes_router
from db.models import Assignment, Base, ContentMaterial, Notification, StudyGroup, User, UserRole
from db.sessions import getDb
from services.notification_service import create_assignment_notifications


class NotificationsApiTests(unittest.TestCase):
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
            self.group_student = User(
                email="group@example.test",
                fullName="Group Student",
                role=UserRole.STUDENT,
            )
            self.teacher = User(
                email="teacher@example.test",
                fullName="Teacher",
                role=UserRole.TEACHER,
            )
            session.add_all([self.student, self.group_student, self.teacher])
            session.flush()

            material = ContentMaterial(title="Geometry", teacherId=self.teacher.id)
            group = StudyGroup(
                name="Geometry group",
                uniqueGroupCode="QZ-NOTIFY",
                creatorId=self.teacher.id,
                members=[self.group_student],
            )
            session.add_all([material, group])
            session.commit()
            self.material_id = material.id
            self.group_id = group.id
            self.student_id = self.student.id
            self.group_student_id = self.group_student.id
            self.student_token = _create_access_token(self.student)
            self.group_student_token = _create_access_token(self.group_student)
            self.teacher_token = _create_access_token(self.teacher)

        app = FastAPI()
        app.include_router(quizzes_router)
        app.include_router(notifications_router)

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

    def test_teacher_assignment_creates_notifications_for_individual_and_group_recipients(self):
        available_from = datetime.utcnow() + timedelta(days=1)
        response = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Geometry quiz",
                "description": "Triangles and angles.",
                "materialId": self.material_id,
                "dueDate": (date.today() + timedelta(days=4)).isoformat(),
                "availableFrom": available_from.isoformat(),
                "studentIds": [self.student_id],
                "groupIds": [self.group_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        assignment_id = response.json()["assignmentId"]

        individual_notifications = self.client.get(
            "/notifications",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(individual_notifications.status_code, 200)
        individual_items = individual_notifications.json()["notifications"]
        self.assertEqual(len(individual_items), 2)
        self.assertEqual(
            {item["type"] for item in individual_items},
            {"assignment", "quiz"},
        )
        self.assertTrue(all(item["relatedUrl"] == f"/assignments/{assignment_id}" for item in individual_items))

        group_notifications = self.client.get(
            "/notifications",
            headers=self.auth(self.group_student_token),
        )
        self.assertEqual(group_notifications.status_code, 200)
        self.assertEqual(len(group_notifications.json()["notifications"]), 2)

        with self.session_factory() as session:
            assignment = session.get(Assignment, assignment_id)
            create_assignment_notifications(session, assignment)
            session.commit()
            count = (
                session.query(Notification)
                .filter(Notification.sourceId == assignment_id)
                .count()
            )
        self.assertEqual(count, 4)

    def test_read_state_unread_count_and_cross_student_access(self):
        created = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Assigned exercise",
                "materialId": self.material_id,
                "dueDate": (date.today() + timedelta(days=2)).isoformat(),
                "studentIds": [self.student_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(created.status_code, 201, created.text)

        student_headers = self.auth(self.student_token)
        items = self.client.get("/notifications", headers=student_headers).json()
        self.assertEqual(items["unreadCount"], 1)
        notification_id = items["notifications"][0]["id"]

        self.assertEqual(
            self.client.post(
                f"/notifications/{notification_id}/read",
                headers=self.auth(self.group_student_token),
            ).status_code,
            404,
        )
        marked = self.client.post(
            f"/notifications/{notification_id}/read",
            headers=student_headers,
        )
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertEqual(
            self.client.get("/notifications/unread-count", headers=student_headers).json()["unreadCount"],
            0,
        )
        persisted = self.client.get("/notifications", headers=student_headers).json()
        self.assertTrue(persisted["notifications"][0]["isRead"])

    def test_mark_all_read_and_student_role_enforcement(self):
        self.client.post(
            "/quizzes/assign",
            json={
                "title": "Assigned exercise",
                "materialId": self.material_id,
                "dueDate": (date.today() + timedelta(days=2)).isoformat(),
                "studentIds": [self.student_id],
            },
            headers=self.auth(self.teacher_token),
        )
        marked = self.client.post(
            "/notifications/read-all",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertEqual(marked.json()["unreadCount"], 0)
        self.assertEqual(
            self.client.get(
                "/notifications",
                headers=self.auth(self.teacher_token),
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
