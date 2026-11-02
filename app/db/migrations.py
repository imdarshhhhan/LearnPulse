from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from db.models import AuditLog, Base, TeacherClass, assignmentClasses, classMembership


def migrate_auth_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        raise RuntimeError("The users table must exist before applying auth migrations.")

    columns = {column["name"]: column for column in inspector.get_columns("users")}

    with engine.begin() as connection:
        if "hashed_password" not in columns:
            connection.execute(
                text('ALTER TABLE users ADD COLUMN hashed_password VARCHAR')
            )

        if "hashed_password" in columns and not columns["hashed_password"]["nullable"]:
            connection.execute(
                text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")
            )


def migrate_student_usn_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        raise RuntimeError("The users table must exist before applying USN migrations.")

    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as connection:
        if "usn" not in columns:
            connection.execute(text('ALTER TABLE users ADD COLUMN "usn" VARCHAR'))

        connection.execute(
            text('CREATE UNIQUE INDEX IF NOT EXISTS "uq_users_usn" ON users ("usn")')
        )


def migrate_class_management_schema(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            TeacherClass.__table__,
            classMembership,
            assignmentClasses,
        ],
        checkfirst=True,
    )


def migrate_question_difficulty_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("question_pool"):
        raise RuntimeError("The question_pool table must exist before difficulty migrations.")

    columns = {column["name"] for column in inspector.get_columns("question_pool")}
    with engine.begin() as connection:
        if "difficulty" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE question_pool "
                    "ADD COLUMN difficulty VARCHAR(16) NOT NULL DEFAULT 'medium'"
                )
            )
        connection.execute(
            text(
                "UPDATE question_pool SET difficulty = 'medium' "
                "WHERE difficulty IS NULL OR difficulty NOT IN ('easy', 'medium', 'difficult')"
            )
        )

        if engine.dialect.name == "postgresql":
            constraints = {
                item["name"]
                for item in inspect(connection).get_check_constraints("question_pool")
            }
            if "ck_question_pool_difficulty" not in constraints:
                connection.execute(
                    text(
                        "ALTER TABLE question_pool ADD CONSTRAINT "
                        "ck_question_pool_difficulty "
                        "CHECK (difficulty IN ('easy', 'medium', 'difficult'))"
                    )
                )
        elif engine.dialect.name == "sqlite":
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS trg_question_pool_difficulty_insert "
                    "BEFORE INSERT ON question_pool "
                    "WHEN NEW.difficulty IS NULL OR "
                    "NEW.difficulty NOT IN ('easy', 'medium', 'difficult') "
                    "BEGIN SELECT RAISE(ABORT, 'invalid question difficulty'); END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS trg_question_pool_difficulty_update "
                    "BEFORE UPDATE OF difficulty ON question_pool "
                    "WHEN NEW.difficulty IS NULL OR "
                    "NEW.difficulty NOT IN ('easy', 'medium', 'difficult') "
                    "BEGIN SELECT RAISE(ABORT, 'invalid question difficulty'); END"
                )
            )


def migrate_firebase_auth_schema(engine: Engine) -> None:
    migrate_auth_schema(engine)


def migrate_folder_storage_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("folder_documents"):
        raise RuntimeError("The folder_documents table must exist before applying folder storage migrations.")

    columns = {column["name"] for column in inspector.get_columns("folder_documents")}
    with engine.begin() as connection:
        if "storageKey" not in columns:
            connection.execute(text('ALTER TABLE folder_documents ADD COLUMN "storageKey" VARCHAR'))
        if "sizeBytes" not in columns:
            connection.execute(text('ALTER TABLE folder_documents ADD COLUMN "sizeBytes" INTEGER'))


def migrate_homework_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("assignments") or not inspector.has_table("quiz_attempts"):
        raise RuntimeError("Assignment and attempt tables must exist before applying homework migrations.")

    assignment_columns = {column["name"] for column in inspector.get_columns("assignments")}
    attempt_columns = {column["name"] for column in inspector.get_columns("quiz_attempts")}
    with engine.begin() as connection:
        if "description" not in assignment_columns:
            connection.execute(text('ALTER TABLE assignments ADD COLUMN "description" VARCHAR'))
        if "createdAt" not in assignment_columns:
            connection.execute(text('ALTER TABLE assignments ADD COLUMN "createdAt" TIMESTAMP'))
        if "answers" not in attempt_columns:
            connection.execute(text('ALTER TABLE quiz_attempts ADD COLUMN "answers" JSON'))
        if "isSubmitted" not in attempt_columns:
            connection.execute(
                text('ALTER TABLE quiz_attempts ADD COLUMN "isSubmitted" BOOLEAN NOT NULL DEFAULT TRUE')
            )


def migrate_assessment_feedback_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("assignments"):
        raise RuntimeError("The assignments table must exist before applying feedback migrations.")

    columns = {column["name"] for column in inspector.get_columns("assignments")}
    with engine.begin() as connection:
        if "activityType" not in columns:
            connection.execute(
                text(
                    'ALTER TABLE assignments ADD COLUMN "activityType" '
                    "VARCHAR(16) NOT NULL DEFAULT 'quiz'"
                )
            )


