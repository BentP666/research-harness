"""Network-layer fault injectors.

Uses pytest monkeypatch against common HTTP client symbols in the
codebase. Goal: simulate outage, timeout, and 5xx without spinning up a
real mock server. The fake proxy mock (Phase 0.4) handles the
programmable-LLM case; these injectors target paper-search providers
(arxiv, s2, openalex).

Two classes of injector here:
1. Low-level HTTP patches (``network_outage``, ``http_5xx``,
   ``http_timeout``) — useful when the provider chain is opaque and we
   just want every outbound call to fail uniformly.
2. Provider-suite patches (``fake_provider_suite``, ``failing_provider``)
   — plug a controlled fake at the ``build_provider_suite`` seam so
   paper_search sees a deterministic provider that raises a named
   exception. The aggregator's per-provider try/except records these
   into ``provider_errors`` and the test asserts on that structured
   output rather than relying on which HTTP library the provider uses.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest


@contextlib.contextmanager
def network_outage(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make every outbound HTTP request raise ConnectionError.

    Patches ``requests.request``, ``requests.Session.request``, and
    ``httpx.Client.send``. Anything else (raw socket, aiohttp) will still
    escape — add more patches as the codebase grows.
    """

    def _die(*args, **kwargs):  # noqa: ANN002,ANN003
        raise ConnectionError("simulated network outage")

    targets = [
        "requests.request",
        "requests.Session.request",
        "urllib.request.urlopen",
    ]
    for dotted in targets:
        try:
            monkeypatch.setattr(dotted, _die)
        except (AttributeError, ImportError):
            continue

    try:
        import httpx

        monkeypatch.setattr(httpx.Client, "send", _die)
    except ImportError:
        pass

    yield


@contextlib.contextmanager
def http_5xx(monkeypatch: pytest.MonkeyPatch, status_code: int = 503) -> Iterator[None]:
    """Every ``requests`` call returns a response with ``status_code``.

    Callers that blindly assume 200 will pass garbage downstream; callers
    that check status will treat it as a retryable error.
    """

    class _FakeResponse:
        def __init__(self):
            self.status_code = status_code
            self.text = "Service Unavailable"
            self.headers = {"Retry-After": "1"}
            self.content = self.text.encode()

        def json(self):
            raise ValueError("not JSON")

        def raise_for_status(self):
            from requests import HTTPError

            raise HTTPError(f"{status_code} Server Error", response=self)

    def _fake_request(*args, **kwargs):  # noqa: ANN002,ANN003
        return _FakeResponse()

    try:
        monkeypatch.setattr("requests.request", _fake_request)
        monkeypatch.setattr("requests.Session.request", _fake_request)
    except (AttributeError, ImportError):
        pytest.skip("requests not installed")
    yield


@contextlib.contextmanager
def http_timeout(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every ``requests`` call raises ``requests.Timeout``."""
    try:
        import requests as _req
    except ImportError:
        pytest.skip("requests not installed")

    def _timeout(*args, **kwargs):  # noqa: ANN002,ANN003
        raise _req.Timeout("simulated timeout")

    monkeypatch.setattr("requests.request", _timeout)
    monkeypatch.setattr("requests.Session.request", _timeout)
    yield


__all__ = [
    "network_outage",
    "http_5xx",
    "http_timeout",
    "RateLimitedProvider",
    "FailingProvider",
    "fake_provider_suite",
]


# ---------------------------------------------------------------------------
# Provider-suite injectors (paper_search)
# ---------------------------------------------------------------------------


@dataclass
class RateLimitedProvider:
    """A SearchProvider that raises on the first ``fail_n`` calls.

    Used by the s2 rate-limit regression test: the aggregator catches the
    exception and records a ``ProviderError(provider='s2', ...)`` so the
    rest of the search pipeline can keep going without dropping papers
    silently.
    """

    name: str = "s2"
    fail_n: int = 1
    error_type: type[Exception] = RuntimeError
    error_message: str = "429 Too Many Requests"
    _calls: int = field(default=0, init=False)

    def search(self, query: Any) -> list[Any]:  # noqa: ANN401 — duck typed
        self._calls += 1
        if self._calls <= self.fail_n:
            raise self.error_type(self.error_message)
        return []


@dataclass
class FailingProvider:
    """A SearchProvider whose search() always raises.

    Used by the academic-outage regression test: every external provider
    is down, so the aggregator should record one ProviderError per
    provider AND paper_search.provider_errors must be non-empty (i.e.
    the outage is surfaced, not silently mapped to "0 results found").
    """

    name: str = "arxiv"
    error_type: type[Exception] = ConnectionError
    error_message: str = "simulated outage"

    def search(self, query: Any) -> list[Any]:  # noqa: ANN401
        raise self.error_type(self.error_message)


@contextlib.contextmanager
def fake_provider_suite(
    monkeypatch: pytest.MonkeyPatch, providers: list[Any]
) -> Iterator[None]:
    """Replace ``build_provider_suite()`` with a closure returning the
    given list of provider instances.

    Important: paper_search imports build_provider_suite from
    ``research_harness.primitives.impls`` (re-exported), so patching the
    primitive-side symbol is enough — the aggregator picks them up via
    the function call.
    """
    monkeypatch.setattr(
        "research_harness.primitives.impls.build_provider_suite",
        lambda **_kw: list(providers),
    )
    yield
