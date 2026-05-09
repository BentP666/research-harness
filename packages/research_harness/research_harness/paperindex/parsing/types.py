from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ParsedDocument:
    """Normalized parser output for downstream paper indexing.

    The existing paperindex pipeline needs page text and an optional PDF table
    of contents. Rich parsers can additionally provide Markdown and raw
    structured data without forcing the rest of the pipeline to depend on a
    specific vendor library.
    """

    source_path: str
    parser_name: str
    parser_version: str = ""
    page_count: int = 0
    title: str = ""
    pages_text: tuple[str, ...] = ()
    markdown: str = ""
    toc: tuple[tuple[int, str, int], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_raw_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable provenance payload."""

        payload = {
            **self.raw,
            "parser": self.parser_name,
            "parser_version": self.parser_version,
            "page_count": self.page_count,
            "title": self.title,
            "pages_text": list(self.pages_text),
            "toc": [[level, title, page] for level, title, page in self.toc],
            "warnings": list(self.warnings),
        }
        if self.markdown:
            payload["markdown"] = self.markdown
        return payload


@runtime_checkable
class DocumentParser(Protocol):
    parser_name: str

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        """Parse a local PDF into a normalized document representation."""
