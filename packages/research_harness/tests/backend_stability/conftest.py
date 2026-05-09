"""Tier-aware pytest configuration for backend_stability tests.

Adds a ``--tier`` CLI option that auto-translates to pytest marker
filters. Without ``--tier``, runs the smoke tier (safest default).

Usage:
    pytest packages/research_harness/tests/backend_stability --tier smoke
    pytest packages/research_harness/tests/backend_stability --tier pre_merge
    pytest packages/research_harness/tests/backend_stability --tier nightly

Tier semantics live in packages/research_harness/pyproject.toml.
"""

from __future__ import annotations

import os

import pytest

from .replay.recorder import install_replay_hook, uninstall_replay_hook

_VALID_TIERS = ("smoke", "pre_merge", "nightly", "all")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--tier",
        action="store",
        default=os.environ.get("RH_TEST_TIER", "smoke"),
        choices=_VALID_TIERS,
        help=(
            "Which test tier to run. smoke=<3min structural checks, "
            "pre_merge=<15min with record-or-replay, nightly=full E2E with "
            "live LLM. Default: smoke."
        ),
    )
    parser.addoption(
        "--replay-mode",
        action="store",
        default=os.environ.get("RH_REPLAY_MODE", "replay"),
        choices=("record", "replay", "auto"),
        help="LLM replay mode: record hits real LLM, replay is cache-only, auto stubs on miss.",
    )
    parser.addoption(
        "--replay-file",
        action="store",
        default=os.environ.get(
            "RH_REPLAY_FILE",
            str(_default_replay_path()),
        ),
        help="Path to jsonl replay cache.",
    )


def _default_replay_path() -> str:
    from pathlib import Path

    return str(Path(__file__).parent / "replay" / "cache" / "default.jsonl")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests that don't match the selected tier.

    Selection rules:
      smoke     → only items marked @pytest.mark.smoke OR @pytest.mark.regression
      pre_merge → smoke + pre_merge + regression
      nightly   → everything
      all       → everything (explicit override)
    """
    tier = config.getoption("--tier")
    if tier == "all" or tier == "nightly":
        return  # collect everything

    allowed: set[str]
    if tier == "smoke":
        allowed = {"smoke", "regression"}
    else:  # pre_merge
        allowed = {"smoke", "pre_merge", "regression"}

    skip_marker = pytest.mark.skip(
        reason=f"tier={tier} — this test needs a higher tier"
    )
    for item in items:
        marks = {m.name for m in item.iter_markers()}
        # Un-marked tests default to pre_merge (must be explicit about tier)
        if not marks & {"smoke", "pre_merge", "nightly", "regression"}:
            marks.add("pre_merge")
        if not marks & allowed:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session", autouse=True)
def _install_llm_replay(request: pytest.FixtureRequest):
    """Install the LLM record/replay hook for the whole backend_stability session."""
    mode = request.config.getoption("--replay-mode")
    cache_file = request.config.getoption("--replay-file")
    try:
        install_replay_hook(cache_path=cache_file, mode=mode)
    except Exception as exc:  # noqa: BLE001 — hook is best-effort at collection
        pytest.skip(f"cannot install LLM replay hook: {exc}")
    yield
    uninstall_replay_hook()
