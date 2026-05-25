"""Small Codex app-server client for RH Zotero chat streaming.

The Zotero plugin talks to the RH HTTP API, and RH owns the bridge to Codex.
This module intentionally implements only the narrow JSON-RPC surface needed by
that bridge: initialize, thread start/resume, turn start, and assistant deltas.
"""

from __future__ import annotations

import json
import logging
import os
import select
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

logger = logging.getLogger(__name__)


class CodexAppServerError(RuntimeError):
    """Raised when the Codex app-server protocol cannot complete a turn."""


@dataclass(frozen=True)
class CodexStreamEvent:
    """Normalized stream event emitted by the app-server bridge."""

    event: str
    data: dict[str, Any]


class JsonRpcTransport(Protocol):
    """Transport abstraction used so protocol behavior is unit-testable."""

    def send(self, message: dict[str, Any]) -> None: ...

    def read(self, timeout_seconds: float | None = None) -> dict[str, Any]: ...

    def close(self) -> None: ...


class SubprocessJsonRpcTransport:
    """Line-delimited JSON-RPC transport for `codex app-server --listen stdio://`."""

    def __init__(
        self,
        *,
        command: list[str],
        cwd: str | Path,
        env: dict[str, str] | None = None,
    ) -> None:
        self._process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._write_lock = threading.Lock()
        self._stderr_tail: list[str] = []
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr_background, daemon=True
        )
        self._stderr_thread.start()

    def send(self, message: dict[str, Any]) -> None:
        if self._process.stdin is None:
            raise CodexAppServerError("Codex app-server stdin is closed")
        line = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            self._process.stdin.write(f"{line}\n")
            self._process.stdin.flush()

    def read(self, timeout_seconds: float | None = None) -> dict[str, Any]:
        if self._process.stdout is None:
            raise CodexAppServerError("Codex app-server stdout is closed")
        deadline = (
            None if timeout_seconds is None else time.monotonic() + timeout_seconds
        )
        while True:
            if self._process.poll() is not None:
                stderr = self._drain_stderr()
                raise CodexAppServerError(
                    f"Codex app-server exited with code {self._process.returncode}: {stderr}".strip()
                )
            remaining = (
                None if deadline is None else max(0.0, deadline - time.monotonic())
            )
            if remaining == 0.0:
                raise TimeoutError("timed out waiting for Codex app-server message")
            readable, _, _ = select.select([self._process.stdout], [], [], remaining)
            if not readable:
                raise TimeoutError("timed out waiting for Codex app-server message")
            line = self._process.stdout.readline()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CodexAppServerError(
                    f"invalid Codex app-server JSON message: {line[:200]}"
                ) from exc
            if isinstance(message, dict):
                return message
            raise CodexAppServerError("Codex app-server emitted non-object JSON")

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2)

    def _drain_stderr_background(self) -> None:
        if self._process.stderr is None:
            return
        try:
            for line in self._process.stderr:
                text = line.rstrip()
                if text:
                    logger.debug("Codex app-server stderr: %s", text)
                    self._stderr_tail = [*self._stderr_tail[-19:], text]
        except Exception:
            logger.debug("Codex app-server stderr drainer stopped", exc_info=True)

    def _drain_stderr(self) -> str:
        return "\n".join(self._stderr_tail[-20:])[:1000]


TransportFactory = Callable[[], JsonRpcTransport]
CodexClientFactory = Callable[..., "CodexAppServerClient"]


