"""Local subprocess sandbox for experiment execution.

Runs experiment code in an isolated subprocess with timeout,
captures stdout/stderr, and parses metrics.

Adapted from AutoResearchClaw (MIT license).
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .metric_parser import detect_nan_divergence, parse_metrics

logger = logging.getLogger(__name__)

# Default LLM API keys that transparently flow into agent experiments.
DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "HUGGINGFACE_TOKEN",
        "HF_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
        "OPENROUTER_API_KEY",
        "REPLICATE_API_TOKEN",
        "PERPLEXITY_API_KEY",
        "WANDB_API_KEY",
    }
)


def build_experiment_env(
    *,
    extra_env: dict[str, str] | None = None,
    allowlist: frozenset[str] | set[str] | None = None,
    include_path: bool = True,
) -> dict[str, str]:
    """Compose the subprocess env for an experiment.

    Starts with the allowlisted subset of the parent env (LLM keys,
    auxiliary URLs) plus PATH/HOME/LANG/TERM/TMPDIR so Python can start up,
    then overlays ``extra_env`` (spec-declared extras).
    """
    allow = frozenset(allowlist) if allowlist is not None else DEFAULT_ENV_ALLOWLIST
    env: dict[str, str] = {}

    # Minimum infrastructure vars for Python startup.
    baseline = ["PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "PYTHONPATH"]
    if include_path:
        for key in baseline:
            val = os.environ.get(key)
            if val is not None:
                env[key] = val

    # Allowlisted secrets from parent.
    for key in allow:
        val = os.environ.get(key)
        if val:
            env[key] = val

    # Spec-level extras win over parent.
    if extra_env:
        for key, val in extra_env.items():
            env[key] = str(val)

    return env


@dataclass(frozen=True)
class SandboxResult:
    """Result of running an experiment in the sandbox."""

    returncode: int
    stdout: str
    stderr: str
    elapsed_sec: float
    metrics: dict[str, float] = field(default_factory=dict)
    timed_out: bool = False
    divergence: str = ""
    code_hash: str = ""


def run_experiment(
    code: str | None = None,
    *,
    files: dict[str, str] | None = None,
    entry_point: str = "main.py",
    timeout_sec: float = 300.0,
    work_dir: Path | None = None,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    env_allowlist: frozenset[str] | set[str] | None = None,
) -> SandboxResult:
    """Execute experiment code in a subprocess sandbox.

    Accepts either a single-file ``code`` string (written to ``entry_point``)
    or a multi-file ``files`` dict (all written to ``work_dir``, entry_point
    decides the invocation target). Uses the RH interpreter (``sys.executable``)
    so the experiment inherits RH's installed Python packages.

    When ``env`` is provided it is used verbatim. Otherwise a minimal allowlist
    of LLM API keys (see ``build_experiment_env``) is composed from ``os.environ``
    and overlaid with ``extra_env``.
    """
    import time

    # Normalize inputs: prefer files, fall back to code.
    if files is None:
        files = {}
    if code and entry_point not in files:
        files = dict(files)
        files[entry_point] = code
    if not files:
        raise ValueError("run_experiment requires either 'code' or 'files'")
    if entry_point not in files:
        raise ValueError(
            f"entry_point {entry_point!r} not present in files: {sorted(files)}"
        )

    entry_code = files[entry_point]
    code_hash = hashlib.sha256(entry_code.encode()).hexdigest()[:16]

    # Create work directory
    if work_dir is None:
        tmp = tempfile.mkdtemp(prefix="rh_experiment_")
        work_dir = Path(tmp)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Write all files (nested paths supported).
    for rel_path, content in files.items():
        target = work_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    entry_path = work_dir / entry_point

    # Compose subprocess env.
    if env is None:
        run_env = build_experiment_env(extra_env=extra_env, allowlist=env_allowlist)
    else:
        run_env = dict(env)
        if extra_env:
            for k, v in extra_env.items():
                run_env[k] = str(v)

    # Run
    start = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            [sys.executable, str(entry_path)],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(work_dir),
            env=run_env,
        )
        elapsed = time.monotonic() - start
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        timed_out = True
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        returncode = -1

    # Parse metrics and detect divergence
    metrics = parse_metrics(stdout)
    divergence = detect_nan_divergence(stdout, stderr)

    return SandboxResult(
        returncode=returncode,
        stdout=stdout[-5000:],  # Cap to avoid memory issues
        stderr=stderr[-2000:],
        elapsed_sec=elapsed,
        metrics=metrics,
        timed_out=timed_out,
        divergence=divergence,
        code_hash=code_hash,
    )


def is_improvement(
    new_value: float,
    best_value: float,
    *,
    direction: str = "maximize",
    min_delta: float = 0.0,
) -> bool:
    """Check if new_value improves over best_value."""
    if direction == "maximize":
        return new_value > best_value + min_delta
    return new_value < best_value - min_delta
