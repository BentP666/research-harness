"""SQLite content-hash cache for embeddings (migration 051)."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from ..storage.db import Database

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    """Collapse whitespace so trivial variants don't defeat the cache."""
    return " ".join((text or "").split()).strip()


def content_hash(text: str) -> str:
    """Stable hex digest over the normalized text."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def read_cached(
    db: Database,
    *,
    provider: str,
    model: str,
    texts: list[str],
) -> dict[str, list[float]]:
    """Return a {content_hash: vector} mapping for any cache hits."""
    if not texts:
        return {}
    hashes = [content_hash(t) for t in texts]
    placeholders = ",".join("?" * len(hashes))
    conn = db.connect()
    try:
        rows = conn.execute(
            f"""
            SELECT content_hash, vector_json
            FROM embedding_cache
            WHERE provider = ? AND model = ? AND content_hash IN ({placeholders})
            """,
            [provider, model, *hashes],
        ).fetchall()
    finally:
        conn.close()
    out: dict[str, list[float]] = {}
    for r in rows:
        try:
            out[r["content_hash"]] = json.loads(r["vector_json"])
        except (ValueError, TypeError):
            logger.warning("Corrupt cached vector for %s", r["content_hash"])
    return out


def write_cached(
    db: Database,
    *,
    provider: str,
    model: str,
    pairs: list[tuple[str, list[float]]],
) -> None:
    """Persist (text, vector) pairs. Dedupes by content_hash."""
    if not pairs:
        return
    conn = db.connect()
    try:
        for text, vector in pairs:
            if not vector:
                continue
            h = content_hash(text)
            vector_json = json.dumps([float(x) for x in vector])
            conn.execute(
                """
                INSERT OR IGNORE INTO embedding_cache
                (provider, model, content_hash, vector_json, dim)
                VALUES (?, ?, ?, ?, ?)
                """,
                (provider, model, h, vector_json, len(vector)),
            )
        conn.commit()
    finally:
        conn.close()


def clear_cache(
    db: Database,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> int:
    """Drop cached rows (all, or per-provider/model)."""
    conn = db.connect()
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if provider is not None:
            clauses.append("provider = ?")
            params.append(provider)
        if model is not None:
            clauses.append("model = ?")
            params.append(model)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        cur = conn.execute(f"DELETE FROM embedding_cache{where}", params)
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()