class CodexAppServerClient:
    """Minimal client for the Codex app-server JSON-RPC protocol."""

    def __init__(
        self,
        *,
        codex_bin: str | None = None,
        cwd: str | Path | None = None,
        timeout_seconds: float | None = None,
        model: str | None = None,
        service_tier: str | None = None,
        effort: str | None = None,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        default_codex_bin = (
            "/opt/homebrew/bin/codex"
            if Path("/opt/homebrew/bin/codex").exists()
            else "codex"
        )
        self.codex_bin = codex_bin or os.getenv(
            "RESEARCH_HARNESS_CODEX_BIN", default_codex_bin
        )
        self.cwd = Path(cwd or os.getenv("RESEARCH_HARNESS_CODEX_CWD", ".")).resolve()
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("RESEARCH_HARNESS_ZOTERO_CODEX_TIMEOUT_SECONDS", "240")
        )
        self.model = (
            model
            or os.getenv("RESEARCH_HARNESS_ZOTERO_CODEX_MODEL", "")
            or "gpt-5.3-codex-spark"
        )
        self.service_tier = (
            service_tier
            or os.getenv("RESEARCH_HARNESS_ZOTERO_CODEX_SERVICE_TIER", "")
            or None
        )
        self.effort = (
            effort or os.getenv("RESEARCH_HARNESS_ZOTERO_CODEX_EFFORT", "") or "low"
        )
        self._transport_factory = transport_factory
        self._transport: JsonRpcTransport | None = None
        self._next_id = 1
        self._initialized = False

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            self._initialized = False

    def __enter__(self) -> "CodexAppServerClient":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {}
        result = self._request(
            "initialize",
            {
                "clientInfo": {
                    "name": "research-harness-zotero",
                    "title": "Research Harness Zotero Panel",
                    "version": "0.1.0",
                },
                "capabilities": {"experimentalApi": False},
            },
        )
        # Codex app-server accepts the JSON-RPC initialized notification without params.
        self._send_notification("initialized")
        self._initialized = True
        return result

    def start_thread(self, *, cwd: str | Path, instructions: str) -> str:
        params: dict[str, Any] = {
            "cwd": str(Path(cwd).resolve()),
            "approvalPolicy": "never",
            "approvalsReviewer": "user",
            "sandbox": "read-only",
            "baseInstructions": instructions,
            "threadSource": "user",
            "ephemeral": False,
        }
        if self.model:
            params["model"] = self.model
        if self.service_tier:
            params["serviceTier"] = self.service_tier
        result = self._request("thread/start", params)
        thread_id = result.get("thread", {}).get("id")
        if not thread_id:
            raise CodexAppServerError("thread/start response did not include thread.id")
        return str(thread_id)

    def resume_thread(
        self, thread_id: str, *, cwd: str | Path, instructions: str
    ) -> str:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "cwd": str(Path(cwd).resolve()),
            "approvalPolicy": "never",
            "approvalsReviewer": "user",
            "sandbox": "read-only",
            "baseInstructions": instructions,
        }
        if self.model:
            params["model"] = self.model
        if self.service_tier:
            params["serviceTier"] = self.service_tier
        result = self._request("thread/resume", params)
        resumed_id = result.get("thread", {}).get("id") or thread_id
        return str(resumed_id)

    def stream_turn(
        self,
        thread_id: str,
        prompt: str,
        *,
        image_urls: list[str] | None = None,
    ) -> Iterator[CodexStreamEvent]:
        """Start a turn and yield normalized streaming events until completion."""
        input_items: list[dict[str, Any]] = [
            {"type": "text", "text": prompt, "text_elements": []}
        ]
        for image_url in image_urls or []:
            if image_url:
                input_items.append(
                    {
                        "type": "image",
                        "url": image_url,
                        "detail": "high",
                    }
                )
        request_id = self._send_request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": input_items,
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                **({"model": self.model} if self.model else {}),
                **({"serviceTier": self.service_tier} if self.service_tier else {}),
                **({"effort": self.effort} if self.effort else {}),
            },
        )
        turn_id: str | None = None
        saw_response = False
        completed = False
        while not completed:
            message = self._read_next()
            if self._is_server_request(message):
                self._answer_server_request(message)
                continue
            if message.get("id") == request_id:
                saw_response = True
                result = self._response_result(message)
                turn_id = str(result.get("turn", {}).get("id") or turn_id or "") or None
                continue
            method = message.get("method")
            params = message.get("params") or {}
            if method == "turn/started" and params.get("threadId") == thread_id:
                turn = params.get("turn") or {}
                turn_id = str(turn.get("id") or turn_id or "") or None
                yield CodexStreamEvent(
                    "started",
                    {"thread_id": thread_id, "turn_id": turn_id},
                )
                continue
            if (
                method == "item/agentMessage/delta"
                and params.get("threadId") == thread_id
            ):
                if turn_id and params.get("turnId") and params.get("turnId") != turn_id:
                    continue
                yield CodexStreamEvent(
                    "delta",
                    {
                        "thread_id": thread_id,
                        "turn_id": params.get("turnId") or turn_id,
                        "item_id": params.get("itemId"),
                        "text": params.get("delta") or "",
                    },
                )
                continue
            if (
                method == "thread/status/changed"
                and params.get("threadId") == thread_id
            ):
                status_payload = params.get("status")
                yield CodexStreamEvent(
                    "status",
                    {"thread_id": thread_id, "status": status_payload},
                )
                if (
                    isinstance(status_payload, dict)
                    and status_payload.get("type") == "idle"
                    and turn_id
                ):
                    completed = True
                    yield CodexStreamEvent(
                        "done",
                        {
                            "thread_id": thread_id,
                            "turn_id": turn_id,
                            "status": "completed",
                            "completion_source": "thread_idle",
                        },
                    )
                continue
            if method == "turn/completed" and params.get("threadId") == thread_id:
                turn = params.get("turn") or {}
                completed_turn_id = str(turn.get("id") or turn_id or "") or None
                if turn_id and completed_turn_id and completed_turn_id != turn_id:
                    continue
                status = turn.get("status")
                if status not in (None, "completed"):
                    raise CodexAppServerError(f"Codex turn ended with status {status}")
                completed = True
                yield CodexStreamEvent(
                    "done",
                    {
                        "thread_id": thread_id,
                        "turn_id": completed_turn_id,
                        "status": status,
                    },
                )
                continue
            if method == "error":
                raise CodexAppServerError(str(params))
        if not saw_response:
            # The turn can complete after a started notification and before the response arrives
            # only if the protocol changes. Keep this explicit so tests catch drift.
            logger.debug("Codex turn completed before turn/start response was observed")

    def _request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        request_id = self._send_request(method, params)
        while True:
            message = self._read_next()
            if self._is_server_request(message):
                self._answer_server_request(message)
                continue
            if message.get("id") != request_id:
                continue
            return self._response_result(message)

    def _send_request(self, method: str, params: dict[str, Any] | None = None) -> int:
        request_id = self._next_id
        self._next_id += 1
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._ensure_transport().send(message)
        return request_id

    def _send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        self._ensure_transport().send(message)

    def _read_next(self) -> dict[str, Any]:
        try:
            return self._ensure_transport().read(self.timeout_seconds)
        except TimeoutError as exc:
            raise CodexAppServerError(str(exc)) from exc

    def _ensure_transport(self) -> JsonRpcTransport:
        if self._transport is None:
            if self._transport_factory is not None:
                self._transport = self._transport_factory()
            else:
                self._transport = SubprocessJsonRpcTransport(
                    command=[self.codex_bin, "app-server", "--listen", "stdio://"],
                    cwd=self.cwd,
                    env=os.environ.copy(),
                )
        return self._transport

    @staticmethod
    def _response_result(message: dict[str, Any]) -> dict[str, Any]:
        if "error" in message:
            raise CodexAppServerError(str(message["error"]))
        result = message.get("result")
        if result is None:
            return {}
        if not isinstance(result, dict):
            raise CodexAppServerError(
                "Codex app-server response result was not an object"
            )
        return result

    @staticmethod
    def _is_server_request(message: dict[str, Any]) -> bool:
        return (
            "id" in message
            and "method" in message
            and "result" not in message
            and "error" not in message
        )

    def _answer_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        request_id = message.get("id")
        if request_id is None:
            return
        result: dict[str, Any]
        if method in {
            "item/commandExecution/requestApproval",
            "execCommandApproval",
        }:
            # The RH Zotero bridge is read-only/non-mutating by default.
            result = {"decision": "decline" if method.startswith("item/") else "denied"}
        elif method in {"item/fileChange/requestApproval", "applyPatchApproval"}:
            result = {"decision": "decline" if method.startswith("item/") else "denied"}
        elif method == "mcpServer/elicitation/request":
            result = {"action": "decline", "content": None, "_meta": None}
        elif method == "item/tool/requestUserInput":
            result = {"answers": {}}
        elif method == "item/permissions/requestApproval":
            result = {"permissions": {}, "scope": "turn", "strictAutoReview": True}
        elif method == "item/tool/call":
            result = {
                "contentItems": [
                    {
                        "type": "text",
                        "text": "RH Zotero bridge does not proxy dynamic tools.",
                    }
                ],
                "success": False,
            }
        else:
            self._ensure_transport().send(
                {
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unsupported client callback: {method}",
                    },
                }
            )
            return
        self._ensure_transport().send({"id": request_id, "result": result})


