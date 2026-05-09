"""Storage-layer fault injectors.

Target failure modes the orchestrator has historically handled poorly:
- corrupt_paper_row:   mangle a single row's JSON field so SELECTs error
- sqlite_writer_lock:  hold an exclusive write lock while tests run code
                       that expects to write — stresses retry/backoff
- drop_required_index: temporarily drop an index to simulate a migration
                       that hasn't re-indexed (nightly tier)
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import time
from collections.abc import Iterator

from research_harness.storage.db import Database


@contextlib.contextmanager
def corrupt_paper_row(db: Database, paper_id: int) -> Iterator[None]:
    """Overwrite paper's authors column with a non-JSON blob, then
    restore on exit. Exercises batch queries that json.loads(authors)."""
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT authors FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"paper_id={paper_id} not found")
        original = row["authors"]
    finally:
        conn.close()

    conn = db.connect()
    try:
        conn.execute(
            "UPDATE papers SET authors = ? WHERE id = ?",
            ("<<<NOT JSON>>>{{", paper_id),
        )
        conn.commit()
    finally:
        conn.close()
    try:
        yield
    finally:
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE papers SET authors = ? WHERE id = ?", (original, paper_id)
            )
            conn.commit()
        finally:
            conn.close()


@contextlib.contextmanager
def sqlite_writer_lock(
    db: Database, hold_seconds: float = 0.5
) -> Iterator[threading.Event]:
    """Hold a BEGIN EXCLUSIVE in a background thread for ``hold_seconds``.

    Yields a ``threading.Event`` — the event is set as soon as the lock
    is actually held, so the test can wait for it before triggering the
    code-under-test.

    Use to verify the orchestrator retries with exponential backoff
    instead of crashing with ``database is locked``.
    """
    ready = threading.Event()
    done = threading.Event()

    def _holder():
        conn = sqlite3.connect(str(db.db_path), timeout=0.1)
        try:
            conn.execute("BEGIN EXCLUSIVE")
            ready.set()
            time.sleep(hold_seconds)
            conn.execute("COMMIT")
        finally:
            conn.close()
            done.set()

    thread = threading.Thread(target=_holder, daemon=True)
    thread.start()
    if not ready.wait(timeout=5):
        raise RuntimeError("sqlite_writer_lock: failed to acquire lock in 5s")
    try:
        yield ready
    finally:
        done.wait(timeout=hold_seconds + 5)


@contextlib.contextmanager
def drop_index(db: Database, index_name: str) -> Iterator[None]:
    """DROP INDEX + restore on exit. Used to simulate a broken migration.

    If the index doesn't exist, silently no-ops (so tests stay portable).
    """
    conn = db.connect()
    original_sql: str | None = None
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        original_sql = row["sql"] if row else None
        if original_sql:
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
            conn.commit()
    finally:
        conn.close()
    try:
        yield
    finally:
        if original_sql:
            conn = db.connect()
            try:
                conn.execute(original_sql)
                conn.commit()
            finally:
                conn.close()


__all__ = ["corrupt_paper_row", "sqlite_writer_lock", "drop_index"]
