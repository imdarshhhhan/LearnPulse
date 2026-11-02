import unittest
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

from api.auth import _create_access_token
from api.notifications import router as notifications_router
from api.quizzes import router as quizzes_router
from api.social import router as social_router
from api.teacher_classes import router as teacher_classes_router
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


class TeacherCompletionNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = TemporaryDirectory()
        self.engine = create_engine(
            URL.create(
                "sqlite",
                database=str(Path(self.temp_directory.name) / "completion-tests.sqlite"),
            ),
            connect_args={"check_same_thread": False},
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
            self.students = [
                User(
                    email=f"student{index}@example.test",
                    fullName=f"Student {index}",
                    usn=f"1AB23CS00{index}",
                    role=UserRole.STUDENT,
                )
                for index in range(1, 5)
            ]
            session.add_all([self.teacher, self.other_teacher, *self.students])
            session.flush()
            self.section_a = TeacherClass(
                name="Section A",
                teacherId=self.teacher.id,
                members=self.students[:2],
            )
            self.section_b = TeacherClass(
                name="Section B",
                teacherId=self.teacher.id,
                members=self.students[2:3],
            )
            self.empty_section = TeacherClass(name="Empty section", teacherId=self.teacher.id)
            self.group = StudyGroup(
                name="Selected group",
                uniqueGroupCode="QZ-COMPLETE",
                creatorId=self.teacher.id,
                members=[self.students[0], self.students[2]],
            )
            material = ContentMaterial(title="Algebra", teacherId=self.teacher.id)
            session.add_all([self.section_a, self.section_b, self.empty_section, self.group, material])
            session.flush()
            session.add_all(
                [
                    QuestionPool(
                        materialId=material.id,
                        conceptTag="Algebra",
                        questionText="What is 2 + 2?",
                        optionsMatrix=["3", "4", "5", "6"],
                        correctAnswer="4",
                        sourceQuote="Source",
                    ),
                    QuestionPool(
                        materialId=material.id,
                        conceptTag="Algebra",
                        questionText="What is 3 + 3?",
                        optionsMatrix=["5", "6", "7", "8"],
                        correctAnswer="6",
                        sourceQuote="Source",
                    ),
                ]
            )
            session.commit()
            self.teacher_id = self.teacher.id
            self.other_teacher_token = _create_access_token(self.other_teacher)
            self.teacher_token = _create_access_token(self.teacher)
            self.student_tokens = [_create_access_token(student) for student in self.students]
            self.student_ids = [student.id for student in self.students]
            self.section_ids = [self.section_a.id, self.section_b.id]
            self.empty_section_id = self.empty_section.id
            self.group_id = self.group.id
            self.material_id = material.id
            self.question_ids = [
                question_id
                for (question_id,) in session.query(QuestionPool.id)
                .filter(QuestionPool.materialId == material.id)
                .order_by(QuestionPool.id)
                .all()
            ]

        app = FastAPI()
        app.include_router(quizzes_router)
        app.include_router(notifications_router)
        app.include_router(social_router)
        app.include_router(teacher_classes_router)

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
        self.temp_directory.cleanup()

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def create_assignment(self, title, activity_type, **targets):
        response = self.client.post(
            "/quizzes/assign",
            json={
                "title": title,
                "activityType": activity_type,
                "materialId": self.material_id,
                "dueDate": (datetime.utcnow() + timedelta(days=2)).date().isoformat(),
                **targets,
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["assignmentId"]

    def submit(self, assignment_id, student_index, submission_id):
        return self.client.post(
            f"/quizzes/assignments/{assignment_id}/submit",
            json={
                "answers": [
                    {"questionId": self.question_ids[0], "selectedOption": "4"},
                    {"questionId": self.question_ids[1], "selectedOption": "6"},
                ],
                "submissionId": submission_id.ljust(16, "x"),
            },
            headers=self.auth(self.student_tokens[student_index]),
        )

    def teacher_notifications(self, activity_type=None, token=None):
        url = "/notifications/teacher"
        if activity_type:
            url += f"?activityType={activity_type}"
        return self.client.get(
            url,
            headers=self.auth(token or self.teacher_token),
        )

    def test_partial_final_submission_per_section_duplicate_retries_and_read_state(self):
        assignment_id = self.create_assignment(
            "Section quiz",
            "quiz",
            classIds=self.section_ids,
        )
        invalid = self.client.post(
            f"/quizzes/assignments/{assignment_id}/submit",
            json={
                "answers": [
                    {"questionId": self.question_ids[0], "selectedOption": "not-an-option"},
                    {"questionId": self.question_ids[1], "selectedOption": "6"},
                ]
            },
            headers=self.auth(self.student_tokens[0]),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.teacher_notifications().json()["notifications"], [])

        self.assertEqual(self.submit(assignment_id, 0, "section-a-001").status_code, 200)
        self.assertEqual(self.teacher_notifications().json()["notifications"], [])

        self.assertEqual(self.submit(assignment_id, 2, "section-b-001").status_code, 200)
        section_b_done = self.teacher_notifications().json()["notifications"]
        self.assertEqual(len(section_b_done), 1)
        self.assertEqual(section_b_done[0]["audienceName"], "Section B")
        self.assertEqual(section_b_done[0]["eligibleCount"], 1)
        self.assertEqual(section_b_done[0]["submittedCount"], 1)
        self.assertIn(f"activityId={assignment_id}", section_b_done[0]["relatedUrl"])

        retry = self.submit(assignment_id, 2, "section-b-001")
        self.assertEqual(retry.status_code, 200)
        second_attempt = self.submit(assignment_id, 2, "section-b-002")
        self.assertEqual(second_attempt.status_code, 200)
        self.assertEqual(len(self.teacher_notifications().json()["notifications"]), 1)

        self.assertEqual(self.submit(assignment_id, 1, "section-a-002").status_code, 200)
        complete = self.teacher_notifications().json()
        self.assertEqual(len(complete["notifications"]), 2)
        self.assertEqual(
            {item["audienceName"] for item in complete["notifications"]},
            {"Section A", "Section B"},
        )
        self.assertTrue(all(item["createdAt"] for item in complete["notifications"]))
        self.assertEqual(complete["unreadCount"], 2)

        other_teacher = self.teacher_notifications(token=self.other_teacher_token).json()
        self.assertEqual(other_teacher["notifications"], [])
        notification_id = next(
            item["id"]
            for item in complete["notifications"]
            if item["audienceName"] == "Section A"
        )
        self.assertEqual(
            self.client.post(
                f"/notifications/{notification_id}/read",
                headers=self.auth(self.other_teacher_token),
            ).status_code,
            404,
        )
        marked = self.client.post(
            f"/notifications/{notification_id}/read",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(marked.status_code, 200)
        reread = self.teacher_notifications().json()
        self.assertEqual(reread["unreadCount"], 1)
        self.assertTrue(
            next(
                item for item in reread["notifications"] if item["id"] == notification_id
            )["isRead"]
        )
        self.client.post(
            "/notifications/read-all",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(self.teacher_notifications().json()["unreadCount"], 0)
        added_to_section = self.client.post(
            f"/teacher/classes/{self.section_ids[0]}/students",
            json={"studentId": self.student_ids[3]},
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(added_to_section.status_code, 201, added_to_section.text)
        self.assertEqual(added_to_section.json()["memberCount"], 3)
        remaining = self.teacher_notifications().json()["notifications"]
        self.assertEqual(len(remaining), 1, remaining)
        self.assertEqual(remaining[0]["audienceName"], "Section B")

    def test_group_audience_homework_and_empty_section(self):
        homework_id = self.create_assignment(
            "Group homework",
            "homework",
            groupIds=[self.group_id],
        )
        self.assertEqual(self.submit(homework_id, 0, "group-homework-001").status_code, 200)
        self.assertEqual(self.teacher_notifications().json()["notifications"], [])
        self.assertEqual(self.submit(homework_id, 2, "group-homework-002").status_code, 200)
        homework_notifications = self.teacher_notifications("homework").json()["notifications"]
        self.assertEqual(len(homework_notifications), 1)
        self.assertEqual(homework_notifications[0]["activityType"], "homework")
        self.assertEqual(homework_notifications[0]["audienceName"], "Selected group")
        self.assertEqual(homework_notifications[0]["eligibleCount"], 2)

        joined = self.client.post(
            "/social/groups/join",
            json={"code": "QZ-COMPLETE"},
            headers=self.auth(self.student_tokens[1]),
        )
        self.assertEqual(joined.status_code, 200, joined.text)
        self.assertEqual(self.teacher_notifications("homework").json()["notifications"], [])

        empty_assignment_id = self.create_assignment(
            "Empty section quiz",
            "quiz",
            classIds=[self.empty_section_id],
        )
        with self.session_factory() as session:
            empty_completion_count = (
                session.query(Notification)
                .filter(
                    Notification.recipientId == self.teacher_id,
                    Notification.sourceId == empty_assignment_id,
                    Notification.sourceType.like("teacher_completion:%"),
                )
                .count()
            )
        self.assertEqual(empty_completion_count, 0)

    def test_changed_assignment_audience_reconciles_old_section_events(self):
        assignment_id = self.create_assignment(
            "Changing audience",
            "quiz",
            classIds=self.section_ids,
        )
        self.submit(assignment_id, 0, "audience-a-001")
        self.submit(assignment_id, 1, "audience-a-002")
        self.submit(assignment_id, 2, "audience-b-001")
        self.assertEqual(len(self.teacher_notifications().json()["notifications"]), 2)

        updated = self.client.put(
            f"/quizzes/assignments/{assignment_id}/recipients",
            json={"studentIds": [self.student_ids[0]]},
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["studentCount"], 1)
        notifications = self.teacher_notifications().json()["notifications"]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["audienceName"], "Selected students")
        self.assertEqual(notifications[0]["eligibleCount"], 1)
        self.assertEqual(notifications[0]["submittedCount"], 1)

        forbidden = self.client.put(
            f"/quizzes/assignments/{assignment_id}/recipients",
            json={"studentIds": [self.student_ids[0]]},
            headers=self.auth(self.other_teacher_token),
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_completion_count_is_distinct_by_student(self):
        assignment_id = self.create_assignment(
            "Distinct submissions",
            "quiz",
            classIds=[self.section_ids[0]],
        )
        self.submit(assignment_id, 0, "distinct-first-001")
        self.submit(assignment_id, 0, "distinct-first-002")
        self.assertEqual(self.teacher_notifications().json()["notifications"], [])
        self.submit(assignment_id, 1, "distinct-second-001")
        notification = self.teacher_notifications().json()["notifications"][0]
        self.assertEqual(notification["eligibleCount"], 2)
        self.assertEqual(notification["submittedCount"], 2)
        with self.session_factory() as session:
            self.assertEqual(
                session.query(Notification)
                .filter(
                    Notification.sourceId == assignment_id,
                    Notification.sourceType.like("teacher_completion:%"),
                )
                .count(),
                1,
            )

    def test_concurrent_final_submissions_create_one_completion_notification(self):
        assignment_id = self.create_assignment(
            "Concurrent quiz",
            "quiz",
            classIds=[self.section_ids[0]],
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    lambda args: self.submit(assignment_id, *args),
                    [
                        (0, "concurrent-student-a"),
                        (1, "concurrent-student-b"),
                    ],
                )
            )

        self.assertEqual([response.status_code for response in responses], [200, 200])
        notifications = self.teacher_notifications().json()["notifications"]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["eligibleCount"], 2)
        self.assertEqual(notifications[0]["submittedCount"], 2)


if __name__ == "__main__":
    unittest.main()
