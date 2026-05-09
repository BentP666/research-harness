"""LLM pathological-output injectors.

Pair with ``replay/recorder.py``: instead of returning cached responses,
each injector makes the patched ``get_provider`` return a deterministic
pathological shape so stages must cope with it.

The injectors are context managers so tests can scope a fault to one
block::

    with llm_returns_truncated_json():
        run_stage("analyze", ...)
    # after exit, provider is restored

Covered failure modes:
  - rate_limit:         raises provider-specific 429 twice, then succeeds
  - empty_response:     returns ``""`` — callers must not silently treat as success
  - refusal:            returns "I can't help with that." — classic safety refusal
  - truncated_json:     returns '{"claims": [{"id": 1,' — unterminated
  - unicode_garbage:    returns random high-codepoint chars — encoding path stress
  - hallucinated_cite:  returns well-formed JSON with a fake arxiv_id — evidence mismatch
  - slow_response:      sleeps ``delay`` seconds then returns stub — latency-retry path
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from typing import Any, Callable


class RateLimitError(RuntimeError):
    """Simulated 429 Too Many Requests."""


def _patch_provider(
    fake: Callable[..., Any],
) -> contextlib.AbstractContextManager[None]:
    """Install ``fake`` as the interceptor for every provider.

    Returns a context manager that restores the real get_provider on exit.
    """
    from llm_router import client as llm_client

    @contextlib.contextmanager
    def _cm() -> Iterator[None]:
        original = llm_client.get_provider

        def wrapped(name: str):
            def intercepted(prompt: str, model: str, **kwargs: Any) -> str:
                return fake(name=name, prompt=prompt, model=model, **kwargs)

            return intercepted

        llm_client.get_provider = wrapped
        try:
            yield
        finally:
            llm_client.get_provider = original

    return _cm()


@contextlib.contextmanager
def llm_rate_limit(fail_n: int = 2) -> Iterator[None]:
    """First ``fail_n`` calls raise RateLimitError; the rest return a stub."""
    counter = {"n": 0}

    def fake(**_: Any) -> str:
        counter["n"] += 1
        if counter["n"] <= fail_n:
            raise RateLimitError(f"simulated 429 (call {counter['n']}/{fail_n})")
        return '{"ok": true, "after_rate_limit": true}'

    with _patch_provider(fake):
        yield


@contextlib.contextmanager
def llm_empty_response() -> Iterator[None]:
    """Every call returns the empty string. Tests whether callers treat
    empty as "success with no content" (historical bug) vs "failure"."""
    with _patch_provider(lambda **_: ""):
        yield


@contextlib.contextmanager
def llm_refusal(
    message: str = "I'm sorry, but I can't help with that request.",
) -> Iterator[None]:
    """Every call returns a safety refusal. Callers must surface this
    as a failure with a clear error, not try to JSON-parse it."""
    with _patch_provider(lambda **_: message):
        yield


@contextlib.contextmanager
def llm_truncated_json() -> Iterator[None]:
    """Every call returns unterminated JSON. Stresses the parse+fallback path."""
    with _patch_provider(lambda **_: '{"claims": [{"id": 1, "text": "partial'):
        yield


@contextlib.contextmanager
def llm_unicode_garbage() -> Iterator[None]:
    """Every call returns high-codepoint noise. Historical failure mode
    was encoding-mismatch exceptions that crashed the worker."""
    # Mix of surrogate-adjacent, RTL override, zero-width joiner
    garbage = "\u202e\u200d\U0001f4a9\u0000\uffff\ud83d" * 50
    with _patch_provider(lambda **_: garbage):
        yield


@contextlib.contextmanager
def llm_hallucinated_citation() -> Iterator[None]:
    """Returns well-formed JSON claiming a paper that was never ingested.

    Downstream assert_citations_no_dangling should catch this.
    """
    payload = (
        '{"claims": [{"id": 1, "text": "As shown by Nonexistent et al. (2099).",'
        ' "cite_key": "nonexistent2099"}]}'
    )
    with _patch_provider(lambda **_: payload):
        yield


@contextlib.contextmanager
def llm_slow_response(delay: float = 2.0) -> Iterator[None]:
    """Each call sleeps ``delay`` seconds before returning. Use with a
    small delay (1–3s) to exercise latency-retry logic without making
    tests painful."""

    def fake(**_: Any) -> str:
        time.sleep(delay)
        return '{"ok": true, "slow": true}'

    with _patch_provider(fake):
        yield


__all__ = [
    "RateLimitError",
    "llm_rate_limit",
    "llm_empty_response",
    "llm_refusal",
    "llm_truncated_json",
    "llm_unicode_garbage",
    "llm_hallucinated_citation",
    "llm_slow_response",
]
