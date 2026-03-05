"""Unit tests for reasoner.rag.parsers.*"""
from __future__ import annotations

import csv
import io
import json

import pytest

from reasoner.rag.parsers import (
    CsvParser,
    JsonParser,
    TextParser,
    UnsupportedFileTypeError,
    dispatch_parser,
)
from reasoner.rag.parsers.base import ParserPort


# ─── TextParser ───────────────────────────────────────────────────────────────


class TestTextParser:
    def test_parse_utf8_bytes(self) -> None:
        data = b"Hello, world!"
        doc = TextParser().parse(data)
        assert doc.text == "Hello, world!"

    def test_metadata_type_is_text(self) -> None:
        doc = TextParser().parse(b"x")
        assert doc.metadata["type"] == "text"

    def test_parse_multiline(self) -> None:
        lines = "line1\nline2\nline3"
        doc = TextParser().parse(lines.encode())
        assert doc.text == lines

    def test_parse_unicode(self) -> None:
        text = "Ünïcödé chäracters: 日本語"
        doc = TextParser().parse(text.encode("utf-8"))
        assert doc.text == text

    def test_empty_bytes_gives_empty_text(self) -> None:
        doc = TextParser().parse(b"")
        assert doc.text == ""


# ─── CsvParser ────────────────────────────────────────────────────────────────


class TestCsvParser:
    def _make_csv(self, rows: list[list[str]]) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def test_parse_returns_csv_text(self) -> None:
        data = self._make_csv([["name", "age"], ["alice", "30"]])
        doc = CsvParser().parse(data)
        assert "name" in doc.text
        assert "alice" in doc.text

    def test_metadata_type_is_csv(self) -> None:
        doc = CsvParser().parse(b"a,b\n1,2\n")
        assert doc.metadata["type"] == "csv"

    def test_parse_empty_csv(self) -> None:
        doc = CsvParser().parse(b"")
        assert doc.text == ""


# ─── JsonParser ───────────────────────────────────────────────────────────────


class TestJsonParser:
    def test_parse_dict(self) -> None:
        data = json.dumps({"key": "value"}).encode()
        doc = JsonParser().parse(data)
        parsed = json.loads(doc.text)
        assert parsed["key"] == "value"

    def test_parse_list(self) -> None:
        data = json.dumps([1, 2, 3]).encode()
        doc = JsonParser().parse(data)
        parsed = json.loads(doc.text)
        assert parsed == [1, 2, 3]

    def test_metadata_type_is_json(self) -> None:
        doc = JsonParser().parse(b'{"x": 1}')
        assert doc.metadata["type"] == "json"

    def test_output_is_indented(self) -> None:
        data = b'{"a":1}'
        doc = JsonParser().parse(data)
        assert "\n" in doc.text

    def test_unicode_preserved(self) -> None:
        obj = {"greeting": "こんにちは"}
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        doc = JsonParser().parse(data)
        assert "こんにちは" in doc.text


# ─── PdfParser ────────────────────────────────────────────────────────────────


class TestPdfParser:
    def test_parse_real_pdf(self) -> None:
        """Create a minimal valid PDF and verify the parser handles it."""
        import pypdf

        buf = io.BytesIO()
        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        from reasoner.rag.parsers.pdf_parser import PdfParser

        doc = PdfParser().parse(pdf_bytes)
        assert doc.metadata["type"] == "pdf"
        # Blank page gives empty text — that's fine.
        assert isinstance(doc.text, str)

    def test_metadata_type_is_pdf(self) -> None:
        import pypdf

        buf = io.BytesIO()
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(buf)

        from reasoner.rag.parsers.pdf_parser import PdfParser

        doc = PdfParser().parse(buf.getvalue())
        assert doc.metadata["type"] == "pdf"


# ─── DocxParser ───────────────────────────────────────────────────────────────


class TestDocxParser:
    def _make_docx(self, paragraphs: list[str]) -> bytes:
        import docx

        document = docx.Document()
        for p in paragraphs:
            document.add_paragraph(p)
        buf = io.BytesIO()
        document.save(buf)
        return buf.getvalue()

    def test_parse_single_paragraph(self) -> None:
        from reasoner.rag.parsers.docx_parser import DocxParser

        data = self._make_docx(["Hello from docx"])
        doc = DocxParser().parse(data)
        assert "Hello from docx" in doc.text

    def test_parse_multiple_paragraphs(self) -> None:
        from reasoner.rag.parsers.docx_parser import DocxParser

        data = self._make_docx(["First paragraph", "Second paragraph"])
        doc = DocxParser().parse(data)
        assert "First paragraph" in doc.text
        assert "Second paragraph" in doc.text

    def test_metadata_type_is_docx(self) -> None:
        from reasoner.rag.parsers.docx_parser import DocxParser

        data = self._make_docx(["test"])
        doc = DocxParser().parse(data)
        assert doc.metadata["type"] == "docx"


# ─── dispatch_parser ──────────────────────────────────────────────────────────


class TestDispatchParser:
    @pytest.mark.parametrize(
        "filename",
        [
            "notes.txt",
            "readme.md",
            "script.py",
            "module.go",
            "app.ts",
            "component.tsx",
            "index.js",
            "page.jsx",
            "docs.rst",
        ],
    )
    def test_text_extensions_dispatch_to_text_parser(self, filename: str) -> None:
        doc = dispatch_parser(filename, b"some content")
        assert doc.metadata["type"] == "text"

    def test_csv_dispatch(self) -> None:
        doc = dispatch_parser("data.csv", b"col1,col2\n1,2\n")
        assert doc.metadata["type"] == "csv"

    def test_json_dispatch(self) -> None:
        doc = dispatch_parser("config.json", b'{"k": "v"}')
        assert doc.metadata["type"] == "json"

    def test_case_insensitive_extension(self) -> None:
        doc = dispatch_parser("DATA.CSV", b"a,b\n1,2\n")
        assert doc.metadata["type"] == "csv"

    def test_unsupported_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            dispatch_parser("archive.zip", b"data")

    def test_no_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            dispatch_parser("Makefile", b"all:\n\techo hi")

    @pytest.mark.parametrize(
        "ext",
        [".xyz", ".exe", ".bin", ".tar"],
    )
    def test_various_unsupported_extensions(self, ext: str) -> None:
        with pytest.raises(UnsupportedFileTypeError, match="Unsupported file type"):
            dispatch_parser(f"file{ext}", b"data")

    def test_unsupported_error_is_value_error_subclass(self) -> None:
        with pytest.raises(ValueError):
            dispatch_parser("bad.unknown", b"x")


# ─── UnsupportedFileTypeError ─────────────────────────────────────────────────


class TestUnsupportedFileTypeError:
    def test_is_value_error(self) -> None:
        err = UnsupportedFileTypeError("bad ext")
        assert isinstance(err, ValueError)

    def test_message_preserved(self) -> None:
        err = UnsupportedFileTypeError("Unsupported file type: '.xyz'")
        assert ".xyz" in str(err)


# ─── ParserPort protocol ──────────────────────────────────────────────────────


class TestParserPort:
    def test_text_parser_satisfies_protocol(self) -> None:
        assert isinstance(TextParser(), ParserPort)

    def test_csv_parser_satisfies_protocol(self) -> None:
        assert isinstance(CsvParser(), ParserPort)

    def test_json_parser_satisfies_protocol(self) -> None:
        assert isinstance(JsonParser(), ParserPort)
