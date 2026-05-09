"""Tests for `rh domain seed cs` — insert-or-update 15 CS domains."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from research_harness.cli import CS_DOMAIN_SEED, main
from research_harness.storage.db import Database


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "seed.db"
    d = Database(p)
    d.migrate()
    return str(p)


def test_seed_cs_inserts_15_domains(db_path, monkeypatch):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db_path, "--json", "domain", "seed", "cs"])
    assert result.exit_code == 0, result.output

    d = Database(db_path)
    conn = d.connect()
    try:
        rows = conn.execute(
            "SELECT name FROM domains WHERE name LIKE 'cs.%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    names = [r[0] for r in rows]
    expected = sorted(n for n, _ in CS_DOMAIN_SEED)
    assert names == expected


def test_seed_cs_idempotent(db_path):
    runner = CliRunner()
    first = runner.invoke(main, ["--db", db_path, "--json", "domain", "seed", "cs"])
    assert first.exit_code == 0
    second = runner.invoke(main, ["--db", db_path, "--json", "domain", "seed", "cs"])
    assert second.exit_code == 0

    d = Database(db_path)
    conn = d.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM domains WHERE name LIKE 'cs.%'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 15  # no duplicates created
