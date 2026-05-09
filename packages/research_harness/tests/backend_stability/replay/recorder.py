"""Record/replay hook that wraps llm_router's provider dispatch.

Design:
- Wraps ``llm_router.providers.base.get_provider`` so every call through
  the client (chat / chat_with_usage / tier-routed / explicit provider)
  goes through our interceptor, regardless of which real provider fn is
  returned.
- Keys each request by (provider, model, tier, prompt_hash).
- Hash is SHA-256 of the normalized prompt so whitespace/trailing newlines
  don't cause misses.

Modes:
- "record": try replay cache first; on miss, call real provider and APPEND
            the result to the jsonl cache. Requires real API access.
- "replay": cache-only. MISS = raise ReplayMiss. Used by offline tests.
- "auto":   same as replay but falls back to a deterministic stub response
            so tests don't crash (useful for regressions that don't care
            about LLM content fidelity).

The cache file format is JSONL with one entry per line:
    {"key": {...}, "response": "...", "ts": "2026-05-06T14:30:00Z"}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_PATCH_LOCK = threading.Lock()
_ORIGINAL_GET_PROVIDER: Callable[..., Any] | None = None
_STUB_RESPONSE = '{"stub": true, "reason": "replay-auto-fallback"}'


class ReplayMiss(RuntimeError):
    """Raised in replay mode when no cached response matches the request."""


@dataclass(frozen=True)
class CacheKey:
    provider: str
    model: str
    prompt_hash: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def normalize_prompt_hash(prompt: str) -> str:
    """Stable hash for prompts — collapse whitespace so trivial formatting
    changes don't force re-recording."""
    normalized = " ".join(prompt.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _load_cache(path: Path) -> dict[tuple[str, str, str], str]:
    cache: dict[tuple[str, str, str], str] = {}
    if not path.exists():
        return cache
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("replay: bad jsonl at %s:%d", path, line_no)
                continue
            key = entry["key"]
            cache[(key["provider"], key["model"], key["prompt_hash"])] = entry[
                "response"
            ]
    return cache


def _append_cache(path: Path, key: CacheKey, response: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "key": key.to_dict(),
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def install_replay_hook(
    cache_path: str | Path,
    mode: str = "replay",
    stub_response: str | None = None,
) -> None:
    """Monkey-patch the llm_router provider registry.

    Parameters
    ----------
    cache_path : path to jsonl cache file
    mode       : "record" | "replay" | "auto"
    stub_response : response string to return in "auto" mode on miss
                    (defaults to a JSON-parseable stub marker)
    """
    global _ORIGINAL_GET_PROVIDER
    if mode not in {"record", "replay", "auto"}:
        raise ValueError(f"invalid replay mode: {mode!r}")

    path = Path(cache_path)
    cache = _load_cache(path)
    fallback = stub_response if stub_response is not None else _STUB_RESPONSE

    from llm_router import client as llm_client

    with _PATCH_LOCK:
        if _ORIGINAL_GET_PROVIDER is None:
            _ORIGINAL_GET_PROVIDER = llm_client.get_provider

        original = _ORIGINAL_GET_PROVIDER

        def wrapped_get_provider(name: str) -> Callable[..., Any]:
            real_fn = original(name)

            def intercepted(prompt: str, model: str, **kwargs: Any) -> str:
                key = CacheKey(
                    provider=name,
                    model=str(model or "none"),
                    prompt_hash=normalize_prompt_hash(prompt),
                )
                tup = (key.provider, key.model, key.prompt_hash)

                if tup in cache:
                    return cache[tup]

                if mode == "replay":
                    raise ReplayMiss(
                        f"No cached response for provider={name} "
                        f"model={model} prompt_hash={key.prompt_hash[:8]} — "
                        f"run in record mode first."
                    )

                if mode == "auto":
                    logger.info("replay-auto stub for %s/%s", name, model)
                    return fallback

                # record mode — hit real LLM, persist
                response = real_fn(prompt, model, **kwargs)
                _append_cache(path, key, response)
                cache[tup] = response
                return response

            return intercepted

        llm_client.get_provider = wrapped_get_provider


def uninstall_replay_hook() -> None:
    """Restore the original provider registry (for teardown)."""
    global _ORIGINAL_GET_PROVIDER
    if _ORIGINAL_GET_PROVIDER is None:
        return
    from llm_router import client as llm_client

    with _PATCH_LOCK:
        llm_client.get_provider = _ORIGINAL_GET_PROVIDER
        _ORIGINAL_GET_PROVIDER = None


def env_mode() -> str:
    """Resolve mode from RH_REPLAY_MODE (default: replay)."""
    return os.environ.get("RH_REPLAY_MODE", "replay")


def env_cache_path() -> Path | None:
    """Resolve cache path from RH_REPLAY_FILE."""
    p = os.environ.get("RH_REPLAY_FILE")
    return Path(p) if p else None
