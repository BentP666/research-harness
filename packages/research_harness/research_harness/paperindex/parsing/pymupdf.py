from __future__ import annotations

from importlib import metadata
from pathlib import Path

import fitz

from ..utils import first_nonempty_line
from .types import ParsedDocument


class PyMuPDFDocumentParser:
    """Lightweight local parser that preserves RH's current PDF behavior."""

    parser_name = "pymupdf"

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(path)

        doc = fitz.open(path)
        try:
            pages_text = tuple(page.get_text("text") or "" for page in doc)
            toc = tuple(
                (int(level), str(title).strip(), int(page or 1))
                for level, title, page in doc.get_toc(simple=True)
            )
            title = first_nonempty_line(pages_text[0]) if pages_text else path.stem
            return ParsedDocument(
                source_path=str(path),
                parser_name=self.parser_name,
                parser_version=_package_version("PyMuPDF"),
                page_count=doc.page_count,
                title=title or path.stem,
                pages_text=pages_text,
                toc=toc,
            )
        finally:
            doc.close()


def _package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return ""
