from __future__ import annotations

import sys
import types
import builtins
from pathlib import Path

import pytest
from click.testing import CliRunner

from research_harness.paperindex import PaperIndexer
from research_harness.paperindex.cli import main
from research_harness.paperindex.parsing import (
    DoclingDocumentParser,
    ParsedDocument,
    PyMuPDFDocumentParser,
    resolve_document_parser,
)


def test_pymupdf_parser_preserves_pages_and_toc(sample_pdf: Path):
    parsed = PyMuPDFDocumentParser().parse(sample_pdf)

    assert parsed.parser_name == "pymupdf"
    assert parsed.page_count == 3
    assert len(parsed.pages_text) == 3
    assert parsed.toc[0] == (1, "Abstract", 1)
    assert "Sample Paper Title" in parsed.title
    assert parsed.to_raw_dict()["parser"] == "pymupdf"


def test_indexer_accepts_parser_name(sample_pdf: Path):
    result = PaperIndexer(parser="pymupdf").extract_structure(sample_pdf)

    assert result.raw["parser"] == "pymupdf"
    assert result.raw["source"] == "toc"
    assert [node.title for node in result.tree] == ["Abstract", "Method", "Experiments"]


def test_cli_parse_and_structure_accept_parser(sample_pdf: Path):
    runner = CliRunner()

    parsed = runner.invoke(
        main, ["parse", str(sample_pdf), "--parser", "pymupdf", "--format", "json"]
    )
    assert parsed.exit_code == 0
    assert '"parser": "pymupdf"' in parsed.output

    structure = runner.invoke(
        main, ["structure", str(sample_pdf), "--parser", "pymupdf", "--json-output"]
    )
    assert structure.exit_code == 0
    assert '"source": "toc"' in structure.output


def test_resolve_parser_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown document parser"):
        resolve_document_parser("not-a-parser")


def test_markdown_heading_sections_get_bounded_text(tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% fake parser object test\n")
    markdown = "\n".join(
        [
            "## Abstract",
            "Abstract body.",
            "## Method",
            "Method body.",
            "## Experiments",
            "Experiment body.",
        ]
    )

    class FakeMarkdownParser:
        parser_name = "fake-markdown"

        def parse(self, pdf_path: str | Path) -> ParsedDocument:
            return ParsedDocument(
                source_path=str(pdf_path),
                parser_name=self.parser_name,
                page_count=3,
                pages_text=(markdown,),
                markdown=markdown,
                toc=((2, "Abstract", 1), (2, "Method", 1), (2, "Experiments", 1)),
                raw={"structure_source": "markdown_headings"},
            )

    result = PaperIndexer(parser=FakeMarkdownParser()).extract_structure(pdf_path)

    assert [node.title for node in result.tree] == [
        "Abstract",
        "Method",
        "Experiments",
    ]
    assert "Abstract body." in result.tree[0].section_text
    assert "Method body." not in result.tree[0].section_text
    assert "Method body." in result.tree[1].section_text
    assert "Experiment body." not in result.tree[1].section_text


def test_docling_parser_uses_optional_python_api(monkeypatch, tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% fake for parser adapter test\n")

    class FakeDocument:
        pages = {1: object(), 2: object()}

        def export_to_markdown(self) -> str:
            return "# Fake Paper\n\n## Abstract\nDocling markdown."

        def export_to_dict(self) -> dict:
            return {
                "name": "Fake Paper",
                "pages": {
                    "1": {"text": "Abstract text"},
                    "2": {"text": "Method text"},
                },
            }

    class FakeConverter:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def convert(self, source: str):
            assert source == str(pdf_path)
            return types.SimpleNamespace(document=FakeDocument(), status="SUCCESS")

    class FakePdfPipelineOptions:
        do_ocr = True
        do_table_structure = True

    class FakePdfFormatOption:
        def __init__(self, *args, **kwargs):
            del args, kwargs

    docling_module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = FakeConverter
    converter_module.PdfFormatOption = FakePdfFormatOption
    base_models_module = types.ModuleType("docling.datamodel.base_models")
    base_models_module.InputFormat = types.SimpleNamespace(PDF="pdf")
    pipeline_options_module = types.ModuleType("docling.datamodel.pipeline_options")
    pipeline_options_module.PdfPipelineOptions = FakePdfPipelineOptions
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)
    monkeypatch.setitem(sys.modules, "docling.datamodel.base_models", base_models_module)
    monkeypatch.setitem(
        sys.modules, "docling.datamodel.pipeline_options", pipeline_options_module
    )
    monkeypatch.setattr(
        "importlib.metadata.version",
        lambda name: "2.0.0" if name == "docling" else "0",
    )

    parsed = DoclingDocumentParser().parse(pdf_path)

    assert parsed.parser_name == "docling"
    assert parsed.parser_version == "2.0.0"
    assert parsed.page_count == 2
    assert parsed.markdown.startswith("# Fake Paper")
    assert parsed.pages_text == ("Abstract text", "Method text")
    assert [item[1] for item in parsed.toc] == ["Fake Paper", "Abstract"]
    assert parsed.raw["status"] == "SUCCESS"


def test_docling_parser_has_actionable_error_when_missing(monkeypatch, tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("docling"):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match=r"research-harness\[docling\]"):
        DoclingDocumentParser().parse(pdf_path)
