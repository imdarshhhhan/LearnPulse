import unittest

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from db.migrations import (
    migrate_assessment_feedback_schema,
    migrate_teacher_completion_notification_schema,
    migrate_question_difficulty_schema,
    migrate_homework_schema,
    migrate_notification_schema,
    migrate_student_usn_schema,
    migrate_submission_idempotency_schema,
)


class HomeworkMigrationTests(unittest.TestCase):
    def test_adds_assessment_type_to_existing_assignments(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE assignments (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO assignments (id) VALUES (1)"))

        migrate_assessment_feedback_schema(engine)
        migrate_assessment_feedback_schema(engine)
        with engine.begin() as connection:
            self.assertEqual(
                connection.execute(
                    text('SELECT "activityType" FROM assignments WHERE id = 1')
                ).scalar(),
                "quiz",
            )
        engine.dispose()

    def test_adds_homework_fields_to_existing_assignment_tables(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE assignments (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE quiz_attempts (id INTEGER PRIMARY KEY)"))

        migrate_homework_schema(engine)
        inspector = inspect(engine)
        assignment_columns = {column["name"] for column in inspector.get_columns("assignments")}
        attempt_columns = {column["name"] for column in inspector.get_columns("quiz_attempts")}
        self.assertTrue({"description", "createdAt"}.issubset(assignment_columns))
        self.assertTrue({"answers", "isSubmitted"}.issubset(attempt_columns))
        engine.dispose()

    def test_adds_notification_details_and_deduplication_index(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE notifications ("
                    "id INTEGER PRIMARY KEY, recipientId INTEGER NOT NULL, "
                    "notificationType VARCHAR NOT NULL, messageBody VARCHAR NOT NULL, "
                    "isRead BOOLEAN, createdAt TIMESTAMP)"
                )
            )

        migrate_notification_schema(engine)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("notifications")}
        indexes = {index["name"] for index in inspector.get_indexes("notifications")}
        self.assertTrue({"title", "relatedUrl", "sourceType", "sourceId"}.issubset(columns))
        self.assertIn("uq_notifications_recipient_source", indexes)
        migrate_teacher_completion_notification_schema(engine)
        columns = {column["name"] for column in inspect(engine).get_columns("notifications")}
        self.assertTrue(
            {"activityType", "audienceName", "eligibleCount", "submittedCount"}.issubset(columns)
        )
        engine.dispose()

    def test_adds_nullable_unique_usn_without_fabricating_legacy_values(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL)"
                )
            )
            connection.execute(
                text("INSERT INTO users (id, email) VALUES (1, 'legacy@example.test')")
            )

        migrate_student_usn_schema(engine)
        inspector = inspect(engine)
        usn_column = next(
            column for column in inspector.get_columns("users") if column["name"] == "usn"
        )
        indexes = {index["name"]: index for index in inspector.get_indexes("users")}
        self.assertTrue(usn_column["nullable"])
        self.assertTrue(indexes["uq_users_usn"]["unique"])

        with engine.begin() as connection:
            self.assertIsNone(connection.execute(text("SELECT usn FROM users WHERE id = 1")).scalar())
            connection.execute(text("UPDATE users SET usn = '1AB23CS001' WHERE id = 1"))
            with self.assertRaises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO users (id, email, usn) "
                        "VALUES (2, 'duplicate@example.test', '1AB23CS001')"
                    )
                )
        engine.dispose()

    def test_adds_unique_submission_key_and_is_repeatable(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE quiz_attempts (id INTEGER PRIMARY KEY)")
            )

        migrate_submission_idempotency_schema(engine)
        migrate_submission_idempotency_schema(engine)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("quiz_attempts")}
        indexes = {index["name"]: index for index in inspector.get_indexes("quiz_attempts")}
        self.assertIn("submissionKey", columns)
        self.assertTrue(indexes["uq_quiz_attempts_submission_key"]["unique"])
        engine.dispose()

    def test_backfills_question_difficulty_to_medium_and_rejects_invalid_values(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE question_pool (id INTEGER PRIMARY KEY, questionText VARCHAR)"
                )
            )
            connection.execute(
                text("INSERT INTO question_pool (id, questionText) VALUES (1, 'Existing item')")
            )

        migrate_question_difficulty_schema(engine)
        with engine.begin() as connection:
            self.assertEqual(
                connection.execute(
                    text("SELECT difficulty FROM question_pool WHERE id = 1")
                ).scalar(),
                "medium",
            )
            with self.assertRaises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO question_pool (id, questionText, difficulty) "
                        "VALUES (2, 'Invalid item', 'impossible')"
                    )
                )
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
