"""RAG file parsers — dispatch by extension."""
from __future__ import annotations

import os

from reasoner.rag.domain.models import ParsedDocument
from reasoner.rag.parsers.base import UnsupportedFileTypeError
from reasoner.rag.parsers.csv_parser import CsvParser
from reasoner.rag.parsers.docx_parser import DocxParser
from reasoner.rag.parsers.json_parser import JsonParser
from reasoner.rag.parsers.pdf_parser import PdfParser
from reasoner.rag.parsers.text_parser import TextParser

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
