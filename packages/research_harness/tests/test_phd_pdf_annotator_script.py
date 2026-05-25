from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import fitz


SCRIPT = Path("skills/paper-reading-annotation/scripts/phd_pdf_annotator.py")


def test_phd_pdf_annotator_applies_highlights_from_spec(tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This paper defines a new research problem for agents.")
    page.insert_text((72, 110), "Theoretical innovation is a reusable taxonomy.")
    doc.save(pdf_path)
    doc.close()

    spec_path = tmp_path / "plan.json"
    spec_path.write_text(
        json.dumps(
            {
                "paper_id": 1,
                "title": "Demo Paper",
                "profile": "phd-quick-grasp-v1",
                "annotations": [
                    {
                        "anchor": "defines a new research problem",
                        "page": 1,
                        "category": "problem",
                        "subject": "问题定义",
                        "comment": "【问题定义】这里定义论文要解决的问题。",
                        "priority": 5,
                    },
                    {
                        "anchor": "reusable taxonomy",
                        "page": 1,
                        "category": "theoretical-innovation",
                        "subject": "理论创新",
                        "comment": "【理论创新】这里说明可复用 taxonomy。",
                        "priority": 5,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out_path = tmp_path / "annotated.pdf"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pdf",
            str(pdf_path),
            "--spec",
            str(spec_path),
            "--out",
            str(out_path),
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    receipt = json.loads(result.stdout)
    assert receipt["applied_count"] == 2
    assert receipt["missing_count"] == 0

    annotated = fitz.open(out_path)
    annotations = []
    for page in annotated:
        annot = page.first_annot
        while annot:
            annotations.append(annot.info)
            annot = annot.next
    annotated.close()

    assert len(annotations) == 2
    assert any("RH-PHD-v1" in (info.get("content") or "") for info in annotations)
    assert {info.get("subject") for info in annotations} == {
        "问题定义 · problem",
        "理论创新 · theoretical-innovation",
    }
