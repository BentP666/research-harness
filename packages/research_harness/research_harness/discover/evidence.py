"""Multi-route evidence collection for RH Discovery.

Discovery evidence is intentionally separate from the editorial weekly issue
contract. Weekly issues can stay concise, while this module owns the heavier
evidence snapshot used to prove that each visible Discovery problem is backed by
hundred-scale, recent, multi-source material.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from ..paper_source_clients import (
    OpenAlexProvider,
    available_provider_specs,
    build_provider_suite,
)
from ..paper_sources import PaperRecord, SearchAggregator, SearchQuery, normalize_title
from ..primitives.impls import paper_search as rh_paper_search
from ..primitives.types import PaperRef
from ..storage.db import Database

EvidenceRoute = Literal["rh_paper_search", "provider_fanout", "curated_signals"]
EvidenceType = Literal["paper", "blog", "product", "repo", "model", "benchmark", "news"]


@dataclass(frozen=True)
class DiscoveryEvidenceProblemSpec:
    """A Discovery top-level problem space that needs evidence coverage."""

    problem_id: str
    title: str
    category: str
    queries: tuple[str, ...]
    subject_categories: tuple[str, ...] = ("cs.AI", "cs.LG", "cs.CL")
    required_routes: tuple[EvidenceRoute, ...] = (
        "rh_paper_search",
        "provider_fanout",
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["queries"] = list(self.queries)
        payload["subject_categories"] = list(self.subject_categories)
        payload["required_routes"] = list(self.required_routes)
        return payload


@dataclass(frozen=True)
class EvidenceRecord:
    """Normalized evidence item collected for a Discovery problem."""

    problem_id: str
    evidence_type: EvidenceType
    title: str
    url: str
    source_route: str
    provider: str
    published_at: str = ""
    year: int | None = None
    query: str = ""
    reason: str = ""
    abstract: str = ""
    authors: tuple[str, ...] = field(default_factory=tuple)
    venue: str = ""
    doi: str = ""
    arxiv_id: str = ""
    s2_id: str = ""
    openalex_id: str = ""
    openreview_id: str = ""
    citation_count: int | None = None

    def evidence_key(self) -> str:
        for prefix, value in (
            ("doi", self.doi),
            ("arxiv", self.arxiv_id),
            ("s2", self.s2_id),
            ("openalex", self.openalex_id),
            ("openreview", self.openreview_id),
            ("url", self.url),
        ):
            cleaned = value.strip().lower()
            if cleaned:
                return f"{self.problem_id}:{prefix}:{cleaned}"
        title_key = normalize_title(self.title)
        return f"{self.problem_id}:title:{title_key}:{self.year or ''}"

    def evidence_id(self) -> str:
        digest = hashlib.sha1(self.evidence_key().encode("utf-8")).hexdigest()
        return f"ev-{digest[:16]}"

    def to_manifest_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id(),
            "problem_id": self.problem_id,
            "evidence_type": self.evidence_type,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "year": self.year,
            "source_routes": [self.source_route],
            "providers": [self.provider] if self.provider else [],
            "queries": [self.query] if self.query else [],
            "reason": self.reason,
            "abstract": self.abstract,
            "authors": list(self.authors),
            "venue": self.venue,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "s2_id": self.s2_id,
            "openalex_id": self.openalex_id,
            "openreview_id": self.openreview_id,
            "citation_count": self.citation_count,
        }


def default_evidence_problem_specs() -> list[DiscoveryEvidenceProblemSpec]:
    """Return the 10 problem spaces shown on the Discovery homepage."""

    return [
        DiscoveryEvidenceProblemSpec(
            problem_id="agentic-systems",
            title="Agentic Systems",
            category="Agent 系统",
            queries=(
                "tool using AI agents execution boundary audit",
                "long horizon autonomous agents workflow reliability",
                "AI agent sandbox tool permission evaluation",
                "multi agent workflow failure trace benchmark",
            ),
            subject_categories=("cs.AI", "cs.SE", "cs.CR", "cs.HC"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="ai-for-research",
            title="AI for Research",
            category="自动科研",
            queries=(
                "AI for research autonomous scientific discovery agents",
                "research agents literature review experiment automation",
                "scientific workflow agents provenance reproducibility",
                "automated research software engineering with AI agents",
            ),
            subject_categories=("cs.AI", "cs.SE", "cs.DL", "cs.CL"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="evaluation-benchmarks",
            title="Evaluation & Benchmarks",
            category="评测基准",
            queries=(
                "AI agents benchmark real world tasks evaluation",
                "deep research agent evaluation benchmark evidence reliability",
                "LLM agent benchmark dynamic environment failure taxonomy",
                "multimodal agent benchmark grounding evaluation",
            ),
            subject_categories=("cs.AI", "cs.CL", "cs.HC", "cs.CV"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="safety-governance",
            title="Safety & Governance",
            category="安全治理",
            queries=(
                "AI agent safety governance audit policy gate",
                "tool using LLM agents security prompt injection permissions",
                "AI agents trustworthy governance high consequence actions",
                "LLM agent audit logs policy compliance evaluation",
            ),
            subject_categories=("cs.AI", "cs.CR", "cs.CY", "cs.HC"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="enterprise-ai-workflow",
            title="Enterprise AI Workflow",
            category="企业工作流",
            queries=(
                "enterprise AI agents workflow automation evaluation",
                "agentic workflow observability human in the loop enterprise",
                "AI agent identity access management enterprise tools",
                "LLM agents enterprise productivity benchmark governance",
            ),
            subject_categories=("cs.AI", "cs.SE", "cs.CY", "cs.HC"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="multimodal-intelligence",
            title="Multimodal Intelligence",
            category="多模态智能",
            queries=(
                "multimodal agents document video GUI grounding",
                "vision language agents multimodal evidence retrieval",
                "long video multimodal reasoning benchmark agents",
                "multimodal large language models tool use grounding",
            ),
            subject_categories=("cs.CV", "cs.CL", "cs.AI", "cs.MM"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="ai-infrastructure",
            title="AI Infrastructure",
            category="AI 基础设施",
            queries=(
                "agentic LLM inference serving systems observability",
                "LLM inference cost latency tracing agent workloads",
                "AI agent sandbox gateway infrastructure systems",
                "long context multi step agent workload optimization",
            ),
            subject_categories=("cs.DC", "cs.OS", "cs.AI", "cs.PF"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="retrieval-knowledge-data",
            title="Retrieval / Knowledge / Data",
            category="检索与知识",
            queries=(
                "retrieval augmented generation evidence reliability evaluation",
                "multi source evidence synthesis deep research agents",
                "knowledge intensive LLM agents citation grounding benchmark",
                "scientific retrieval agents conflicting evidence handling",
            ),
            subject_categories=("cs.IR", "cs.CL", "cs.AI", "cs.DB"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="domain-science-ai",
            title="Domain Science AI",
            category="领域科学 AI",
            queries=(
                "AI agents scientific discovery biology materials chemistry",
                "laboratory automation AI agents scientific experiments",
                "foundation models for scientific discovery agents",
                "domain specific scientific workflow agents evaluation",
            ),
            subject_categories=("cs.AI", "cs.LG", "cs.CE", "cs.RO"),
        ),
        DiscoveryEvidenceProblemSpec(
            problem_id="robotics-embodied-ai",
            title="Robotics / Embodied AI",
            category="具身智能",
            queries=(
                "embodied AI agents success detection safety evaluation",
                "robotics foundation model task planning evaluation",
                "vision language action models embodied agents benchmark",
                "physical world AI agents multimodal grounding safety",
            ),
            subject_categories=("cs.RO", "cs.CV", "cs.AI", "cs.SY"),
        ),
    ]


def provider_plan(*, include_pasa: bool = False) -> list[dict[str, Any]]:
    """Expose provider status for the evidence collection runbook."""

    with _stable_provider_env(include_pasa=include_pasa):
        specs = [asdict(item) for item in available_provider_specs()]
    if not include_pasa:
        for item in specs:
            if item["name"] == "pasa":
                item["enabled"] = False
                item["reason"] = "disabled by Discovery evidence default for stability"
    return specs


def build_evidence_manifest(
    *,
    problem_specs: list[DiscoveryEvidenceProblemSpec] | None = None,
    records: Iterable[EvidenceRecord],
    route_statuses: Iterable[dict[str, Any]] | None = None,
    min_per_problem: int = 100,
    freshness_year_from: int | None = None,
    min_recent_per_problem: int | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deduplicated evidence manifest from normalized records."""

    specs = problem_specs or default_evidence_problem_specs()
    year_from = freshness_year_from or (datetime.now(timezone.utc).year - 1)
    recent_floor = (
        min_recent_per_problem
        if min_recent_per_problem is not None
        else min_per_problem
    )
    deduped = _dedupe_records(records)
    base_manifest = {
        "schema_version": "discovery-evidence-manifest/v1",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "min_per_problem": min_per_problem,
        "freshness_year_from": year_from,
        "min_recent_per_problem": recent_floor,
        "problem_count": len(specs),
        "provider_plan": provider_plan(),
        "problems": [spec.to_dict() for spec in specs],
        "route_statuses": list(route_statuses or []),
        "records": sorted(
            deduped.values(),
            key=lambda item: (
                item["problem_id"],
                -(item.get("year") or 0),
                item["title"],
            ),
        ),
    }
    base_manifest["coverage"] = _compute_coverage(base_manifest)
    return base_manifest