@dataclass
class _PooledCodexEntry:
    client: Any
    lock: threading.Lock
    initialized: bool = False


@dataclass(frozen=True)
class _CodexPoolKey:
    cwd: str
    model: str | None
    effort: str | None
    service_tier: str | None


class CodexAppServerPool:
    """Reuse initialized Codex app-server clients for Zotero chat turns.

    A single app-server stdio transport is not safe for concurrent reads/writes,
    so the pool serializes turns per (cwd, model, effort, service tier) client.
    Different model choices get independent app-server processes.
    """

    def __init__(
        self,
        *,
        client_factory: CodexClientFactory | None = None,
    ) -> None:
        self._client_factory = client_factory or CodexAppServerClient
        self._entries: dict[_CodexPoolKey, _PooledCodexEntry] = {}
        self._entries_lock = threading.Lock()

    def stream_turn(
        self,
        *,
        cwd: str | Path,
        instructions: str,
        existing_thread_id: str | None,
        prompt: str,
        model: str | None = None,
        effort: str | None = None,
        service_tier: str | None = None,
        image_urls: list[str] | None = None,
    ) -> Iterator[CodexStreamEvent]:
        key = _CodexPoolKey(
            cwd=str(Path(cwd).resolve()),
            model=model,
            effort=effort,
            service_tier=service_tier,
        )
        entry = self._entry_for(key)
        with entry.lock:
            try:
                if not entry.initialized:
                    entry.client.initialize()
                    entry.initialized = True

                thread_id = ""
                if existing_thread_id:
                    try:
                        thread_id = entry.client.resume_thread(
                            existing_thread_id,
                            cwd=key.cwd,
                            instructions=instructions,
                        )
                    except CodexAppServerError:
                        logger.warning(
                            "Failed to resume Codex thread %s; starting a new thread",
                            existing_thread_id,
                            exc_info=True,
                        )
                if not thread_id:
                    thread_id = entry.client.start_thread(
                        cwd=key.cwd,
                        instructions=instructions,
                    )

                yield CodexStreamEvent(
                    "started",
                    {
                        "thread_id": thread_id,
                        "turn_id": None,
                        "resumed": bool(
                            existing_thread_id and thread_id == existing_thread_id
                        ),
                    },
                )
                if image_urls:
                    yield from entry.client.stream_turn(
                        thread_id,
                        prompt,
                        image_urls=image_urls,
                    )
                else:
                    yield from entry.client.stream_turn(thread_id, prompt)
            except Exception:
                self._drop_entry(key, entry)
                raise

    def prewarm(
        self,
        *,
        cwd: str | Path,
        model: str | None = None,
        effort: str | None = None,
        service_tier: str | None = None,
    ) -> None:
        """Start and initialize a pooled Codex app-server before the first turn.

        This intentionally does not start or resume a thread, so it avoids
        creating a conversation or consuming model tokens. It only pays the
        local subprocess + JSON-RPC initialize cost ahead of the user's first
        Zotero question.
        """

        key = _CodexPoolKey(
            cwd=str(Path(cwd).resolve()),
            model=model,
            effort=effort,
            service_tier=service_tier,
        )
        entry = self._entry_for(key)
        with entry.lock:
            if not entry.initialized:
                entry.client.initialize()
                entry.initialized = True

    def close_all(self) -> None:
        with self._entries_lock:
            entries = list(self._entries.values())
            self._entries = {}
        for entry in entries:
            try:
                entry.client.close()
            except Exception:
                logger.debug("Failed to close pooled Codex client", exc_info=True)

    def _entry_for(self, key: _CodexPoolKey) -> _PooledCodexEntry:
        with self._entries_lock:
            entry = self._entries.get(key)
            if entry is not None:
                return entry
            client = self._client_factory(
                cwd=key.cwd,
                model=key.model,
                effort=key.effort,
                service_tier=key.service_tier,
            )
            entry = _PooledCodexEntry(client=client, lock=threading.Lock())
            self._entries[key] = entry
            return entry

    def _drop_entry(self, key: _CodexPoolKey, entry: _PooledCodexEntry) -> None:
        with self._entries_lock:
            if self._entries.get(key) is entry:
                self._entries.pop(key, None)
        try:
            entry.client.close()
        except Exception:
            logger.debug("Failed to close failed pooled Codex client", exc_info=True)


class ZoteroCodexConversationStore:
    """Durable conversation_id -> Codex thread_id mapping for multi-turn chat."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def get_thread_id(self, conversation_id: str) -> str | None:
        record = self.read_all().get(conversation_id)
        thread_id = (record or {}).get("thread_id")
        return str(thread_id) if thread_id else None

    def save_thread(
        self,
        *,
        conversation_id: str,
        thread_id: str,
        paper_id: int | None = None,
        topic_id: int | None = None,
        zotero_item_key: str = "",
    ) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            data = self._read_unlocked()
            previous = data.get(conversation_id, {})
            data[conversation_id] = {
                **previous,
                "thread_id": thread_id,
                "paper_id": paper_id,
                "topic_id": topic_id,
                "zotero_item_key": zotero_item_key,
                "created_at": previous.get("created_at") or now,
                "updated_at": now,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp_path.replace(self.path)

    def read_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def _read_unlocked(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read Zotero Codex thread store: %s", self.path)
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value for key, value in data.items() if isinstance(value, dict)
        }
