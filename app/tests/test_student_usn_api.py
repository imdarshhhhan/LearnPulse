import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token, router
from db.models import Base, User, UserRole
from db.sessions import getDb


class StudentUSNApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
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

    def test_student_registration_login_and_usn_uniqueness(self):
        registration = self.client.post(
            "/auth/register",
            json={
                "email": "student@example.test",
                "password": "long-password",
                "fullName": "Student One",
                "role": "student",
                "usn": "1ab23cs001",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        self.assertEqual(registration.json()["user"]["usn"], "1AB23CS001")

        login = self.client.post(
            "/auth/login",
            json={"email": "student@example.test", "password": "long-password"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["user"]["usn"], "1AB23CS001")

        duplicate = self.client.post(
            "/auth/register",
            json={
                "email": "student-two@example.test",
                "password": "long-password",
                "fullName": "Student Two",
                "usn": "1AB23CS001",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_student_registration_requires_well_formed_usn(self):
        missing = self.client.post(
            "/auth/register",
            json={
                "email": "missing@example.test",
                "password": "long-password",
                "fullName": "Missing USN",
            },
        )
        self.assertEqual(missing.status_code, 422)

        malformed = self.client.post(
            "/auth/register",
            json={
                "email": "malformed@example.test",
                "password": "long-password",
                "fullName": "Malformed USN",
                "usn": "not a usn",
            },
        )
        self.assertEqual(malformed.status_code, 422)

    def test_teacher_registration_does_not_require_or_receive_student_usn(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "teacher@example.test",
                "password": "long-password",
                "fullName": "Teacher",
                "role": "teacher",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIsNone(response.json()["user"]["usn"])

    def test_existing_student_can_add_usn_after_login(self):
        with self.session_factory() as session:
            student = User(
                email="legacy@example.test",
                fullName="Legacy Student",
                role=UserRole.STUDENT,
            )
            session.add(student)
            session.commit()
            token = _create_access_token(student)

        profile = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertIsNone(profile.json()["usn"])

        update = self.client.put(
            "/auth/usn",
            headers={"Authorization": f"Bearer {token}"},
            json={"usn": "1AB23CS002"},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["usn"], "1AB23CS002")
