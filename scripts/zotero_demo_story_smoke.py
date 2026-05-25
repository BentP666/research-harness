#!/usr/bin/env python3
"""Smoke-test the Xiaohongshu RH Zotero demo storyline.

This does not require a running Zotero UI. It validates the local RH API
contract that the video relies on: context-aware collection mode, generic
collection-import action previews, and PDF attach action previews.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from research_harness.storage.db import Database
from research_harness_mcp import http_api


def seed_demo_db(db_path: Path, pdf_path: Path) -> None:
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO topics (name, description) VALUES ('AI程序员能修Bug吗', '')")
        conn.execute(
            """
            INSERT INTO papers
                (title, authors, year, venue, doi, arxiv_id, url, abstract, status, deep_read, pdf_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Understanding Software Engineering Agents",
                json.dumps(["Ada Lovelace"]),
                2026,
                "ICLR",
                "10.1234/se-agents",
                "2501.12345",
                "https://arxiv.org/abs/2501.12345",
                "A paper for a cinematic CCF-A hot-topic RH Zotero demo.",
                "pdf_ready",
                1,
                str(pdf_path),
            ),
        )
        conn.execute(
            "INSERT INTO paper_topics (paper_id, topic_id, relevance) VALUES (1, 1, 'high')"
        )
        conn.commit()
    finally:
        conn.close()


def post_stream(client: TestClient, payload: dict) -> str:
    response = client.post("/api/zotero/chat/stream", json=payload)
    if response.status_code != 200:
        raise AssertionError(f"HTTP {response.status_code}: {response.text}")
    return response.text


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}\n--- response ---\n{text}")


def main() -> None:
    original_db_path = http_api.DB_PATH
    original_pdf_roots = list(http_api.PDF_ROOTS)
    original_stream = http_api._stream_zotero_codex_turn

    def fail_if_codex_runs(**_: object):
        raise AssertionError("Demo smoke should be satisfied by RH action routing, not Codex streaming")

    with tempfile.TemporaryDirectory(prefix="rh-zotero-demo-") as tmp:
        root = Path(tmp)
        pdf_dir = root / "pdfs"
        pdf_dir.mkdir()
        pdf_path = pdf_dir / "understanding-software-engineering-agents.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n% RH Zotero demo smoke PDF\n")
        db_path = root / "pool.db"
        seed_demo_db(db_path, pdf_path)

        http_api.DB_PATH = db_path
        http_api.PDF_ROOTS = [pdf_dir.resolve()]
        http_api._stream_zotero_codex_turn = fail_if_codex_runs
        client = TestClient(http_api.app)

        try:
            collection_text = post_stream(
                client,
                {
                    "message": "这个目录可以怎么推进？",
                    "item": {
                        "library_id": 1,
                        "current_directory_key": "CURRDIR1",
                        "current_directory_name": "自动科研",
                        "current_directory_path": "Research Harness / AI程序员能修Bug吗",
                    },
                },
            )
            require(collection_text, '"kind":"collection"', "collection context")
            require(collection_text, "init_topic_from_collection", "init-topic action")
            require(collection_text, "sync_rh_missing_papers_to_collection", "missing-paper action")
            print("PASS 1/3 collection mode exposes init/recommend actions")

            import_text = post_stream(
                client,
                {
                    "message": "把这个主题里精读过的 1 篇论文导入当前目录",
                    "item": {
                        "zotero_item_key": "ABCD1234",
                        "library_id": 1,
                        "title": "Understanding Software Engineering Agents",
                        "tags": ["rh-paper-id:1", "rh-topic:自动科研", "rh-deep-read"],
                        "current_directory_key": "CURRDIR1",
                        "current_directory_name": "自动科研",
                        "current_directory_path": "Research Harness / AI程序员能修Bug吗",
                    },
                },
            )
            require(import_text, "event: action_preview", "import action preview event")
            require(import_text, '"action_type":"sync_rh_papers_to_collection"', "generic import action type")
            require(import_text, '"type":"http_json"', "HTTP apply spec")
            require(import_text, '"label":"确认导入"', "confirm label")
            print("PASS 2/3 import request returns generic action preview")

            pdf_text = post_stream(
                client,
                {
                    "message": "下载并附加 PDF 到当前条目，先 dry-run，确认后 apply",
                    "item": {
                        "zotero_item_key": "ABCD1234",
                        "library_id": 1,
                        "title": "Understanding Software Engineering Agents",
                        "arxiv_id": "2501.12345",
                        "tags": ["rh-paper-id:1", "rh-topic:自动科研"],
                    },
                },
            )
            require(pdf_text, "event: action_preview", "PDF action preview event")
            require(pdf_text, '"action_type":"zotero_attach_pdf"', "PDF action type")
            require(pdf_text, '"handler":"zotero_import_file_attachment"', "local Zotero handler")
            require(pdf_text, f'"pdf_path":"{pdf_path.resolve()}"', "validated PDF path")
            require(pdf_text, '"parent_item_key":"ABCD1234"', "target Zotero item key")
            print("PASS 3/3 PDF request returns local Zotero attachment action preview")
        finally:
            http_api.DB_PATH = original_db_path
            http_api.PDF_ROOTS = original_pdf_roots
            http_api._stream_zotero_codex_turn = original_stream

    print("\nDemo storyline API contract is ready for recording.")


if __name__ == "__main__":
    main()
