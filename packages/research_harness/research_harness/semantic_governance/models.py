"""Semantic governance v0.1 immutable data model.

This package is intentionally read-only: it models normalized governance bundles
without touching RH database, MCP primitives, or existing CLI behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


class ObjectType(str, Enum):
    PAPER = "paper"
    CLAIM = "claim"
    EVIDENCE_SPAN = "evidence_span"
    CITATION_LINK = "citation_link"
    BASELINE = "baseline"
    EXPERIMENT = "experiment"
    METRIC = "metric"
    CODE_ARTIFACT = "code_artifact"
    SECTION_DRAFT = "section_draft"
    REVIEW_ISSUE = "review_issue"
    GATE_DECISION = "gate_decision"
    ROLLBACK_EVENT = "rollback_event"
    RUN_TRACE = "run_trace"


class EdgeType(str, Enum):
    CITES = "cites"
    SUPPORTED_BY = "supported_by"
    PARTIALLY_SUPPORTED_BY = "partially_supported_by"
    CONTRADICTED_BY = "contradicted_by"
    DERIVED_FROM = "derived_from"
    CONSUMES = "consumes"
    VERIFIES = "verifies"
    INVALIDATES = "invalidates"
    COMPARES_TO = "compares_to"


class ReliabilityState(str, Enum):
    UNVERIFIED = "unverified"
    RETRIEVED = "retrieved"
    SPAN_SUPPORTED = "span_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    AMBIGUOUS = "ambiguous"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    STALE = "stale"
    BLOCKED = "blocked"
    PASSED = "passed"


class GateVerdict(str, Enum):
    PASS = "pass"
    PASS_WITH_CAVEAT = "pass_with_caveat"
    BLOCK = "block"
    NEEDS_REVIEW = "needs_review"
    ROLLBACK = "rollback"


class RollbackAction(str, Enum):
    REVALIDATE = "revalidate"
    REVISE = "revise"
    BLOCK = "block"
    RETIRE = "retire"
    HUMAN_REVIEW = "human_review"


_ENUM_FIELDS = {
    "object_type": ObjectType,
    "edge_type": EdgeType,
    "reliability_state": ReliabilityState,
    "from_state": ReliabilityState,
    "to_state": ReliabilityState,
    "verdict": GateVerdict,
}


def _coerce_enum(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:  # pragma: no cover - exact message asserted by callers
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(
            f"unknown {field_name}: {value!r}; allowed: {allowed}"
        ) from exc


def _tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    return dict(value)


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


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    object_id: str | None = None
    source_ref: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("diagnostic code is required")
        if not self.severity:
            raise ValueError("diagnostic severity is required")
        object.__setattr__(self, "details", _dict(self.details))

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class SemanticObject:
    object_id: str
    object_type: ObjectType | str
    subtype: str = ""
    raw_id: str = ""
    source_ref: str = ""
    reliability_state: ReliabilityState | str = ReliabilityState.UNVERIFIED
    fields: dict[str, Any] = field(default_factory=dict)
    content_hash: str | None = None
    created_by: str = "semantic_governance_v0.1_converter"
    created_at: str = ""
    source_refs: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("object_id is required")
        object.__setattr__(
            self,
            "object_type",
            _coerce_enum(self.object_type, ObjectType, "object_type"),
        )
        object.__setattr__(
            self,
            "reliability_state",
            _coerce_enum(self.reliability_state, ReliabilityState, "reliability_state"),
        )
        object.__setattr__(self, "fields", _dict(self.fields))
        object.__setattr__(
            self, "source_refs", tuple(str(item) for item in _tuple(self.source_refs))
        )
        object.__setattr__(
            self, "risk_flags", tuple(str(item) for item in _tuple(self.risk_flags))
        )
        if not self.raw_id:
            object.__setattr__(self, "raw_id", self.object_id)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class SemanticEdge:
    edge_id: str
    source_object_id: str
    target_object_id: str
    edge_type: EdgeType | str
    raw_relation: str = ""
    raw_source_id: str = ""
    raw_target_id: str = ""
    canonicalization_notes: str = ""
    source_ref: str = ""
    confidence: str = "legacy_inferred"
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.edge_id:
            raise ValueError("edge_id is required")
        if not self.source_object_id:
            raise ValueError("source_object_id is required")
        if not self.target_object_id:
            raise ValueError("target_object_id is required")
        object.__setattr__(
            self, "edge_type", _coerce_enum(self.edge_type, EdgeType, "edge_type")
        )
        object.__setattr__(self, "meta", _dict(self.meta))
        if not self.raw_source_id:
            object.__setattr__(self, "raw_source_id", self.source_object_id)
        if not self.raw_target_id:
            object.__setattr__(self, "raw_target_id", self.target_object_id)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class GateDecision:
    gate_id: str
    stage: str
    verdict: GateVerdict | str
    criteria: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    target_object_ids: tuple[str, ...] = ()
    invalidated_object_ids: tuple[str, ...] = ()
    preserved_object_refs: tuple[str, ...] = ()
    raw_verdict: str = ""
    source_ref: str = ""
    risk_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.gate_id:
            raise ValueError("gate_id is required")
        if not self.stage:
            raise ValueError("stage is required")
        object.__setattr__(
            self, "verdict", _coerce_enum(self.verdict, GateVerdict, "verdict")
        )
        object.__setattr__(
            self, "criteria", tuple(str(item) for item in _tuple(self.criteria))
        )
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(item) for item in _tuple(self.evidence_refs)),
        )
        object.__setattr__(
            self,
            "target_object_ids",
            tuple(str(item) for item in _tuple(self.target_object_ids)),
        )
        object.__setattr__(
            self,
            "invalidated_object_ids",
            tuple(str(item) for item in _tuple(self.invalidated_object_ids)),
        )
        object.__setattr__(
            self,
            "preserved_object_refs",
            tuple(str(item) for item in _tuple(self.preserved_object_refs)),
        )
        object.__setattr__(
            self, "risk_flags", tuple(str(item) for item in _tuple(self.risk_flags))
        )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class VerificationSignal:
    signal_id: str
    check_id: str
    passed: bool | None
    label: str
    evidence_summary: str = ""
    target_object_ids: tuple[str, ...] = ()
    signal_type: str = "deterministic"
    source_ref: str = ""
    risk_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if not self.check_id:
            raise ValueError("check_id is required")
        object.__setattr__(
            self,
            "target_object_ids",
            tuple(str(item) for item in _tuple(self.target_object_ids)),
        )
        object.__setattr__(
            self, "risk_flags", tuple(str(item) for item in _tuple(self.risk_flags))
        )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class ValidityLedgerEntry:
    entry_id: str
    object_id: str
    from_state: ReliabilityState | str
    to_state: ReliabilityState | str
    reason: str
    evidence_ref: str
    gate_id: str | None = None
    signal_id: str | None = None
    provenance: str = "semantic_governance_v0.1_converter"

    def __post_init__(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if not self.object_id:
            raise ValueError("object_id is required")
        if not self.evidence_ref:
            raise ValueError("evidence_ref is required")
        object.__setattr__(
            self,
            "from_state",
            _coerce_enum(self.from_state, ReliabilityState, "from_state"),
        )
        object.__setattr__(
            self, "to_state", _coerce_enum(self.to_state, ReliabilityState, "to_state")
        )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class RollbackCone:
    trigger_object_id: str
    affected_object_ids: tuple[str, ...]
    preserved_object_refs: tuple[str, ...] = ()
    required_actions: tuple[RollbackAction, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not self.trigger_object_id:
            raise ValueError("trigger_object_id is required")
        object.__setattr__(
            self,
            "affected_object_ids",
            tuple(str(item) for item in _tuple(self.affected_object_ids)),
        )
        object.__setattr__(
            self,
            "preserved_object_refs",
            tuple(str(item) for item in _tuple(self.preserved_object_refs)),
        )
        object.__setattr__(
            self,
            "required_actions",
            tuple(
                item if isinstance(item, RollbackAction) else RollbackAction(item)
                for item in _tuple(self.required_actions)
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(item) for item in _tuple(self.evidence_refs)),
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class RunTrace:
    trace_id: str
    provider: str = ""
    model: str = ""
    runner: str = ""
    allowed_tools: tuple[str, ...] = ()
    gold_visible: bool | None = None
    judge_visible: bool | None = None
    wall_clock_seconds: float | None = None
    token_usage: Any = None
    cost_trace: dict[str, Any] = field(default_factory=dict)
    retrieved_sources_count: int = 0
    started_at: str = ""
    finished_at: str = ""
    risk_flags: tuple[str, ...] = ()
    raw_ref: str = ""

    def __post_init__(self) -> None:
        if not self.trace_id:
            raise ValueError("trace_id is required")
        object.__setattr__(
            self,
            "allowed_tools",
            tuple(str(item) for item in _tuple(self.allowed_tools)),
        )
        object.__setattr__(self, "cost_trace", _dict(self.cost_trace))
        object.__setattr__(
            self, "risk_flags", tuple(str(item) for item in _tuple(self.risk_flags))
        )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class SemanticGovernanceBundle:
    task_id: str
    baseline_id: str
    source_run_root: str
    objects: tuple[SemanticObject, ...]
    edges: tuple[SemanticEdge, ...]
    gate_decisions: tuple[GateDecision, ...]
    schema_version: str = "0.1.0"
    verification_signals: tuple[VerificationSignal, ...] = ()
    validity_ledger: tuple[ValidityLedgerEntry, ...] = ()
    rollback_cones: tuple[RollbackCone, ...] = ()
    run_trace: RunTrace | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    source_files: dict[str, Any] = field(default_factory=dict)
    aggregate_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.baseline_id:
            raise ValueError("baseline_id is required")
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "gate_decisions", tuple(self.gate_decisions))
        object.__setattr__(
            self, "verification_signals", tuple(self.verification_signals)
        )
        object.__setattr__(self, "validity_ledger", tuple(self.validity_ledger))
        object.__setattr__(self, "rollback_cones", tuple(self.rollback_cones))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "source_files", _dict(self.source_files))
        object.__setattr__(self, "aggregate_context", _dict(self.aggregate_context))

    @property
    def object_ids(self) -> frozenset[str]:
        return frozenset(obj.object_id for obj in self.objects)

    def object_by_id(self) -> dict[str, SemanticObject]:
        return {obj.object_id: obj for obj in self.objects}

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class ValidationReport:
    mode: str
    is_valid: bool
    diagnostics: tuple[Diagnostic, ...] = ()
    object_count: int = 0
    edge_count: int = 0
    gate_count: int = 0
    verification_signal_count: int = 0
    ledger_entry_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))
