"""Agent self-declaration config — ``.rh-agent.toml``.

Each agent platform that wants to consume Research Harness skills declares,
in its own repo or working directory, **where** to install skills, **what
format** the agent expects, and **how** to deliver them (symlink / copy /
runtime). RH itself does not need to know about the agent in advance.

A minimal config:

    # .rh-agent.toml
    [agent]
    name = "claude-code"

    [skills]
    install_path = "~/.claude/skills"   # required (env vars + ~ expanded)
    format       = "claude-skill-md"    # optional, default "claude-skill-md"
    strategy     = "symlink"            # optional: symlink | copy | mcp-runtime

A more involved config:

    [agent]
    name = "openclaw"
    version = ">=0.4"

    [skills]
    install_path = "${OPENCLAW_HOME}/skills"
    format       = "claude-skill-md"
    strategy     = "copy"
    # Per-skill flat-name remap (optional). Most agents don't need this.
    naming       = "kebab"              # kebab | snake | as-is

    [skills.include]
    only = ["paper-writing", "literature-search", "gap-analysis"]

    [skills.exclude]
    names = ["task-taxonomy"]            # reference-only skills

Lookup order when ``rh skill install`` runs without ``--target`` / ``--agent``:

1. ``$RH_AGENT_CONFIG`` env var (explicit path)
2. ``./.rh-agent.toml`` in CWD
3. Walk up from CWD until a ``.rh-agent.toml`` is found OR a ``.git``
   directory is hit (treat that as repo root)
4. ``~/.config/research-harness/agent.toml`` (user-global default)

If none are found, ``rh skill install`` refuses to guess and exits with a
hint. (We don't auto-detect by sniffing for ``.claude/`` or ``.codex/``
directories — that produced the brittle hard-coded mapping we are explicitly
trying to avoid.)
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


CONFIG_FILENAME = ".rh-agent.toml"
USER_CONFIG_PATH = Path("~/.config/research-harness/agent.toml").expanduser()
ENV_CONFIG_VAR = "RH_AGENT_CONFIG"


VALID_STRATEGIES = {"symlink", "copy", "mcp-runtime"}
DEFAULT_STRATEGY = "symlink"
DEFAULT_FORMAT = "claude-skill-md"


@dataclasses.dataclass
class IncludeRule:
    only: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ExcludeRule:
    names: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class AgentConfig:
    """Parsed ``.rh-agent.toml``.

    Attributes:
        source: Path to the file this config came from (for diagnostics).
        agent_name: Free-form name the agent gives itself.
        agent_version: Optional version constraint (informational only).
        install_path: Resolved absolute path where skills should be installed.
        format: The SKILL.md format the agent expects. Currently only
            ``claude-skill-md`` is shipped, but the field exists so future
            adapters can declare alternative formats.
        strategy: ``symlink`` | ``copy`` | ``mcp-runtime``.
        naming: Optional naming transform applied to skill directory names.
        include: ``only=[...]`` whitelist (empty = all skills).
        exclude: ``names=[...]`` blacklist applied after include.
        extras: Forward-compatible bucket for unknown TOML keys.
    """

    source: Path
    agent_name: str
    agent_version: str | None
    install_path: Path
    format: str
    strategy: str
    naming: str
    include: IncludeRule
    exclude: ExcludeRule
    extras: dict[str, Any]

    def filter_skills(self, names: list[str]) -> list[str]:
        if self.include.only:
            keep = [n for n in names if n in self.include.only]
        else:
            keep = list(names)
        if self.exclude.names:
            keep = [n for n in keep if n not in self.exclude.names]
        return keep

    def transform_name(self, name: str) -> str:
        if self.naming == "snake":
            return name.replace("-", "_")
        if self.naming == "kebab":
            return name.replace("_", "-")
        return name


# ----------------------------- discovery -------------------------------------


def find_agent_config(start: Path | None = None) -> Path | None:
    """Locate the agent config file, returning ``None`` if not found.

    Order: env override -> CWD/parents (until .git) -> user-global.
    """

    env_path = os.environ.get(ENV_CONFIG_VAR)
    if env_path:
        p = Path(env_path).expanduser()
        if p.is_file():
            return p
        return None  # explicit path missing is an error the caller surfaces

    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        cfg = candidate / CONFIG_FILENAME
        if cfg.is_file():
            return cfg
        if (candidate / ".git").exists():
            break  # don't escape the current repo

    if USER_CONFIG_PATH.is_file():
        return USER_CONFIG_PATH

    return None


def _expand(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value))


def _require(table: dict[str, Any], key: str, source: Path) -> Any:
    if key not in table:
        raise ValueError(f"{source}: missing required key '{key}'")
    return table[key]


def load_agent_config(path: Path) -> AgentConfig:
    """Parse a ``.rh-agent.toml`` file into an :class:`AgentConfig`."""

    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    agent = raw.get("agent") or {}
    skills = raw.get("skills") or {}

    if not agent.get("name"):
        raise ValueError(f"{path}: [agent].name is required")

    install_path_str = _require(skills, "install_path", path)
    install_path = Path(_expand(str(install_path_str))).expanduser()

    fmt = str(skills.get("format") or DEFAULT_FORMAT)
    strategy = str(skills.get("strategy") or DEFAULT_STRATEGY)
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"{path}: skills.strategy='{strategy}' is invalid; "
            f"expected one of {sorted(VALID_STRATEGIES)}"
        )

    naming = str(skills.get("naming") or "as-is")
    if naming not in {"as-is", "kebab", "snake"}:
        raise ValueError(
            f"{path}: skills.naming='{naming}' is invalid; "
            "expected as-is | kebab | snake"
        )

    include_table = skills.get("include") or {}
    exclude_table = skills.get("exclude") or {}
    include = IncludeRule(only=[str(x) for x in include_table.get("only") or []])
    exclude = ExcludeRule(names=[str(x) for x in exclude_table.get("names") or []])

    consumed = {
        "install_path",
        "format",
        "strategy",
        "naming",
        "include",
        "exclude",
    }
    extras = {k: v for k, v in skills.items() if k not in consumed}

    return AgentConfig(
        source=path,
        agent_name=str(agent["name"]),
        agent_version=str(agent.get("version")) if agent.get("version") else None,
        install_path=install_path,
        format=fmt,
        strategy=strategy,
        naming=naming,
        include=include,
        exclude=exclude,
        extras=extras,
    )


# ----------------------------- ad-hoc construction ---------------------------


def make_explicit_config(
    install_path: Path,
    *,
    agent_name: str = "explicit",
    strategy: str = DEFAULT_STRATEGY,
    fmt: str = DEFAULT_FORMAT,
) -> AgentConfig:
    """Build an :class:`AgentConfig` from CLI flags (``--target``).

    Used when the user passes ``--target PATH`` and skips the discovery file.
    """

    return AgentConfig(
        source=Path("<cli>"),
        agent_name=agent_name,
        agent_version=None,
        install_path=install_path,
        format=fmt,
        strategy=strategy,
        naming="as-is",
        include=IncludeRule(),
        exclude=ExcludeRule(),
        extras={},
    )
