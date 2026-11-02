from datetime import datetime, timedelta, timezone
import re

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from db.models import User, UserRole
from db.sessions import getDb


router = APIRouter(prefix="/auth", tags=["User Authentication"])
security = HTTPBearer(auto_error=False)


class RegisterPayload(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    fullName: str = Field(..., min_length=1)
    role: UserRole = UserRole.STUDENT
    usn: str | None = Field(default=None, max_length=32)


class LoginPayload(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)


class StudentUSNPayload(BaseModel):
    usn: str = Field(..., min_length=4, max_length=32)


def _normalize_usn(value: str) -> str:
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9/-]{3,31}", normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="USN must be 4-32 letters, numbers, hyphens, or slashes.",
        )
    return normalized


def _hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(raw_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _serialize_user(user: User) -> dict:
    return {
        "userId": user.id,
        "role": user.role.value,
        "email": user.email,
        "fullName": user.fullName,
        "usn": user.usn,
        "avatarUrl": user.avatarUrl,
        "achievements": user.achievements or [],
    }


def _create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token is invalid or expired.",
        ) from exc


def _get_token_from_request(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()

    token = request.cookies.get("access_token")
    if token:
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing bearer token.",
    )


def get_current_user(
    request: Request,
    db: Session = Depends(getDb),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    token = credentials.credentials if credentials else _get_token_from_request(request)
    payload = _decode_access_token(token)
    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing the user identity.",
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This user is not registered in the application.",
        )

    return _serialize_user(user)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterPayload, db: Session = Depends(getDb)):
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    full_name = payload.fullName.strip()
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name is required.",
        )

    usn = None
    if payload.role == UserRole.STUDENT:
        if payload.usn is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Student USN is required.",
            )
        usn = _normalize_usn(payload.usn)
        if db.query(User).filter(User.usn == usn).first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this USN already exists.",
            )
    elif payload.usn is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Teacher accounts do not use student USNs.",
        )

    user = User(
        email=email,
        fullName=full_name,
        role=payload.role,
        usn=usn,
        hashedPassword=_hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if usn and db.query(User).filter(User.usn == usn).first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this USN already exists.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    db.refresh(user)
    access_token = _create_access_token(user)
    return {
        "token": access_token,
        "tokenType": "bearer",
        "user": _serialize_user(user),
    }


@router.put("/usn")
def update_student_usn(
    payload: StudentUSNPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts can set a USN.",
        )

    usn = _normalize_usn(payload.usn)
    user = db.query(User).filter(User.id == current_user["userId"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if db.query(User).filter(User.usn == usn, User.id != user.id).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this USN already exists.",
        )

    user.usn = usn
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this USN already exists.",
        ) from exc

    db.refresh(user)
    return _serialize_user(user)


@router.post("/login")
def login_user(payload: LoginPayload, db: Session = Depends(getDb)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not _verify_password(payload.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token = _create_access_token(user)
    return {
        "token": access_token,
        "tokenType": "bearer",
        "user": _serialize_user(user),
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout_user():
    return {"status": "success", "message": "Logged out successfully."}
