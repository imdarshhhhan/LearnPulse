
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.sessions import getDb
from db.models import AuditLog, ContentMaterial, QuestionPool
from services.rag_service import RAGService
from api.auth import get_current_user
from services.document_parser import (
    DocumentValidationError,
    MAX_UPLOAD_BYTES,
    extract_upload_pages_and_text,
    extract_upload_text,
)
from services.llm_service import LLMService
from services.validator import QuestionValidator


router = APIRouter(
    prefix="/documents",
    tags=["Teacher Content Management"]
)

ragService = RAGService()
llmService = LLMService()

class UploadMaterialSchema(BaseModel):
    title: str
    textBody: str


def _require_teacher(current_user: dict) -> int:
    if current_user.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You don't have access to this feature",
        )
    teacher_id = current_user.get("userId")
    if not teacher_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Teacher database ID not found.",
        )
    return teacher_id


@router.post("/generate-test")
def generate_test_from_upload(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=200),
    questionCount: int = Form(default=5),
    questionType: str = Form(default="mcq"),
    current_user: dict = Depends(get_current_user),
):
    _require_teacher(current_user)
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="Choose a PDF or JSON file.")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    try:
        source_text, pages_data = extract_upload_pages_and_text(filename, content)
    except DocumentValidationError as exc:
        status_code = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if len(content) > MAX_UPLOAD_BYTES
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    quiz_title = (title or "").strip() or filename.rsplit(".", 1)[0].strip()
    if not quiz_title:
        raise HTTPException(status_code=400, detail="A quiz title is required.")
    if len(quiz_title) > 200:
        raise HTTPException(status_code=400, detail="Quiz titles must be 200 characters or fewer.")

    count = max(1, min(questionCount, 30))
    q_type = (questionType or "mcq").strip().lower()
    if q_type not in {"mcq", "true_false"}:
        q_type = "mcq"
    try:
        questions = llmService.generate_test(
            quiz_title,
            num_questions=count,
            context=source_text,
            pages=pages_data,
            question_type=q_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {
        "title": quiz_title,
        "sourceText": source_text,
        "pages": pages_data,
        "questions": questions,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def processTeacherDocument(
    payload: UploadMaterialSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user)
):
    
    #Creates a teacher content record in PostgreSQL and indexes its text content into ChromaDB.
  

    teacherId = _require_teacher(current_user)

    newMaterialRecord = ContentMaterial(
        title=payload.title,
        generatedStudyGuide=payload.textBody[:200],
        teacherId=teacherId
    )

    db.add(newMaterialRecord)
    db.commit()
    db.refresh(newMaterialRecord)

    # Index content into ChromaDB
    try:
        totalChunksIndexed = ragService.add_document_content(
            payload.textBody
        )

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector database indexing failed: {str(e)}"
        )

    return {
        "status": "success",
        "materialId": newMaterialRecord.id,
        "title": newMaterialRecord.title,
        "chunksIndexed": totalChunksIndexed
    }


