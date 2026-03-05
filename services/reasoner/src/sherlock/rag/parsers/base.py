"""Parser base types."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from sherlock.rag.domain.models import ParsedDocument


class UnsupportedFileTypeError(ValueError):
    """Raised when the file extension has no registered parser."""


@runtime_checkable
class ParserPort(Protocol):
    def parse(self, data: bytes) -> ParsedDocument: ...
