import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token, _serialize_user
from api.folders import router
from config import settings
from db.migrations import migrate_folder_storage_schema
from db.models import Base, FolderDocument, User, UserRole
from db.sessions import getDb


class StudentFoldersApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_storage_dir = settings.FOLDER_STORAGE_DIR
        settings.FOLDER_STORAGE_DIR = Path(self.temp_dir.name) / "uploads"
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as session:
            self.student = User(email="student@example.test", fullName="Student", role=UserRole.STUDENT)
            self.other_student = User(email="other@example.test", fullName="Other Student", role=UserRole.STUDENT)
            self.teacher = User(email="teacher@example.test", fullName="Teacher", role=UserRole.TEACHER)
            session.add_all([self.student, self.other_student, self.teacher])
            session.commit()
            self.student_id = self.student.id
            self.other_student_id = self.other_student.id
            self.teacher_id = self.teacher.id
            self.student_token = _create_access_token(self.student)
            self.other_student_token = _create_access_token(self.other_student)
            self.teacher_token = _create_access_token(self.teacher)

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
        settings.FOLDER_STORAGE_DIR = self.previous_storage_dir
        self.temp_dir.cleanup()

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def create_folder(self, name="DBMS"):
        response = self.client.post(
            "/social/folders",
            json={"name": name},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["folder"]

    def upload_pdf(self, folder_id, filename="notes.pdf", content=b"%PDF-1.7\nQuizora test"):
        return self.client.post(
            f"/social/folders/{folder_id}/files",
            files={"file": (filename, content, "application/pdf")},
            headers=self.auth(self.student_token),
        )

    def test_folder_file_crud_persists_and_downloads(self):
        folder = self.create_folder()
        upload = self.upload_pdf(folder["id"])
        self.assertEqual(upload.status_code, 201, upload.text)
        document = upload.json()["document"]
        self.assertEqual(document["fileName"], "notes.pdf")
        self.assertEqual(document["sizeBytes"], len(b"%PDF-1.7\nQuizora test"))

        downloaded = self.client.get(
            f"/social/folders/{folder['id']}/documents/{document['id']}?download=true",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, b"%PDF-1.7\nQuizora test")
        self.assertIn("attachment", downloaded.headers["content-disposition"])

        renamed = self.client.patch(
            f"/social/folders/{folder['id']}",
            json={"name": "Database Systems"},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["folder"]["name"], "Database Systems")

        listed = self.client.get("/social/folders", headers=self.auth(self.student_token))
        self.assertEqual(listed.json()["folders"][0]["documentCount"], 1)
        stored_key = self._document_storage_key(document["id"])
        stored_path = settings.FOLDER_STORAGE_DIR / stored_key
        self.assertTrue(stored_path.is_file())

        deleted_file = self.client.delete(
            f"/social/folders/{folder['id']}/documents/{document['id']}",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(deleted_file.status_code, 200)
        self.assertFalse(stored_path.exists())
        self.assertEqual(self.client.get(
            f"/social/folders/{folder['id']}/documents",
            headers=self.auth(self.student_token),
        ).json()["documents"], [])

        second_upload = self.upload_pdf(folder["id"], "delete-me.pdf")
        second_id = second_upload.json()["document"]["id"]
        second_key = self._document_storage_key(second_id)
        second_path = settings.FOLDER_STORAGE_DIR / second_key
        self.assertTrue(second_path.exists())
        deleted_folder = self.client.delete(
            f"/social/folders/{folder['id']}",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(deleted_folder.status_code, 200)
        self.assertFalse(second_path.exists())
        self.assertEqual(self.client.get(
            f"/social/folders/{folder['id']}/documents",
            headers=self.auth(self.student_token),
        ).status_code, 404)

    def test_folders_and_documents_are_private_to_the_owner(self):
        folder = self.create_folder()
        upload = self.upload_pdf(folder["id"])
        document_id = upload.json()["document"]["id"]
        other_headers = self.auth(self.other_student_token)

        self.assertEqual(self.client.get("/social/folders", headers=other_headers).json()["folders"], [])
        self.assertEqual(self.client.get(
            f"/social/folders/{folder['id']}/documents",
            headers=other_headers,
        ).status_code, 404)
        self.assertEqual(self.client.post(
            f"/social/folders/{folder['id']}/files",
            files={"file": ("other.pdf", b"%PDF-1.4\nprivate", "application/pdf")},
            headers=other_headers,
        ).status_code, 404)
        self.assertEqual(self.client.patch(
            f"/social/folders/{folder['id']}",
            json={"name": "stolen"},
            headers=other_headers,
        ).status_code, 404)
        self.assertEqual(self.client.get(
            f"/social/folders/{folder['id']}/documents/{document_id}",
            headers=other_headers,
        ).status_code, 404)
        self.assertEqual(self.client.delete(
            f"/social/folders/{folder['id']}/documents/{document_id}",
            headers=other_headers,
        ).status_code, 404)
        self.assertEqual(self.client.delete(
            f"/social/folders/{folder['id']}",
            headers=other_headers,
        ).status_code, 404)

    def test_only_students_can_use_folder_endpoints(self):
        self.assertEqual(self.client.get("/social/folders").status_code, 401)
        headers = self.auth(self.teacher_token)
        self.assertEqual(self.client.get("/social/folders", headers=headers).status_code, 403)
        self.assertEqual(self.client.post(
            "/social/folders",
            json={"name": "Faculty materials"},
            headers=headers,
        ).status_code, 403)
        self.assertEqual(self.client.post(
            "/social/folders/1/files",
            files={"file": ("file.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            headers=headers,
        ).status_code, 403)

    def test_upload_validates_supported_type_and_file_signature(self):
        folder = self.create_folder()
        unsupported = self.upload_pdf(folder["id"], "payload.exe", b"%PDF-1.7\nnot executable")
        self.assertEqual(unsupported.status_code, 415)
        invalid_pdf = self.upload_pdf(folder["id"], "fake.pdf", b"not a pdf")
        self.assertEqual(invalid_pdf.status_code, 415)
        empty_pdf = self.upload_pdf(folder["id"], "empty.pdf", b"")
        self.assertEqual(empty_pdf.status_code, 400)
        self.assertEqual(self.client.get(
            f"/social/folders/{folder['id']}/documents",
            headers=self.auth(self.student_token),
        ).json()["documents"], [])

    def test_upload_rejects_files_over_ten_megabytes(self):
        folder = self.create_folder()
        oversized = b"%PDF-1.7\n" + (b"x" * (10 * 1024 * 1024))
        response = self.upload_pdf(folder["id"], "large.pdf", oversized)
        self.assertEqual(response.status_code, 413)

    def test_legacy_text_notes_remain_available(self):
        folder = self.create_folder()
        response = self.client.post(
            f"/social/folders/{folder['id']}/documents",
            json={
                "title": "Revision notes",
                "fileName": "revision.txt",
                "content": "Study notes",
            },
            headers=self.auth(self.student_token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        document_id = response.json()["document"]["id"]
        download = self.client.get(
            f"/social/folders/{folder['id']}/documents/{document_id}",
            headers=self.auth(self.student_token),
        )
        self.assertEqual(download.json()["content"], "Study notes")
        self.assertEqual(self.client.get(
            f"/social/folders/{folder['id']}/documents/{document_id}?download=true",
            headers=self.auth(self.student_token),
        ).text, "Study notes")
        rejected = self.client.post(
            f"/social/folders/{folder['id']}/documents",
            json={"title": "Bad file", "fileName": "payload.exe", "content": "not executable"},
            headers=self.auth(self.student_token),
        )
        self.assertEqual(rejected.status_code, 415)

    def test_storage_metadata_migration_is_idempotent(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE TABLE folder_documents (id INTEGER PRIMARY KEY, content VARCHAR NOT NULL)"
                ))
            migrate_folder_storage_schema(engine)
            migrate_folder_storage_schema(engine)
            columns = {column["name"] for column in inspect(engine).get_columns("folder_documents")}
            self.assertIn("storageKey", columns)
            self.assertIn("sizeBytes", columns)
        finally:
            engine.dispose()

    def test_authenticated_user_profile_includes_account_details(self):
        with self.session_factory() as session:
            student = session.get(User, self.student_id)
            student.avatarUrl = "https://example.test/avatar.png"
            student.achievements = ["First quiz"]
            session.commit()
            profile = _serialize_user(student)
        self.assertEqual(profile["avatarUrl"], "https://example.test/avatar.png")
        self.assertEqual(profile["achievements"], ["First quiz"])

    def _document_storage_key(self, document_id):
        with self.session_factory() as session:
            return session.query(FolderDocument).filter_by(id=document_id).one().storageKey


if __name__ == "__main__":
    unittest.main()
