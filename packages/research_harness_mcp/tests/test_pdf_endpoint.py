"""Tests for GET /api/papers/{id}/pdf — path traversal guard + edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "pdf.db"
    from research_harness.storage.db import Database

    Database(db_path).migrate()

    # Build a sandbox PDF tree we'll trust, plus an evil file outside it.
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    good_pdf = safe_root / "ok.pdf"
    good_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    evil_root = tmp_path / "evil"
    evil_root.mkdir()
    evil_pdf = evil_root / "secret.pdf"
    evil_pdf.write_bytes(b"%PDF-1.4\n%nope\n")

    # Seed the papers table with three rows: good, evil, missing.
    conn = Database(db_path).connect()
    try:
        for pid, path in [
            (1, str(good_pdf)),
            (2, str(evil_pdf)),
            (3, str(safe_root / "does-not-exist.pdf")),
            (4, ""),  # no PDF on file at all
        ]:
            conn.execute(
                "INSERT INTO papers (id, title, pdf_path, doi, arxiv_id, s2_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pid, f"p{pid}", path, f"doi-{pid}", f"ax-{pid}", f"s2-{pid}"),
            )
        conn.commit()
    finally:
        conn.close()

    from research_harness_mcp import http_api

    original_db = http_api.DB_PATH
    original_roots = list(http_api.PDF_ROOTS)
    http_api.DB_PATH = db_path
    http_api.PDF_ROOTS = [safe_root.resolve()]
    monkeypatch.setattr(http_api, "DB_PATH", db_path)
    monkeypatch.setattr(http_api, "PDF_ROOTS", [safe_root.resolve()])
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original_db
        http_api.PDF_ROOTS = original_roots


def test_pdf_serves_when_under_trusted_root(client: TestClient):
    r = client.get("/api/papers/1/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_pdf_403_when_outside_trusted_roots(client: TestClient):
    r = client.get("/api/papers/2/pdf")
    assert r.status_code == 403, r.text
    assert "outside" in r.json()["detail"].lower()


def test_pdf_404_when_path_trusted_but_file_missing(client: TestClient):
    r = client.get("/api/papers/3/pdf")
    assert r.status_code == 404, r.text


def test_pdf_404_when_no_pdf_on_file(client: TestClient):
    r = client.get("/api/papers/4/pdf")
    assert r.status_code == 404, r.text
    assert "no pdf" in r.json()["detail"].lower()


def test_pdf_404_for_unknown_paper(client: TestClient):
    r = client.get("/api/papers/99999/pdf")
    assert r.status_code == 404, r.text
