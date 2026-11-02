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
    Notification,
    QuestionPool,
    StudyGroup,
    TeacherClass,
    User,
    UserRole,
)
from db.sessions import getDb


class TeacherAssignActivityApiTests(unittest.TestCase):
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
            self.quiz = ContentMaterial(title="Biology quiz", teacherId=self.teacher.id)
            self.material_without_quiz = ContentMaterial(
                title="Unquizzed notes",
                teacherId=self.teacher.id,
            )
            self.other_quiz = ContentMaterial(
                title="Another teacher's quiz",
                teacherId=self.other_teacher.id,
            )
            self.group = StudyGroup(
                name="Teacher group",
                uniqueGroupCode="QZ-ASSIGN-ONE",
                creatorId=self.teacher.id,
                members=[self.student],
            )
            self.other_group = StudyGroup(
                name="Other teacher group",
                uniqueGroupCode="QZ-ASSIGN-TWO",
                creatorId=self.other_teacher.id,
                members=[self.other_student],
            )
            self.teacher_class = TeacherClass(
                name="Biology class",
                teacher=self.teacher,
                members=[self.student],
            )
            session.add_all(
                [
                    self.quiz,
                    self.material_without_quiz,
                    self.other_quiz,
                    self.group,
                    self.other_group,
                    self.teacher_class,
                ]
            )
            session.flush()
            session.add_all(
                [
                    QuestionPool(
                        materialId=self.quiz.id,
                        conceptTag="Biology",
                        questionText="What is DNA?",
                        optionsMatrix=["Genetic material", "A cell", "A protein", "A lipid"],
                        correctAnswer="Genetic material",
                        sourceQuote="DNA stores genetic information.",
                    ),
                    QuestionPool(
                        materialId=self.other_quiz.id,
                        conceptTag="Biology",
                        questionText="What is a cell?",
                        optionsMatrix=["Life's unit", "A planet", "A mineral", "A force"],
                        correctAnswer="Life's unit",
                        sourceQuote="Cells are units of life.",
                    ),
                ]
            )
            session.commit()
            self.teacher_id = self.teacher.id
            self.student_id = self.student.id
            self.other_student_id = self.other_student.id
            self.quiz_id = self.quiz.id
            self.no_quiz_id = self.material_without_quiz.id
            self.other_quiz_id = self.other_quiz.id
            self.group_id = self.group.id
            self.other_group_id = self.other_group.id
            self.teacher_class_id = self.teacher_class.id
            self.teacher_token = _create_access_token(self.teacher)
            self.other_teacher_token = _create_access_token(self.other_teacher)
            self.student_token = _create_access_token(self.student)

        app = FastAPI()
        app.include_router(quizzes_router)
        app.include_router(homework_router)

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

    def assign(self, **payload):
        request = {
            "title": "Review photosynthesis",
            "description": "Complete the quiz and review your answers.",
            "materialId": self.quiz_id,
            "dueDate": (date.today() + timedelta(days=4)).isoformat(),
        }
        request.update(payload)
        return self.client.post(
            "/quizzes/assign",
            json=request,
            headers=self.auth(self.teacher_token),
        )

    def test_individual_assignment_persists_due_date_and_notifies_only_recipient(self):
        response = self.assign(studentIds=[self.student_id])
        self.assertEqual(response.status_code, 201, response.text)
        assignment_id = response.json()["assignmentId"]
        expected_due_date = datetime.combine(date.today() + timedelta(days=4), datetime.min.time())

        with self.session_factory() as session:
            assignment = session.get(Assignment, assignment_id)
            self.assertEqual(assignment.teacherId, self.teacher_id)
            self.assertEqual(assignment.description, "Complete the quiz and review your answers.")
            self.assertEqual(assignment.dueDate, expected_due_date)
            self.assertEqual([student.id for student in assignment.targetStudents], [self.student_id])
            notifications = session.query(Notification).filter_by(sourceId=assignment_id).all()
            self.assertEqual({notification.recipientId for notification in notifications}, {self.student_id})

        visible_to_target = self.client.get(
            "/homework/assignments",
            headers=self.auth(self.student_token),
        ).json()["assignments"]
        with self.session_factory() as session:
            other_student_token = _create_access_token(session.get(User, self.other_student_id))
        visible_to_other = self.client.get(
            "/homework/assignments",
            headers=self.auth(other_student_token),
        ).json()["assignments"]
        self.assertIn(assignment_id, {item["id"] for item in visible_to_target})
        self.assertNotIn(assignment_id, {item["id"] for item in visible_to_other})

    def test_group_assignment_is_visible_to_members_only(self):
        response = self.assign(groupIds=[self.group_id])
        self.assertEqual(response.status_code, 201, response.text)
        assignment_id = response.json()["assignmentId"]

        with self.session_factory() as session:
            assignment = session.get(Assignment, assignment_id)
            self.assertEqual([group.id for group in assignment.targetGroups], [self.group_id])

        member_homework = self.client.get(
            "/homework/assignments",
            headers=self.auth(self.student_token),
        ).json()["assignments"]
        with self.session_factory() as session:
            other_student_token = _create_access_token(session.get(User, self.other_student_id))
        nonmember_homework = self.client.get(
            "/homework/assignments",
            headers=self.auth(other_student_token),
        ).json()["assignments"]
        self.assertIn(assignment_id, {item["id"] for item in member_homework})
        self.assertNotIn(assignment_id, {item["id"] for item in nonmember_homework})

    def test_class_assignment_persists_membership_recipients_and_notifications(self):
        response = self.assign(classIds=[self.teacher_class_id])
        self.assertEqual(response.status_code, 201, response.text)
        assignment_id = response.json()["assignmentId"]

        with self.session_factory() as session:
            assignment = session.get(Assignment, assignment_id)
            self.assertEqual(
                [teacher_class.id for teacher_class in assignment.targetClasses],
                [self.teacher_class_id],
            )
            notifications = session.query(Notification).filter_by(sourceId=assignment_id).all()
            self.assertEqual(
                {notification.recipientId for notification in notifications},
                {self.student_id},
            )

        visible = self.client.get(
            "/homework/assignments",
            headers=self.auth(self.student_token),
        ).json()["assignments"]
        self.assertIn(assignment_id, {item["id"] for item in visible})

        with self.session_factory() as session:
            other_student_token = _create_access_token(session.get(User, self.other_student_id))
        other_visible = self.client.get(
            "/homework/assignments",
            headers=self.auth(other_student_token),
        ).json()["assignments"]
        self.assertNotIn(assignment_id, {item["id"] for item in other_visible})

    def test_only_teacher_owned_materials_and_groups_can_be_assigned(self):
        other_material = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Unauthorized material",
                "materialId": self.other_quiz_id,
                "dueDate": (date.today() + timedelta(days=1)).isoformat(),
                "studentIds": [self.student_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(other_material.status_code, 404)

        existing_activity = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Study material activity",
                "materialId": self.no_quiz_id,
                "dueDate": (date.today() + timedelta(days=1)).isoformat(),
                "studentIds": [self.student_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(existing_activity.status_code, 201, existing_activity.text)

        other_group = self.assign(groupIds=[self.other_group_id])
        self.assertEqual(other_group.status_code, 400)

        student_assignment = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Student assignment",
                "materialId": self.quiz_id,
                "dueDate": (date.today() + timedelta(days=1)).isoformat(),
                "studentIds": [self.student_id],
            },
            headers=self.auth(self.student_token),
        )
        self.assertEqual(student_assignment.status_code, 403)

    def test_empty_recipients_and_past_due_dates_are_rejected(self):
        no_recipients = self.assign()
        self.assertEqual(no_recipients.status_code, 400)

        past_due = self.assign(
            studentIds=[self.student_id],
            dueDate=(date.today() - timedelta(days=1)).isoformat(),
        )
        self.assertEqual(past_due.status_code, 400)


if __name__ == "__main__":
    unittest.main()
