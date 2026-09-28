"""
Document text extraction service.
Supports PDF (via pypdf), DOCX (via python-docx), and plain TXT files.
"""

import os
from pathlib import Path

from pypdf import PdfReader
from docx import Document


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 25


def validate_upload(filename: str, file_size: int) -> tuple[bool, str]:
    """Validate file extension and size. Returns (is_valid, error_message)."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return False, f"File exceeds maximum size of {MAX_FILE_SIZE_MB} MB"
    return True, ""


def extract_text(file_path: str) -> str:
    """
    Extract text from a document file.
    Dispatches to the correct extractor based on file extension.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext == ".txt":
        return _extract_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pypdf."""
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    doc = Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_txt(file_path: str) -> str:
    """Read a plain text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
