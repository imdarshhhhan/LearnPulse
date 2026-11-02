import json
from io import BytesIO
from pathlib import Path
from typing import Any

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_CHARS = 60_000
MIN_SOURCE_CHARS = 30


class DocumentValidationError(ValueError):
    pass


def extract_upload_pages_and_text(filename: str, content: bytes) -> tuple[str, list[dict]]:
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".json"}:
        raise DocumentValidationError("Only PDF and JSON files are supported.")
    if not content:
        raise DocumentValidationError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentValidationError("The uploaded file exceeds the 10 MB limit.")

    pages_data: list[dict] = []
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentValidationError("The uploaded file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise DocumentValidationError("Password-protected PDFs are not supported.")
            char_cursor = 0
            page_texts = []
            for page_idx, page in enumerate(reader.pages, start=1):
                raw_text = page.extract_text() or ""
                clean_text = " ".join(raw_text.split())
                page_texts.append(clean_text)
                start_offset = char_cursor
                char_cursor += len(clean_text) + 1
                pages_data.append({
                    "pageNumber": page_idx,
                    "text": clean_text,
                    "charStart": start_offset,
                    "charEnd": char_cursor - 1,
                })
            full_text = "\n".join(page_texts)
        except DocumentValidationError:
            raise
        except (PdfReadError, ValueError, OSError) as exc:
            raise DocumentValidationError("The uploaded PDF could not be read.") from exc
    else:
        try:
            decoded = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise DocumentValidationError("The uploaded JSON file is invalid.") from exc
        raw_items = _json_text_values(decoded)
        full_text = "\n".join(raw_items)
        # Partition JSON sections as logical pages/sections
        cursor = 0
        for sec_idx, item in enumerate(raw_items, start=1):
            clean_item = " ".join(item.split())
            if not clean_item:
                continue
            pages_data.append({
                "pageNumber": sec_idx,
                "text": clean_item,
                "charStart": cursor,
                "charEnd": cursor + len(clean_item),
            })
            cursor += len(clean_item) + 1

    normalized = " ".join(full_text.split())
    if len(normalized) < MIN_SOURCE_CHARS:
        raise DocumentValidationError(
            "The file does not contain enough readable text to generate a quiz."
        )
    return normalized[:MAX_SOURCE_CHARS], pages_data


def extract_upload_text(filename: str, content: bytes) -> str:
    text, _ = extract_upload_pages_and_text(filename, content)
    return text


def _json_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.extend(_json_text_values(item))
        return parts
    if isinstance(value, list):
        return [part for item in value for part in _json_text_values(item)]
    return []
