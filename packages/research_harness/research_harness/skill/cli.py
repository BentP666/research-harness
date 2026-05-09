"""Click subcommands for ``rh skill ...``.

Wired into the main CLI in :mod:`research_harness.cli` via ``register(main)``.
Kept in its own module so the 4k-line top-level cli.py doesn't grow further.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from . import (
    AgentConfig,
    CONFIG_FILENAME,
    build_manifest,
    find_agent_config,
    find_repo_root,
    install as install_skills,
    load_agent_config,
    load_manifest,
    make_explicit_config,
    verify as verify_skills,
    which as which_skill,
    write_manifest,
)


# ----------------------------- shared helpers --------------------------------


def _resolve_skills_root(skills_root: str | None) -> Path:
    if skills_root:
        return Path(skills_root).expanduser().resolve()
    return find_repo_root()


def _resolve_config(
    target: str | None,
    agent_profile: str | None,
    repo_root: Path,
) -> AgentConfig:
    """Pick the right :class:`AgentConfig` for an install/verify call."""

    if target:
        return make_explicit_config(Path(target).expanduser().resolve())

    if agent_profile:
        # Allow either a bare name (resolved to skills/agent-profiles/<name>.toml)
        # or a path to a TOML file.
        as_path = Path(agent_profile).expanduser()
        if as_path.suffix == ".toml" and as_path.is_file():
            return load_agent_config(as_path)
        candidate = repo_root / "skills" / "agent-profiles" / f"{agent_profile}.toml"
        if candidate.is_file():
            return load_agent_config(candidate)
        raise click.ClickException(
            f"agent profile '{agent_profile}' not found "
            f"(looked in {candidate} and as a direct path)"
        )

    cfg_path = find_agent_config()
    if cfg_path is None:
        raise click.ClickException(
            f"no {CONFIG_FILENAME} found. Pass --target PATH or --agent NAME, "
            "or drop a .rh-agent.toml in this directory. See "
            "skills/agent-profiles/ for examples."
        )
    return load_agent_config(cfg_path)


def _emit(ctx: click.Context, payload: object, text_fn) -> None:
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    text_fn()


# ----------------------------- subcommands -----------------------------------


@click.group("skill")
def skill_group() -> None:
    """Manage Research Harness skills (index, install, verify)."""


@skill_group.command("index")
@click.option(
    "--skills-root",
    default=None,
    help="Repo root that contains the skills/ directory. Auto-detected if omitted.",
)
@click.option(
    "--write/--no-write",
    default=True,
    help="Write skills/manifest.json (default) or just print.",
)
@click.pass_context
def skill_index(
    ctx: click.Context,
    skills_root: str | None,
    write: bool,
) -> None:
    """Rebuild skills/manifest.json from SKILL.md front-matter."""

    root = _resolve_skills_root(skills_root)
    manifest = build_manifest(root)
    if write:
        path = write_manifest(manifest, root)
        click.echo(f"Indexed {len(manifest.skills)} skills -> {path}")
    else:
        click.echo(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))


@skill_group.command("list")
@click.option("--skills-root", default=None)
@click.option(
    "--triggers", is_flag=True, help="Show full description (incl. triggers)."
)
@click.pass_context
def skill_list(
    ctx: click.Context,
    skills_root: str | None,
    triggers: bool,
) -> None:
    """List every shipped skill."""

    root = _resolve_skills_root(skills_root)
    try:
        manifest = load_manifest(root)
    except FileNotFoundError:
        manifest = build_manifest(root)

    payload = manifest.to_dict()
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return

    for s in manifest.skills:
        line = f"  {s.name:24s}"
        if s.tracks:
            line += f"  ({len(s.tracks)} tracks)"
        click.echo(line)
        if triggers and s.description:
            click.echo(f"      {s.description}")
    click.echo(f"\nTotal: {len(manifest.skills)} skills under {manifest.skills_dir}/")


@skill_group.command("install")
@click.argument("names", nargs=-1)
@click.option("--skills-root", default=None, help="Repo root with skills/ directory.")
@click.option("--target", default=None, help="Force install path; bypass agent config.")
@click.option(
    "--agent",
    "agent_profile",
    default=None,
    help="Use a profile from skills/agent-profiles/<NAME>.toml or a path to a .toml.",
)
@click.option("--dry-run", is_flag=True, help="Show what would happen, no writes.")
@click.pass_context
def skill_install(
    ctx: click.Context,
    names: tuple[str, ...],
    skills_root: str | None,
    target: str | None,
    agent_profile: str | None,
    dry_run: bool,
) -> None:
    """Install skills into the agent's expected location.

    Without --target/--agent, looks up .rh-agent.toml from CWD upward.
    """

    root = _resolve_skills_root(skills_root)
    try:
        manifest = load_manifest(root)
    except FileNotFoundError:
        manifest = build_manifest(root)
        write_manifest(manifest, root)

    config = _resolve_config(target, agent_profile, root)
    report = install_skills(
        manifest,
        config,
        root,
        dry_run=dry_run,
        only=list(names) or None,
    )

    if ctx.obj and ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "config_source": str(report.config_source),
                    "agent_name": report.agent_name,
                    "strategy": report.strategy,
                    "install_path": str(report.install_path),
                    "results": [
                        {
                            "name": r.name,
                            "target": str(r.target),
                            "action": r.action,
                            "reason": r.reason,
                        }
                        for r in report.results
                    ],
                },
                ensure_ascii=False,
            )
        )
        return

    click.echo(
        f"agent={report.agent_name} strategy={report.strategy} "
        f"target={report.install_path}"
    )
    click.echo(f"config: {report.config_source}")
    for r in report.results:
        marker = {
            "created": "+",
            "updated": "~",
            "skipped": "=",
            "error": "!",
            "runtime-only": "@",
        }.get(r.action, "?")
        suffix = f"  ({r.reason})" if r.reason else ""
        click.echo(f"  {marker} {r.name:24s} -> {r.target}{suffix}")
    counts = report.by_action()
    click.echo("summary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


@skill_group.command("verify")
@click.option("--skills-root", default=None)
@click.option("--target", default=None)
@click.option("--agent", "agent_profile", default=None)
@click.pass_context
def skill_verify(
    ctx: click.Context,
    skills_root: str | None,
    target: str | None,
    agent_profile: str | None,
) -> None:
    """Compare installed skills against the manifest."""

    root = _resolve_skills_root(skills_root)
    manifest = load_manifest(root)
    config = _resolve_config(target, agent_profile, root)
    report = verify_skills(manifest, config, root)

    if ctx.obj and ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "agent": report.agent_name,
                    "strategy": report.strategy,
                    "install_path": str(report.install_path),
                    "results": [
                        {
                            "name": r.name,
                            "target": str(r.target),
                            "action": r.action,
                            "reason": r.reason,
                        }
                        for r in report.results
                    ],
                },
                ensure_ascii=False,
            )
        )
        return

    for r in report.results:
        click.echo(f"  [{r.action:8s}] {r.name:24s}  {r.reason}")
    counts = report.by_action()
    click.echo("summary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    bad = sum(counts.get(k, 0) for k in ("missing", "stale", "extra", "error"))
    if bad:
        ctx.exit(1)


@skill_group.command("which")
@click.argument("name")
@click.option("--skills-root", default=None)
@click.option("--target", default=None)
@click.option("--agent", "agent_profile", default=None)
@click.pass_context
def skill_which(
    ctx: click.Context,
    name: str,
    skills_root: str | None,
    target: str | None,
    agent_profile: str | None,
) -> None:
    """Show where a skill would be / is installed."""

    root = _resolve_skills_root(skills_root)
    manifest = load_manifest(root)
    config = _resolve_config(target, agent_profile, root)
    path = which_skill(manifest, config, name)
    if path is None:
        raise click.ClickException(f"skill '{name}' not found in manifest")
    click.echo(str(path))


# ----------------------------- registration ----------------------------------


def register(main_group: click.Group) -> None:
    """Attach this skill subcommand tree to the main ``rh`` CLI."""

    main_group.add_command(skill_group)
