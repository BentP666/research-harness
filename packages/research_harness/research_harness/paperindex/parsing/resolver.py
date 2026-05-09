from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .docling import DoclingDocumentParser
from .pymupdf import PyMuPDFDocumentParser
from .types import DocumentParser, ParsedDocument


ParserInput = str | DocumentParser | None


def resolve_document_parser(parser: ParserInput = None) -> DocumentParser:
    """Resolve a parser name or parser object to a DocumentParser instance."""

    if parser is None:
        parser = os.getenv("PAPERINDEX_PARSER", "pymupdf")

    if isinstance(parser, str):
        normalized = parser.strip().lower().replace("-", "_")
        if normalized in {"", "pymupdf", "fitz"}:
            return PyMuPDFDocumentParser()
        if normalized == "docling":
            return DoclingDocumentParser()
        raise ValueError(
            "Unknown document parser "
            f"'{parser}'. Expected one of: pymupdf, docling."
        )

    if isinstance(parser, DocumentParser):
        return parser

    if hasattr(parser, "parse") and callable(getattr(parser, "parse")):
        return _ParserAdapter(parser)

    raise TypeError("parser must be None, a parser name, or an object with parse()")


class _ParserAdapter:
    def __init__(self, parser: Any):
        self._parser = parser
        self.parser_name = str(getattr(parser, "parser_name", parser.__class__.__name__))

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        return self._parser.parse(pdf_path)