def migrate_submission_idempotency_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("quiz_attempts"):
        raise RuntimeError("The quiz_attempts table must exist before submission migrations.")

    columns = {column["name"] for column in inspector.get_columns("quiz_attempts")}
    with engine.begin() as connection:
        if "submissionKey" not in columns:
            connection.execute(
                text('ALTER TABLE quiz_attempts ADD COLUMN "submissionKey" VARCHAR(64)')
            )
        connection.execute(
            text(
                'CREATE UNIQUE INDEX IF NOT EXISTS "uq_quiz_attempts_submission_key" '
                'ON quiz_attempts ("submissionKey")'
            )
        )


def migrate_notification_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("notifications"):
        raise RuntimeError("The notifications table must exist before applying notification migrations.")

    columns = {column["name"] for column in inspector.get_columns("notifications")}
    with engine.begin() as connection:
        if "title" not in columns:
            connection.execute(text('ALTER TABLE notifications ADD COLUMN "title" VARCHAR'))
        if "relatedUrl" not in columns:
            connection.execute(text('ALTER TABLE notifications ADD COLUMN "relatedUrl" VARCHAR'))
        if "sourceType" not in columns:
            connection.execute(text('ALTER TABLE notifications ADD COLUMN "sourceType" VARCHAR'))
        if "sourceId" not in columns:
            connection.execute(text('ALTER TABLE notifications ADD COLUMN "sourceId" INTEGER'))
        connection.execute(
            text(
                'CREATE UNIQUE INDEX IF NOT EXISTS "uq_notifications_recipient_source" '
                'ON notifications ("recipientId", "sourceType", "sourceId")'
            )
        )
        if engine.dialect.name == "postgresql":
            connection.execute(
                text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'QUIZ'")
            )


def migrate_teacher_completion_notification_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("notifications"):
        raise RuntimeError(
            "The notifications table must exist before applying teacher notification migrations."
        )

    columns = {column["name"] for column in inspector.get_columns("notifications")}
    additions = {
        "activityType": 'VARCHAR(16)',
        "audienceName": 'VARCHAR(200)',
        "eligibleCount": "INTEGER",
        "submittedCount": "INTEGER",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in columns:
                connection.execute(
                    text(
                        f'ALTER TABLE notifications ADD COLUMN "{name}" {column_type}'
                    )
                )


def migrate_capstone_features_schema(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[AuditLog.__table__],
        checkfirst=True,
    )
    inspector = inspect(engine)

    if inspector.has_table("question_pool"):
        qp_columns = {column["name"] for column in inspector.get_columns("question_pool")}
        qp_additions = {
            "questionType": "VARCHAR(16) DEFAULT 'mcq'",
            "explanation": "TEXT",
            "sourcePage": "INTEGER",
            "subtopic": "VARCHAR",
            "qualityScore": "FLOAT",
            "qualityFlags": "JSON",
            "discriminationIndex": "FLOAT",
            "distractorStats": "JSON",
            "isArchived": "BOOLEAN DEFAULT FALSE",
        }
        with engine.begin() as connection:
            for name, col_type in qp_additions.items():
                if name not in qp_columns:
                    connection.execute(text(f'ALTER TABLE question_pool ADD COLUMN "{name}" {col_type}'))

    if inspector.has_table("assignments"):
        asg_columns = {column["name"] for column in inspector.get_columns("assignments")}
        asg_additions = {
            "timeLimitMinutes": "INTEGER",
            "maxAttempts": "INTEGER DEFAULT 1",
            "randomizeQuestions": "BOOLEAN DEFAULT TRUE",
            "randomizeOptions": "BOOLEAN DEFAULT TRUE",
            "poolQuestionCount": "INTEGER",
        }
        with engine.begin() as connection:
            for name, col_type in asg_additions.items():
                if name not in asg_columns:
                    connection.execute(text(f'ALTER TABLE assignments ADD COLUMN "{name}" {col_type}'))

    if inspector.has_table("quiz_attempts"):
        att_columns = {column["name"] for column in inspector.get_columns("quiz_attempts")}
        att_additions = {
            "startedAt": "TIMESTAMP",
            "timeSpentSeconds": "INTEGER",
            "questionOrder": "JSON",
            "optionOrders": "JSON",
            "remediationData": "JSON",
        }
        with engine.begin() as connection:
            for name, col_type in att_additions.items():
                if name not in att_columns:
                    connection.execute(text(f'ALTER TABLE quiz_attempts ADD COLUMN "{name}" {col_type}'))

    if inspector.has_table("student_mastery"):
        mst_columns = {column["name"] for column in inspector.get_columns("student_mastery")}
        mst_additions = {
            "attemptsCount": "INTEGER DEFAULT 0",
            "history": "JSON",
        }
        with engine.begin() as connection:
            for name, col_type in mst_additions.items():
                if name not in mst_columns:
                    connection.execute(text(f'ALTER TABLE student_mastery ADD COLUMN "{name}" {col_type}'))

