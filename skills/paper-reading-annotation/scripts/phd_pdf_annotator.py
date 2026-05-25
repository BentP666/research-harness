#!/usr/bin/env python3
"""Apply PhD-level reading-guide annotations to a PDF from a JSON plan.

The tool is intentionally deterministic: an agent prepares the intellectual
annotation plan; this script only locates anchors and embeds PDF highlights.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit("PyMuPDF is required: pip install pymupdf") from exc

CATEGORY_COLORS = {
    "problem": (1.0, 0.82, 0.25),
    "motivation": (1.0, 0.73, 0.30),
    "core-claim": (1.0, 0.55, 0.20),
    "theoretical-innovation": (0.67, 0.45, 1.0),
    "application-innovation": (0.10, 0.80, 0.55),
    "concept-boundary": (0.25, 0.70, 1.0),
    "method-taxonomy": (0.35, 0.80, 1.0),
    "hidden-assumption": (1.0, 0.45, 0.45),
    "evidence": (0.20, 0.90, 0.90),
    "baseline": (0.55, 0.85, 0.35),
    "limitation-risk": (1.0, 0.35, 0.50),
    "writing-move": (0.95, 0.55, 1.0),
    "surprise": (1.0, 0.92, 0.20),
    "reusable-framing": (0.70, 0.95, 0.35),
    "rh-mapping": (0.45, 0.65, 1.0),
    "follow-up": (0.85, 0.85, 0.85),
}
DEFAULT_COLOR = (1.0, 0.85, 0.25)
MARKER = "RH-PHD-v1"


@dataclass(frozen=True)
class PlannedAnnotation:
    index: int
    anchor: str
    page: int | None
    category: str
    subject: str
    comment: str
    priority: int | None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _load_plan(path: Path) -> tuple[dict[str, Any], list[PlannedAnnotation]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items = payload.get("annotations") or []
    if not isinstance(raw_items, list):
        raise ValueError("annotation plan field 'annotations' must be a list")
    items: list[PlannedAnnotation] = []
    for idx, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"annotation #{idx} must be an object")
        anchor = _normalize_text(raw.get("anchor", ""))
        comment = _normalize_text(raw.get("comment", ""))
        if not anchor:
            raise ValueError(f"annotation #{idx} missing anchor")
        if not comment:
            raise ValueError(f"annotation #{idx} missing comment")
        page_raw = raw.get("page")
        page = int(page_raw) if page_raw not in {None, ""} else None
        priority_raw = raw.get("priority")
        priority = int(priority_raw) if priority_raw not in {None, ""} else None
        category = _normalize_text(raw.get("category", "")) or "reading-note"
        subject = _normalize_text(raw.get("subject", "")) or category
        items.append(
            PlannedAnnotation(
                index=idx,
                anchor=anchor,
                page=page,
                category=category,
                subject=subject,
                comment=comment,
                priority=priority,
            )
        )
    return payload, items


def _candidate_pages(doc: fitz.Document, page: int | None) -> list[int]:
    if page is None:
        return list(range(doc.page_count))
    idx = page - 1
    pages = []
    if 0 <= idx < doc.page_count:
        pages.append(idx)
    # Nearby-page fallback handles front-matter/TOC shifts.
    for delta in (-1, 1, -2, 2):
        near = idx + delta
        if 0 <= near < doc.page_count and near not in pages:
            pages.append(near)
    for any_idx in range(doc.page_count):
        if any_idx not in pages:
            pages.append(any_idx)
    return pages


def _anchor_variants(anchor: str) -> list[str]:
    base = _normalize_text(anchor)
    variants = [base]
    # Long anchors sometimes fail due hyphenation/line breaks; try shorter spans.
    words = base.split()
    if len(words) > 18:
        variants.append(" ".join(words[:18]))
        variants.append(" ".join(words[-18:]))
    if len(words) > 10:
        variants.append(" ".join(words[:10]))
    # Remove common PDF hyphenation artifacts.
    variants.extend([v.replace("- ", "") for v in list(variants)])
    deduped = []
    for item in variants:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _find_quads(doc: fitz.Document, item: PlannedAnnotation) -> tuple[int | None, list[Any], str]:
    for page_idx in _candidate_pages(doc, item.page):
        page = doc[page_idx]
        for variant in _anchor_variants(item.anchor):
            quads = page.search_for(variant, quads=True)
            if quads:
                return page_idx, quads, variant
    return None, [], ""


def _existing_marker_contents(doc: fitz.Document) -> set[str]:
    seen: set[str] = set()
    for page in doc:
        annot = page.first_annot
        while annot:
            info = annot.info or {}
            content = str(info.get("content") or "")
            if MARKER in content:
                seen.add(content)
            annot = annot.next
    return seen


def _annotation_content(item: PlannedAnnotation) -> str:
    priority = f" | priority={item.priority}" if item.priority is not None else ""
    return f"[{MARKER} | {item.category}{priority}] {item.comment}"


def apply_annotations(pdf_path: Path, out_path: Path, plan_path: Path) -> dict[str, Any]:
    plan_payload, items = _load_plan(plan_path)
    doc = fitz.open(str(pdf_path))
    seen = _existing_marker_contents(doc)
    applied: list[dict[str, Any]] = []
    skipped_duplicates: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for item in items:
        content = _annotation_content(item)
        if content in seen:
            skipped_duplicates.append({"index": item.index, "subject": item.subject})
            continue
        page_idx, quads, matched_anchor = _find_quads(doc, item)
        if page_idx is None or not quads:
            missing.append(
                {
                    "index": item.index,
                    "subject": item.subject,
                    "category": item.category,
                    "anchor": item.anchor,
                    "page": item.page,
                }
            )
            continue
        page = doc[page_idx]
        annot = page.add_highlight_annot(quads)
        annot.set_colors(stroke=CATEGORY_COLORS.get(item.category, DEFAULT_COLOR))
        annot.set_info(
            title="Research Harness",
            subject=f"{item.subject} · {item.category}",
            content=content,
        )
        annot.update()
        seen.add(content)
        applied.append(
            {
                "index": item.index,
                "page": page_idx + 1,
                "subject": item.subject,
                "category": item.category,
                "matched_anchor": matched_anchor,
            }
        )

    if out_path == pdf_path:
        tmp = out_path.with_suffix(out_path.suffix + ".tmp-rh-annotated")
        doc.save(str(tmp), garbage=4, deflate=True)
        doc.close()
        tmp.replace(out_path)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_path), garbage=4, deflate=True)
        doc.close()

    return {
        "status": "success",
        "profile": plan_payload.get("profile") or "phd-quick-grasp-v1",
        "paper_id": plan_payload.get("paper_id"),
        "title": plan_payload.get("title") or "",
        "pdf_path": str(pdf_path),
        "output_path": str(out_path),
        "plan_path": str(plan_path),
        "planned_count": len(items),
        "applied_count": len(applied),
        "duplicate_count": len(skipped_duplicates),
        "missing_count": len(missing),
        "applied": applied,
        "duplicates": skipped_duplicates,
        "missing": missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument("--spec", required=True, help="Annotation plan JSON path")
    parser.add_argument("--out", default="", help="Output PDF path; defaults to input when --in-place")
    parser.add_argument("--in-place", action="store_true", help="Modify PDF in place")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup for --in-place")
    parser.add_argument("--json", action="store_true", help="Print machine-readable receipt")
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf).expanduser().resolve()
    plan_path = Path(args.spec).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    if not plan_path.exists():
        raise SystemExit(f"annotation plan not found: {plan_path}")
    if args.in_place:
        out_path = pdf_path
        if not args.no_backup:
            suffix = datetime.now().strftime("%Y%m%d%H%M%S")
            backup = pdf_path.with_name(pdf_path.name + f".bak-rh-phd-annotations-{suffix}")
            shutil.copy2(pdf_path, backup)
        else:
            backup = None
    else:
        if not args.out:
            raise SystemExit("Provide --out unless using --in-place")
        out_path = Path(args.out).expanduser().resolve()
        backup = None

    receipt = apply_annotations(pdf_path, out_path, plan_path)
    if backup is not None:
        receipt["backup_path"] = str(backup)
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(
            f"Applied {receipt['applied_count']}/{receipt['planned_count']} annotations "
            f"to {receipt['output_path']}"
        )
        if receipt["missing_count"]:
            print(f"Missing anchors: {receipt['missing_count']}", file=sys.stderr)
    return 0 if receipt["missing_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
