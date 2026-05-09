"""Token ledger accounting — hooks into llm_router to record every LLM call.

Usage:
    from research_harness.token_accounting import (
        set_call_context, record_usage, check_budget, BudgetExceeded,
    )

    # Before an LLM call:
    set_call_context(topic_id=5, stage="analyze", role="generator", agent_id=1)
    check_budget(topic_id=5, estimated_cost=0.05)  # raises BudgetExceeded
    text, usage = client.chat_with_usage(prompt)
    record_usage(model="claude-opus-4-7", usage=usage)
"""

from __future__ import annotations

import contextvars
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Contextvars — set by callers before each LLM call
# ---------------------------------------------------------------------------

ctx_topic_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "ctx_topic_id", default=None
)
ctx_stage: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_stage", default=None
)
ctx_role: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_role", default=None
)
ctx_agent_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "ctx_agent_id", default=None
)
ctx_primitive: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_primitive", default=None
)
ctx_idempotency_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_idempotency_key", default=None
)


def set_call_context(
    *,
    topic_id: int | None = None,
    stage: str | None = None,
    role: str | None = None,
    agent_id: int | None = None,
    primitive: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    if topic_id is not None:
        ctx_topic_id.set(topic_id)
    if stage is not None:
        ctx_stage.set(stage)
    if role is not None:
        ctx_role.set(role)
    if agent_id is not None:
        ctx_agent_id.set(agent_id)
    if primitive is not None:
        ctx_primitive.set(primitive)
    ctx_idempotency_key.set(idempotency_key or str(uuid.uuid4()))


def clear_call_context() -> None:
    ctx_topic_id.set(None)
    ctx_stage.set(None)
    ctx_role.set(None)
    ctx_agent_id.set(None)
    ctx_primitive.set(None)
    ctx_idempotency_key.set(None)


# ---------------------------------------------------------------------------
# BudgetExceeded
# ---------------------------------------------------------------------------


class BudgetExceeded(Exception):
    def __init__(self, scope: str, cap: float, spent: float):
        self.scope = scope
        self.cap = cap
        self.spent = spent
        super().__init__(
            f"Budget exceeded for {scope}: cap=${cap:.2f}, spent=${spent:.2f}"
        )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_db_path() -> Path:
    import os

    from research_harness.config import GLOBAL_DB_PATH

    return Path(os.environ.get("RESEARCH_HARNESS_DB_PATH") or str(GLOBAL_DB_PATH))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_get_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Record usage to token_ledger
# ---------------------------------------------------------------------------


def record_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    agent_id: int | None = None,
    topic_id: int | None = None,
    stage: str | None = None,
    role: str | None = None,
    primitive: str | None = None,
    idempotency_key: str | None = None,
) -> float:
    from research_harness.pricing.models import cost_usd

    agent_id = agent_id or ctx_agent_id.get()
    topic_id = topic_id or ctx_topic_id.get()
    stage = stage or ctx_stage.get()
    role = role or ctx_role.get()
    primitive = primitive or ctx_primitive.get()
    idempotency_key = idempotency_key or ctx_idempotency_key.get()

    cost = cost_usd(model, prompt_tokens, completion_tokens)

    if agent_id is None:
        agent_id = _resolve_or_create_default_agent(model)

    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO token_ledger
                (agent_id, topic_id, stage, primitive, role,
                 prompt_tokens, completion_tokens, cost_usd, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                topic_id,
                stage,
                primitive,
                role,
                prompt_tokens,
                completion_tokens,
                cost,
                idempotency_key,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        logger.debug("Duplicate idempotency_key %s — skipping", idempotency_key)
    finally:
        conn.close()

    return cost


def _resolve_or_create_default_agent(model: str) -> int:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id FROM agent_registry WHERE model = ? AND status = 'active' LIMIT 1",
            (model,),
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            """
            INSERT INTO agent_registry (nickname, provider, provider_family, model, api_key_env, role_prefs)
            VALUES (?, 'auto', 'auto', ?, 'AUTO', '{}')
            """,
            (f"auto-{model}", model),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Budget check (pre-call)
# ---------------------------------------------------------------------------


def check_budget(topic_id: int | None = None, estimated_cost: float = 0.0) -> None:
    topic_id = topic_id or ctx_topic_id.get()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _check_scope(conn, "global", None, estimated_cost)
        if topic_id is not None:
            _check_scope(conn, "topic", topic_id, estimated_cost)
        conn.commit()
    except BudgetExceeded:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Stage-level budget checks
# ---------------------------------------------------------------------------

DEFAULT_STAGE_BUDGETS: dict[str, tuple[int, int]] = {
    "gap_detect": (8_000, 12_000),
    "claim_extract": (6_000, 10_000),
    "section_draft": (16_000, 24_000),
    "section_revise": (12_000, 18_000),
    "evidence_link": (4_000, 8_000),
    "baseline_identify": (4_000, 8_000),
    "outline_generate": (8_000, 12_000),
    "code_generate": (16_000, 24_000),
}


@dataclass
class StageBudgetResult:
    ok: bool
    warning: str | None = None
    stage: str = ""
    spent_tokens: int = 0
    soft_warn_tokens: int = 0
    hard_cap_tokens: int = 0


def check_stage_budget(
    topic_id: int,
    stage: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> StageBudgetResult:
    """Check per-stage token budget.

    Returns a StageBudgetResult:
    - ok=True, warning=None: within budget
    - ok=True, warning="...": soft limit hit, caller should log
    - ok=False, warning="...": hard cap exceeded, caller should block
    """
    own_conn = conn is None
    if own_conn:
        conn = _connect()
    try:
        # Try DB-configured budgets first
        row = conn.execute(
            """
            SELECT soft_warn_tokens, hard_cap_tokens
            FROM stage_budgets
            WHERE stage = ? AND (topic_id IS NULL OR topic_id = ?)
            ORDER BY topic_id DESC
            LIMIT 1
            """,
            (stage, topic_id),
        ).fetchone()

        if row:
            soft_warn = row["soft_warn_tokens"]
            hard_cap = row["hard_cap_tokens"]
        elif stage in DEFAULT_STAGE_BUDGETS:
            soft_warn, hard_cap = DEFAULT_STAGE_BUDGETS[stage]
        else:
            return StageBudgetResult(ok=True, stage=stage)

        # Sum tokens spent on this stage for this topic
        spent_row = conn.execute(
            """
            SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0) as total
            FROM token_ledger
            WHERE topic_id = ? AND stage = ?
            """,
            (topic_id, stage),
        ).fetchone()

        # Also check provenance_records as a fallback
        prov_row = conn.execute(
            """
            SELECT COALESCE(SUM(COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0)), 0) as total
            FROM provenance_records
            WHERE topic_id = ? AND primitive = ?
            """,
            (topic_id, stage),
        ).fetchone()

        spent = max(
            spent_row["total"] if spent_row else 0,
            prov_row["total"] if prov_row else 0,
        )

        if spent >= hard_cap:
            msg = (
                f"Stage '{stage}' hard cap exceeded for topic {topic_id}: "
                f"{spent:,} tokens >= {hard_cap:,} cap"
            )
            logger.warning(msg)
            return StageBudgetResult(
                ok=False,
                warning=msg,
                stage=stage,
                spent_tokens=spent,
                soft_warn_tokens=soft_warn,
                hard_cap_tokens=hard_cap,
            )

        if spent >= soft_warn:
            msg = (
                f"Stage '{stage}' approaching budget for topic {topic_id}: "
                f"{spent:,} tokens >= {soft_warn:,} soft limit "
                f"(hard cap: {hard_cap:,})"
            )
            logger.info(msg)
            return StageBudgetResult(
                ok=True,
                warning=msg,
                stage=stage,
                spent_tokens=spent,
                soft_warn_tokens=soft_warn,
                hard_cap_tokens=hard_cap,
            )

        return StageBudgetResult(
            ok=True,
            stage=stage,
            spent_tokens=spent,
            soft_warn_tokens=soft_warn,
            hard_cap_tokens=hard_cap,
        )
    except sqlite3.OperationalError as exc:
        if "no such table: stage_budgets" in str(exc):
            # Table not migrated yet — fall back to defaults
            return StageBudgetResult(ok=True, stage=stage)
        raise
    finally:
        if own_conn:
            conn.close()


def _check_scope(
    conn: sqlite3.Connection, scope: str, scope_id: int | None, estimated: float
) -> None:
    budget = conn.execute(
        "SELECT monthly_cap_usd, hard_stop FROM budgets WHERE scope = ? AND scope_id IS ?",
        (scope, scope_id),
    ).fetchone()
    if not budget:
        return
    if not budget["hard_stop"]:
        return

    cap = budget["monthly_cap_usd"]
    month_filter = "substr(ts, 1, 7) = strftime('%Y-%m', 'now')"

    if scope == "global":
        spent_row = conn.execute(
            f"SELECT COALESCE(SUM(cost_usd), 0) AS spent FROM token_ledger WHERE {month_filter}"
        ).fetchone()
    else:
        spent_row = conn.execute(
            f"SELECT COALESCE(SUM(cost_usd), 0) AS spent FROM token_ledger WHERE topic_id = ? AND {month_filter}",
            (scope_id,),
        ).fetchone()

    spent = spent_row["spent"] if spent_row else 0.0
    if spent + estimated > cap:
        raise BudgetExceeded(scope=scope, cap=cap, spent=spent)
