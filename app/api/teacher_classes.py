from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import Assignment, TeacherClass, User, UserRole
from db.sessions import getDb
from services.notification_service import reconcile_assignment_completion_notifications


router = APIRouter(prefix="/teacher/classes", tags=["Teacher Class Management"])


class ClassPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    subject: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class ClassStudentPayload(BaseModel):
    studentId: int = Field(..., gt=0)


def _require_teacher(current_user: dict) -> int:
    if current_user.get("role") != UserRole.TEACHER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Class management is only available to teachers.",
        )
    return current_user["userId"]


def _get_owned_class(db: Session, class_id: int, teacher_id: int) -> TeacherClass:
    teacher_class = (
        db.query(TeacherClass)
        .filter(TeacherClass.id == class_id, TeacherClass.teacherId == teacher_id)
        .first()
    )
    if teacher_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    return teacher_class


def _student_data(student: User) -> dict:
    return {
        "id": student.id,
        "fullName": student.fullName,
        "usn": student.usn,
        "email": student.email,
    }


def _class_data(teacher_class: TeacherClass) -> dict:
    students = sorted(teacher_class.members, key=lambda student: (student.fullName.casefold(), student.id))
    return {
        "id": teacher_class.id,
        "name": teacher_class.name,
        "subject": teacher_class.subject,
        "description": teacher_class.description,
        "createdAt": teacher_class.createdAt.isoformat() if teacher_class.createdAt else None,
        "memberCount": len(students),
        "students": [_student_data(student) for student in students],
    }


@router.get("/students")
def list_available_students(
    search: str | None = Query(default=None, max_length=100),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    _require_teacher(current_user)
    query = db.query(User).filter(User.role == UserRole.STUDENT)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (User.fullName.ilike(term))
            | (User.usn.ilike(term))
            | (User.email.ilike(term))
        )
    students = query.order_by(User.fullName.asc(), User.id.asc()).all()
    return {"students": [_student_data(student) for student in students]}


@router.get("")
def list_teacher_classes(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    classes = (
        db.query(TeacherClass)
        .filter(TeacherClass.teacherId == teacher_id)
        .order_by(TeacherClass.name.asc(), TeacherClass.id.asc())
        .all()
    )
    return {"classes": [_class_data(teacher_class) for teacher_class in classes]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_teacher_class(
    payload: ClassPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Class name is required.",
        )
    teacher_class = TeacherClass(
        name=name,
        subject=payload.subject.strip() if payload.subject and payload.subject.strip() else None,
        description=(
            payload.description.strip()
            if payload.description and payload.description.strip()
            else None
        ),
        teacherId=teacher_id,
    )
    db.add(teacher_class)
    db.commit()
    db.refresh(teacher_class)
    return _class_data(teacher_class)


@router.get("/{class_id}")
def read_teacher_class(
    class_id: int = Path(..., gt=0),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_class = _get_owned_class(db, class_id, _require_teacher(current_user))
    return _class_data(teacher_class)


@router.post("/{class_id}/students", status_code=status.HTTP_201_CREATED)
def add_student_to_class(
    payload: ClassStudentPayload,
    class_id: int = Path(..., gt=0),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_class = _get_owned_class(db, class_id, _require_teacher(current_user))
    student = (
        db.query(User)
        .filter(User.id == payload.studentId, User.role == UserRole.STUDENT)
        .first()
    )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )
    if any(member.id == student.id for member in teacher_class.members):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This student is already in the class.",
        )

    teacher_class.members.append(student)
    try:
        db.flush()
        assignments = (
            db.query(Assignment)
            .filter(Assignment.targetClasses.any(TeacherClass.id == teacher_class.id))
            .all()
        )
        for assignment in assignments:
            reconcile_assignment_completion_notifications(db, assignment)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This student is already in the class.",
        ) from exc
    db.refresh(teacher_class)
    return _class_data(teacher_class)


@router.delete("/{class_id}/students/{student_id}", status_code=status.HTTP_200_OK)
def remove_student_from_class(
    class_id: int = Path(..., gt=0),
    student_id: int = Path(..., gt=0),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_class = _get_owned_class(db, class_id, _require_teacher(current_user))
    student = next((member for member in teacher_class.members if member.id == student_id), None)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class member not found.")
    teacher_class.members.remove(student)
    db.flush()
    assignments = (
        db.query(Assignment)
        .filter(Assignment.targetClasses.any(TeacherClass.id == teacher_class.id))
        .all()
    )
    for assignment in assignments:
        reconcile_assignment_completion_notifications(db, assignment)
    db.commit()
    return _class_data(teacher_class)


@router.delete("/{class_id}", status_code=status.HTTP_200_OK)
def delete_teacher_class(
    class_id: int = Path(..., gt=0),
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    teacher_id = _require_teacher(current_user)
    teacher_class = _get_owned_class(db, class_id, teacher_id)
    teacher_class.members.clear()
    db.delete(teacher_class)
    db.commit()
    return {"status": "success", "message": f"Class '{teacher_class.name}' removed successfully."}
