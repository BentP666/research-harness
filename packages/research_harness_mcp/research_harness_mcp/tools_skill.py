"""MCP tools for the skill subsystem: ``skill_list`` and ``skill_get``.

Lets agents that prefer runtime pull (no filesystem install) discover and
read RH skills on demand. Coexists with the filesystem-based install path —
both are first-class.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.types import Tool

from research_harness.skill import (
    build_manifest,
    find_repo_root,
    load_manifest,
)


def _skills_root() -> Path:
    """Locate the skills root, preferring a fresh on-disk manifest if present."""

    return find_repo_root()


def _manifest_dict() -> dict[str, Any]:
    root = _skills_root()
    try:
        manifest = load_manifest(root)
    except FileNotFoundError:
        manifest = build_manifest(root)
    return manifest.to_dict()


# ----------------------------- tool implementations --------------------------


def skill_list(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the full skill manifest, optionally filtered by category."""

    data = _manifest_dict()
    category = arguments.get("category")
    if category:
        data["skills"] = [s for s in data["skills"] if s.get("category") == category]
    return data


def skill_get(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return a single skill's SKILL.md (and optional track) contents."""

    name = arguments.get("name")
    if not name:
        return {"error": "missing required argument: name"}

    root = _skills_root()
    try:
        manifest = load_manifest(root)
    except FileNotFoundError:
        manifest = build_manifest(root)

    record = manifest.get(name)
    if record is None:
        return {
            "error": f"unknown skill: {name}",
            "available": manifest.names(),
        }

    skill_md_path = root / record.skill_md
    try:
        skill_md_text = skill_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"could not read {skill_md_path}: {exc}"}

    response: dict[str, Any] = {
        "name": record.name,
        "path": record.path,
        "skill_md_path": record.skill_md,
        "description": record.description,
        "tracks": list(record.tracks),
        "content": skill_md_text,
    }

    track = arguments.get("track")
    if track:
        track_path = root / record.path / "tracks" / f"{track}.md"
        if track_path.is_file():
            response["track"] = {
                "name": track,
                "path": str(track_path.relative_to(root)),
                "content": track_path.read_text(encoding="utf-8"),
            }
        else:
            response["track_error"] = (
                f"track '{track}' not found for skill '{name}'; "
                f"available: {record.tracks}"
            )

    return response


# ----------------------------- MCP tool definitions --------------------------


SKILL_TOOLS: dict[str, Tool] = {
    "skill_list": Tool(
        name="skill_list",
        description=(
            "List every Research Harness skill shipped under the repo's skills/ "
            "directory. Returns the manifest including name, description, tracks, "
            "and category for each skill. Use this to discover what natural-language "
            "triggers and capabilities are available."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g. 'writing').",
                },
            },
        },
    ),
    "skill_get": Tool(
        name="skill_get",
        description=(
            "Return the SKILL.md (and optionally a specific track) for a single "
            "skill. Use after skill_list to fetch the actual skill instructions "
            "the agent should follow. For multi-track skills like paper-writing, "
            "pass `track` to fetch a specific variant (e.g. 'survey-review')."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill name from skill_list (e.g. 'paper-writing').",
                },
                "track": {
                    "type": "string",
                    "description": (
                        "Optional track name for multi-track skills "
                        "(e.g. 'survey-review' under paper-writing)."
                    ),
                },
            },
            "required": ["name"],
        },
    ),
}


SKILL_TOOL_HANDLERS = {
    "skill_list": skill_list,
    "skill_get": skill_get,
}


def execute_skill_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = SKILL_TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown skill tool: {name}"}
    return handler(arguments or {})
