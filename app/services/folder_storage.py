import os
import uuid
from pathlib import Path

from config import settings


def save_folder_file(content: bytes) -> str:
    storage_key = f"{uuid.uuid4().hex}.upload"
    root = settings.FOLDER_STORAGE_DIR
    root.mkdir(parents=True, exist_ok=True)
    destination = root / storage_key
    temporary = root / f".{storage_key}.tmp"
    try:
        with temporary.open("xb") as stored_file:
            stored_file.write(content)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return storage_key


def resolve_folder_file(storage_key: str) -> Path:
    if not storage_key or Path(storage_key).name != storage_key:
        raise ValueError("Invalid folder file storage key.")
    root = settings.FOLDER_STORAGE_DIR.resolve()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise ValueError("Invalid folder file storage key.")
    return path


def delete_folder_file(storage_key: str) -> None:
    resolve_folder_file(storage_key).unlink(missing_ok=True)
