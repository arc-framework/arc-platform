"""Parser for CSV files."""
from __future__ import annotations

from reasoner.rag.domain.models import ParsedDocument


class CsvParser:
    def parse(self, data: bytes) -> ParsedDocument:
        text = data.decode("utf-8")
        return ParsedDocument(text=text, metadata={"type": "csv"})
