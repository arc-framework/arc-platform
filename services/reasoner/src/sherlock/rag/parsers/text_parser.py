"""Parser for plain-text file formats."""
from __future__ import annotations

from sherlock.rag.domain.models import ParsedDocument


class TextParser:
    def parse(self, data: bytes) -> ParsedDocument:
        text = data.decode("utf-8")
        return ParsedDocument(text=text, metadata={"type": "text"})
