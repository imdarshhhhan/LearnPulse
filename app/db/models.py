import enum
from datetime import datetime
from sqlalchemy import CheckConstraint, Column, Integer, String, ForeignKey, DateTime, JSON, Float, Boolean, Enum, Index, Table, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class UserRole(str, enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"

class NotificationType(str, enum.Enum):
    SUBMISSION = "submission"     
    ASSIGNMENT = "assignment"     
    GROUP_INVITE = "group_invite"
    QUIZ = "quiz"

groupMembership = Table(
    "group_membership",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("study_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.utcnow)
)

assignmentStudents = Table(
    "assignment_students",
    Base.metadata,
    Column("assignment_id", Integer, ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

assignmentGroups = Table(
    "assignment_groups",
    Base.metadata,
    Column("assignment_id", Integer, ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("study_groups.id", ondelete="CASCADE"), primary_key=True),
)

communityMembership = Table(
    "community_membership",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("community_id", Integer, ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.utcnow)
)

classMembership = Table(
    "teacher_class_memberships",
    Base.metadata,
    Column("class_id", Integer, ForeignKey("teacher_classes.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.utcnow, nullable=False),
)

assignmentClasses = Table(
    "assignment_classes",
    Base.metadata,
    Column("assignment_id", Integer, ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", Integer, ForeignKey("teacher_classes.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    fullName = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    usn = Column(String, nullable=True)
    avatarUrl = Column(String, nullable=True)
    achievements = Column(JSON, default=list)
    createdAt = Column(DateTime, default=datetime.utcnow)
    hashedPassword = Column("hashed_password", String, nullable=True)

    __table_args__ = (Index("uq_users_usn", "usn", unique=True),)

    @property
    def hashed_password(self):
        return self.hashedPassword

    @hashed_password.setter
    def hashed_password(self, value: str | None):
        self.hashedPassword = value

    # Relationships
    folders = relationship("Folder", back_populates="owner", cascade="all, delete-orphan")
    materialsCreated = relationship("ContentMaterial", back_populates="teacher")
    assignmentsCreated = relationship("Assignment", back_populates="creator")
    quizAttempts = relationship("QuizAttempt", back_populates="student")
    masteries = relationship("StudentMastery", back_populates="student")
    ownedGroups = relationship("StudyGroup", back_populates="creator")
    joinedGroups = relationship("StudyGroup", secondary=groupMembership, back_populates="members")
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")
    ownedCommunities = relationship("Community", back_populates="creator", cascade="all, delete-orphan")
    communities = relationship("Community", secondary=communityMembership, back_populates="members")
    communityPosts = relationship("CommunityPost", back_populates="author", cascade="all, delete-orphan")
    teacherClasses = relationship("TeacherClass", back_populates="teacher", cascade="all, delete-orphan")
    studentClasses = relationship("TeacherClass", secondary=classMembership, back_populates="members")


class Folder(Base):
    #Subject-wise or exam-wise containers managed by students."""
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    folderType = Column(String, default="subject") # "subject" or "exam"
    ownerId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="folders")
    savedQuizzes = relationship("SavedQuiz", back_populates="folder", cascade="all, delete-orphan")
    documents = relationship("FolderDocument", back_populates="folder", cascade="all, delete-orphan")


class FolderDocument(Base):
    __tablename__ = "folder_documents"

    id = Column(Integer, primary_key=True, index=True)
    folderId = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    fileName = Column(String, nullable=False)
    mimeType = Column(String, nullable=False, default="application/octet-stream")
    content = Column(String, nullable=False)
    storageKey = Column(String, nullable=True, unique=True)
    sizeBytes = Column(Integer, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow)

    folder = relationship("Folder", back_populates="documents")


class ContentMaterial(Base):
    #Saves texts uploaded or compiled by instructors for RAG generations
    __tablename__ = "content_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    generatedStudyGuide = Column(String, nullable=True) # Summary generated notes text
    teacherId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    teacher = relationship("User", back_populates="materialsCreated")
    questions = relationship("QuestionPool", back_populates="sourceMaterial", cascade="all, delete-orphan")


class QuestionPool(Base):

    __tablename__ = "question_pool"
    __table_args__ = (
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'difficult')",
            name="ck_question_pool_difficulty",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    materialId = Column(Integer, ForeignKey("content_materials.id", ondelete="CASCADE"), nullable=False)
    conceptTag = Column(String, index=True, nullable=False) # e.g. "Photosynthesis"
    cognitiveLevel = Column(String, default="Remember")    # Bloom's value
    questionText = Column(String, nullable=False)
    optionsMatrix = Column(JSON, nullable=False)            # 4 string options
    correctAnswer = Column(String, nullable=False)
    sourceQuote = Column(String, nullable=False)
    difficulty = Column(String(16), nullable=False, default="medium", server_default="medium")
    
    # Validation gates flags
    isApprovedAutomatically = Column(Boolean, default=True)
    validationWarnings = Column(JSON, default=list)
    
    # Psychometrics 
    totalAttemptsLogged = Column(Integer, default=0)
    correctAttemptsLogged = Column(Integer, default=0)
    difficulty_index_p = Column(Float, default=1.0) # Correct / Total ratio

    questionType = Column(String(16), default="mcq", nullable=False)
    explanation = Column(String, nullable=True)
    sourcePage = Column(Integer, nullable=True)
    subtopic = Column(String, nullable=True)
    qualityScore = Column(Float, nullable=True)
    qualityFlags = Column(JSON, default=list)
    discriminationIndex = Column(Float, nullable=True)
    distractorStats = Column(JSON, default=dict)
    isArchived = Column(Boolean, default=False, nullable=False)

    sourceMaterial = relationship("ContentMaterial", back_populates="questions")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "activityType IN ('quiz', 'homework')",
            name="ck_assignments_activity_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    activityType = Column(String(16), nullable=False, default="quiz", server_default="quiz")
    materialId = Column(Integer, ForeignKey("content_materials.id"), nullable=False)
    teacherId = Column(Integer, ForeignKey("users.id"), nullable=False)
    availableWindowStart = Column(DateTime, default=datetime.utcnow)
    dueDate = Column(DateTime, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    timeLimitMinutes = Column(Integer, nullable=True)
    maxAttempts = Column(Integer, default=1, nullable=False)
    randomizeQuestions = Column(Boolean, default=True, nullable=False)
    randomizeOptions = Column(Boolean, default=True, nullable=False)
    poolQuestionCount = Column(Integer, nullable=True)

    creator = relationship("User", back_populates="assignmentsCreated")
    attempts = relationship("QuizAttempt", back_populates="assignment", cascade="all, delete-orphan")
    targetStudents = relationship("User", secondary=assignmentStudents)
    targetGroups = relationship("StudyGroup", secondary=assignmentGroups)
    targetClasses = relationship("TeacherClass", secondary=assignmentClasses, back_populates="assignments")


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    subject = Column(String(120), nullable=True)
    description = Column(String(1000), nullable=True)
    teacherId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)

    teacher = relationship("User", back_populates="teacherClasses")
    members = relationship("User", secondary=classMembership, back_populates="studentClasses")
    assignments = relationship("Assignment", secondary=assignmentClasses, back_populates="targetClasses")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("uq_quiz_attempts_submission_key", "submissionKey", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assignmentId = Column(Integer, ForeignKey("assignments.id"), nullable=True) # None if practice test
    score = Column(Float, nullable=False)
    totalQuestions = Column(Integer, nullable=False)
    answers = Column(JSON, nullable=True)
    submissionKey = Column(String(64), nullable=True)
    isSubmitted = Column(Boolean, default=True, nullable=False)
    studentFeedbackNotes = Column(String, nullable=True) # Grounded remediation tips
    attemptTimestamp = Column(DateTime, default=datetime.utcnow)
    startedAt = Column(DateTime, default=datetime.utcnow)
    timeSpentSeconds = Column(Integer, nullable=True)
    questionOrder = Column(JSON, nullable=True)
    optionOrders = Column(JSON, nullable=True)
    remediationData = Column(JSON, nullable=True)

    student = relationship("User", back_populates="quizAttempts")
    assignment = relationship("Assignment", back_populates="attempts")
    savedReferences = relationship("SavedQuiz", back_populates="attemptOrigin", cascade="all, delete-orphan")


class StudentFeedback(Base):
    __tablename__ = "student_feedback"
    __table_args__ = (
        UniqueConstraint("studentId", "assignmentId", name="uq_student_feedback_assessment"),
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5",
            name="ck_student_feedback_rating",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignmentId = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(String(2000), nullable=False)
    category = Column(String(32), nullable=True)
    rating = Column(Integer, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)

    student = relationship("User")
    assignment = relationship("Assignment")


class SavedQuiz(Base):
    __tablename__ = "saved_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    folderId = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False)
    attemptId = Column(Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False)
    bookmarkedAt = Column(DateTime, default=datetime.utcnow)

    folder = relationship("Folder", back_populates="savedQuizzes")
    attemptOrigin = relationship("QuizAttempt", back_populates="savedReferences")


class StudentSavedQuiz(Base):
    __tablename__ = "student_saved_quizzes"
    __table_args__ = (
        UniqueConstraint("studentId", "assignmentId", name="uq_student_saved_quiz"),
    )

    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assignmentId = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    savedAt = Column(DateTime, default=datetime.utcnow, nullable=False)


class StudyGroup(Base):
    __tablename__ = "study_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    uniqueGroupCode = Column(String, unique=True, index=True, nullable=False)
    creatorId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="ownedGroups")
    members = relationship("User", secondary=groupMembership, back_populates="joinedGroups")


class StudentMastery(Base):
    __tablename__ = "student_mastery"

    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conceptTag = Column(String, index=True, nullable=False)
    masteryScore = Column(Float, default=0.5)
    lastUpdated = Column(DateTime, default=datetime.utcnow)
    attemptsCount = Column(Integer, default=0, nullable=False)
    history = Column(JSON, default=list)

    student = relationship("User", back_populates="masteries")


class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    creatorId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="ownedCommunities")
    members = relationship("User", secondary=communityMembership, back_populates="communities")
    posts = relationship("CommunityPost", back_populates="community", cascade="all, delete-orphan")


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id = Column(Integer, primary_key=True, index=True)
    communityId = Column(Integer, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    authorId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(String, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    community = relationship("Community", back_populates="posts")
    author = relationship("User", back_populates="communityPosts")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "uq_notifications_recipient_source",
            "recipientId",
            "sourceType",
            "sourceId",
            unique=True,
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    recipientId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notificationType = Column(Enum(NotificationType), nullable=False)
    title = Column(String, nullable=True)
    messageBody = Column(String, nullable=False)
    relatedUrl = Column(String, nullable=True)
    sourceType = Column(String, nullable=True)
    sourceId = Column(Integer, nullable=True)
    activityType = Column(String(16), nullable=True)
    audienceName = Column(String(200), nullable=True)
    eligibleCount = Column(Integer, nullable=True)
    submittedCount = Column(Integer, nullable=True)
    isRead = Column(Boolean, default=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    recipient = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    targetType = Column(String(64), nullable=True)
    targetId = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

