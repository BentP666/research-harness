"""LLM replay: record real responses once, replay offline afterward.

Usage:

    # Record mode (one-time, hits real LLM):
    RH_REPLAY_MODE=record RH_REPLAY_FILE=tests/.../survey.jsonl pytest ...

    # Replay mode (default during test runs):
    RH_REPLAY_MODE=replay RH_REPLAY_FILE=tests/.../survey.jsonl pytest ...

    # Miss behavior: fail-fast (record new entries only in explicit record mode).
"""

from .recorder import (
    ReplayMiss,
    install_replay_hook,
    normalize_prompt_hash,
    uninstall_replay_hook,
)

__all__ = [
    "install_replay_hook",
    "uninstall_replay_hook",
    "normalize_prompt_hash",
    "ReplayMiss",
]
