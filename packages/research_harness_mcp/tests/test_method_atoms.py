"""Tests for Iteration 07a: method_atoms harvest (migration 060)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


_MOCK_ATOMS = [
    {
        "atom_type": "loss",
        "name": "Temporal Contrastive Loss",
        "description": "Contrasts adjacent time steps to learn temporal patterns.",
        "deps": [],
        "reported_gain": "-3% MAPE",
        "reuse_risk": "low",
    },
    {
        "atom_type": "data_trick",
        "name": "Sliding Window Normalization",
        "description": "Normalizes each window independently before feeding to model.",
        "deps": [],
        "reported_gain": None,
        "reuse_risk": "low",
    },
    {
        "atom_type": "augmentation",
        "name": "Jitter + Scale",
        "description": "Adds Gaussian noise and random scaling to training series.",
        "deps": [],
        "reported_gain": "+1.2 BLEU",
        "reuse_risk": "medium",
    },
    {
        "atom_type": "training_schedule",
        "name": "Cosine Annealing + Warmup",
        "description": "Linear warmup for 5 epochs then cosine decay.",
        "deps": [],
        "reported_gain": None,
        "reuse_risk": "low",
    },
    {
        "atom_type": "inference_heuristic",
        "name": "Ensemble Mean",
        "description": "Average predictions from 3 random seeds.",
        "deps": [],
        "reported_gain": "-1% MAPE",
        "reuse_risk": "low",
    },
    {
        "atom_type": "micro_block",
        "name": "Cross-Attention Fusion",
        "description": "Fuses text embeddings with time-series via cross-attention.",
        "deps": ["Temporal Contrastive Loss"],
        "reported_gain": "-5% MAPE",
        "reuse_risk": "high",
    },
]


def _mock_harvest_retry(chat_fn, prompt, *, retries=1):
    return json.dumps(_MOCK_ATOMS)


_PATCH_TARGET = (
    "research_harness.primitives.harvest_atoms_impl._call_with_transient_retry"
)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "atoms.db"
    db = Database(db_path)
    db.migrate()

    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO topics (id, name, status) VALUES (1, 'test topic', 'active')"
        )
        conn.execute(
            "INSERT INTO projects (id, topic_id, name) VALUES (1, 1, 'test project')"
        )
        conn.execute(
            "INSERT INTO papers (id, title, abstract, compiled_summary, s2_id, arxiv_id, doi) "
            "VALUES (10, 'Paper A', 'Abstract A', 'Method section with techniques.', 's2-10', 'arxiv-10', 'doi-10')"
        )
        conn.execute(
            "INSERT INTO papers (id, title, abstract, compiled_summary, s2_id, arxiv_id, doi) "
            "VALUES (11, 'Paper B', 'Abstract B', 'Another method section.', 's2-11', 'arxiv-11', 'doi-11')"
        )
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (10, 1)")
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (11, 1)")
        conn.commit()
    finally:
        conn.close()

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


@pytest.fixture()
def db_path(client: TestClient) -> Path:
    from research_harness_mcp import http_api

    return http_api.DB_PATH


def test_harvest_returns_summary(client: TestClient):
    with patch(_PATCH_TARGET, side_effect=_mock_harvest_retry):
        r = client.post(
            "/api/topics/1/method-atoms/harvest",
            json={"paper_ids": [10]},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["papers_processed"] == 1
    assert data["total_atoms"] == 6
    assert data["errors"] == []


def test_harvest_writes_to_db(client: TestClient, db_path: Path):
    with patch(_PATCH_TARGET, side_effect=_mock_harvest_retry):
        client.post("/api/topics/1/method-atoms/harvest", json={"paper_ids": [10]})

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM method_atoms WHERE topic_id = 1 AND source_paper_id = 10"
    ).fetchall()
    conn.close()
    assert len(rows) == 6
    types = {r["atom_type"] for r in rows}
    assert types == {
        "loss",
        "data_trick",
        "augmentation",
        "training_schedule",
        "inference_heuristic",
        "micro_block",
    }


def test_list_atoms_all(client: TestClient):
    with patch(_PATCH_TARGET, side_effect=_mock_harvest_retry):
        client.post("/api/topics/1/method-atoms/harvest", json={"paper_ids": [10]})

    r = client.get("/api/topics/1/method-atoms")
    assert r.status_code == 200
    atoms = r.json()
    assert len(atoms) == 6


def test_list_atoms_filtered(client: TestClient):
    with patch(_PATCH_TARGET, side_effect=_mock_harvest_retry):
        client.post("/api/topics/1/method-atoms/harvest", json={"paper_ids": [10]})

    r = client.get("/api/topics/1/method-atoms?atom_type=loss")
    assert r.status_code == 200
    atoms = r.json()
    assert len(atoms) == 1
    assert atoms[0]["atom_type"] == "loss"


def test_delete_atom(client: TestClient, db_path: Path):
    with patch(_PATCH_TARGET, side_effect=_mock_harvest_retry):
        client.post("/api/topics/1/method-atoms/harvest", json={"paper_ids": [10]})

    atoms = client.get("/api/topics/1/method-atoms").json()
    atom_id = atoms[0]["id"]

    r = client.delete(f"/api/method-atoms/{atom_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] == atom_id

    remaining = client.get("/api/topics/1/method-atoms").json()
    assert len(remaining) == 5


def test_harvest_batch_two_papers(client: TestClient):
    with patch(_PATCH_TARGET, side_effect=_mock_harvest_retry):
        r = client.post(
            "/api/topics/1/method-atoms/harvest",
            json={"paper_ids": [10, 11]},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["papers_processed"] == 2
    assert data["total_atoms"] == 12


def test_harvest_empty_paper_ids_400(client: TestClient):
    r = client.post("/api/topics/1/method-atoms/harvest", json={"paper_ids": []})
    assert r.status_code == 400
