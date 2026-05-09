"""Tests for token_accounting: ledger recording, budget enforcement, WAL mode."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research_harness.storage.db import Database


@pytest.fixture()
def ledger_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fresh DB with migrations applied; patches env so token_accounting uses it."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))

    conn = db.connect()
    conn.execute(
        """
        INSERT INTO agent_registry (nickname, provider, provider_family, model, api_key_env, role_prefs)
        VALUES ('test-agent', 'anthropic', 'anthropic', 'claude-opus-4-7', 'KEY', '{}')
        """
    )
    conn.commit()
    agent_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    return db_path, agent_id


def test_record_usage_inserts_row(ledger_db):
    db_path, agent_id = ledger_db
    from research_harness.token_accounting import record_usage

    cost = record_usage(
        "claude-opus-4-7",
        prompt_tokens=1000,
        completion_tokens=500,
        agent_id=agent_id,
        stage="analyze",
        role="generator",
    )

    assert cost > 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM token_ledger").fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["agent_id"] == agent_id
    assert rows[0]["prompt_tokens"] == 1000
    assert rows[0]["completion_tokens"] == 500
    assert rows[0]["cost_usd"] == pytest.approx(cost)


def test_record_usage_idempotency(ledger_db):
    db_path, agent_id = ledger_db
    from research_harness.token_accounting import record_usage

    record_usage(
        "claude-opus-4-7",
        prompt_tokens=100,
        completion_tokens=50,
        agent_id=agent_id,
        idempotency_key="dedup-key-1",
    )
    record_usage(
        "claude-opus-4-7",
        prompt_tokens=100,
        completion_tokens=50,
        agent_id=agent_id,
        idempotency_key="dedup-key-1",
    )

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM token_ledger").fetchone()[0]
    conn.close()

    assert count == 1


def test_budget_exceeded_on_zero_cap(ledger_db):
    db_path, agent_id = ledger_db
    from research_harness.token_accounting import BudgetExceeded, check_budget

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO budgets (scope, scope_id, monthly_cap_usd, hard_stop) VALUES ('global', NULL, 0.0, 1)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(BudgetExceeded) as exc_info:
        check_budget(estimated_cost=0.01)

    assert exc_info.value.scope == "global"
    assert exc_info.value.cap == 0.0


def test_budget_soft_cap_does_not_raise(ledger_db):
    db_path, agent_id = ledger_db
    from research_harness.token_accounting import check_budget

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO budgets (scope, scope_id, monthly_cap_usd, hard_stop) VALUES ('global', NULL, 0.0, 0)"
    )
    conn.commit()
    conn.close()

    check_budget(estimated_cost=100.0)


def test_wal_mode(ledger_db):
    db_path, _ = ledger_db
    conn = sqlite3.connect(str(db_path))
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()

    assert mode == "wal"


def test_cost_usd_calculation():
    from research_harness.pricing.models import cost_usd

    cost = cost_usd("claude-opus-4-7", prompt_tokens=1_000_000, completion_tokens=0)
    assert cost == pytest.approx(15.0)

    cost2 = cost_usd("claude-opus-4-7", prompt_tokens=0, completion_tokens=1_000_000)
    assert cost2 == pytest.approx(75.0)

    cost3 = cost_usd(
        "unknown-model", prompt_tokens=1_000_000, completion_tokens=1_000_000
    )
    assert cost3 == pytest.approx(3.0 + 15.0)