# ─── POST A REVIEWED AI-GENERATED TEST ───
class TestQuestionSchema(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    options: list[str] = Field(..., min_length=2, max_length=4)
    answer: str = Field(..., min_length=1, max_length=1000)
    difficulty: Literal["easy", "medium", "difficult"] = "medium"
    cognitiveLevel: Literal["Remember", "Understand", "Apply", "Analyse"] = "Remember"
    conceptTag: str | None = None
    subtopic: str | None = None
    questionType: Literal["mcq", "true_false"] = "mcq"
    explanation: str | None = None
    sourceQuote: str | None = None
    sourcePage: int | None = None
    isApprovedAutomatically: bool = True
    validationWarnings: list[str] = Field(default_factory=list)
    qualityScore: float | None = None

class PostTestSchema(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    questions: list[TestQuestionSchema] = Field(..., min_length=1, max_length=50)
    sourceText: str | None = Field(default=None, max_length=60_000)

@router.post("/post-test", status_code=status.HTTP_201_CREATED)
def postTeacherTest(
    payload: PostTestSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user)
):
    teacherId = _require_teacher(current_user)

    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is missing.")
    if not payload.questions:
        raise HTTPException(status_code=400, detail="Keep at least one question before posting.")
    seen_stems: list[str] = []
    for number, q in enumerate(payload.questions, start=1):
        q_stem = q.question.strip()
        for past_stem in seen_stems:
            if QuestionValidator.is_duplicate(q_stem, past_stem):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {number} is a duplicate of a previously included question in this quiz.",
                )
        seen_stems.append(q_stem)

        normalized_options = [option.strip().casefold() for option in q.options]
        expected_len = 2 if q.questionType == "true_false" or len(q.options) == 2 else 4
        if (
            not q.question.strip()
            or any(not option.strip() for option in q.options)
            or len(set(normalized_options)) != len(q.options)
            or len(q.options) != expected_len
            or q.answer not in q.options
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Question {number} is not a valid {expected_len}-option question."
            )

    try:
        material = ContentMaterial(
            title=topic,
            generatedStudyGuide=payload.sourceText or f"AI-generated test on {topic}",
            teacherId=teacherId
        )
        db.add(material)
        db.flush()

        db.add_all([
            QuestionPool(
                materialId=material.id,
                conceptTag=q.conceptTag.strip() if q.conceptTag else topic,
                subtopic=q.subtopic.strip() if q.subtopic else topic,
                cognitiveLevel=q.cognitiveLevel or "Remember",
                difficulty=q.difficulty,
                questionType=q.questionType if len(q.options) > 2 else "true_false",
                questionText=q.question.strip(),
                optionsMatrix=q.options,
                correctAnswer=q.answer,
                explanation=q.explanation or "Directly grounded in source material.",
                sourceQuote=q.sourceQuote or f"Teacher-approved AI question on: {topic}",
                sourcePage=q.sourcePage or 1,
                isApprovedAutomatically=q.isApprovedAutomatically,
                validationWarnings=q.validationWarnings or [],
                qualityScore=q.qualityScore or 90.0,
            )
            for q in payload.questions
        ])

        audit = AuditLog(
            userId=teacherId,
            action="POST_TEST",
            targetType="material",
            targetId=material.id,
            details={"title": topic, "questionsCount": len(payload.questions)},
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save the test: {str(e)}"
        )

    # Index material chunks into ChromaDB for RAG context retrieval
    if payload.sourceText:
        try:
            ragService.add_document_content(payload.sourceText, material_id=material.id)
        except Exception:
            pass

    return {
        "status": "success",
        "materialId": material.id,
        "title": material.title,
        "questionsPosted": len(payload.questions)
    }


class UpdateQuestionSchema(BaseModel):
    questionText: str | None = None
    optionsMatrix: list[str] | None = None
    correctAnswer: str | None = None
    difficulty: Literal["easy", "medium", "difficult"] | None = None
    cognitiveLevel: Literal["Remember", "Understand", "Apply", "Analyse"] | None = None
    conceptTag: str | None = None
    subtopic: str | None = None
    explanation: str | None = None


@router.patch("/questions/{question_id}")
def updateQuestionTags(
    question_id: int,
    payload: UpdateQuestionSchema,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    question = (
        db.query(QuestionPool)
        .join(ContentMaterial, QuestionPool.materialId == ContentMaterial.id)
        .filter(QuestionPool.id == question_id, ContentMaterial.teacherId == teacher_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found or unauthorized.")

    if payload.questionText is not None:
        question.questionText = payload.questionText.strip()
    if payload.optionsMatrix is not None:
        question.optionsMatrix = payload.optionsMatrix
    if payload.correctAnswer is not None:
        question.correctAnswer = payload.correctAnswer.strip()
    if payload.difficulty is not None:
        question.difficulty = payload.difficulty
    if payload.cognitiveLevel is not None:
        question.cognitiveLevel = payload.cognitiveLevel
    if payload.conceptTag is not None:
        question.conceptTag = payload.conceptTag.strip()
    if payload.subtopic is not None:
        question.subtopic = payload.subtopic.strip()
    if payload.explanation is not None:
        question.explanation = payload.explanation.strip()

    audit = AuditLog(
        userId=teacher_id,
        action="UPDATE_QUESTION_TAGS",
        targetType="question",
        targetId=question.id,
        details={"conceptTag": question.conceptTag, "difficulty": question.difficulty, "cognitiveLevel": question.cognitiveLevel},
    )
    db.add(audit)
    db.commit()
    db.refresh(question)

    return {
        "status": "success",
        "questionId": question.id,
        "questionText": question.questionText,
        "conceptTag": question.conceptTag,
        "subtopic": question.subtopic,
        "difficulty": question.difficulty,
        "cognitiveLevel": question.cognitiveLevel,
        "correctAnswer": question.correctAnswer,
        "optionsMatrix": question.optionsMatrix,
    }


@router.delete("/questions/{question_id}")
def archiveQuestion(
    question_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    question = (
        db.query(QuestionPool)
        .join(ContentMaterial, QuestionPool.materialId == ContentMaterial.id)
        .filter(QuestionPool.id == question_id, ContentMaterial.teacherId == teacher_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found or unauthorized.")

    question.isArchived = True
    audit = AuditLog(
        userId=teacher_id,
        action="ARCHIVE_QUESTION",
        targetType="question",
        targetId=question.id,
        details={"questionText": question.questionText[:60]},
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": "Question archived successfully."}

