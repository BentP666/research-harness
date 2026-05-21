"""Deterministic validators for ResearchFlowBench Pilot-20 task packs.

The validator is intentionally read-only. It parses task-pack files, checks
manifest/hash consistency, and enforces gold/judge visibility contracts before
any model execution is allowed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


REQUIRED_TASK_FILES = (
    "task.json",
    "prompt.md",
    "input_bundle.json",
    "gold_bundle.json",
    "judge_bundle.json",
    "tool_fixtures/allowed_tools_contract.json",
    "tool_fixtures/visible_input_manifest.json",
    "tool_fixtures/local_static_corpus.jsonl",
    "calibration_refs/dev_example_ids.json",
)

REQUIRED_PACK_FILES = (
    "pilot20_manifest_draft.json",
    "goldgraph_seed_assets.jsonl",
    "corrupted_evidence_cases.jsonl",
    "schemas/goldgraph_asset_schema_v0.json",
    "schemas/semantic_object_contract_v0_1.json",
)

REQUIRED_ASSET_FIELDS = {
    "pack_id",
    "schema_version",
    "asset_id",
    "asset_type",
    "maps_to_semantic_object_type",
    "content",
    "source_refs",
    "status",
}

REQUIRED_CORRUPTION_FIELDS = {
    "case_id",
    "task",
    "clean_objects",
    "corrupted_prompt_object",
    "expected_states",
    "expected_edges",
    "affected_downstream_objects",
    "preserved_objects",
    "outcome_oracle",
    "process_oracle",
    "semantic_trigger_type",
}

FORBIDDEN_EXTERNAL_TOOLS = {
    "external_search",
    "web_search",
    "paper_search",
    "browser_network_search",
}

EXPECTED_TASK_NUMBERS = ("T01", "T02", "T03", "T04", "T05")

PILOT20_REQUIRED_OBJECTS_BY_TASK_NO = {
    "T01": {
        "claim",
        "citation_link",
        "evidence_span",
        "review_issue",
        "gate_decision",
        "run_trace",
    },
    "T02": {
        "paper",
        "claim",
        "evidence_span",
        "citation_link",
        "review_issue",
        "gate_decision",
        "run_trace",
    },
    "T03": {
        "claim",
        "evidence_span",
        "citation_link",
        "review_issue",
        "gate_decision",
        "run_trace",
    },
    "T04": {
        "evidence_span",
        "citation_link",
        "claim",
        "section_draft",
        "gate_decision",
        "rollback_event",
        "run_trace",
    },
    "T05": {
        "claim",
        "baseline",
        "evidence_span",
        "review_issue",
        "gate_decision",
        "rollback_event",
        "run_trace",
    },
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    path: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("ValidationIssue.code is required")
        if not self.severity:
            raise ValueError("ValidationIssue.severity is required")
        object.__setattr__(self, "details", dict(self.details or {}))

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class ValidationReport:
    root: str
    is_valid: bool
    issues: tuple[ValidationIssue, ...] = ()
    checked_task_count: int = 0
    checked_file_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def validate_pilot20_task_pack(root: str | Path) -> ValidationReport:
    """Validate a Pilot-20 T01–T05 task pack without mutating it."""

    root_path = Path(root)
    issues: list[ValidationIssue] = []
    checked_files: set[Path] = set()

    if not root_path.exists():
        return ValidationReport(
            root=str(root_path),
            is_valid=False,
            issues=(
                ValidationIssue(
                    code="task_pack_root_missing",
                    severity="error",
                    message=f"ResearchFlowBench task-pack root does not exist: {root_path}",
                    path=str(root_path),
                ),
            ),
        )

    for rel_path in REQUIRED_PACK_FILES:
        path = root_path / rel_path
        if not path.exists():
            issues.append(
                _issue(
                    "required_pack_file_missing",
                    f"required pack file is missing: {rel_path}",
                    rel_path,
                )
            )
        else:
            checked_files.add(path)

    parse_result = _parse_all_json_files(root_path)
    issues.extend(parse_result.issues)
    checked_files.update(parse_result.checked_files)
    if any(issue.severity == "error" for issue in parse_result.issues):
        return _final_report(
            root_path,
            issues,
            checked_task_count=0,
            checked_file_count=len(checked_files),
        )

    manifest = _load_json(root_path / "pilot20_manifest_draft.json", issues)
    if not isinstance(manifest, dict):
        issues.append(
            _issue(
                "manifest_not_object",
                "pilot20 manifest must be a JSON object",
                "pilot20_manifest_draft.json",
            )
        )
        return _final_report(
            root_path,
            issues,
            checked_task_count=0,
            checked_file_count=len(checked_files),
        )

    asset_records = _load_jsonl(root_path / "goldgraph_seed_assets.jsonl", issues)
    case_records = _load_jsonl(root_path / "corrupted_evidence_cases.jsonl", issues)
    asset_ids = _validate_goldgraph_assets(manifest, asset_records, issues)
    case_ids = _validate_corruption_cases(case_records, issues)
    _validate_manifest_inventory_and_hashes(root_path, manifest, issues, checked_files)

    tasks = list(manifest.get("tasks") or [])
    if len(tasks) != 5:
        issues.append(
            _issue(
                "pilot20_task_count_mismatch",
                "Pilot-20 v0 validator expects exactly T01–T05 task entries",
                "pilot20_manifest_draft.json#/tasks",
                {"task_count": len(tasks)},
            )
        )

    seen_task_numbers: set[str] = set()
    seen_task_ids: set[str] = set()
    for task_entry in tasks:
        if not isinstance(task_entry, dict):
            issues.append(
                _issue(
                    "manifest_task_not_object",
                    "manifest task entry must be an object",
                    "pilot20_manifest_draft.json#/tasks",
                )
            )
            continue
        task_no = str(task_entry.get("task_no") or "")
        seen_task_numbers.add(task_no)
        task_id = str(task_entry.get("task_id") or "")
        if task_id in seen_task_ids:
            issues.append(
                _issue(
                    "task_id_duplicate",
                    f"duplicate manifest task_id: {task_id}",
                    "pilot20_manifest_draft.json#/tasks",
                    {"task_id": task_id},
                )
            )
        seen_task_ids.add(task_id)
        task_dir = root_path / str(task_entry.get("directory") or "")
        _validate_task_directory(
            root_path,
            task_dir,
            manifest,
            task_entry,
            asset_ids,
            case_ids,
            issues,
            checked_files,
        )

    missing_task_numbers = sorted(set(EXPECTED_TASK_NUMBERS) - seen_task_numbers)
    if missing_task_numbers:
        issues.append(
            _issue(
                "pilot20_task_number_missing",
                "Pilot-20 v0 manifest is missing expected T01–T05 task numbers",
                "pilot20_manifest_draft.json#/tasks",
                {"missing_task_numbers": missing_task_numbers},
            )
        )

    return _final_report(
        root_path,
        issues,
        checked_task_count=len(tasks),
        checked_file_count=len(checked_files),
    )


@dataclass(frozen=True)
class _ParseResult:
    issues: tuple[ValidationIssue, ...]
    checked_files: frozenset[Path]


def _parse_all_json_files(root_path: Path) -> _ParseResult:
    issues: list[ValidationIssue] = []
    checked_files: set[Path] = set()
    for path in sorted(root_path.rglob("*.json")):
        checked_files.add(path)
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "json_parse_error",
                    f"invalid JSON: {exc.msg}",
                    _rel(root_path, path),
                    {"line": exc.lineno, "column": exc.colno},
                )
            )
    for path in sorted(root_path.rglob("*.jsonl")):
        checked_files.add(path)
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(
                    _issue(
                        "jsonl_parse_error",
                        f"invalid JSONL line: {exc.msg}",
                        _rel(root_path, path),
                        {"line": line_no, "column": exc.colno},
                    )
                )
    return _ParseResult(tuple(issues), frozenset(checked_files))


def _validate_goldgraph_assets(
    manifest: dict[str, Any], records: list[Any], issues: list[ValidationIssue]
) -> set[str]:
    schema_path = "goldgraph_seed_assets.jsonl"
    allowed_asset_types = set(_load_list_from_manifest_schema(manifest, "asset_types"))
    allowed_object_types = set(_load_contract_object_types(manifest))
    seen_ids: set[str] = set()
    counts: dict[str, int] = {}

    for index, record in enumerate(records, 1):
        path = f"{schema_path}#L{index}"
        if not isinstance(record, dict):
            issues.append(
                _issue(
                    "goldgraph_asset_not_object",
                    "goldgraph asset record must be an object",
                    path,
                )
            )
            continue
        missing = sorted(REQUIRED_ASSET_FIELDS - set(record))
        if missing:
            issues.append(
                _issue(
                    "goldgraph_asset_required_field_missing",
                    "goldgraph asset is missing required fields",
                    path,
                    {"missing": missing},
                )
            )
        asset_id = str(record.get("asset_id") or "")
        if not asset_id:
            issues.append(
                _issue(
                    "goldgraph_asset_id_missing", "goldgraph asset_id is required", path
                )
            )
        elif asset_id in seen_ids:
            issues.append(
                _issue(
                    "goldgraph_asset_id_duplicate",
                    f"duplicate goldgraph asset_id: {asset_id}",
                    path,
                    {"asset_id": asset_id},
                )
            )
        seen_ids.add(asset_id)

        asset_type = str(record.get("asset_type") or "")
        if allowed_asset_types and asset_type not in allowed_asset_types:
            issues.append(
                _issue(
                    "goldgraph_asset_type_unknown",
                    f"unknown goldgraph asset_type: {asset_type}",
                    path,
                    {"asset_type": asset_type},
                )
            )
        counts[asset_type] = counts.get(asset_type, 0) + 1

        object_type = str(record.get("maps_to_semantic_object_type") or "")
        if allowed_object_types and object_type not in allowed_object_types:
            issues.append(
                _issue(
                    "goldgraph_asset_object_type_unknown",
                    f"unknown semantic object type: {object_type}",
                    path,
                    {"object_type": object_type},
                )
            )
        if not isinstance(record.get("source_refs"), list) or not record.get(
            "source_refs"
        ):
            issues.append(
                _issue(
                    "goldgraph_asset_source_refs_missing",
                    "goldgraph asset source_refs must be a non-empty list",
                    path,
                    {"asset_id": asset_id},
                )
            )

    expected_counts = dict(manifest.get("asset_counts") or {})
    for asset_type, expected_count in expected_counts.items():
        actual_count = counts.get(asset_type, 0)
        if actual_count != expected_count:
            issues.append(
                _issue(
                    "goldgraph_asset_count_mismatch",
                    f"goldgraph asset count mismatch for {asset_type}",
                    "pilot20_manifest_draft.json#/asset_counts",
                    {
                        "asset_type": asset_type,
                        "expected": expected_count,
                        "actual": actual_count,
                    },
                )
            )
    return seen_ids


def _validate_corruption_cases(
    records: list[Any], issues: list[ValidationIssue]
) -> set[str]:
    seen_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        path = f"corrupted_evidence_cases.jsonl#L{index}"
        if not isinstance(record, dict):
            issues.append(
                _issue(
                    "corruption_case_not_object",
                    "corruption case record must be an object",
                    path,
                )
            )
            continue
        missing = sorted(REQUIRED_CORRUPTION_FIELDS - set(record))
        if missing:
            issues.append(
                _issue(
                    "corruption_case_required_field_missing",
                    "corruption case missing required oracle fields",
                    path,
                    {"missing": missing},
                )
            )
        case_id = str(record.get("case_id") or "")
        if not case_id:
            issues.append(
                _issue(
                    "corruption_case_id_missing", "corruption case_id is required", path
                )
            )
        elif case_id in seen_ids:
            issues.append(
                _issue(
                    "corruption_case_id_duplicate",
                    f"duplicate corruption case_id: {case_id}",
                    path,
                    {"case_id": case_id},
                )
            )
        seen_ids.add(case_id)
        expected_case_prefix = _case_prefix_for_task(str(record.get("task") or ""))
        if expected_case_prefix and not case_id.startswith(f"{expected_case_prefix}_"):
            issues.append(
                _issue(
                    "corruption_case_id_task_mismatch",
                    "corruption case_id must start with the Cxx counterpart of its Txx task number",
                    path,
                    {"case_id": case_id, "task": record.get("task")},
                )
            )

    expected_case_ids = {
        f"C0{index}_{suffix}"
        for index, suffix in enumerate(
            (
                "full_context_citation_contradiction",
                "open_world_ambiguous_or_missing_source",
                "composite_claim_partial_support",
                "evidence_correction_stale_propagation",
                "false_novelty_missing_close_priors",
            ),
            1,
        )
    }
    if seen_ids != expected_case_ids:
        issues.append(
            _issue(
                "corruption_case_id_set_mismatch",
                "corruption cases must exactly cover C01–C05 v0 oracles",
                "corrupted_evidence_cases.jsonl",
                {"expected": sorted(expected_case_ids), "actual": sorted(seen_ids)},
            )
        )
    return seen_ids


def _validate_manifest_inventory_and_hashes(
    root_path: Path,
    manifest: dict[str, Any],
    issues: list[ValidationIssue],
    checked_files: set[Path],
) -> None:
    inventory = list(manifest.get("file_inventory") or [])
    hashes = dict(manifest.get("file_hashes_sha256") or {})
    for rel_path in inventory:
        path = root_path / rel_path
        if not path.exists():
            issues.append(
                _issue(
                    "manifest_inventory_file_missing",
                    f"manifest inventory file is missing: {rel_path}",
                    f"pilot20_manifest_draft.json#/file_inventory/{rel_path}",
                )
            )
            continue
        checked_files.add(path)
        expected_hash = hashes.get(rel_path)
        if not expected_hash:
            issues.append(
                _issue(
                    "manifest_file_hash_missing",
                    f"manifest file hash is missing: {rel_path}",
                    "pilot20_manifest_draft.json#/file_hashes_sha256",
                    {"path": rel_path},
                )
            )
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            issues.append(
                _issue(
                    "manifest_file_hash_mismatch",
                    f"manifest hash mismatch for {rel_path}",
                    "pilot20_manifest_draft.json#/file_hashes_sha256",
                    {
                        "path": rel_path,
                        "expected": expected_hash,
                        "actual": actual_hash,
                    },
                )
            )

    extra_hash_paths = sorted(set(hashes) - set(inventory))
    if extra_hash_paths:
        issues.append(
            _issue(
                "manifest_hash_without_inventory_entry",
                "manifest contains hashes for paths absent from file_inventory",
                "pilot20_manifest_draft.json#/file_hashes_sha256",
                {"paths": extra_hash_paths},
            )
        )


def _validate_task_directory(
    root_path: Path,
    task_dir: Path,
    manifest: dict[str, Any],
    task_entry: dict[str, Any],
    asset_ids: set[str],
    case_ids: set[str],
    issues: list[ValidationIssue],
    checked_files: set[Path],
) -> None:
    task_rel = _rel(root_path, task_dir)
    if not task_dir.is_dir():
        issues.append(
            _issue(
                "task_directory_missing",
                f"task directory is missing: {task_rel}",
                task_rel,
            )
        )
        return

    for rel_path in REQUIRED_TASK_FILES:
        path = task_dir / rel_path
        if not path.exists():
            issues.append(
                _issue(
                    "required_task_file_missing",
                    f"required task file is missing: {task_rel}/{rel_path}",
                    f"{task_rel}/{rel_path}",
                )
            )
        else:
            checked_files.add(path)

    task = _load_json(task_dir / "task.json", issues)
    input_bundle = _load_json(task_dir / "input_bundle.json", issues)
    gold_bundle = _load_json(task_dir / "gold_bundle.json", issues)
    judge_bundle = _load_json(task_dir / "judge_bundle.json", issues)
    allowed_tools = _load_json(
        task_dir / "tool_fixtures/allowed_tools_contract.json", issues
    )
    visible_manifest = _load_json(
        task_dir / "tool_fixtures/visible_input_manifest.json", issues
    )
    calibration_refs = _load_json(
        task_dir / "calibration_refs/dev_example_ids.json", issues
    )
    local_corpus = _load_jsonl(
        task_dir / "tool_fixtures/local_static_corpus.jsonl", issues
    )

    if not all(
        isinstance(item, dict)
        for item in (
            task,
            input_bundle,
            gold_bundle,
            judge_bundle,
            allowed_tools,
            visible_manifest,
            calibration_refs,
        )
    ):
        issues.append(
            _issue(
                "task_contract_file_not_object",
                "task contract JSON files must be objects",
                task_rel,
            )
        )
        return

    task_id = str(task.get("task_id") or "")
    _validate_task_identity(manifest, task_entry, task, task_dir, issues)
    _validate_task_axes(task_dir, task_entry, task, judge_bundle, gold_bundle, issues)
    _validate_task_asset_refs(
        task_dir,
        task,
        task_entry,
        gold_bundle,
        calibration_refs,
        asset_ids,
        case_ids,
        issues,
    )
    _validate_visible_contract(
        task_dir,
        task,
        input_bundle,
        gold_bundle,
        judge_bundle,
        allowed_tools,
        visible_manifest,
        issues,
        checked_files,
    )
    _validate_local_corpus(task_dir, input_bundle, local_corpus, asset_ids, issues)
    _validate_t05_external_search_policy(
        task_dir, task, input_bundle, allowed_tools, visible_manifest, issues
    )

    for payload_name, payload in (
        ("input_bundle.json", input_bundle),
        ("gold_bundle.json", gold_bundle),
        ("judge_bundle.json", judge_bundle),
        ("tool_fixtures/allowed_tools_contract.json", allowed_tools),
        ("tool_fixtures/visible_input_manifest.json", visible_manifest),
        ("calibration_refs/dev_example_ids.json", calibration_refs),
    ):
        if str(payload.get("task_id") or "") != task_id:
            issues.append(
                _issue(
                    "task_id_cross_file_mismatch",
                    f"{payload_name} task_id does not match task.json",
                    f"{_rel(task_dir, task_dir / payload_name)}",
                    {"expected": task_id, "actual": payload.get("task_id")},
                )
            )


def _validate_task_identity(
    manifest: dict[str, Any],
    task_entry: dict[str, Any],
    task: dict[str, Any],
    task_dir: Path,
    issues: list[ValidationIssue],
) -> None:
    task_no = str(task_entry.get("task_no") or "")
    task_id = str(task.get("task_id") or "")
    path = _rel(task_dir, task_dir / "task.json")
    if task_id != task_entry.get("task_id"):
        issues.append(
            _issue(
                "task_id_manifest_mismatch",
                "task.json task_id does not match manifest task_id",
                path,
                {"expected": task_entry.get("task_id"), "actual": task_id},
            )
        )
    if task.get("pilot_pack_id") != manifest.get("pack_id"):
        issues.append(
            _issue(
                "task_pack_id_mismatch",
                "task pilot_pack_id does not match pack manifest",
                path,
                {
                    "expected": manifest.get("pack_id"),
                    "actual": task.get("pilot_pack_id"),
                },
            )
        )
    if not str(task.get("template_id") or "").endswith(task_no):
        issues.append(
            _issue(
                "task_template_id_mismatch",
                "template_id must end with manifest task_no",
                path,
                {"task_no": task_no, "template_id": task.get("template_id")},
            )
        )
    if task.get("stage") != task_entry.get("stage"):
        issues.append(
            _issue(
                "task_stage_manifest_mismatch",
                "task stage does not match manifest stage",
                path,
                {"expected": task_entry.get("stage"), "actual": task.get("stage")},
            )
        )
    if (
        task.get("status") != "draft_not_release_grade"
        or task.get("split") != "draft_dev"
    ):
        issues.append(
            _issue(
                "task_dev_status_mismatch",
                "Pilot-20 v0 tasks must remain draft_dev and not release-grade",
                path,
                {"status": task.get("status"), "split": task.get("split")},
            )
        )


def _validate_task_axes(
    task_dir: Path,
    task_entry: dict[str, Any],
    task: dict[str, Any],
    judge_bundle: dict[str, Any],
    gold_bundle: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    for rel_name, payload in (("task.json", task), ("judge_bundle.json", judge_bundle)):
        scoring = dict(payload.get("scoring") or {})
        missing_axes = sorted({"outcome", "process", "combined"} - set(scoring))
        if missing_axes:
            issues.append(
                _issue(
                    "scoring_axis_missing",
                    "scoring must keep outcome/process/combined axes separate",
                    _rel(task_dir, task_dir / rel_name),
                    {"missing_axes": missing_axes},
                )
            )
        if not dict(scoring.get("combined") or {}).get("axis_separation_required"):
            issues.append(
                _issue(
                    "combined_axis_separation_missing",
                    "combined scoring must require axis separation",
                    _rel(task_dir, task_dir / rel_name),
                )
            )

    if not gold_bundle.get("outcome_oracle") or not gold_bundle.get("process_oracle"):
        issues.append(
            _issue(
                "gold_oracle_axis_missing",
                "gold bundle must include separate outcome_oracle and process_oracle",
                _rel(task_dir, task_dir / "gold_bundle.json"),
            )
        )
    if (
        gold_bundle.get("release_grade") is not False
        or gold_bundle.get("human_calibration_required") is not True
    ):
        issues.append(
            _issue(
                "gold_release_readiness_mismatch",
                "Pilot-20 v0 gold bundle must be dev-only and require human calibration",
                _rel(task_dir, task_dir / "gold_bundle.json"),
            )
        )

    expected_objects = set(
        str(item) for item in task.get("expected_semantic_objects") or []
    )
    manifest_expected_objects = set(
        str(item) for item in task_entry.get("expected_semantic_objects") or []
    )
    if expected_objects != manifest_expected_objects:
        issues.append(
            _issue(
                "task_expected_semantic_objects_manifest_mismatch",
                "task expected semantic objects must match manifest task entry",
                _rel(task_dir, task_dir / "task.json"),
                {
                    "manifest": sorted(manifest_expected_objects),
                    "task": sorted(expected_objects),
                },
            )
        )
    task_no = str(task_entry.get("task_no") or "")
    required_objects = PILOT20_REQUIRED_OBJECTS_BY_TASK_NO.get(
        task_no, {"gate_decision", "run_trace"}
    )
    missing_required = sorted(required_objects - expected_objects)
    if missing_required:
        issues.append(
            _issue(
                "task_required_semantic_object_missing",
                "task must require the stage-specific Pilot-20 semantic object contract",
                _rel(task_dir, task_dir / "task.json"),
                {"task_no": task_no, "missing": missing_required},
            )
        )


def _validate_task_asset_refs(
    task_dir: Path,
    task: dict[str, Any],
    task_entry: dict[str, Any],
    gold_bundle: dict[str, Any],
    calibration_refs: dict[str, Any],
    asset_ids: set[str],
    case_ids: set[str],
    issues: list[ValidationIssue],
) -> None:
    task_gold_ids = list(task.get("gold_asset_ids") or [])
    manifest_gold_ids = list(task_entry.get("primary_gold_asset_ids") or [])
    gold_bundle_ids = list(gold_bundle.get("gold_asset_ids") or [])
    if task_gold_ids != manifest_gold_ids or task_gold_ids != gold_bundle_ids:
        issues.append(
            _issue(
                "task_gold_asset_refs_mismatch",
                "manifest, task.json, and gold_bundle gold asset ids must match",
                _rel(task_dir, task_dir / "task.json"),
                {
                    "manifest": manifest_gold_ids,
                    "task": task_gold_ids,
                    "gold_bundle": gold_bundle_ids,
                },
            )
        )
    for asset_id in task_gold_ids:
        if asset_id not in asset_ids:
            issues.append(
                _issue(
                    "task_gold_asset_missing",
                    f"task references missing gold asset {asset_id}",
                    _rel(task_dir, task_dir / "task.json"),
                    {"asset_id": asset_id},
                )
            )

    task_case_ids = list(task.get("corrupted_case_ids") or [])
    manifest_case_ids = list(task_entry.get("corrupted_case_ids") or [])
    gold_case_ids = list(gold_bundle.get("corrupted_case_ids") or [])
    calibration_case_ids = list(calibration_refs.get("corrupted_case_ids") or [])
    if task_case_ids != manifest_case_ids or task_case_ids != gold_case_ids:
        issues.append(
            _issue(
                "task_corrupted_case_refs_mismatch",
                "manifest, task.json, and gold_bundle corrupted case ids must match",
                _rel(task_dir, task_dir / "task.json"),
                {
                    "manifest": manifest_case_ids,
                    "task": task_case_ids,
                    "gold_bundle": gold_case_ids,
                },
            )
        )
    for case_id in set(task_case_ids + calibration_case_ids):
        if case_id not in case_ids:
            issues.append(
                _issue(
                    "task_corrupted_case_missing",
                    f"task references missing corrupted case {case_id}",
                    _rel(task_dir, task_dir / "task.json"),
                    {"case_id": case_id},
                )
            )


def _validate_visible_contract(
    task_dir: Path,
    task: dict[str, Any],
    input_bundle: dict[str, Any],
    gold_bundle: dict[str, Any],
    judge_bundle: dict[str, Any],
    allowed_tools: dict[str, Any],
    visible_manifest: dict[str, Any],
    issues: list[ValidationIssue],
    checked_files: set[Path],
) -> None:
    visible_files = [
        str(item) for item in visible_manifest.get("visible_to_agent") or []
    ]
    hidden_files = [
        str(item) for item in visible_manifest.get("judge_only_hidden") or []
    ]
    visible_set = set(visible_files)
    hidden_set = set(hidden_files)
    leaked = sorted(
        visible_set & hidden_set
        | (visible_set & {"gold_bundle.json", "judge_bundle.json"})
    )
    if leaked:
        issues.append(
            _issue(
                "visible_manifest_exposes_hidden_file",
                "visible manifest exposes judge/gold-only files",
                _rel(task_dir, task_dir / "tool_fixtures/visible_input_manifest.json"),
                {"leaked_paths": leaked},
            )
        )
    if not {"gold_bundle.json", "judge_bundle.json"}.issubset(hidden_set):
        issues.append(
            _issue(
                "visible_manifest_hidden_files_missing",
                "visible manifest must list gold and judge bundles as hidden",
                _rel(task_dir, task_dir / "tool_fixtures/visible_input_manifest.json"),
                {"hidden": hidden_files},
            )
        )
    if (
        visible_manifest.get("gold_blind") is not True
        or visible_manifest.get("external_search_policy") != "forbidden_in_v0"
    ):
        issues.append(
            _issue(
                "visible_manifest_policy_mismatch",
                "visible manifest must be gold-blind and external-search-forbidden in v0",
                _rel(task_dir, task_dir / "tool_fixtures/visible_input_manifest.json"),
            )
        )

    hashes = dict(visible_manifest.get("file_hashes_sha256") or {})
    for rel_path in visible_files:
        path = task_dir / rel_path
        if not path.exists():
            issues.append(
                _issue(
                    "visible_file_missing",
                    f"visible file is missing: {rel_path}",
                    _rel(task_dir, path),
                )
            )
            continue
        checked_files.add(path)
        expected_hash = hashes.get(rel_path)
        if not expected_hash:
            issues.append(
                _issue(
                    "visible_file_hash_missing",
                    f"visible manifest missing hash for {rel_path}",
                    _rel(
                        task_dir, task_dir / "tool_fixtures/visible_input_manifest.json"
                    ),
                )
            )
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            issues.append(
                _issue(
                    "visible_file_hash_mismatch",
                    f"visible manifest hash mismatch for {rel_path}",
                    _rel(
                        task_dir, task_dir / "tool_fixtures/visible_input_manifest.json"
                    ),
                    {
                        "path": rel_path,
                        "expected": expected_hash,
                        "actual": actual_hash,
                    },
                )
            )

    if (
        gold_bundle.get("judge_only") is not True
        or judge_bundle.get("judge_only") is not True
    ):
        issues.append(
            _issue(
                "gold_judge_bundle_not_marked_hidden",
                "gold and judge bundles must be marked judge_only",
                _rel(task_dir, task_dir / "gold_bundle.json"),
            )
        )
    if (
        allowed_tools.get("gold_visible") is not False
        or allowed_tools.get("judge_visible") is not False
    ):
        issues.append(
            _issue(
                "allowed_tools_gold_judge_visible",
                "allowed tools contract must keep gold/judge invisible",
                _rel(task_dir, task_dir / "tool_fixtures/allowed_tools_contract.json"),
            )
        )
    if allowed_tools.get("requires_preflight") is not True:
        issues.append(
            _issue(
                "allowed_tools_preflight_not_required",
                "allowed tools contract must require preflight",
                _rel(task_dir, task_dir / "tool_fixtures/allowed_tools_contract.json"),
            )
        )

    contract_tool_names = {
        str(item.get("tool_name"))
        for item in allowed_tools.get("allowed_tools", [])
        if isinstance(item, dict)
    }
    task_tool_names = set(str(item) for item in task.get("allowed_tools") or [])
    input_tool_names = set(
        str(item) for item in input_bundle.get("allowed_tools") or []
    )
    if task_tool_names != contract_tool_names or task_tool_names != input_tool_names:
        issues.append(
            _issue(
                "allowed_tools_cross_file_mismatch",
                "task, input bundle, and allowed tools contract must agree on allowed tools",
                _rel(task_dir, task_dir / "tool_fixtures/allowed_tools_contract.json"),
                {
                    "task": sorted(task_tool_names),
                    "input": sorted(input_tool_names),
                    "contract": sorted(contract_tool_names),
                },
            )
        )
    forbidden_tools = set(
        str(item) for item in allowed_tools.get("forbidden_tools") or []
    )
    missing_forbidden = sorted(FORBIDDEN_EXTERNAL_TOOLS - forbidden_tools)
    if missing_forbidden:
        issues.append(
            _issue(
                "external_tool_not_forbidden",
                "v0 allowed-tools contract must explicitly forbid external search tools",
                _rel(task_dir, task_dir / "tool_fixtures/allowed_tools_contract.json"),
                {"missing": missing_forbidden},
            )
        )
    if "local_static_corpus" in task_tool_names:
        fixtures = [
            str(item.get("fixture_path"))
            for item in allowed_tools.get("allowed_tools", [])
            if isinstance(item, dict) and item.get("tool_name") == "local_static_corpus"
        ]
        if "local_static_corpus.jsonl" not in fixtures:
            issues.append(
                _issue(
                    "local_static_corpus_fixture_missing",
                    "local_static_corpus tool must declare local_static_corpus.jsonl fixture",
                    _rel(
                        task_dir, task_dir / "tool_fixtures/allowed_tools_contract.json"
                    ),
                    {"fixtures": fixtures},
                )
            )


def _validate_local_corpus(
    task_dir: Path,
    input_bundle: dict[str, Any],
    records: list[Any],
    asset_ids: set[str],
    issues: list[ValidationIssue],
) -> None:
    record_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        path = f"{_rel(task_dir, task_dir / 'tool_fixtures/local_static_corpus.jsonl')}#L{index}"
        if not isinstance(record, dict):
            issues.append(
                _issue(
                    "local_corpus_record_not_object",
                    "local corpus record must be an object",
                    path,
                )
            )
            continue
        record_id = str(record.get("record_id") or "")
        if not record_id:
            issues.append(
                _issue(
                    "local_corpus_record_id_missing",
                    "local corpus record_id is required",
                    path,
                )
            )
        elif record_id in record_ids:
            issues.append(
                _issue(
                    "local_corpus_record_id_duplicate",
                    f"duplicate local corpus record_id: {record_id}",
                    path,
                    {"record_id": record_id},
                )
            )
        record_ids.add(record_id)
        if record_id and record_id not in asset_ids:
            issues.append(
                _issue(
                    "local_corpus_record_not_in_goldgraph_assets",
                    f"local corpus record is not backed by GoldGraph seed asset: {record_id}",
                    path,
                    {"record_id": record_id},
                )
            )
        if not record.get("semantic_object_type"):
            issues.append(
                _issue(
                    "local_corpus_semantic_type_missing",
                    "local corpus record must include semantic_object_type",
                    path,
                    {"record_id": record_id},
                )
            )
        if not isinstance(record.get("source_refs"), list) or not record.get(
            "source_refs"
        ):
            issues.append(
                _issue(
                    "local_corpus_source_refs_missing",
                    "local corpus record must include source_refs",
                    path,
                    {"record_id": record_id},
                )
            )

    visible_ids = set(
        str(item) for item in input_bundle.get("visible_local_corpus_record_ids") or []
    )
    missing_visible = sorted(visible_ids - record_ids)
    if missing_visible:
        issues.append(
            _issue(
                "visible_local_corpus_record_missing",
                "input bundle references records absent from local_static_corpus",
                _rel(task_dir, task_dir / "input_bundle.json"),
                {"missing": missing_visible},
            )
        )


def _validate_t05_external_search_policy(
    task_dir: Path,
    task: dict[str, Any],
    input_bundle: dict[str, Any],
    allowed_tools: dict[str, Any],
    visible_manifest: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    task_id = str(task.get("task_id") or "")
    if ".false_novelty_baseline_gap." not in task_id and not str(
        task.get("template_id") or ""
    ).endswith("T05"):
        return
    task_tools = set(str(item) for item in task.get("allowed_tools") or [])
    input_tools = set(str(item) for item in input_bundle.get("allowed_tools") or [])
    contract_tools = {
        str(item.get("tool_name"))
        for item in allowed_tools.get("allowed_tools", [])
        if isinstance(item, dict)
    }
    forbidden_tools = set(
        str(item) for item in allowed_tools.get("forbidden_tools") or []
    )
    policies = {
        str(task.get("external_search_policy") or ""),
        str(input_bundle.get("external_search_policy") or ""),
        str(visible_manifest.get("external_search_policy") or ""),
    }
    external_enabled = (
        policies != {"forbidden_in_v0"}
        or bool((task_tools | input_tools | contract_tools) & FORBIDDEN_EXTERNAL_TOOLS)
        or not FORBIDDEN_EXTERNAL_TOOLS.issubset(forbidden_tools)
    )
    if external_enabled:
        issues.append(
            _issue(
                "t05_external_search_enabled",
                "T05 v0 external search must remain disabled until query/result/cost traces and human approval exist",
                _rel(task_dir, task_dir / "task.json"),
                {
                    "policies": sorted(policies),
                    "task_tools": sorted(task_tools),
                    "input_tools": sorted(input_tools),
                    "contract_tools": sorted(contract_tools),
                    "missing_forbidden": sorted(
                        FORBIDDEN_EXTERNAL_TOOLS - forbidden_tools
                    ),
                },
            )
        )


def _load_json(path: Path, issues: list[ValidationIssue]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append(
            _issue("json_file_missing", f"JSON file is missing: {path}", str(path))
        )
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "json_parse_error",
                f"invalid JSON: {exc.msg}",
                str(path),
                {"line": exc.lineno, "column": exc.colno},
            )
        )
    return {}


def _load_jsonl(path: Path, issues: list[ValidationIssue]) -> list[Any]:
    records: list[Any] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        issues.append(
            _issue("jsonl_file_missing", f"JSONL file is missing: {path}", str(path))
        )
        return records
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "jsonl_parse_error",
                    f"invalid JSONL line: {exc.msg}",
                    str(path),
                    {"line": line_no, "column": exc.colno},
                )
            )
    return records


def _load_list_from_manifest_schema(
    manifest: dict[str, Any], field_name: str
) -> list[str]:
    # The pack schema file is validated by path/hash separately; this helper keeps
    # the in-memory validator schema-free when callers supply a synthetic manifest.
    schema = manifest.get("_goldgraph_asset_schema")
    if isinstance(schema, dict):
        return [str(item) for item in schema.get(field_name, [])]
    return [
        "paper_seed",
        "claim_seed",
        "evidence_span_seed",
        "baseline_prior_object",
        "corrupted_evidence_case",
    ]


def _load_contract_object_types(manifest: dict[str, Any]) -> list[str]:
    contract = manifest.get("_semantic_object_contract")
    if isinstance(contract, dict):
        return [str(item) for item in contract.get("object_types", [])]
    return [
        "paper",
        "claim",
        "evidence_span",
        "citation_link",
        "baseline",
        "experiment",
        "metric",
        "code_artifact",
        "section_draft",
        "review_issue",
        "gate_decision",
        "rollback_event",
        "run_trace",
    ]


def _final_report(
    root_path: Path,
    issues: list[ValidationIssue],
    checked_task_count: int,
    checked_file_count: int,
) -> ValidationReport:
    is_valid = not any(issue.severity == "error" for issue in issues)
    return ValidationReport(
        root=str(root_path),
        is_valid=is_valid,
        issues=tuple(issues),
        checked_task_count=checked_task_count,
        checked_file_count=checked_file_count,
    )


def _issue(
    code: str,
    message: str,
    path: str,
    details: dict[str, Any] | None = None,
    severity: str = "error",
) -> ValidationIssue:
    return ValidationIssue(
        code=code, severity=severity, message=message, path=path, details=details or {}
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _case_prefix_for_task(task_no: str) -> str:
    if len(task_no) == 3 and task_no.startswith("T") and task_no[1:].isdigit():
        return f"C{task_no[1:]}"
    return ""
