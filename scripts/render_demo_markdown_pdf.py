#!/usr/bin/env python3
"""Render a simple Markdown file to PDF for RH/Zotero demo artifacts.

This intentionally supports a small, predictable subset of Markdown used by
our demo scripts: headings, paragraphs, fenced code blocks, pipe tables,
horizontal rules, and an explicit ---PAGEBREAK--- marker.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = "ArialUnicode"
FALLBACK_FONT = "STSong-Light"
FONT_CANDIDATES = (
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
AVAILABLE_WIDTH = PAGE_W - 2 * MARGIN


def _register_fonts() -> None:
    global FONT
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont(FONT, candidate))
            return
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont(FALLBACK_FONT))
    FONT = FALLBACK_FONT


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCJK",
            parent=base["Title"],
            fontName=FONT,
            fontSize=20,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=10,
            wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "H1CJK",
            parent=base["Heading1"],
            fontName=FONT,
            fontSize=16,
            leading=21,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=12,
            spaceAfter=7,
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "H2CJK",
            parent=base["Heading2"],
            fontName=FONT,
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=10,
            spaceAfter=5,
            wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "H3CJK",
            parent=base["Heading3"],
            fontName=FONT,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#334155"),
            spaceBefore=8,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "BodyCJK",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.4,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "SmallCJK",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.3,
            leading=11.5,
            wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "CaptionCJK",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.2,
            leading=11,
            textColor=colors.HexColor("#475569"),
            wordWrap="CJK",
        ),
    }


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font color='#7C2D12'>\1</font>", text)
    text = text.replace("  ", "&nbsp;&nbsp;")
    return text


def _flush_paragraph(lines: list[str], story: list, styles: dict[str, ParagraphStyle]) -> None:
    if not lines:
        return
    text = " ".join(line.strip() for line in lines).strip()
    if text:
        story.append(Paragraph(_inline(text), styles["body"]))
    lines.clear()


def _render_table(table_lines: list[str], story: list, styles: dict[str, ParagraphStyle]) -> None:
    rows: list[list[str]] = []
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return
    cols = max(len(r) for r in rows)
    normalized = [r + [""] * (cols - len(r)) for r in rows]
    data = [[Paragraph(_inline(cell), styles["small"]) for cell in row] for row in normalized]
    col_widths = [AVAILABLE_WIDTH / cols] * cols
    table = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0F2FE")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 5))


def build_story(markdown: str) -> list:
    styles = _styles()
    lines = markdown.splitlines()
    story: list = []
    para: list[str] = []
    table: list[str] = []
    code: list[str] = []
    in_code = False

    def flush_table() -> None:
        nonlocal table
        if table:
            _render_table(table, story, styles)
            table = []

    for raw in lines:
        line = raw.rstrip("\n")
        if line.strip() == "```":
            flush_table()
            _flush_paragraph(para, story, styles)
            if in_code:
                story.append(Preformatted("\n".join(code), ParagraphStyle("CodeCJK", fontName=FONT, fontSize=8.2, leading=11, backColor=colors.HexColor("#F8FAFC"))))
                story.append(Spacer(1, 5))
                code = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code.append(line)
            continue

        stripped = line.strip()
        if stripped == "---PAGEBREAK---":
            flush_table()
            _flush_paragraph(para, story, styles)
            story.append(PageBreak())
            continue
        if stripped == "---":
            flush_table()
            _flush_paragraph(para, story, styles)
            story.append(Spacer(1, 8))
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            _flush_paragraph(para, story, styles)
            table.append(stripped)
            continue
        if table:
            flush_table()
        if not stripped:
            _flush_paragraph(para, story, styles)
            continue
        if stripped.startswith("# "):
            _flush_paragraph(para, story, styles)
            story.append(Paragraph(_inline(stripped[2:].strip()), styles["title"] if not story else styles["h1"]))
            continue
        if stripped.startswith("## "):
            _flush_paragraph(para, story, styles)
            story.append(Paragraph(_inline(stripped[3:].strip()), styles["h2"]))
            continue
        if stripped.startswith("### "):
            _flush_paragraph(para, story, styles)
            story.append(Paragraph(_inline(stripped[4:].strip()), styles["h3"]))
            continue
        if stripped.startswith("- [") or stripped.startswith("- "):
            _flush_paragraph(para, story, styles)
            bullet = stripped[2:].strip()
            story.append(Paragraph("• " + _inline(bullet), styles["body"]))
            continue
        if re.match(r"^\d+\.\s+", stripped):
            _flush_paragraph(para, story, styles)
            story.append(Paragraph(_inline(stripped), styles["body"]))
            continue
        para.append(stripped)

    flush_table()
    _flush_paragraph(para, story, styles)
    return story


def render(input_path: Path, output_path: Path) -> None:
    _register_fonts()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=input_path.stem,
        author="Research Harness",
    )
    story = build_story(input_path.read_text(encoding="utf-8"))
    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.input, args.output)


if __name__ == "__main__":
    main()
