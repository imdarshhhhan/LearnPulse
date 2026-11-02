import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.teacher_classes import router
from db.models import Base, TeacherClass, User, UserRole, classMembership
from db.sessions import getDb


class TeacherClassesApiTests(unittest.TestCase):
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
                fullName="Alex Student",
                role=UserRole.STUDENT,
                usn="1AB23CS001",
            )
            self.other_student = User(
                email="other-student@example.test",
                fullName="Sam Student",
                role=UserRole.STUDENT,
                usn="1AB23CS002",
            )
            session.add_all(
                [self.teacher, self.other_teacher, self.student, self.other_student]
            )
            session.commit()
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

    def create_class(self, token=None, name="Biology"):
        return self.client.post(
            "/teacher/classes",
            headers=self.auth(token or self.teacher_token),
            json={"name": name, "subject": "Life sciences", "description": "Year 1"},
        )

    def test_teacher_can_create_search_and_manage_class_members(self):
        created = self.create_class()
        self.assertEqual(created.status_code, 201, created.text)
        class_id = created.json()["id"]
        self.assertEqual(created.json()["name"], "Biology")
        self.assertEqual(created.json()["memberCount"], 0)

        search = self.client.get(
            "/teacher/classes/students?search=1ab23cs001",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(search.status_code, 200, search.text)
        self.assertEqual(
            [student["usn"] for student in search.json()["students"]],
            ["1AB23CS001"],
        )

        added = self.client.post(
            f"/teacher/classes/{class_id}/students",
            headers=self.auth(self.teacher_token),
            json={"studentId": self.student.id},
        )
        self.assertEqual(added.status_code, 201, added.text)
        self.assertEqual(added.json()["memberCount"], 1)
        self.assertEqual(added.json()["students"][0]["usn"], "1AB23CS001")

        duplicate = self.client.post(
            f"/teacher/classes/{class_id}/students",
            headers=self.auth(self.teacher_token),
            json={"studentId": self.student.id},
        )
        self.assertEqual(duplicate.status_code, 409)

        removed = self.client.delete(
            f"/teacher/classes/{class_id}/students/{self.student.id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()["memberCount"], 0)

    def test_student_can_join_multiple_classes_but_teachers_cannot_be_added(self):
        first = self.create_class().json()
        second = self.create_class(name="Chemistry").json()
        for class_id in (first["id"], second["id"]):
            response = self.client.post(
                f"/teacher/classes/{class_id}/students",
                headers=self.auth(self.teacher_token),
                json={"studentId": self.student.id},
            )
            self.assertEqual(response.status_code, 201, response.text)

        teacher_response = self.client.post(
            f"/teacher/classes/{first['id']}/students",
            headers=self.auth(self.teacher_token),
            json={"studentId": self.other_teacher_id()},
        )
        self.assertEqual(teacher_response.status_code, 404)
        with self.session_factory() as session:
            membership_count = session.execute(
                select(func.count())
                .select_from(classMembership)
                .where(classMembership.c.student_id == self.student.id)
            ).scalar_one()
        self.assertEqual(membership_count, 2)

    def test_class_data_is_private_to_owning_teacher(self):
        teacher_class = self.create_class().json()
        other_teacher_class = self.create_class(
            token=self.other_teacher_token,
            name="Other class",
        ).json()
        forbidden_list = self.client.get(
            "/teacher/classes",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(forbidden_list.status_code, 403)

        hidden_class = self.client.get(
            f"/teacher/classes/{other_teacher_class['id']}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(hidden_class.status_code, 404)
        listed = self.client.get(
            "/teacher/classes",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual([item["id"] for item in listed.json()["classes"]], [teacher_class["id"]])

    def other_teacher_id(self):
        with self.session_factory() as session:
            return session.query(User.id).filter(User.email == "other-teacher@example.test").scalar()


if __name__ == "__main__":
    unittest.main()
