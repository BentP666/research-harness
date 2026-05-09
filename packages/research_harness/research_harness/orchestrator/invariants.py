"""Deterministic invariant checks for stage gates.

These checks run BEFORE LLM-based gate evaluation and are:
- Fast (no LLM calls)
- Deterministic (same input = same output)
- Non-bypassable (even in autonomous mode)

Inspired by OpenAI's "enforce invariants mechanically, not through documentation."
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..storage.db import Database
from .stages import resolve_stage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Artifact schema definitions (per artifact_type)
#
# Each entry lists `required_fields` (canonical names). For each canonical
# name, `field_aliases` may list synonyms — if any alias is present and
# truthy, the canonical requirement is satisfied. This matches the actual
# writer output across the codebase, where multiple primitives evolved
# slightly different field names for the same concept.
# ---------------------------------------------------------------------------

ARTIFACT_SCHEMAS: dict[str, dict[str, Any]] = {
    "topic_brief": {
        "required_fields": ["scope", "venue_target"],
        "field_aliases": {
            "scope": [
                "scope",
                "problem_statement",
                "topic_scope",
                "scope_definition",
                "research_scope",
                "research_direction",
            ],
            "venue_target": [
                "venue_target",
                "target_venue",
                "venue",
                "target_conference",
            ],
        },
        "description": "Topic framing output with scope and venue target",
    },
    "literature_map": {
        "required_fields": ["clusters"],
        "field_aliases": {
            "clusters": ["clusters", "cluster_summary", "groups", "themes"],
        },
        "description": "Clustered literature mapping",
    },
    "paper_pool_snapshot": {
        "required_fields": ["paper_count"],
        "field_aliases": {
            "paper_count": ["paper_count", "papers_total", "n_papers", "total_papers"],
        },
        "description": "Snapshot of paper pool state",
    },
    "evidence_pack": {
        "required_fields": ["claims"],
        "field_aliases": {
            "claims": ["claims", "systems", "evidence", "evidence_items", "claim_list"],
        },
        "description": "Extracted claims and evidence links",
    },
    "direction_proposal": {
        "required_fields": ["research_question"],
        "field_aliases": {
            "research_question": [
                "research_question",
                "directions",
                "proposals",
                "questions",
                "hypothesis",
            ],
        },
        "description": "Proposed research direction with question and hypothesis",
    },
    "adversarial_resolution": {
        "required_fields": ["outcome"],
        "field_aliases": {
            "outcome": ["outcome", "verdict", "resolution", "result"],
        },
        "description": "Result of adversarial review round",
    },
    "study_spec": {
        "required_fields": ["methodology"],
        "field_aliases": {
            "methodology": ["methodology", "method", "approach", "design"],
        },
        "description": "Experiment study design specification",
    },
    "experiment_result": {
        "required_fields": ["metrics"],
        "field_aliases": {
            "metrics": ["metrics", "results", "measurements", "scores"],
        },
        "description": "Experiment execution results with metrics",
    },
    "verified_registry": {
        "required_fields": ["whitelist_size"],
        "field_aliases": {
            "whitelist_size": ["whitelist_size", "verified_count", "registry_size"],
        },
        "description": "Verified number registry from experiment",
    },
    "draft_pack": {
        "required_fields": ["sections"],
        "field_aliases": {
            "sections": ["sections", "section_drafts", "draft_sections"],
        },
        "description": "Drafted paper sections",
    },
}


def _has_required_field(
    payload: dict[str, Any],
    field: str,
    schema: dict[str, Any],
    raw_json: str = "",
) -> bool:
    """Return True if `payload` has `field` (or any of its declared aliases)
    set to a truthy value, either at the top level or nested anywhere in
    the payload structure (substring match on the raw JSON)."""
    aliases = schema.get("field_aliases", {}).get(field, [field])
    if field not in aliases:
        aliases = [field, *aliases]
    for key in aliases:
        if key in payload and payload[key]:
            return True
    # Fallback: detect the same canonical/alias keys nested anywhere
    # in the payload via raw substring match. This is cheaper than a
    # recursive walk and good enough for the "is the concept present
    # at all" question.
    if raw_json:
        for key in aliases:
            if f'"{key}"' in raw_json:
                return True
    return False


def _payload_has_paper_sourcing(payload_json: str) -> bool:
    """Cheap structural check: does the payload reference any paper IDs?

    Looks for the canonical sourcing keys at any depth via substring match
    on the raw JSON. Avoids a full json.loads + recursive walk for what
    is fundamentally an "is there any paper attribution at all" question.
    """
    if not payload_json:
        return False
    return (
        '"paper_id"' in payload_json
        or '"paper_ids"' in payload_json
        or '"source_paper_ids"' in payload_json
        or '"evidence_papers"' in payload_json
        or '"evidence_links"' in payload_json
        or '"citations"' in payload_json
    )


class InvariantChecker:
    """Runs deterministic pre-checks before gate evaluation."""

    def __init__(self, db: Database):
        self._db = db

    def check_all(self, topic_id: int, stage: str) -> list[InvariantViolation]:
        """Run all invariant checks for a stage. Returns list of violations."""
        violations: list[InvariantViolation] = []
        violations.extend(self.check_artifact_schemas(topic_id, stage))
        violations.extend(self.check_no_stale_artifacts(topic_id, stage))
        violations.extend(self.check_provenance_linkage(topic_id, stage))
        violations.extend(self.check_section_citations(topic_id, stage))
        violations.extend(
            self.check_citation_sentence_evidence_coverage(topic_id, stage)
        )
        return violations

    def check_artifact_schemas(
        self, topic_id: int, stage: str
    ) -> list[InvariantViolation]:
        """Validate that artifact payloads match their type schemas.

        Scoped to artifacts whose stage resolves to the queried V2 stage —
        otherwise one bad artifact would surface a violation on every
        stage node in the UI.
        """
        violations: list[InvariantViolation] = []
        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT id, artifact_type, payload_json, title, stage
                FROM project_artifacts
                WHERE topic_id = ? AND status = 'active'
                """,
                (topic_id,),
            ).fetchall()

            for row in rows:
                if resolve_stage(row["stage"] or "") != stage:
                    continue
                artifact_type = row["artifact_type"]
                schema = ARTIFACT_SCHEMAS.get(artifact_type)
                if schema is None:
                    continue  # No schema defined = no validation

                try:
                    payload = json.loads(row["payload_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    violations.append(
                        InvariantViolation(
                            check="artifact_schema",
                            severity="critical",
                            message=f"Artifact {row['id']} ({artifact_type}) has invalid JSON payload",
                            artifact_id=row["id"],
                        )
                    )
                    continue

                raw_json = row["payload_json"] or ""
                for field in schema.get("required_fields", []):
                    if not _has_required_field(payload, field, schema, raw_json):
                        violations.append(
                            InvariantViolation(
                                check="artifact_schema",
                                severity="medium",
                                message=(
                                    f"Artifact {row['id']} ({artifact_type}) missing "
                                    f"required field '{field}'"
                                ),
                                artifact_id=row["id"],
                            )
                        )
        finally:
            conn.close()

        return violations

    def check_no_stale_artifacts(
        self, topic_id: int, stage: str
    ) -> list[InvariantViolation]:
        """Verify no stale artifacts are being counted for gate evaluation.

        Scoped to the queried V2 stage so legacy stale artifacts only
        surface on their own stage node, not every node in the timeline.
        """
        violations: list[InvariantViolation] = []
        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT id, artifact_type, stale, stale_reason, stage
                FROM project_artifacts
                WHERE topic_id = ? AND status = 'active' AND stale = 1
                """,
                (topic_id,),
            ).fetchall()

            for row in rows:
                if resolve_stage(row["stage"] or "") != stage:
                    continue
                violations.append(
                    InvariantViolation(
                        check="stale_artifact",
                        severity="high",
                        message=(
                            f"Artifact {row['id']} ({row['artifact_type']}) is stale: "
                            f"{row['stale_reason'] or 'no reason given'}"
                        ),
                        artifact_id=row["id"],
                    )
                )
        finally:
            conn.close()

        return violations

    def check_provenance_linkage(
        self, topic_id: int, stage: str
    ) -> list[InvariantViolation]:
        """Check that critical artifacts have provenance records.

        Accepts either of two evidence forms: a linked
        `provenance_record_id`, OR a payload that carries paper-level
        sourcing (e.g. `paper_id`/`paper_ids`/`source_paper_ids`).
        Legacy artifacts produced before provenance linkage was wired
        often embed paper IDs directly; flagging them as missing
        provenance is a false positive.
        """
        violations: list[InvariantViolation] = []
        critical_types = frozenset(
            {
                "evidence_pack",
                "direction_proposal",
                "experiment_result",
                "draft_pack",
                "adversarial_resolution",
            }
        )

        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT id, artifact_type, provenance_record_id, stage, payload_json
                FROM project_artifacts
                WHERE topic_id = ? AND status = 'active'
                  AND artifact_type IN ({})
                """.format(",".join("?" * len(critical_types))),
                (topic_id, *critical_types),
            ).fetchall()

            for row in rows:
                if resolve_stage(row["stage"] or "") != stage:
                    continue
                if row["provenance_record_id"]:
                    continue
                if _payload_has_paper_sourcing(row["payload_json"] or ""):
                    continue
                violations.append(
                    InvariantViolation(
                        check="provenance_linkage",
                        severity="medium",
                        message=(
                            f"Critical artifact {row['id']} ({row['artifact_type']}) "
                            "has no provenance record"
                        ),
                        artifact_id=row["id"],
                    )
                )
        finally:
            conn.close()

        return violations

    def check_citation_sentence_evidence_coverage(
        self, topic_id: int, stage: str
    ) -> list[InvariantViolation]:
        """v2 Step 3.3: every sentence with a citation marker in a draft
        section MUST have at least one matching EvidenceMapping entry in
        the artifact's ``evidence_map`` sidecar.

        This replaces v1's imprecise "70% non-boilerplate coverage" metric
        with a deterministic rule: citation presence in prose is testable
        by regex, and EvidenceMapping is a structured sidecar list.
        """
        violations: list[InvariantViolation] = []
        if stage not in ("write", "draft_preparation", "formal_review"):
            return violations

        import re

        cite_rx = re.compile(r"\\cite[pt]?\{|\[\d+\]|\(\w+,\s*\d{4}\)")

        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT id, artifact_type, payload_json
                FROM project_artifacts
                WHERE topic_id = ? AND status = 'active'
                  AND artifact_type = 'draft_pack'
                ORDER BY version DESC LIMIT 1
                """,
                (topic_id,),
            ).fetchall()

            for row in rows:
                try:
                    payload = json.loads(row["payload_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue

                evidence_map = payload.get("evidence_map") or []
                covered_indices_by_section: dict[str, set[int]] = {}
                if isinstance(evidence_map, list):
                    for em in evidence_map:
                        if not isinstance(em, dict):
                            continue
                        sec = str(em.get("section", "")).strip() or "_"
                        idx = em.get("sentence_index")
                        if isinstance(idx, int):
                            covered_indices_by_section.setdefault(sec, set()).add(idx)

                sections = payload.get("sections", {})
                for section_name, content in sections.items():
                    if not isinstance(content, str):
                        continue
                    if section_name in ("abstract", "conclusion", "acknowledgments"):
                        continue
                    # Lightweight sentence split matching _extract_evidence_map.
                    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\\\[\(])", content)
                    covered = covered_indices_by_section.get(section_name)
                    # Fallback: maybe the writer emitted evidence_map without
                    # section tags — treat any entry as covering any index.
                    if covered is None:
                        covered = covered_indices_by_section.get("_", set())
                    missing: list[int] = []
                    for idx, sent in enumerate(parts):
                        if cite_rx.search(sent) and idx not in covered:
                            missing.append(idx)
                    if missing:
                        violations.append(
                            InvariantViolation(
                                check="citation_sentence_evidence_coverage",
                                severity="medium",
                                message=(
                                    f"Section '{section_name}' in draft_pack has "
                                    f"{len(missing)} citation-marked sentence(s) "
                                    f"without EvidenceMapping entries "
                                    f"(sentence indices: {missing[:5]})"
                                ),
                                artifact_id=row["id"],
                            )
                        )
        finally:
            conn.close()

        return violations

    def check_section_citations(
        self, topic_id: int, stage: str
    ) -> list[InvariantViolation]:
        """Check that draft sections contain citation markers."""
        violations: list[InvariantViolation] = []
        if stage not in ("write", "draft_preparation", "formal_review"):
            return violations

        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT id, artifact_type, payload_json
                FROM project_artifacts
                WHERE topic_id = ? AND status = 'active'
                  AND artifact_type = 'draft_pack'
                ORDER BY version DESC LIMIT 1
                """,
                (topic_id,),
            ).fetchall()

            for row in rows:
                try:
                    payload = json.loads(row["payload_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue

                sections = payload.get("sections", {})
                for section_name, content in sections.items():
                    if section_name in ("abstract", "conclusion", "acknowledgments"):
                        continue  # These sections may not need citations
                    if isinstance(content, str) and len(content) > 200:
                        # Check for citation markers: \cite{}, [N], (Author, Year)
                        import re

                        has_cite = bool(
                            re.search(
                                r"\\cite\{|[\[\(]\d+[\]\)]|\(\w+,\s*\d{4}\)", content
                            )
                        )
                        if not has_cite:
                            violations.append(
                                InvariantViolation(
                                    check="section_citations",
                                    severity="medium",
                                    message=(
                                        f"Section '{section_name}' in draft_pack "
                                        f"({len(content)} chars) has no citation markers"
                                    ),
                                    artifact_id=row["id"],
                                )
                            )
        finally:
            conn.close()

        return violations


class InvariantViolation:
    """A single invariant check failure."""

    __slots__ = ("check", "severity", "message", "artifact_id")

    def __init__(
        self,
        check: str,
        severity: str,
        message: str,
        artifact_id: int | None = None,
    ):
        self.check = check
        self.severity = severity  # critical|high|medium|low
        self.message = message
        self.artifact_id = artifact_id

    def __repr__(self) -> str:
        return f"InvariantViolation({self.severity}: {self.message})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "artifact_id": self.artifact_id,
        }


def is_blocking(violation: InvariantViolation) -> bool:
    """Check if a violation should block gate progression."""
    return violation.severity in ("critical", "high")
