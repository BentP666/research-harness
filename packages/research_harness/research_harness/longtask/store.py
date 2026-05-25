"""SQLite-backed state store for long Codex tasks."""

from __future__ import annotations

import json
import secrets
import sqlite3
import stat
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .models import LongTaskGate, LongTaskRun, LongTaskTask


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _decode_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key in (
        "dependencies_json",
        "write_scope_json",
        "result_json",
        "payload_json",
        "scoring_json",
    ):
        if key in item:
            target = key.removesuffix("_json")
            item[target] = _decode_json(
                item.pop(key), [] if key.endswith("s_json") else {}
            )
    if "token_hash" in item:
        item["token_required"] = bool(item.pop("token_hash"))
    return item


class LongTaskStore:
    """Durable local state for long-running Codex supervisor runs."""

    def __init__(self, home: str | Path):
        self.home = Path(home).expanduser().resolve()
        self.runs_dir = self.home / "runs"
        self.db_path = self.home / "state.db"
        self.home.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        _chmod_private_dir(self.home)
        _chmod_private_dir(self.runs_dir)
        self.migrate()
        self.harden_file(self.db_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            for suffix in ("", "-wal", "-shm"):
                _chmod_private_file(Path(f"{self.db_path}{suffix}"))
            conn.close()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS longtask_runs (
                  id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  objective TEXT NOT NULL,
                  status TEXT NOT NULL,
                  max_workers INTEGER NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS longtask_tasks (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES longtask_runs(id) ON DELETE CASCADE,
                  title TEXT NOT NULL,
                  prompt TEXT NOT NULL,
                  status TEXT NOT NULL,
                  dependencies_json TEXT NOT NULL DEFAULT '[]',
                  write_scope_json TEXT NOT NULL DEFAULT '[]',
                  risk_level TEXT NOT NULL DEFAULT 'low',
                  summary TEXT NOT NULL DEFAULT '',
                  result_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS longtask_attempts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL REFERENCES longtask_tasks(id) ON DELETE CASCADE,
                  run_id TEXT NOT NULL REFERENCES longtask_runs(id) ON DELETE CASCADE,
                  status TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  finished_at TEXT,
                  exit_code INTEGER,
                  error TEXT,
                  events_path TEXT,
                  final_path TEXT,
                  result_path TEXT,
                  quarantine_reason_path TEXT
                );

                CREATE TABLE IF NOT EXISTS longtask_gates (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES longtask_runs(id) ON DELETE CASCADE,
                  task_id TEXT REFERENCES longtask_tasks(id) ON DELETE SET NULL,
                  gate_type TEXT NOT NULL,
                  title TEXT NOT NULL,
                  status TEXT NOT NULL,
                  decision TEXT,
                  note TEXT,
                  actor TEXT,
                  token_hash TEXT,
                  created_at TEXT NOT NULL,
                  decided_at TEXT
                );

                CREATE TABLE IF NOT EXISTS longtask_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL REFERENCES longtask_runs(id) ON DELETE CASCADE,
                  task_id TEXT REFERENCES longtask_tasks(id) ON DELETE CASCADE,
                  event_type TEXT NOT NULL,
                  message TEXT NOT NULL,
                  payload_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL
                );
                """
            )

    def next_run_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"run_{stamp}_{secrets.token_hex(3)}"

    def next_task_id(self, run_id: str) -> str:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM longtask_tasks WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return f"T{int(row['count']) + 1:03d}"

    def create_run(self, run: LongTaskRun) -> None:
        ts = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO longtask_runs
                (id, title, objective, status, max_workers, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run.id, run.title, run.objective, run.status, run.max_workers, ts, ts),
            )
            self.add_event(conn, run.id, None, "run_created", f"Created {run.title}")

    def create_task(self, task: LongTaskTask) -> None:
        ts = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO longtask_tasks
                (id, run_id, title, prompt, status, dependencies_json,
                 write_scope_json, risk_level, summary, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.run_id,
                    task.title,
                    task.prompt,
                    task.status,
                    json.dumps(task.dependencies, ensure_ascii=False),
                    json.dumps(task.write_scope, ensure_ascii=False),
                    task.risk_level,
                    task.summary,
                    "{}",
                    ts,
                    ts,
                ),
            )
            self.add_event(conn, task.run_id, task.id, "task_created", task.title)

    def get_gate(self, gate_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM longtask_gates WHERE id = ?",
                (gate_id,),
            ).fetchone()
        if row is None:
            raise KeyError(gate_id)
        return _row_to_dict(row)

    def task_title_exists(self, run_id: str, title: str) -> bool:
        normalized = " ".join(title.casefold().split())
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT title FROM longtask_tasks WHERE run_id = ?",
                (run_id,),
            ).fetchall()
        return any(
            " ".join(str(row["title"]).casefold().split()) == normalized for row in rows
        )

    def update_task_status(
        self,
        task_id: str,
        status: str,
        *,
        summary: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        fields = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, now_iso()]
        if summary is not None:
            fields.append("summary = ?")
            params.append(summary)
        if result is not None:
            fields.append("result_json = ?")
            params.append(json.dumps(result, ensure_ascii=False))
        params.append(task_id)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE longtask_tasks SET {', '.join(fields)} WHERE id = ?",
                params,
            )

    def set_run_status(self, run_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE longtask_runs SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_iso(), run_id),
            )

    def record_attempt(
        self,
        *,
        run_id: str,
        task_id: str,
        status: str,
        started_at: str,
        finished_at: str | None,
        exit_code: int | None,
        error: str | None,
        events_path: str | None,
        final_path: str | None,
        result_path: str | None,
        quarantine_reason_path: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO longtask_attempts
                (task_id, run_id, status, started_at, finished_at, exit_code, error,
                 events_path, final_path, result_path, quarantine_reason_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    run_id,
                    status,
                    started_at,
                    finished_at,
                    exit_code,
                    error,
                    events_path,
                    final_path,
                    result_path,
                    quarantine_reason_path,
                ),
            )
            self.add_event(
                conn,
                run_id,
                task_id,
                f"task_{status}",
                error or f"Task {task_id} {status}",
            )

    def create_gate(
        self,
        gate: LongTaskGate,
        *,
        token_hash: str | None,
    ) -> None:
        ts = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO longtask_gates
                (id, run_id, task_id, gate_type, title, status, token_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate.id,
                    gate.run_id,
                    gate.task_id,
                    gate.gate_type,
                    gate.title,
                    gate.status,
                    token_hash,
                    ts,
                ),
            )
            self.add_event(conn, gate.run_id, gate.task_id, "gate_created", gate.title)

    def update_gate(
        self,
        gate_id: str,
        *,
        status: str,
        decision: str,
        actor: str,
        note: str,
    ) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT run_id, task_id, title, status FROM longtask_gates WHERE id = ?",
                (gate_id,),
            ).fetchone()
            if row is None:
                return False
            cursor = conn.execute(
                """
                UPDATE longtask_gates
                SET status = ?, decision = ?, actor = ?, note = ?, decided_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, decision, actor, note, now_iso(), gate_id),
            )
            if cursor.rowcount == 1:
                self.add_event(
                    conn,
                    row["run_id"],
                    row["task_id"],
                    "gate_decided",
                    f"{row['title']}: {decision}",
                    {"actor": actor, "note": note},
                )
                return True
            self.add_event(
                conn,
                row["run_id"],
                row["task_id"],
                "gate_decision_rejected",
                f"{row['title']}: gate is not pending",
                {"actor": actor, "note": note, "current_status": row["status"]},
            )
            return False

    def gate_token_hash(self, gate_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT token_hash FROM longtask_gates WHERE id = ?",
                (gate_id,),
            ).fetchone()
        return str(row["token_hash"]) if row and row["token_hash"] else None

    def signing_secret(self) -> str:
        """Return a local-only HMAC secret for signed gate action links."""
        secret_path = self.home / "signing.key"
        if secret_path.exists():
            return secret_path.read_text(encoding="utf-8").strip()
        secret = secrets.token_urlsafe(48)
        secret_path.write_text(secret, encoding="utf-8")
        try:
            secret_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            # chmod can fail on some non-POSIX filesystems; the token still
            # remains local to the LongTask state directory.
            pass
        return secret

    def get_run_detail(self, run_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            run = conn.execute(
                "SELECT * FROM longtask_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            tasks = conn.execute(
                "SELECT * FROM longtask_tasks WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            attempts = conn.execute(
                "SELECT * FROM longtask_attempts WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            gates = conn.execute(
                "SELECT * FROM longtask_gates WHERE run_id = ? ORDER BY created_at, id",
                (run_id,),
            ).fetchall()
            events = conn.execute(
                "SELECT * FROM longtask_events WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()

        return {
            "run": _row_to_dict(run),
            "tasks": [_row_to_dict(row) for row in tasks],
            "attempts": [dict(row) for row in attempts],
            "gates": [_row_to_dict(row) for row in gates],
            "events": [_row_to_dict(row) for row in events],
        }

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*,
                       COUNT(DISTINCT t.id) AS task_count,
                       COUNT(DISTINCT CASE WHEN t.status = 'complete' THEN t.id END) AS complete_count,
                       COUNT(DISTINCT CASE WHEN g.status = 'pending' THEN g.id END) AS pending_gate_count
                FROM longtask_runs r
                LEFT JOIN longtask_tasks t ON t.run_id = r.id
                LEFT JOIN longtask_gates g ON g.run_id = r.id
                GROUP BY r.id
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def ready_tasks(self, run_id: str) -> list[dict[str, Any]]:
        detail = self.get_run_detail(run_id)
        complete = {
            task["id"] for task in detail["tasks"] if task["status"] == "complete"
        }
        pending_gate = any(gate["status"] == "pending" for gate in detail["gates"])
        if pending_gate:
            return []
        ready: list[dict[str, Any]] = []
        for task in detail["tasks"]:
            if task["status"] != "queued":
                continue
            deps = task.get("dependencies", [])
            if all(dep in complete for dep in deps):
                ready.append(task)
        return ready

    def record_event(
        self,
        *,
        run_id: str,
        task_id: str | None,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            self.add_event(conn, run_id, task_id, event_type, message, payload)

    def harden_file(self, path: str | Path | None) -> None:
        if path is None:
            return
        _chmod_private_file(Path(path))

    def harden_dir(self, path: str | Path | None) -> None:
        if path is None:
            return
        _chmod_private_dir(Path(path))

    def write_private_text(self, path: str | Path, text: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _chmod_private_dir(target.parent)
        target.write_text(text, encoding="utf-8")
        _chmod_private_file(target)

    def add_event(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        task_id: str | None,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO longtask_events
            (run_id, task_id, event_type, message, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                task_id,
                event_type,
                message,
                json.dumps(payload or {}, ensure_ascii=False),
                now_iso(),
            ),
        )


def _chmod_private_dir(path: Path) -> None:
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _chmod_private_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.chmod(0o600)
    except OSError:
        pass
