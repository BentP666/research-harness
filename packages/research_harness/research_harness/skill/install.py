"""Install (or sync) skills into an agent's expected location.

Three strategies are supported, declared by the agent in ``.rh-agent.toml``:

* ``symlink``  — create a symlink per skill so RH updates flow automatically
  (the default for local development).
* ``copy``     — recursive copy (CI, sandboxes, environments where symlinks
  don't survive — e.g. some package managers).
* ``mcp-runtime`` — no filesystem write at all; the agent reads skills via the
  MCP ``skill_list`` / ``skill_get`` tools at runtime. The CLI in this case
  just prints a status message.

Each install action produces an :class:`InstallReport` describing exactly
what changed, so ``rh skill install`` can show a useful summary and so
``rh skill verify`` can compare current state against the manifest later.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path

from .agent_config import AgentConfig
from .manifest import SkillManifest


@dataclasses.dataclass
class SkillInstallResult:
    name: str
    target: Path
    action: str  # 'created' | 'updated' | 'skipped' | 'error' | 'runtime-only'
    reason: str = ""


@dataclasses.dataclass
class InstallReport:
    config_source: Path
    agent_name: str
    strategy: str
    install_path: Path
    results: list[SkillInstallResult] = dataclasses.field(default_factory=list)

    def by_action(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.action] = counts.get(r.action, 0) + 1
        return counts


# ----------------------------- core helpers ----------------------------------


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _is_our_symlink(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    try:
        return Path(os.readlink(target)).resolve() == source.resolve()
    except OSError:
        return False


def _install_symlink(source: Path, target: Path) -> SkillInstallResult:
    name = target.name
    if target.is_symlink() or target.exists():
        if _is_our_symlink(target, source):
            return SkillInstallResult(name, target, "skipped", "already linked")
        # Remove old link or stale dir/file
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
        target.symlink_to(source.resolve(), target_is_directory=True)
        return SkillInstallResult(name, target, "updated", "relinked")
    target.symlink_to(source.resolve(), target_is_directory=True)
    return SkillInstallResult(name, target, "created", "symlinked")


def _install_copy(source: Path, target: Path) -> SkillInstallResult:
    name = target.name
    if target.exists():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return SkillInstallResult(name, target, "updated", "recopied")
    shutil.copytree(source, target)
    return SkillInstallResult(name, target, "created", "copied")


# ----------------------------- public api ------------------------------------


def install(
    manifest: SkillManifest,
    config: AgentConfig,
    repo_root: Path,
    *,
    dry_run: bool = False,
    only: list[str] | None = None,
) -> InstallReport:
    """Install all skills (or the subset in ``only``) per ``config``.

    The function is idempotent: running it twice in a row produces a report
    where every skill is ``skipped`` on the second run (for ``symlink``).
    """

    selected_names = [s.name for s in manifest.skills]
    if only:
        only_set = set(only)
        selected_names = [n for n in selected_names if n in only_set]
    selected_names = config.filter_skills(selected_names)

    report = InstallReport(
        config_source=config.source,
        agent_name=config.agent_name,
        strategy=config.strategy,
        install_path=config.install_path,
    )

    if config.strategy == "mcp-runtime":
        for name in selected_names:
            report.results.append(
                SkillInstallResult(
                    name=name,
                    target=config.install_path,
                    action="runtime-only",
                    reason="strategy=mcp-runtime; no filesystem install",
                )
            )
        return report

    if not dry_run:
        _ensure_dir(config.install_path)

    for record in manifest.skills:
        if record.name not in selected_names:
            continue
        source = (repo_root / record.path).resolve()
        target_name = config.transform_name(record.name)
        target = config.install_path / target_name

        if dry_run:
            report.results.append(
                SkillInstallResult(record.name, target, "skipped", "dry-run")
            )
            continue

        try:
            if config.strategy == "symlink":
                result = _install_symlink(source, target)
            elif config.strategy == "copy":
                result = _install_copy(source, target)
            else:  # pragma: no cover - validated upstream
                result = SkillInstallResult(
                    record.name,
                    target,
                    "error",
                    f"unknown strategy: {config.strategy}",
                )
        except OSError as exc:
            result = SkillInstallResult(record.name, target, "error", str(exc))
        report.results.append(result)

    return report


def verify(
    manifest: SkillManifest,
    config: AgentConfig,
    repo_root: Path,
) -> InstallReport:
    """Check whether installed skills match the manifest.

    Each skill is reported as one of:

    * ``ok``       — present and (for symlink) points to the right source
    * ``missing``  — manifest lists it but it isn't installed
    * ``stale``    — installed but doesn't match the manifest source
    * ``extra``    — present at install_path but not in the manifest
    """

    report = InstallReport(
        config_source=config.source,
        agent_name=config.agent_name,
        strategy=config.strategy,
        install_path=config.install_path,
    )
    if config.strategy == "mcp-runtime":
        report.results.append(
            SkillInstallResult(
                name="(all)",
                target=config.install_path,
                action="runtime-only",
                reason="strategy=mcp-runtime",
            )
        )
        return report

    expected_names = config.filter_skills([s.name for s in manifest.skills])
    expected_targets: dict[str, Path] = {}
    for record in manifest.skills:
        if record.name in expected_names:
            expected_targets[record.name] = (repo_root / record.path).resolve()

    install_path = config.install_path
    if not install_path.is_dir():
        for name in expected_names:
            target = install_path / config.transform_name(name)
            report.results.append(
                SkillInstallResult(name, target, "missing", "install_path absent")
            )
        return report

    actual_dirs = {
        p.name: p for p in install_path.iterdir() if p.is_dir() or p.is_symlink()
    }

    for name in expected_names:
        transformed = config.transform_name(name)
        target = install_path / transformed
        if transformed not in actual_dirs:
            report.results.append(
                SkillInstallResult(name, target, "missing", "not installed")
            )
            continue
        installed = actual_dirs[transformed]
        if installed.is_symlink():
            if _is_our_symlink(installed, expected_targets[name]):
                report.results.append(SkillInstallResult(name, target, "ok", "symlink"))
            else:
                report.results.append(
                    SkillInstallResult(name, target, "stale", "symlink mismatch")
                )
        else:
            # Best-effort copy check via SKILL.md byte equality.
            src_md = expected_targets[name] / "SKILL.md"
            tgt_md = installed / "SKILL.md"
            try:
                if (
                    tgt_md.is_file()
                    and src_md.is_file()
                    and tgt_md.read_bytes() == src_md.read_bytes()
                ):
                    report.results.append(
                        SkillInstallResult(name, target, "ok", "copy")
                    )
                else:
                    report.results.append(
                        SkillInstallResult(name, target, "stale", "copy out of date")
                    )
            except OSError as exc:
                report.results.append(
                    SkillInstallResult(name, target, "error", str(exc))
                )

    expected_dirnames = {config.transform_name(n) for n in expected_names}
    for dirname, _path in actual_dirs.items():
        if dirname not in expected_dirnames:
            report.results.append(
                SkillInstallResult(
                    name=dirname,
                    target=install_path / dirname,
                    action="extra",
                    reason="not in manifest",
                )
            )

    return report


def which(
    manifest: SkillManifest,
    config: AgentConfig,
    name: str,
) -> Path | None:
    """Return the resolved path where a given skill was installed."""

    if config.strategy == "mcp-runtime":
        return None
    record = manifest.get(name)
    if record is None:
        return None
    return config.install_path / config.transform_name(name)
