import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.documents import llmService, router as documents_router
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
from services.document_parser import MAX_UPLOAD_BYTES


def make_text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 40 100 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 200] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Root 1 0 R /Size {len(offsets)} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


class TeacherQuizCreationApiTests(unittest.TestCase):
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
            session.add_all([self.teacher, self.student, self.other_student])
            session.flush()
            self.group = StudyGroup(
                name="Biology group",
                uniqueGroupCode="QZ-TEACHER-QUIZ",
                creatorId=self.teacher.id,
                members=[self.student],
            )
            session.add(self.group)
            session.commit()
            self.teacher_id = self.teacher.id
            self.teacher_token = _create_access_token(self.teacher)
            self.student_token = _create_access_token(self.student)
            self.student_id = self.student.id
            self.other_student_id = self.other_student.id
            self.group_id = self.group.id

        app = FastAPI()
        app.include_router(documents_router)
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

    @staticmethod
    def generated_questions():
        return [
            {
                "question": f"Question {number}?",
                "options": ["A", "B", "C", f"D{number}"],
                "answer": "A",
            }
            for number in range(1, 6)
        ]

    def test_pdf_upload_extracts_text_and_uses_quiz_generator(self):
        source = (
            "Plants use sunlight to convert water and carbon dioxide into sugars "
            "and oxygen during photosynthesis."
        )
        with patch.object(llmService, "generate_test", return_value=self.generated_questions()) as generate:
            response = self.client.post(
                "/documents/generate-test",
                files={"file": ("plants.pdf", make_text_pdf(source), "application/pdf")},
                headers=self.auth(self.teacher_token),
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["title"], "plants")
        self.assertIn("photosynthesis", response.json()["sourceText"])
        self.assertEqual(len(response.json()["questions"]), 5)
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs["context"], response.json()["sourceText"])

    def test_json_upload_generate_post_and_group_homework_visibility(self):
        source = (
            '{"title":"Cell biology","material":"Cells contain genetic information. '
            'The nucleus stores DNA and regulates cell activity."}'
        )
        with patch.object(llmService, "generate_test", return_value=self.generated_questions()):
            generated = self.client.post(
                "/documents/generate-test",
                data={"title": "Cell quiz"},
                files={"file": ("cells.json", source, "application/json")},
                headers=self.auth(self.teacher_token),
            )
        self.assertEqual(generated.status_code, 200, generated.text)
        self.assertIn("nucleus", generated.json()["sourceText"])

        reviewed_questions = generated.json()["questions"]
        reviewed_questions[0] = {
            "question": "What is the updated cell function?",
            "options": ["Updated answer", "B", "C", "D1"],
            "answer": "Updated answer",
        }
        posted = self.client.post(
            "/documents/post-test",
            json={
                "topic": generated.json()["title"],
                "sourceText": generated.json()["sourceText"],
                "questions": reviewed_questions,
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(posted.status_code, 201, posted.text)
        material_id = posted.json()["materialId"]
        with self.session_factory() as session:
            material = session.get(ContentMaterial, material_id)
            self.assertEqual(material.teacherId, self.teacher_id)
            self.assertIn("nucleus", material.generatedStudyGuide)
            self.assertEqual(session.query(QuestionPool).filter_by(materialId=material_id).count(), 5)
            edited_question = (
                session.query(QuestionPool)
                .filter_by(materialId=material_id)
                .order_by(QuestionPool.id)
                .first()
            )
            self.assertEqual(edited_question.questionText, "What is the updated cell function?")
            self.assertEqual(edited_question.correctAnswer, "Updated answer")

        assigned = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Cell quiz homework",
                "materialId": material_id,
                "dueDate": (date.today() + timedelta(days=5)).isoformat(),
                "groupIds": [self.group_id],
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(assigned.status_code, 201, assigned.text)
        assignment_id = assigned.json()["assignmentId"]
        with self.session_factory() as session:
            assignment = session.get(Assignment, assignment_id)
            self.assertEqual(assignment.teacherId, self.teacher_id)
            self.assertEqual([user.id for user in assignment.targetGroups[0].members], [self.student_id])

        student_homework = self.client.get(
            "/homework/assignments",
            headers=self.auth(self.student_token),
        )
        with self.session_factory() as session:
            other_student_token = _create_access_token(session.get(User, self.other_student_id))
        other_homework = self.client.get(
            "/homework/assignments",
            headers=self.auth(other_student_token),
        )
        self.assertIn(assignment_id, {item["id"] for item in student_homework.json()["assignments"]})
        self.assertNotIn(assignment_id, {item["id"] for item in other_homework.json()["assignments"]})

    def test_invalid_uploads_and_missing_source_content_are_rejected(self):
        auth = self.auth(self.teacher_token)
        invalid_type = self.client.post(
            "/documents/generate-test",
            files={"file": ("notes.txt", b"ordinary text content " * 10, "text/plain")},
            headers=auth,
        )
        self.assertEqual(invalid_type.status_code, 400)

        invalid_pdf = self.client.post(
            "/documents/generate-test",
            files={"file": ("notes.pdf", b"%PDF-not a real document", "application/pdf")},
            headers=auth,
        )
        self.assertEqual(invalid_pdf.status_code, 400)

        invalid_json = self.client.post(
            "/documents/generate-test",
            files={"file": ("notes.json", b"{invalid", "application/json")},
            headers=auth,
        )
        self.assertEqual(invalid_json.status_code, 400)

        empty_json = self.client.post(
            "/documents/generate-test",
            files={"file": ("notes.json", b'{"values":[1,2,3]}', "application/json")},
            headers=auth,
        )
        self.assertEqual(empty_json.status_code, 400)

        oversized = self.client.post(
            "/documents/generate-test",
            files={"file": ("notes.json", b"x" * (MAX_UPLOAD_BYTES + 1), "application/json")},
            headers=auth,
        )
        self.assertEqual(oversized.status_code, 413)

    def test_upload_publish_and_recipient_selection_require_teacher_auth(self):
        pdf = make_text_pdf("Readable source text that has enough meaningful information for a quiz.")
        upload = self.client.post(
            "/documents/generate-test",
            files={"file": ("notes.pdf", pdf, "application/pdf")},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(upload.status_code, 403)

        post = self.client.post(
            "/documents/post-test",
            json={"topic": "Biology", "questions": self.generated_questions()},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(post.status_code, 403)
        self.assertEqual(
            self.client.post(
                "/documents/generate-test",
                files={"file": ("notes.pdf", pdf, "application/pdf")},
            ).status_code,
            401,
        )

        with self.session_factory() as session:
            material = ContentMaterial(title="Biology", teacherId=self.teacher.id)
            session.add(material)
            session.commit()
            material_id = material.id
        no_recipients = self.client.post(
            "/quizzes/assign",
            json={
                "title": "Unscoped homework",
                "materialId": material_id,
                "dueDate": (date.today() + timedelta(days=1)).isoformat(),
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(no_recipients.status_code, 400)


if __name__ == "__main__":
    unittest.main()
