#!/usr/bin/env python3
"""Validate Codex/RH workflow metadata without requiring project dependencies."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover - exercised on bare 3.9 envs
        tomllib = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} is missing YAML frontmatter")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            # YAML list/continuation under a field such as allowed-tools.
            continue
        if ":" not in line:
            raise ValueError(f"{path} has invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')

    raise ValueError(f"{path} frontmatter is not closed")


def skill_dirs() -> list[Path]:
    skills_root = ROOT / "skills"
    return sorted(
        path
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )


def validate_skills() -> list[str]:
    errors: list[str] = []
    seen_names: set[str] = set()

    for directory in skill_dirs():
        skill_md = directory / "SKILL.md"
        try:
            fields = parse_frontmatter(skill_md)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        name = fields.get("name", "")
        description = fields.get("description", "")
        if not name:
            errors.append(f"{skill_md} is missing frontmatter field: name")
        if not description:
            errors.append(f"{skill_md} is missing frontmatter field: description")
        if name in seen_names:
            errors.append(f"duplicate skill name: {name}")
        seen_names.add(name)
        if name and name != directory.name:
            errors.append(f"{skill_md} name {name!r} does not match directory {directory.name!r}")

    return errors


def validate_manifest() -> list[str]:
    manifest_path = ROOT / "skills" / "manifest.json"
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation script should report all parse failures
        return [f"failed to read {manifest_path}: {exc}"]

    entries = manifest.get("skills", [])
    if not isinstance(entries, list):
        return ["skills/manifest.json field 'skills' must be a list"]

    manifest_names = {entry.get("name") for entry in entries if isinstance(entry, dict)}
    directory_names = {path.name for path in skill_dirs()}

    missing = sorted(directory_names - manifest_names)
    extra = sorted(name for name in manifest_names - directory_names if isinstance(name, str))

    for name in missing:
        errors.append(f"skills/manifest.json is missing skill directory: {name}")
    for name in extra:
        errors.append(f"skills/manifest.json references missing skill directory: {name}")

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("skills/manifest.json contains a non-object skill entry")
            continue
        for key in ("name", "path", "skill_md", "description"):
            if not entry.get(key):
                errors.append(f"manifest entry {entry!r} is missing {key}")

    return errors


def validate_codex_config() -> list[str]:
    config_path = ROOT / ".codex" / "config.toml"
    if not config_path.exists():
        return [".codex/config.toml is missing"]
    config_text = config_path.read_text(encoding="utf-8")
    if tomllib is None:
        errors: list[str] = []
        if "[mcp_servers.research-harness]" not in config_text:
            errors.append(".codex/config.toml must define mcp_servers.research-harness")
        if 'command = "bash"' not in config_text:
            errors.append("research-harness MCP should launch through bash wrapper")
        if "scripts/rh-mcp-keychain.sh" not in config_text:
            errors.append("research-harness MCP args should use scripts/rh-mcp-keychain.sh")
        return errors

    try:
        data = tomllib.loads(config_text)
    except Exception as exc:  # noqa: BLE001 - validation script should report TOML failures
        return [f"failed to parse .codex/config.toml: {exc}"]

    servers = data.get("mcp_servers", {})
    if "research-harness" not in servers:
        return [".codex/config.toml must define mcp_servers.research-harness"]

    rh = servers["research-harness"]
    errors: list[str] = []
    if rh.get("command") != "bash":
        errors.append("research-harness MCP should launch through bash wrapper")
    args = rh.get("args", [])
    if not any("scripts/rh-mcp-keychain.sh" in str(arg) for arg in args):
        errors.append("research-harness MCP args should use scripts/rh-mcp-keychain.sh")
    return errors


def validate_repo_skill_bridge() -> list[str]:
    bridge = ROOT / ".agents" / "skills"
    if not bridge.exists():
        return [".agents/skills bridge is missing; Codex may not discover repo skills"]
    if bridge.is_symlink():
        target = os.readlink(bridge)
        if target != "../skills":
            return [f".agents/skills should point to ../skills, found {target!r}"]
        return []
    return [".agents/skills should be a symlink to ../skills to avoid duplicated skill bodies"]


def validate_docs() -> list[str]:
    required = [
        ROOT / "docs" / "agent-guide.md",
        ROOT / "docs" / "codex-workflow.md",
        ROOT / "scripts" / "codex-check.sh",
    ]
    return [f"required file missing: {path.relative_to(ROOT)}" for path in required if not path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    checks = {
        "skills": validate_skills(),
        "manifest": validate_manifest(),
        "codex_config": validate_codex_config(),
        "repo_skill_bridge": validate_repo_skill_bridge(),
        "docs": validate_docs(),
    }
    errors = [error for group in checks.values() for error in group]

    if args.json:
        print(json.dumps({"ok": not errors, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        for name, group_errors in checks.items():
            status = "PASS" if not group_errors else "FAIL"
            print(f"{name}: {status}")
            for error in group_errors:
                print(f"  - {error}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