def validate_evidence_manifest(
    manifest: dict[str, Any],
    *,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """Validate the manifest against Discovery evidence gates.

    This recomputes coverage from the raw records rather than trusting any
    embedded coverage summary.
    """

    validation = _compute_coverage(manifest)
    if raise_on_error and not validation["ok"]:
        failures = [
            f"{item['problem_id']}({'; '.join(item['errors'])})"
            for item in validation["problems"]
            if item["errors"]
        ]
        if validation["route_error_count"]:
            failures.append(f"route_errors={validation['route_error_count']}")
        raise ValueError("Discovery evidence coverage failed: " + ", ".join(failures))
    return validation


def collect_discovery_evidence(
    *,
    db: Database,
    problem_specs: list[DiscoveryEvidenceProblemSpec] | None = None,
    routes: tuple[EvidenceRoute, ...] = ("rh_paper_search", "provider_fanout"),
    min_per_problem: int = 100,
    freshness_year_from: int | None = None,
    min_recent_per_problem: int | None = None,
    per_query_limit: int = 50,
    max_queries_per_problem: int | None = None,
    include_pasa: bool = False,
) -> dict[str, Any]:
    """Collect recent evidence across RH paper search and direct providers."""

    specs = problem_specs or default_evidence_problem_specs()
    year_from = freshness_year_from or (datetime.now(timezone.utc).year - 1)
    all_records: list[EvidenceRecord] = []
    route_statuses: list[dict[str, Any]] = []

    for spec in specs:
        queries = (
            spec.queries[:max_queries_per_problem]
            if max_queries_per_problem is not None
            else spec.queries
        )
        for query in queries:
            if "rh_paper_search" in routes:
                records, status = _collect_with_rh_paper_search(
                    db=db,
                    spec=spec,
                    query=query,
                    year_from=year_from,
                    per_query_limit=per_query_limit,
                    include_pasa=include_pasa,
                )
                all_records.extend(records)
                route_statuses.append(status)
            if "provider_fanout" in routes:
                records, status = _collect_with_provider_fanout(
                    spec=spec,
                    query=query,
                    year_from=year_from,
                    per_query_limit=per_query_limit,
                    include_pasa=include_pasa,
                )
                all_records.extend(records)
                route_statuses.append(status)

    manifest = build_evidence_manifest(
        problem_specs=specs,
        records=all_records,
        route_statuses=route_statuses,
        min_per_problem=min_per_problem,
        freshness_year_from=year_from,
        min_recent_per_problem=min_recent_per_problem,
    )
    manifest["provider_plan"] = provider_plan(include_pasa=include_pasa)
    manifest["coverage"] = validate_evidence_manifest(manifest)
    return manifest


def write_evidence_manifest(manifest: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return path


def load_evidence_manifest(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError("Discovery evidence manifest must be a JSON object")
    return payload


def _collect_with_rh_paper_search(
    *,
    db: Database,
    spec: DiscoveryEvidenceProblemSpec,
    query: str,
    year_from: int,
    per_query_limit: int,
    include_pasa: bool,
) -> tuple[list[EvidenceRecord], dict[str, Any]]:
    try:
        with _stable_provider_env(include_pasa=include_pasa):
            output = rh_paper_search(
                db=db,
                query=query,
                max_results=per_query_limit,
                year_from=year_from,
                subject_categories=list(spec.subject_categories),
                per_provider_limit=per_query_limit,
                auto_ingest=False,
            )
        records = [
            _record_from_paper_ref(
                item,
                problem_id=spec.problem_id,
                route="rh_paper_search",
                query=query,
                provider=output.provider or "rh_paper_search",
            )
            for item in output.papers
        ]
        return records, {
            "problem_id": spec.problem_id,
            "route": "rh_paper_search",
            "query": query,
            "result_count": len(records),
            "providers_queried": list(output.providers_queried),
            "provider_errors": list(output.provider_errors),
        }
    except Exception as exc:
        return [], {
            "problem_id": spec.problem_id,
            "route": "rh_paper_search",
            "query": query,
            "result_count": 0,
            "providers_queried": [],
            "provider_errors": [f"{exc.__class__.__name__}: {exc}"],
        }


def _collect_with_provider_fanout(
    *,
    spec: DiscoveryEvidenceProblemSpec,
    query: str,
    year_from: int,
    per_query_limit: int,
    include_pasa: bool,
) -> tuple[list[EvidenceRecord], dict[str, Any]]:
    try:
        providers = _build_provider_fanout(include_pasa=include_pasa)
        outcome = SearchAggregator(providers).search(
            SearchQuery(
                query=query,
                year_from=year_from,
                limit=per_query_limit,
                per_provider_limit=per_query_limit,
                subject_categories=spec.subject_categories,
            ),
            output_limit=per_query_limit,
        )
        records = [
            _record_from_paper_record(
                item,
                problem_id=spec.problem_id,
                route="provider_fanout",
                query=query,
            )
            for item in outcome.results
        ]
        return records, {
            "problem_id": spec.problem_id,
            "route": "provider_fanout",
            "query": query,
            "result_count": len(records),
            "providers_queried": [
                getattr(provider, "name", provider.__class__.__name__)
                for provider in providers
            ],
            "provider_errors": [
                f"{error.provider}: {error.message}"
                for error in outcome.provider_errors
            ],
        }
    except Exception as exc:
        return [], {
            "problem_id": spec.problem_id,
            "route": "provider_fanout",
            "query": query,
            "result_count": 0,
            "providers_queried": [],
            "provider_errors": [f"{exc.__class__.__name__}: {exc}"],
        }


def _build_provider_fanout(*, include_pasa: bool) -> list[Any]:
    with _stable_provider_env(include_pasa=include_pasa):
        providers = build_provider_suite()
    if not include_pasa:
        providers = [
            provider
            for provider in providers
            if getattr(provider, "name", provider.__class__.__name__) != "pasa"
        ]

    provider_names = {
        getattr(provider, "name", provider.__class__.__name__) for provider in providers
    }
    if "openalex" not in provider_names:
        providers = [
            *providers,
            OpenAlexProvider(
                api_key=os.environ.get("OPENALEX_API_KEY", "").strip(),
                email=os.environ.get("OPENALEX_MAILTO", "").strip(),
            ),
        ]
    return providers


def _record_from_paper_ref(
    ref: PaperRef,
    *,
    problem_id: str,
    route: str,
    query: str,
    provider: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        problem_id=problem_id,
        evidence_type="paper",
        title=ref.title,
        url=ref.url,
        source_route=route,
        provider=provider,
        year=ref.year,
        query=query,
        reason=f"Matched Discovery evidence query: {query}",
        abstract=ref.snippet,
        authors=tuple(ref.authors),
        venue=ref.venue,
        doi=ref.doi,
        arxiv_id=ref.arxiv_id,
        s2_id=ref.s2_id,
        citation_count=ref.citation_count,
    )


def _record_from_paper_record(
    record: PaperRecord,
    *,
    problem_id: str,
    route: str,
    query: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        problem_id=problem_id,
        evidence_type="paper",
        title=record.title,
        url=record.url,
        source_route=route,
        provider=record.provider,
        year=record.year,
        query=query,
        reason=f"Matched Discovery evidence query: {query}",
        abstract=record.abstract,
        authors=tuple(record.authors),
        venue=record.venue,
        doi=record.doi,
        arxiv_id=record.arxiv_id,
        s2_id=record.s2_id,
        openalex_id=record.openalex_id,
        openreview_id=record.openreview_id,
        citation_count=record.citation_count,
    )


def _dedupe_records(records: Iterable[EvidenceRecord]) -> dict[str, dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        if not record.title.strip():
            continue
        key = record.evidence_key()
        incoming = record.to_manifest_dict()
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = incoming
            continue
        deduped[key] = _merge_record_dict(existing, incoming)
    return deduped


def _merge_record_dict(
    existing: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    return {
        **existing,
        "source_routes": sorted(
            set(existing.get("source_routes", []))
            | set(incoming.get("source_routes", []))
        ),
        "providers": sorted(
            set(existing.get("providers", [])) | set(incoming.get("providers", []))
        ),
        "queries": sorted(
            set(existing.get("queries", [])) | set(incoming.get("queries", []))
        ),
        "abstract": existing.get("abstract") or incoming.get("abstract") or "",
        "url": existing.get("url") or incoming.get("url") or "",
        "published_at": existing.get("published_at")
        or incoming.get("published_at")
        or "",
        "year": existing.get("year") or incoming.get("year"),
        "citation_count": existing.get("citation_count")
        or incoming.get("citation_count"),
    }


def _compute_coverage(manifest: dict[str, Any]) -> dict[str, Any]:
    min_per_problem = int(manifest.get("min_per_problem") or 100)
    freshness_year_from = int(
        manifest.get("freshness_year_from") or datetime.now(timezone.utc).year - 1
    )
    min_recent_per_problem = int(
        manifest.get("min_recent_per_problem") or min_per_problem
    )
    records = [
        item
        for item in manifest.get("records", [])
        if isinstance(item, dict) and item.get("problem_id")
    ]
    route_errors = _route_errors(manifest)
    problems = [
        item
        for item in manifest.get("problems", [])
        if isinstance(item, dict) and item.get("problem_id")
    ]
    coverage: list[dict[str, Any]] = []
    for problem in problems:
        problem_id = str(problem["problem_id"])
        problem_records = [
            item for item in records if item.get("problem_id") == problem_id
        ]
        routes = sorted(
            {
                str(route)
                for item in problem_records
                for route in item.get("source_routes", [])
                if route
            }
        )
        providers = sorted(
            {
                str(provider)
                for item in problem_records
                for provider in item.get("providers", [])
                if provider
            }
        )
        recent_count = sum(
            1 for item in problem_records if _is_recent(item, freshness_year_from)
        )
        required_routes = tuple(problem.get("required_routes") or [])
        missing_routes = [route for route in required_routes if route not in routes]
        errors: list[str] = []
        if len(problem_records) < min_per_problem:
            errors.append(
                f"needs {min_per_problem} evidence records, got {len(problem_records)}"
            )
        if recent_count < min_recent_per_problem:
            errors.append(
                f"needs {min_recent_per_problem} recent records since {freshness_year_from}, got {recent_count}"
            )
        if missing_routes:
            errors.append(f"missing routes: {', '.join(missing_routes)}")
        coverage.append(
            {
                "problem_id": problem_id,
                "title": problem.get("title", problem_id),
                "evidence_count": len(problem_records),
                "recent_count": recent_count,
                "route_count": len(routes),
                "provider_count": len(providers),
                "routes": routes,
                "providers": providers,
                "latest_year": max(
                    [int(item["year"]) for item in problem_records if item.get("year")]
                    or [None]
                ),
                "errors": errors,
                "ok": not errors,
            }
        )
    ok_count = sum(1 for item in coverage if item["ok"])
    return {
        "ok": ok_count == len(coverage) and bool(coverage) and not route_errors,
        "passed_problem_count": ok_count,
        "problem_count": len(coverage),
        "route_error_count": len(route_errors),
        "route_errors": route_errors[:20],
        "min_per_problem": min_per_problem,
        "freshness_year_from": freshness_year_from,
        "min_recent_per_problem": min_recent_per_problem,
        "problems": coverage,
    }


def _is_recent(item: dict[str, Any], freshness_year_from: int) -> bool:
    year = item.get("year")
    if isinstance(year, int):
        return year >= freshness_year_from
    if isinstance(year, str) and year.isdigit():
        return int(year) >= freshness_year_from
    published_at = str(item.get("published_at") or "")
    match = re.match(r"(\d{4})", published_at)
    return bool(match and int(match.group(1)) >= freshness_year_from)


def _route_errors(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for status in manifest.get("route_statuses", []):
        if not isinstance(status, dict):
            continue
        provider_errors = [
            str(item) for item in status.get("provider_errors", []) if str(item).strip()
        ]
        if not provider_errors:
            continue
        errors.append(
            {
                "problem_id": status.get("problem_id"),
                "route": status.get("route"),
                "query": status.get("query"),
                "provider_errors": provider_errors,
            }
        )
    return errors


def _allow_s2_free_tier() -> bool:
    return os.environ.get("RH_DISCOVER_EVIDENCE_ALLOW_S2_FREE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _allow_arxiv_live_route() -> bool:
    return os.environ.get("RH_DISCOVER_EVIDENCE_ALLOW_ARXIV", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


@contextmanager
def _stable_provider_env(*, include_pasa: bool):
    previous_pasa = os.environ.get("PASA_ENABLE")
    previous_s2 = os.environ.get("SEMANTIC_SCHOLAR_ENABLE")
    previous_arxiv = os.environ.get("ARXIV_ENABLE")
    if not include_pasa:
        os.environ["PASA_ENABLE"] = "0"
    semantic_key = (
        os.environ.get("S2_API_KEY", "").strip()
        or os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    )
    if not semantic_key and not _allow_s2_free_tier():
        os.environ["SEMANTIC_SCHOLAR_ENABLE"] = "0"
    if not _allow_arxiv_live_route():
        os.environ["ARXIV_ENABLE"] = "0"
    try:
        yield
    finally:
        if previous_pasa is None:
            os.environ.pop("PASA_ENABLE", None)
        else:
            os.environ["PASA_ENABLE"] = previous_pasa
        if previous_s2 is None:
            os.environ.pop("SEMANTIC_SCHOLAR_ENABLE", None)
        else:
            os.environ["SEMANTIC_SCHOLAR_ENABLE"] = previous_s2
        if previous_arxiv is None:
            os.environ.pop("ARXIV_ENABLE", None)
        else:
            os.environ["ARXIV_ENABLE"] = previous_arxiv
