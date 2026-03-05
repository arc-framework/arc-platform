"""RAG file parsers — dispatch by extension."""
from __future__ import annotations

import os

from sherlock.rag.domain.models import ParsedDocument
from sherlock.rag.parsers.base import UnsupportedFileTypeError
from sherlock.rag.parsers.csv_parser import CsvParser
from sherlock.rag.parsers.docx_parser import DocxParser
from sherlock.rag.parsers.json_parser import JsonParser
from sherlock.rag.parsers.pdf_parser import PdfParser
from sherlock.rag.parsers.text_parser import TextParser

_TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".py", ".go", ".ts", ".js", ".tsx", ".jsx"}

_PARSER_MAP: dict[str, CsvParser | DocxParser | JsonParser | PdfParser | TextParser] = {
    ".pdf": PdfParser(),
    ".docx": DocxParser(),
    ".json": JsonParser(),
    ".csv": CsvParser(),
}

for _ext in _TEXT_EXTENSIONS:
    _PARSER_MAP[_ext] = TextParser()


def dispatch_parser(filename: str, data: bytes) -> ParsedDocument:
    """Route to the correct parser based on file extension."""
    _, ext = os.path.splitext(filename.lower())
    parser = _PARSER_MAP.get(ext)
    if parser is None:
        raise UnsupportedFileTypeError(f"Unsupported file type: {ext!r}")
    return parser.parse(data)


__all__ = [
    "dispatch_parser",
    "UnsupportedFileTypeError",
    "ParsedDocument",
    "CsvParser",
    "DocxParser",
    "JsonParser",
    "PdfParser",
    "TextParser",
]
