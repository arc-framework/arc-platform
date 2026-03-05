"""Parser for JSON files."""
from __future__ import annotations

import json

from reasoner.rag.domain.models import ParsedDocument


class JsonParser:
    def parse(self, data: bytes) -> ParsedDocument:
        obj = json.loads(data.decode("utf-8"))
        text = json.dumps(obj, indent=2, ensure_ascii=False)
        return ParsedDocument(text=text, metadata={"type": "json"})
