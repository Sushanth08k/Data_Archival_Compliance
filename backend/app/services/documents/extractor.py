"""
Document text extraction service.
Supports PDF (via pypdf), DOCX (via python-docx), plain TXT, and Markdown (MD) files.
"""

import os
import re
from pathlib import Path

from pypdf import PdfReader
from docx import Document


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE_MB = 25


def validate_upload(filename: str, file_size: int) -> tuple[bool, str]:
    """Validate file extension and size. Returns (is_valid, error_message)."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Only PDF, DOCX, TXT, MD files are accepted"
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
    elif ext == ".md":
        return _extract_md(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pypdf layout mode with whitespace normalization."""
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        # Layout mode accurately detects word spacing from glyph positions
        text = ""
        try:
            text = page.extract_text(extraction_mode="layout")
        except Exception:
            pass

        # Fallback to default extraction if layout mode failed or returned nothing
        if not text or not text.strip():
            try:
                text = page.extract_text()
            except Exception:
                text = ""

        if not text:
            continue

        # Normalize layout text: collapse multiple horizontal spaces/tabs, ensure spacing around colons
        cleaned_lines = []
        for line in text.splitlines():
            cleaned = re.sub(r"[ \t]+", " ", line).strip()
            # Ensure space after colons in key-value patterns (e.g. "field:value" -> "field: value")
            cleaned = re.sub(r"([a-zA-Z0-9_]):([a-zA-Z0-9_])", r"\1: \2", cleaned)
            cleaned_lines.append(cleaned)

        page_str = "\n".join(cleaned_lines).strip()
        if page_str:
            pages.append(page_str)

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


def _extract_md(file_path: str) -> str:
    """Extract and normalize text from a Markdown (.md) file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Clean markdown formatting so rule extractors can parse it cleanly
    lines = []
    for line in content.splitlines():
        # Remove markdown heading hashes: e.g. "## POLICY 1:" -> "POLICY 1:"
        cleaned = re.sub(r"^#{1,6}\s+", "", line)
        # Remove bold/italic markers: "**Rule 1:**" -> "Rule 1:", "__text__" -> "text"
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
        cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
        # Normalize list bullet markers at start of line
        cleaned = re.sub(r"^[\s*+-]+\s+", "", cleaned)
        # Convert markdown horizontal dividers (---, ***, ___) to policy divider line
        if re.match(r"^[-*_]{3,}\s*$", cleaned):
            cleaned = "=" * 60
        lines.append(cleaned.strip())

    return "\n".join(lines)
