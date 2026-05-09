"""Skill registry and installation for Research Harness.

Skills live under the repo's top-level ``skills/`` directory. Each skill is a
folder containing a ``SKILL.md`` (YAML front-matter + body, the Claude Code /
Codex skill format) plus optional supporting files (tracks, references).

The skill subsystem provides three things:

1. A *manifest* (``skills/manifest.json``) generated from the SKILL.md
   front-matter, machine-readable so any agent can discover what is shipped.
2. A *pull-based install* CLI (``rh skill install``) that reads
   ``.rh-agent.toml`` from the consumer's working directory or repo root,
   determines where the agent wants its skills, and links/copies them there.
3. An MCP-side runtime fallback (``skill_list`` / ``skill_get``) for agents
   that prefer to read skills on demand without filesystem installation.

The point: Research Harness ships a vendor-neutral skill catalog, and each
agent platform declares for itself how to consume it. RH does not need to
know about every agent in advance.
"""

from .manifest import (
    SkillRecord,
    SkillManifest,
    build_manifest,
    load_manifest,
    write_manifest,
    find_repo_root,
    iter_skill_records,
)
from .agent_config import (
    AgentConfig,
    CONFIG_FILENAME,
    find_agent_config,
    load_agent_config,
    make_explicit_config,
)
from .install import (
    InstallReport,
    SkillInstallResult,
    install,
    verify,
    which,
)

__all__ = [
    "SkillRecord",
    "SkillManifest",
    "build_manifest",
    "load_manifest",
    "write_manifest",
    "find_repo_root",
    "iter_skill_records",
    "AgentConfig",
    "CONFIG_FILENAME",
    "find_agent_config",
    "load_agent_config",
    "make_explicit_config",
    "InstallReport",
    "SkillInstallResult",
    "install",
    "verify",
    "which",
]
