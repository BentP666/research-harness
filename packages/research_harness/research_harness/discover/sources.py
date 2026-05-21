"""Seed source registry for RH Discover.

The registry is a curated starting point, not a live connector implementation.
Each entry declares how it should be wired during incubation: direct connector,
sidecar integration, or manual editorial watchlist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

SourceFamily = Literal["papers", "blogs", "product", "repos_models", "social"]
SourceRegion = Literal["global", "cn"]
SourceUsage = Literal["connector", "sidecar", "manual"]


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    name: str
    family: SourceFamily
    region: SourceRegion
    usage: SourceUsage
    url: str
    signal_types: tuple[str, ...]
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["signal_types"] = list(self.signal_types)
        return data


_SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        id="arxiv_cs_recent",
        name="arXiv CS recent submissions",
        family="papers",
        region="global",
        usage="connector",
        url="https://arxiv.org/list/cs/recent",
        signal_types=("paper",),
        note="Primary paper signal for daily research changes.",
    ),
    SourceDefinition(
        id="semantic_scholar_search",
        name="Semantic Scholar search",
        family="papers",
        region="global",
        usage="connector",
        url="https://www.semanticscholar.org/",
        signal_types=("paper",),
        note="Use for metadata, citation, and related-paper expansion.",
    ),
    SourceDefinition(
        id="openreview_recent",
        name="OpenReview recent activity",
        family="papers",
        region="global",
        usage="connector",
        url="https://openreview.net/",
        signal_types=("paper",),
        note="Useful for conference submission and review-cycle signals.",
    ),
    SourceDefinition(
        id="openai_news",
        name="OpenAI News",
        family="blogs",
        region="global",
        usage="connector",
        url="https://openai.com/news/",
        signal_types=("blog", "product", "model"),
        note="Official lab/company signal; pair with paper search before claiming novelty.",
    ),
    SourceDefinition(
        id="anthropic_news",
        name="Anthropic News",
        family="blogs",
        region="global",
        usage="connector",
        url="https://www.anthropic.com/news",
        signal_types=("blog", "product", "model"),
        note="Official lab/company signal.",
    ),
    SourceDefinition(
        id="google_deepmind_blog",
        name="Google DeepMind Blog",
        family="blogs",
        region="global",
        usage="connector",
        url="https://deepmind.google/blog/",
        signal_types=("blog", "model", "benchmark"),
        note="Official AI lab signal.",
    ),
    SourceDefinition(
        id="meta_ai_blog",
        name="Meta AI Blog",
        family="blogs",
        region="global",
        usage="connector",
        url="https://ai.meta.com/blog/",
        signal_types=("blog", "model", "repo"),
        note="Official AI lab/company signal.",
    ),
    SourceDefinition(
        id="huggingface_blog",
        name="Hugging Face Blog",
        family="product",
        region="global",
        usage="connector",
        url="https://huggingface.co/blog",
        signal_types=("blog", "model", "repo"),
        note="Model/release signal with community adoption context.",
    ),
    SourceDefinition(
        id="github_trending",
        name="GitHub Trending",
        family="repos_models",
        region="global",
        usage="sidecar",
        url="https://github.com/trending",
        signal_types=("repo",),
        note="Treat as adoption/momentum signal, not research evidence by itself.",
    ),
    SourceDefinition(
        id="huggingface_models",
        name="Hugging Face Models",
        family="repos_models",
        region="global",
        usage="sidecar",
        url="https://huggingface.co/models",
        signal_types=("model",),
        note="Useful for model-release and benchmark-followup opportunities.",
    ),
    SourceDefinition(
        id="paperswithcode",
        name="Hugging Face Papers / Papers with Code",
        family="repos_models",
        region="global",
        usage="sidecar",
        url="https://huggingface.co/papers/trending",
        signal_types=("paper", "repo", "benchmark"),
        note="Useful for benchmark and implementation momentum signals.",
    ),
    SourceDefinition(
        id="alibaba_cloud_blog",
        name="Alibaba Cloud Blog",
        family="blogs",
        region="cn",
        usage="manual",
        url="https://www.alibabacloud.com/blog",
        signal_types=("blog", "product"),
        note="Chinese big-tech channel; verify Chinese-language primary sources before publication.",
    ),
    SourceDefinition(
        id="baidu_research",
        name="Baidu Research",
        family="blogs",
        region="cn",
        usage="manual",
        url="https://research.baidu.com/",
        signal_types=("blog", "paper", "product"),
        note="Chinese big-tech/research lab channel.",
    ),
    SourceDefinition(
        id="global_ai_leader_watchlist",
        name="Global AI leader social watchlist",
        family="social",
        region="global",
        usage="manual",
        url="",
        signal_types=("news", "blog", "product", "model"),
        note="Use only as weak signal; require primary source before RH handoff.",
    ),
)


def list_source_definitions(
    family: SourceFamily | None = None,
) -> list[SourceDefinition]:
    """Return source definitions, optionally filtered by family."""

    return [
        source
        for source in _SOURCE_DEFINITIONS
        if family is None or source.family == family
    ]
