"""Tests for topic candidates generation and job polling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_harness.storage.db import Database


@pytest.fixture()
def db_with_domain(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    conn.execute("INSERT INTO domains (name) VALUES ('Test Domain')")
    conn.commit()
    conn.close()
    return db


def test_create_job_and_poll(db_with_domain: Database):
    conn = db_with_domain.connect()
    try:
        domain = conn.execute("SELECT id, name FROM domains WHERE id = 1").fetchone()
        assert domain is not None

        candidates = [
            {
                "name": f"{domain['name']} — Direction {i + 1}",
                "description": f"Exploring aspect {i + 1}",
                "rationale": "Generated from scope analysis",
            }
            for i in range(3)
        ]

        cur = conn.execute(
            """
            INSERT INTO async_jobs (job_type, domain_id, status, input_params, result)
            VALUES ('topic_candidates', ?, 'completed', ?, ?)
            """,
            (
                1,
                json.dumps({"tier": "standard"}),
                json.dumps({"candidates": candidates}),
            ),
        )
        job_id = cur.lastrowid
        conn.commit()

        row = conn.execute(
            "SELECT * FROM async_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        assert row["status"] == "completed"
        result = json.loads(row["result"])
        assert len(result["candidates"]) == 3
        assert "Direction 1" in result["candidates"][0]["name"]
    finally:
        conn.close()


def test_job_not_found(db_with_domain: Database):
    conn = db_with_domain.connect()
    try:
        row = conn.execute("SELECT * FROM async_jobs WHERE id = 9999").fetchone()
        assert row is None
    finally:
        conn.close()


def test_idempotency_key(db_with_domain: Database):
    conn = db_with_domain.connect()
    try:
        conn.execute(
            "INSERT INTO async_jobs (job_type, domain_id, status, idempotency_key, result) "
            "VALUES ('topic_candidates', 1, 'completed', 'key-123', '{}')"
        )
        conn.commit()

        from sqlite3 import IntegrityError

        with pytest.raises(IntegrityError):
            conn.execute(
                "INSERT INTO async_jobs (job_type, domain_id, status, idempotency_key, result) "
                "VALUES ('topic_candidates', 1, 'completed', 'key-123', '{}')"
            )
    finally:
        conn.close()
