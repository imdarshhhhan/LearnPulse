import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import _create_access_token
from api.documents import router as documents_router
from api.quizzes import router as quizzes_router
from db.models import (
    Assignment,
    AuditLog,
    Base,
    ContentMaterial,
    QuestionPool,
    QuizAttempt,
    StudentMastery,
    TeacherClass,
    User,
    UserRole,
)
from db.sessions import getDb
from services.adaptive_engine import AdaptiveEngine
from services.document_parser import extract_upload_pages_and_text
from services.item_analysis_service import compute_item_analysis_for_material
from services.llm_service import LLMService
from services.remediation_service import build_evidence_based_remediation
from services.validator import QuestionValidator


class CapstoneCoreFeaturesTests(unittest.TestCase):
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
                email="prof@example.test",
                fullName="Professor Smith",
                role=UserRole.TEACHER,
            )
            self.student_1 = User(
                email="alice@example.test",
                fullName="Alice Student",
                role=UserRole.STUDENT,
                usn="CS001",
            )
            self.student_2 = User(
                email="bob@example.test",
                fullName="Bob Student",
                role=UserRole.STUDENT,
                usn="CS002",
            )
            session.add_all([self.teacher, self.student_1, self.student_2])
            session.flush()

            self.teacher_class = TeacherClass(
                name="Computer Science 101",
                teacherId=self.teacher.id,
                members=[self.student_1, self.student_2],
            )
            session.add(self.teacher_class)
            session.flush()

            self.material = ContentMaterial(
                title="Algorithms and Data Structures",
                generatedStudyGuide="Algorithms solve computational problems efficiently. Binary search takes logarithmic time O(log n).",
                teacherId=self.teacher.id,
            )
            session.add(self.material)
            session.flush()

            # Create calibrated questions
            self.q1 = QuestionPool(
                materialId=self.material.id,
                conceptTag="Searching",
                subtopic="Binary Search",
                cognitiveLevel="Understand",
                difficulty="medium",
                questionType="mcq",
                questionText="What is the time complexity of Binary Search on a sorted array?",
                optionsMatrix=["O(1)", "O(log n)", "O(n)", "O(n^2)"],
                correctAnswer="O(log n)",
                sourceQuote="Binary search takes logarithmic time O(log n).",
                sourcePage=1,
                isApprovedAutomatically=True,
                difficulty_index_p=0.5,
            )
            self.q2 = QuestionPool(
                materialId=self.material.id,
                conceptTag="Searching",
                subtopic="Linear Search",
                cognitiveLevel="Remember",
                difficulty="easy",
                questionType="true_false",
                questionText="True or False: Linear search examines each element in sequential order.",
                optionsMatrix=["True", "False"],
                correctAnswer="True",
                sourceQuote="Linear search examines each element in sequential order.",
                sourcePage=1,
                isApprovedAutomatically=True,
                difficulty_index_p=0.8,
            )
            self.q3 = QuestionPool(
                materialId=self.material.id,
                conceptTag="Sorting",
                subtopic="Merge Sort",
                cognitiveLevel="Apply",
                difficulty="difficult",
                questionType="mcq",
                questionText="What is the worst-case time complexity of Merge Sort?",
                optionsMatrix=["O(n)", "O(n log n)", "O(n^2)", "O(2^n)"],
                correctAnswer="O(n log n)",
                sourceQuote="Merge sort has guaranteed O(n log n) worst-case time complexity.",
                sourcePage=2,
                isApprovedAutomatically=True,
                difficulty_index_p=0.3,
            )
            session.add_all([self.q1, self.q2, self.q3])
            session.flush()

            self.q1_id = self.q1.id
            self.q2_id = self.q2.id
            self.q3_id = self.q3.id

            self.assignment = Assignment(
                title="Search & Sort Quiz",
                materialId=self.material.id,
                teacherId=self.teacher.id,
                dueDate=datetime.utcnow() + timedelta(days=3),
                timeLimitMinutes=20,
                maxAttempts=2,
                randomizeQuestions=True,
                randomizeOptions=False,
                targetStudents=[self.student_1, self.student_2],
            )
            session.add(self.assignment)
            session.commit()

            self.teacher_token = _create_access_token(self.teacher)
            self.student_1_token = _create_access_token(self.student_1)
            self.student_2_token = _create_access_token(self.student_2)

            self.teacher_id = self.teacher.id
            self.student_1_id = self.student_1.id
            self.student_2_id = self.student_2.id
            self.material_id = self.material.id
            self.assignment_id = self.assignment.id
            self.class_id = self.teacher_class.id

        app = FastAPI()
        app.include_router(documents_router)
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

    def auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ─── 1. FEATURE 1: SOURCE-GROUNDED GENERATION & MULTI-TYPE ───
    def test_feature1_source_grounded_generation_and_pages(self):
        json_content = (
            '{"section_1": "Dynamic programming breaks problems into overlapping subproblems.", '
            '"section_2": "Memoization stores intermediate results to avoid redundant calculations."}'
        ).encode("utf-8")
        text, pages = extract_upload_pages_and_text("notes.json", json_content)
        self.assertGreaterEqual(len(pages), 2)
        self.assertIn("Dynamic programming", text)

        from unittest.mock import patch
        with patch("services.llm_service.is_ollama_server_reachable", return_value=False):
            llm = LLMService()
            test_questions = llm.generate_test(
                topic="Dynamic Programming",
                num_questions=5,
                context=text,
                pages=pages,
                include_true_false=True,
            )
        self.assertGreaterEqual(len(test_questions), 2)
        # Verify source quote and page tracking
        for q in test_questions:
            self.assertIn("question", q)
            self.assertIn("options", q)
            self.assertIn("answer", q)
            self.assertIn("cognitive_level", q)
            self.assertIn("difficulty", q)
            self.assertTrue(len(q["options"]) in (2, 4))
            self.assertTrue(len(q.get("source_quote", "")) > 0)

    # ─── 2. FEATURE 2: QUESTION QUALITY VALIDATION & FLAGGING ───
    def test_feature2_question_validation_and_flagging(self):
        # A good question
        good_q = {
            "question": "What is the primary characteristic of a binary search tree?",
            "options": [
                "Left child is smaller than parent node",
                "Right child is always empty",
                "All nodes must have exactly three children",
                "Nodes are unsorted",
            ],
            "correct_answer": "Left child is smaller than parent node",
            "source_quote": "Left child is smaller than parent node.",
            "question_type": "mcq",
        }
        res = QuestionValidator.validate_question(good_q, source_context="Left child is smaller than parent node.")
        self.assertTrue(res["is_approved_automatically"])
        self.assertGreaterEqual(res["quality_score"], 80)

        # Ambiguous / weak / flawed question
        bad_q = {
            "question": "Which might be?",  # too short & ambiguous
            "options": ["all of the above", "B", "B", "None"],  # weak & duplicates
            "correct_answer": "Not in options",  # missing answer
            "source_quote": "",
            "question_type": "mcq",
        }
        res_bad = QuestionValidator.validate_question(bad_q)
        self.assertFalse(res_bad["is_approved_automatically"])
        self.assertLess(res_bad["quality_score"], 60)
        self.assertTrue(len(res_bad["validation_warnings"]) >= 3)

    # ─── 3. FEATURE 3: TAGGING & TEACHER TAG MODIFICATION ───
    def test_feature3_teacher_can_modify_question_tags(self):
        resp = self.client.patch(
            f"/documents/questions/{self.q1_id}",
            json={
                "conceptTag": "Advanced Searching",
                "subtopic": "Binary Search Trees",
                "difficulty": "difficult",
                "cognitiveLevel": "Analyse",
            },
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["conceptTag"], "Advanced Searching")
        self.assertEqual(data["difficulty"], "difficult")
        self.assertEqual(data["cognitiveLevel"], "Analyse")

    # ─── 4. FEATURE 4: GENUINE ADAPTIVE ASSESSMENT & PRACTICE ───
    def test_feature4_adaptive_mastery_and_practice_generation(self):
        # Initial mastery
        mastery = AdaptiveEngine.calculateMastery(
            current_mastery=0.5,
            question_difficulty=0.5,
            is_correct=True,
        )
        self.assertGreater(mastery, 0.5)

        # Update mastery in DB
        with self.session_factory() as session:
            new_score = AdaptiveEngine.updateStudentMastery(
                session,
                student_id=self.student_1_id,
                concept_tag="Searching",
                question_difficulty=0.5,
                is_correct=True,
            )
            self.assertGreater(new_score, 0.5)

        # Generate practice quiz prioritizing weak concepts
        resp = self.client.post(
            "/quizzes/practice/generate",
            json={"materialId": self.material_id, "numQuestions": 3},
            headers=self.auth(self.student_1_token),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertGreaterEqual(resp.json()["totalQuestions"], 1)

    # ─── 5. FEATURE 5: ITEM & DISTRACTOR PSYCHOMETRIC ANALYSIS ───
    def test_feature5_item_and_distractor_analysis(self):
        # Create student attempts to test psychometrics
        with self.session_factory() as session:
            att1 = QuizAttempt(
                studentId=self.student_1_id,
                assignmentId=self.assignment_id,
                score=1,
                totalQuestions=1,
                answers={str(self.q1_id): "O(log n)"},  # correct
                isSubmitted=True,
            )
            att2 = QuizAttempt(
                studentId=self.student_2_id,
                assignmentId=self.assignment_id,
                score=0,
                totalQuestions=1,
                answers={str(self.q1_id): "O(n)"},  # distractor
                isSubmitted=True,
            )
            session.add_all([att1, att2])
            session.commit()

        resp = self.client.get(
            f"/quizzes/materials/{self.material_id}/item-analysis",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertIn("questions", data)
        q1_analysis = next(item for item in data["questions"] if item["id"] == self.q1_id)
        self.assertEqual(q1_analysis["totalAttempts"], 2)
        self.assertEqual(q1_analysis["correctAttempts"], 1)
        self.assertEqual(q1_analysis["difficultyIndexP"], 0.5)
        self.assertIn("distractorAnalysis", q1_analysis)

    # ─── 6. FEATURE 6: EVIDENCE-BASED FEEDBACK & REMEDIATION ───
    def test_feature6_evidence_based_remediation_after_submission(self):
        submit_resp = self.client.post(
            f"/quizzes/assignments/{self.assignment_id}/submit",
            json={
                "answers": [
                    {"questionId": self.q1_id, "selectedOption": "O(log n)"},  # correct
                    {"questionId": self.q2_id, "selectedOption": "False"},  # incorrect
                    {"questionId": self.q3_id, "selectedOption": "O(n^2)"},  # incorrect
                ]
            },
            headers=self.auth(self.student_1_token),
        )
        self.assertEqual(submit_resp.status_code, 200, submit_resp.text)
        att_id = submit_resp.json()["attemptId"]

        # Fetch remediation endpoint
        rem_resp = self.client.get(
            f"/quizzes/attempts/{att_id}/remediation",
            headers=self.auth(self.student_1_token),
        )
        self.assertEqual(rem_resp.status_code, 200, rem_resp.text)
        rem_data = rem_resp.json()["remediationData"]
        self.assertIsNotNone(rem_data)
        self.assertIn("conceptsNeedingRevision", rem_data)
        self.assertIn("studyRecommendations", rem_data)
        self.assertIn("questionBreakdown", rem_data)

    # ─── 7. FEATURE 7: RELIABILITY, TIMING, ATTEMPTS & AUDIT TRAIL ───
    def test_feature7_reliability_server_timing_and_audit(self):
        # 1. Assignment details returns server timing & attempt limits
        detail_resp = self.client.get(
            f"/quizzes/assignments/{self.assignment_id}",
            headers=self.auth(self.student_2_token),
        )
        self.assertEqual(detail_resp.status_code, 200)
        body = detail_resp.json()
        self.assertEqual(body["timeLimitMinutes"], 20)
        self.assertGreater(body["remainingSeconds"], 0)
        self.assertEqual(body["maxAttempts"], 2)
        self.assertEqual(body["attemptsUsed"], 0)

        # 2. Autosave progress
        prog_resp = self.client.put(
            f"/quizzes/assignments/{self.assignment_id}/progress",
            json={"answers": [{"questionId": self.q1_id, "selectedOption": "O(log n)"}]},
            headers=self.auth(self.student_2_token),
        )
        self.assertEqual(prog_resp.status_code, 200)

        # 3. Resume and verify saved answers
        resume_resp = self.client.get(
            f"/quizzes/assignments/{self.assignment_id}",
            headers=self.auth(self.student_2_token),
        )
        self.assertEqual(resume_resp.json()["progressAnswers"], {str(self.q1_id): "O(log n)"})

        # 4. Teacher audit logs
        audit_resp = self.client.get(
            "/quizzes/teacher/audit-logs",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(audit_resp.status_code, 200)
        self.assertIn("logs", audit_resp.json())

    # ─── 8. FEATURE 8: MASTERY TRENDS & CLASS HEATMAP ───
    def test_feature8_mastery_trends_and_class_heatmap(self):
        # Student mastery trends
        trends_resp = self.client.get(
            "/quizzes/student/mastery-trends",
            headers=self.auth(self.student_1_token),
        )
        self.assertEqual(trends_resp.status_code, 200)
        self.assertIn("trends", trends_resp.json())

        # Teacher class heatmap
        heatmap_resp = self.client.get(
            f"/quizzes/teacher/heatmap/{self.class_id}",
            headers=self.auth(self.teacher_token),
        )
        self.assertEqual(heatmap_resp.status_code, 200)
        self.assertIn("studentHeatmap", heatmap_resp.json())
        self.assertEqual(heatmap_resp.json()["className"], "Computer Science 101")


if __name__ == "__main__":
    unittest.main()
