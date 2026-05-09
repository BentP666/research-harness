"""Anchor corpus loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Anchor:
    stage: str
    tier: str
    label: str  # "accept" | "reject"
    dimension_scores: dict[str, float]
    paper_title: str = ""
    venue: str = ""
    year: int = 0
    note: str = ""


_DEFAULT_PATH = Path(__file__).with_name("anchors.jsonl")


def load_anchors(path: Path | None = None) -> list[Anchor]:
    src = path or _DEFAULT_PATH
    if not src.exists():
        return []
    anchors: list[Anchor] = []
    with src.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            row = json.loads(line)
            label = row.get("label")
            if label not in {"accept", "reject"}:
                continue
            anchors.append(
                Anchor(
                    stage=row["stage"],
                    tier=row.get("tier", "standard"),
                    label=label,
                    dimension_scores=dict(row.get("dimension_scores", {})),
                    paper_title=row.get("paper_title", ""),
                    venue=row.get("venue", ""),
                    year=int(row.get("year", 0) or 0),
                    note=row.get("note", ""),
                )
            )
    return anchors
