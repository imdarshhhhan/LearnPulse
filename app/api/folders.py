import io
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import Folder, FolderDocument
from db.sessions import getDb
from services.folder_storage import delete_folder_file, resolve_folder_file, save_folder_file

router = APIRouter(prefix="/social/folders", tags=["Student Folders"])
MAX_FILE_SIZE = 10 * 1024 * 1024
READ_CHUNK_SIZE = 64 * 1024
ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
INLINE_FILE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "text/plain", "text/markdown", "text/csv"}


class FolderPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    folderType: str = "custom"


class RenameFolderPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class LegacyDocumentPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    fileName: str = Field(..., min_length=1, max_length=200)
    mimeType: str = "text/plain"
    content: str = ""


def require_student(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access is required for folders.",
        )
    return current_user


def _get_owned_folder(db: Session, folder_id: int, user_id: int) -> Folder:
    folder = (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.ownerId == user_id)
        .first()
    )
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
    return folder


def _serialize_folder(folder: Folder) -> dict:
    return {
        "id": folder.id,
        "name": folder.name,
        "folderType": folder.folderType,
        "createdAt": folder.createdAt.isoformat() if folder.createdAt else None,
        "documentCount": len(folder.documents or []),
    }


def _serialize_document(document: FolderDocument) -> dict:
    return {
        "id": document.id,
        "folderId": document.folderId,
        "title": document.title,
        "fileName": document.fileName,
        "mimeType": document.mimeType,
        "sizeBytes": document.sizeBytes,
        "createdAt": document.createdAt.isoformat() if document.createdAt else None,
        "downloadUrl": f"/social/folders/{document.folderId}/documents/{document.id}?download=true",
    }


def _safe_filename(filename: str | None) -> str:
    candidate = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    candidate = "".join(char for char in candidate if char >= " " and char not in "\r\n")
    candidate = candidate.strip().strip(".")
    if not candidate or len(candidate.encode("utf-8")) > 240:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid file name is required.")
    return candidate


def _validate_file(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    mime_type = ALLOWED_FILE_TYPES.get(extension)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a PDF, image, text, CSV, Markdown, or DOCX file.",
        )
    valid = False
    if extension == ".pdf":
        valid = content.startswith(b"%PDF-")
    elif extension == ".png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension in {".jpg", ".jpeg"}:
        valid = content.startswith(b"\xff\xd8\xff")
    elif extension == ".gif":
        valid = content.startswith((b"GIF87a", b"GIF89a"))
    elif extension == ".webp":
        valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    elif extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as document:
                valid = {"[Content_Types].xml", "word/document.xml"}.issubset(document.namelist())
        except (zipfile.BadZipFile, OSError):
            valid = False
    else:
        try:
            decoded = content.decode("utf-8")
            valid = "\x00" not in decoded
        except UnicodeDecodeError:
            valid = False

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded content does not match its file type or is invalid.",
        )
    return mime_type


async def _read_upload(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await upload.read(READ_CHUNK_SIZE):
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Files must be 10 MB or smaller.",
            )
        chunks.append(chunk)
    if total_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The selected file is empty.")
    return b"".join(chunks)


@router.get("")
def list_folders(
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folders = (
        db.query(Folder)
        .filter(Folder.ownerId == current_user["userId"])
        .order_by(Folder.createdAt.desc())
        .all()
    )
    return {"folders": [_serialize_folder(folder) for folder in folders]}


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/create", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_folder(
    payload: FolderPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder name is required.")
    folder = Folder(name=name, folderType="custom", ownerId=current_user["userId"])
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"message": "Folder created.", "folder": _serialize_folder(folder)}


@router.patch("/{folder_id}")
def rename_folder(
    folder_id: int,
    payload: RenameFolderPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder name is required.")
    folder.name = name
    db.commit()
    db.refresh(folder)
    return {"message": "Folder renamed.", "folder": _serialize_folder(folder)}


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    storage_keys = [document.storageKey for document in folder.documents if document.storageKey]
    db.delete(folder)
    db.commit()
    for storage_key in storage_keys:
        delete_folder_file(storage_key)
    return {"message": "Folder deleted."}


@router.get("/{folder_id}/documents")
def list_folder_documents(
    folder_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    documents = (
        db.query(FolderDocument)
        .filter(FolderDocument.folderId == folder.id)
        .order_by(FolderDocument.createdAt.desc())
        .all()
    )
    return {
        "folder": _serialize_folder(folder),
        "documents": [_serialize_document(document) for document in documents],
    }


@router.post("/{folder_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_folder_file(
    folder_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=200),
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    filename = _safe_filename(file.filename)
    content = await _read_upload(file)
    mime_type = _validate_file(filename, content)
    storage_key = save_folder_file(content)
    document = FolderDocument(
        folderId=folder.id,
        title=(title or Path(filename).stem).strip()[:200] or Path(filename).stem[:200],
        fileName=filename,
        mimeType=mime_type,
        content="",
        storageKey=storage_key,
        sizeBytes=len(content),
    )
    db.add(document)
    try:
        db.commit()
        db.refresh(document)
    except SQLAlchemyError:
        db.rollback()
        delete_folder_file(storage_key)
        raise
    return {"message": "File uploaded.", "document": _serialize_document(document)}


@router.post("/{folder_id}/documents", status_code=status.HTTP_201_CREATED)
def upload_legacy_text_document(
    folder_id: int,
    payload: LegacyDocumentPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    filename = _safe_filename(payload.fileName)
    content_bytes = payload.content.encode("utf-8")
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Files must be 10 MB or smaller.")
    if Path(filename).suffix.lower() not in {".txt", ".md", ".csv"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Text notes must use a .txt, .md, or .csv file name.",
        )
    mime_type = _validate_file(filename, content_bytes)
    document = FolderDocument(
        folderId=folder.id,
        title=payload.title.strip(),
        fileName=filename,
        mimeType=mime_type,
        content=payload.content,
        sizeBytes=len(content_bytes),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {
        "message": "Document uploaded.",
        "document": {**_serialize_document(document), "content": document.content},
    }


@router.get("/{folder_id}/documents/{document_id}")
def download_folder_document(
    folder_id: int,
    document_id: int,
    download: bool = Query(default=False),
    inline: bool = Query(default=False),
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    document = (
        db.query(FolderDocument)
        .filter(FolderDocument.id == document_id, FolderDocument.folderId == folder.id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    if not download and not inline:
        return {
            "id": document.id,
            "title": document.title,
            "fileName": document.fileName,
            "mimeType": document.mimeType,
            "content": document.content if document.storageKey is None else None,
            "downloadName": document.fileName,
        }

    disposition = "inline" if inline and document.mimeType in INLINE_FILE_TYPES else "attachment"
    encoded_filename = quote(document.fileName, safe="")
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_filename}",
        "X-Content-Type-Options": "nosniff",
    }
    if document.storageKey:
        try:
            file_path = resolve_folder_file(document.storageKey)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from exc
        if not file_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
        return FileResponse(
            file_path,
            media_type=document.mimeType,
            headers=headers,
        )
    return Response(
        content=document.content,
        media_type=document.mimeType,
        headers=headers,
    )


@router.delete("/{folder_id}/documents/{document_id}")
def delete_folder_document(
    folder_id: int,
    document_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(require_student),
):
    folder = _get_owned_folder(db, folder_id, current_user["userId"])
    document = (
        db.query(FolderDocument)
        .filter(FolderDocument.id == document_id, FolderDocument.folderId == folder.id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    storage_key = document.storageKey
    db.delete(document)
    db.commit()
    if storage_key:
        delete_folder_file(storage_key)
    return {"message": "File deleted."}
