from __future__ import annotations

from importlib import metadata
from pathlib import Path
import re
from typing import Any

from ..utils import first_nonempty_line
from .types import ParsedDocument


class DoclingDocumentParser:
    """Optional Docling backend for rich PDF-to-Markdown parsing.

    Docling remains an optional dependency so the default RH install stays
    lightweight. Install it with: pip install 'research-harness[docling]'.
    """

    parser_name = "docling"

    def __init__(
        self,
        *,
        do_ocr: bool = False,
        do_table_structure: bool = True,
    ):
        # RH normally ingests born-digital academic PDFs. Keep OCR disabled by
        # default so a first local smoke test does not unexpectedly download OCR
        # models; scanned PDFs can opt into OCR through a later parser profile.
        self._do_ocr = do_ocr
        self._do_table_structure = do_table_structure

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(path)

        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise RuntimeError(
                "Docling parser requires optional dependency `docling`; install it with "
                "`pip install 'research-harness[docling]'` or choose parser='pymupdf'."
            ) from exc

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self._do_ocr
        pipeline_options.do_table_structure = self._do_table_structure
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        try:
            result = converter.convert(str(path))
        except Exception as exc:
            raise RuntimeError(
                "Docling conversion failed. If this is the first run and the "
                "error mentions model download/OCR, retry with network access or "
                "use parser='pymupdf' for the lightweight fallback."
            ) from exc
        document = result.document
        markdown = _safe_export_markdown(document)
        exported = _safe_export_dict(document)
        pages_text = _extract_pages_text(exported, markdown)
        page_count = _infer_page_count(document, exported, pages_text)
        title = _infer_title(exported, markdown, path)
        toc = _extract_markdown_toc(markdown)

        return ParsedDocument(
            source_path=str(path),
            parser_name=self.parser_name,
            parser_version=_package_version("docling"),
            page_count=page_count,
            title=title,
            pages_text=pages_text,
            markdown=markdown,
            toc=toc,
            raw={
                "status": str(getattr(result, "status", "")),
                "docling_keys": sorted(str(key) for key in exported.keys()),
                "structure_source": "markdown_headings" if toc else "",
            },
        )


def _safe_export_markdown(document: Any) -> str:
    export = getattr(document, "export_to_markdown", None)
    if not callable(export):
        return ""
    return str(export() or "")


def _safe_export_dict(document: Any) -> dict[str, Any]:
    export = getattr(document, "export_to_dict", None)
    if not callable(export):
        return {}
    payload = export() or {}
    return payload if isinstance(payload, dict) else {}


def _extract_pages_text(exported: dict[str, Any], markdown: str) -> tuple[str, ...]:
    pages = exported.get("pages")
    if isinstance(pages, dict):
        page_items = sorted(pages.items(), key=lambda item: _page_sort_key(item[0]))
        page_texts = tuple(
            text for _, page in page_items if (text := _collect_text(page).strip())
        )
        if page_texts:
            return page_texts
    if isinstance(pages, list):
        page_texts = tuple(text for page in pages if (text := _collect_text(page).strip()))
        if page_texts:
            return page_texts
    return (markdown,) if markdown else ()


def _collect_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        direct_text = value.get("text")
        if isinstance(direct_text, str):
            return direct_text
        return "\n".join(_collect_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_collect_text(item) for item in value)
    return ""


def _infer_page_count(
    document: Any, exported: dict[str, Any], pages_text: tuple[str, ...]
) -> int:
    pages = getattr(document, "pages", None)
    try:
        return max(1, len(list(pages)))
    except TypeError:
        pass
    except Exception:
        pass

    exported_pages = exported.get("pages")
    if isinstance(exported_pages, (dict, list)):
        return max(1, len(exported_pages))
    return max(1, len(pages_text))


def _infer_title(exported: dict[str, Any], markdown: str, path: Path) -> str:
    for key in ("title", "name", "filename"):
        value = exported.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return first_nonempty_line(markdown) or path.stem


def _extract_markdown_toc(markdown: str) -> tuple[tuple[int, str, int], ...]:
    headings: list[tuple[int, str, int]] = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if not match:
            continue
        title = re.sub(r"\s+", " ", match.group(2)).strip()
        title = re.sub(r"<!--.*?-->", "", title).strip()
        if not title:
            continue
        # Docling markdown does not currently expose reliable heading page
        # numbers through our normalized adapter. Use page 1 as a safe lower
        # bound; downstream can still use the heading tree without an LLM.
        headings.append((len(match.group(1)), title, 1))
    return tuple(headings)


def _page_sort_key(value: Any) -> tuple[int, str]:
    try:
        return (int(value), str(value))
    except (TypeError, ValueError):
        return (10**9, str(value))


def _package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return ""
