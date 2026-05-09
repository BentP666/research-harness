"""Research primitives — typed operations for research workflows."""

from .types import (
    AffiliationOutput,
    Baseline,
    BaselineIdentifyInput,
    BaselineIdentifyOutput,
    Claim,
    ClaimExtractInput,
    ClaimExtractOutput,
    ConsistencyCheckInput,
    ConsistencyCheckOutput,
    ConsistencyIssue,
    CrossPaperLink,
    DeepReadingNote,
    DeepReadingOutput,
    DraftText,
    EvidenceLink,
    EvidenceLinkInput,
    EvidenceLinkOutput,
    Gap,
    GapDetectInput,
    GapDetectOutput,
    GetDeepReadingOutput,
    IndustrialFeasibility,
    PaperIngestInput,
    PaperIngestOutput,
    PaperRef,
    PaperSearchInput,
    PaperSearchOutput,
    PrimitiveCategory,
    PrimitiveResult,
    PrimitiveSpec,
    QueryCandidate,
    QueryRefineOutput,
    SectionDraftInput,
    SectionDraftOutput,
    SummaryOutput,
)
from .registry import (
    PRIMITIVE_REGISTRY,
    get_primitive_impl,
    get_primitive_spec,
    list_by_category,
    list_primitives,
)
from . import analysis_impls as _analysis_impls  # noqa: F401
from . import deepread_impls as _deepread_impls  # noqa: F401
from . import evolution_impls as _evolution_impls  # noqa: F401
from . import candidate_seed as _candidate_seed  # noqa: F401
from . import cs_classify as _cs_classify  # noqa: F401
from . import cs_harvest as _cs_harvest  # noqa: F401
from . import gap_cross_verify as _gap_cross_verify  # noqa: F401
from . import experiment_impls as _experiment_impls  # noqa: F401
from . import experiment_loop_impl as _experiment_loop_impl  # noqa: F401
from . import recommend as _recommend  # noqa: F401
from . import red_ocean as _red_ocean  # noqa: F401
from . import task_canonicalize as _task_canonicalize  # noqa: F401
from . import head_paper as _head_paper  # noqa: F401
from . import impls as _impls  # noqa: F401
from . import query_refinement_impls as _query_refinement_impls  # noqa: F401
from . import verification_impls as _verification_impls  # noqa: F401
from . import writing_impls as _writing_impls  # noqa: F401

__all__ = [
    "AffiliationOutput",
    "Baseline",
    "BaselineIdentifyInput",
    "BaselineIdentifyOutput",
    "Claim",
    "ClaimExtractInput",
    "ClaimExtractOutput",
    "ConsistencyCheckInput",
    "ConsistencyCheckOutput",
    "ConsistencyIssue",
    "CrossPaperLink",
    "DeepReadingNote",
    "DeepReadingOutput",
    "DraftText",
    "EvidenceLink",
    "EvidenceLinkInput",
    "EvidenceLinkOutput",
    "Gap",
    "GapDetectInput",
    "GapDetectOutput",
    "GetDeepReadingOutput",
    "IndustrialFeasibility",
    "PaperIngestInput",
    "PaperIngestOutput",
    "PaperRef",
    "PaperSearchInput",
    "PaperSearchOutput",
    "PRIMITIVE_REGISTRY",
    "PrimitiveCategory",
    "PrimitiveResult",
    "PrimitiveSpec",
    "QueryCandidate",
    "QueryRefineOutput",
    "SectionDraftInput",
    "SectionDraftOutput",
    "SummaryOutput",
    "get_primitive_impl",
    "get_primitive_spec",
    "list_by_category",
    "list_primitives",
]
