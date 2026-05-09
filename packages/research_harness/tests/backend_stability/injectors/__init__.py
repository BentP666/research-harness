"""Fault injection primitives.

Each injector is a context-manager fixture that makes a specific failure
mode surface at a deterministic point in the pipeline, without relying on
actual network or FS flakiness.

Covered modes (mapped to historical P0/P1):
- rate_limit_cascade: simulate S2/arxiv 429 loop                 → llm.llm_rate_limit
- corrupt_paper_row: mangle a single paper row                   → storage.corrupt_paper_row
- sandbox_timeout:   force experiment subprocess to time out     → (Phase 1 later)
- citation_dangling: inject a \\cite{missingkey} into a draft   → llm.llm_hallucinated_citation
- llm_pathological:  empty / unicode / refusal / truncated       → llm.llm_*
- sqlite_lock:       hold a writer lock                          → storage.sqlite_writer_lock
- migration_drift:   drop an index to simulate broken migration  → storage.drop_index
- fs_error:          EACCES / ENOSPC on artifact write           → filesystem.*
- network_outage:    provider HTTP down                          → network.*

Import from the submodule::

    from ..injectors.llm import llm_rate_limit
    from ..injectors.storage import corrupt_paper_row, sqlite_writer_lock
"""

from .filesystem import disk_full_on_write, missing_pdf, readonly_path
from .llm import (
    RateLimitError,
    llm_empty_response,
    llm_hallucinated_citation,
    llm_rate_limit,
    llm_refusal,
    llm_slow_response,
    llm_truncated_json,
    llm_unicode_garbage,
)
from .network import (
    FailingProvider,
    RateLimitedProvider,
    fake_provider_suite,
    http_5xx,
    http_timeout,
    network_outage,
)
from .storage import corrupt_paper_row, drop_index, sqlite_writer_lock

__all__ = [
    # llm
    "RateLimitError",
    "llm_empty_response",
    "llm_hallucinated_citation",
    "llm_rate_limit",
    "llm_refusal",
    "llm_slow_response",
    "llm_truncated_json",
    "llm_unicode_garbage",
    # storage
    "corrupt_paper_row",
    "drop_index",
    "sqlite_writer_lock",
    # filesystem
    "disk_full_on_write",
    "missing_pdf",
    "readonly_path",
    # network
    "FailingProvider",
    "RateLimitedProvider",
    "fake_provider_suite",
    "http_5xx",
    "http_timeout",
    "network_outage",
]
