"""Graph utilities for semantic governance bundles."""

from __future__ import annotations

from collections import defaultdict, deque

from .models import ObjectType, RollbackAction, RollbackCone, SemanticGovernanceBundle


def downstream_adjacency(
    bundle: SemanticGovernanceBundle,
) -> dict[str, tuple[str, ...]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in bundle.edges:
        adjacency[edge.source_object_id].append(edge.target_object_id)
    return {source: tuple(targets) for source, targets in adjacency.items()}


def compute_rollback_cone(
    bundle: SemanticGovernanceBundle,
    trigger_object_id: str,
    preserved_object_refs: tuple[str, ...] | None = None,
) -> RollbackCone:
    """Traverse downstream dependency edges from an invalidated trigger.

    The normalized graph uses dependency direction: upstream support/input →
    downstream dependent. The cone therefore contains transitive dependents.
    """

    adjacency = downstream_adjacency(bundle)
    affected: list[str] = []
    seen = {trigger_object_id}
    queue: deque[str] = deque(adjacency.get(trigger_object_id, ()))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        affected.append(current)
        queue.extend(adjacency.get(current, ()))

    object_by_id = bundle.object_by_id()
    actions: list[RollbackAction] = []
    for object_id in affected:
        obj = object_by_id.get(object_id)
        if obj is None:
            if RollbackAction.REVALIDATE not in actions:
                actions.append(RollbackAction.REVALIDATE)
            continue
        if obj.object_type == ObjectType.GATE_DECISION:
            if RollbackAction.BLOCK not in actions:
                actions.append(RollbackAction.BLOCK)
        elif obj.object_type == ObjectType.SECTION_DRAFT or "draft" in object_id:
            if RollbackAction.REVISE not in actions:
                actions.append(RollbackAction.REVISE)
        else:
            if RollbackAction.REVALIDATE not in actions:
                actions.append(RollbackAction.REVALIDATE)
    if affected and RollbackAction.HUMAN_REVIEW not in actions:
        actions.append(RollbackAction.HUMAN_REVIEW)

    gate_preserved = tuple(
        ref for gate in bundle.gate_decisions for ref in gate.preserved_object_refs
    )
    inferred_preserved = tuple(
        obj.object_id
        for obj in bundle.objects
        if obj.object_id not in set(affected) | {trigger_object_id}
        and (
            obj.object_type
            in {ObjectType.EVIDENCE_SPAN, ObjectType.PAPER, ObjectType.BASELINE}
            or obj.object_id.startswith("ev.")
        )
    )
    preserved = _dedupe_tuple(
        (preserved_object_refs or ()) + gate_preserved + inferred_preserved
    )

    evidence_refs = _dedupe_tuple(
        tuple(
            edge.source_ref
            for edge in bundle.edges
            if edge.source_ref
            and (edge.source_object_id in seen or edge.target_object_id in seen)
        )
        + tuple(ref for gate in bundle.gate_decisions for ref in gate.evidence_refs)
    )

    return RollbackCone(
        trigger_object_id=trigger_object_id,
        affected_object_ids=tuple(affected),
        preserved_object_refs=preserved,
        required_actions=tuple(actions),
        evidence_refs=evidence_refs,
    )


def _dedupe_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
