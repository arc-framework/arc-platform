"""Parser for PDF files using pypdf."""
from __future__ import annotations

import io

import pypdf

from reasoner.rag.domain.models import ParsedDocument


class PdfParser:
    def parse(self, data: bytes) -> ParsedDocument:
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return ParsedDocument(text=text, metadata={"type": "pdf"})
