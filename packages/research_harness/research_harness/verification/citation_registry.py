"""RH-native source registry and citation sanitizer.

This module intentionally implements a small, deterministic verification
contract for Research Harness rather than vendoring any external agent code.
The core invariant is simple: generated reports may cite only sources that
were already registered from RH's paper pool or explicitly passed in.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any
from urllib.parse import parse_qsl
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

from ..storage.db import Database

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "fbclid",
    "gclid",
}
_SHORTENER_HOSTS = {
    "bit.ly",
    "buff.ly",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "t.co",
    "tinyurl.com",
}
_TRAILING_URL_CHARS = ".,;:)]}>\"'"
_URL_RE = re.compile(r"https?://[^\s\])}>\"']+", re.IGNORECASE)
_INLINE_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_REFERENCE_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(references|bibliography|sources)\s*$",
    re.IGNORECASE,
)
_REFERENCE_LINE_RE = re.compile(r"^\s*\[(\d+)\]\s*(.*?)\s*$")
_DOI_RE = re.compile(
    r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\]\)>,;]+)",
    re.IGNORECASE,
)
_ARXIV_RE = re.compile(
    r"(?:arxiv:\s*|https?://arxiv\.org/(?:abs|pdf)/)?"
    r"([a-z-]+/[0-9]{7}|\d{4}\.\d{4,5})(?:v\d+)?",
    re.IGNORECASE,
)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)", re.IGNORECASE)


@dataclass(frozen=True)
class CitationSource:
    """One citable source known to Research Harness."""

    source_id: str
    title: str = ""
    url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    paper_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def stable_key(self) -> str:
        if self.paper_id is not None:
            return f"paper:{self.paper_id}"
        if self.doi:
            return f"doi:{_normalize_doi(self.doi)}"
        if self.arxiv_id:
            return f"arxiv:{_normalize_arxiv(self.arxiv_id)}"
        if self.url:
            return f"url:{_normalize_url(self.url)}"
        return self.source_id


@dataclass(frozen=True)
class ValidCitation:
    """A retained reference after sanitization."""

    original_number: int
    new_number: int
    source_id: str
    ref_text: str
    repaired: bool = False


@dataclass(frozen=True)
class RemovedCitation:
    """A removed reference and the deterministic reason."""

    original_number: int
    ref_text: str
    reason: str


@dataclass(frozen=True)
class CitationSanitizeResult:
    """Output of sanitize_citations."""

    sanitized_text: str
    valid_citations: list[ValidCitation] = field(default_factory=list)
    removed_citations: list[RemovedCitation] = field(default_factory=list)
    repaired_count: int = 0

    @property
    def valid_count(self) -> int:
        return len(self.valid_citations)

    @property
    def removed_count(self) -> int:
        return len(self.removed_citations)


class SourceRegistry:
    """Registry of all sources a generated report is allowed to cite."""

    def __init__(self) -> None:
        self._sources: list[CitationSource] = []
        self._by_url: dict[str, CitationSource] = {}
        self._by_doi: dict[str, CitationSource] = {}
        self._by_arxiv: dict[str, CitationSource] = {}
        self._by_title: dict[str, CitationSource] = {}

    @classmethod
    def from_topic(cls, db: Database, topic_id: int) -> "SourceRegistry":
        """Build a registry from papers linked to a RH topic."""

        registry = cls()
        conn = db.connect()
        try:
            rows = conn.execute(
                """
                SELECT p.id, p.title, p.doi, p.arxiv_id, p.url
                FROM papers p
                JOIN paper_topics pt ON pt.paper_id = p.id
                WHERE pt.topic_id = ?
                """,
                (topic_id,),
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            paper_id = int(row["id"])
            registry.add(
                CitationSource(
                    source_id=f"paper:{paper_id}",
                    paper_id=paper_id,
                    title=row["title"] or "",
                    doi=row["doi"] or "",
                    arxiv_id=row["arxiv_id"] or "",
                    url=row["url"] or "",
                )
            )
        return registry

    def add(self, source: CitationSource) -> None:
        """Register a citable source and all deterministic aliases."""

        self._sources.append(source)
        title_key = _normalize_title(source.title)
        if title_key:
            self._by_title.setdefault(title_key, source)

        for url in _candidate_urls(source):
            normalized = _normalize_url(url)
            if normalized:
                self._by_url.setdefault(normalized, source)

        doi = _normalize_doi(source.doi)
        if doi:
            self._by_doi.setdefault(doi, source)

        arxiv_id = _normalize_arxiv(source.arxiv_id)
        if arxiv_id:
            self._by_arxiv.setdefault(arxiv_id, source)

    def all_sources(self) -> list[CitationSource]:
        return list(self._sources)

    def resolve_url(self, raw_url: str) -> CitationSource | None:
        """Resolve a URL to a source, allowing one unique clipped-URL repair."""

        url = _strip_url(raw_url)
        if not _is_citable_url(url):
            return None
        normalized = _normalize_url(url)
        if normalized in self._by_url:
            return self._by_url[normalized]

        # LLMs sometimes clip a long URL at a word boundary. Repair only if the
        # clipped URL is specific enough and matches exactly one registered URL.
        parsed = urlparse(normalized)
        if len(normalized) < 24 or _is_domain_only(parsed):
            return None
        candidates = [
            source
            for candidate_url, source in self._by_url.items()
            if candidate_url.startswith(normalized)
            or (
                urlparse(candidate_url).netloc == parsed.netloc
                and urlparse(candidate_url).path.startswith(parsed.path)
            )
        ]
        unique = {source.stable_key: source for source in candidates}
        if len(unique) == 1:
            return next(iter(unique.values()))
        return None

    def resolve_doi(self, text: str) -> CitationSource | None:
        doi = _extract_doi(text)
        if not doi:
            return None
        return self._by_doi.get(doi)

    def resolve_arxiv(self, text: str) -> CitationSource | None:
        arxiv_id = _extract_arxiv(text)
        if not arxiv_id:
            return None
        return self._by_arxiv.get(arxiv_id)

    def resolve_title(self, text: str) -> CitationSource | None:
        title = _normalize_title(text)
        if not title:
            return None
        if title in self._by_title:
            return self._by_title[title]
        matches = [
            source for key, source in self._by_title.items() if key and key in title
        ]
        unique = {source.stable_key: source for source in matches}
        if len(unique) == 1:
            return next(iter(unique.values()))
        return None

    def canonical_url(self, source: CitationSource) -> str:
        if source.url:
            return _normalize_url(source.url)
        if source.doi:
            return f"https://doi.org/{quote(_normalize_doi(source.doi), safe='/')}"
        if source.arxiv_id:
            return f"https://arxiv.org/abs/{_normalize_arxiv(source.arxiv_id)}"
        return ""


def sanitize_citations(text: str, registry: SourceRegistry) -> CitationSanitizeResult:
    """Remove, repair, deduplicate, and renumber references in Markdown text."""

    normalized_text = text.replace("【", "[").replace("】", "]")
    split = _split_references(normalized_text)
    if split is None:
        return CitationSanitizeResult(
            sanitized_text=_sanitize_body_urls(normalized_text, registry, {})
        )

    body, header, ref_lines = split
    kept: list[tuple[int, str, CitationSource, str, bool]] = []
    removed: list[RemovedCitation] = []
    duplicate_to_kept: dict[int, int] = {}
    seen_source_to_old_number: dict[str, int] = {}
    repaired_count = 0

    for line in ref_lines:
        parsed = _parse_reference_line(line)
        if parsed is None:
            continue
        old_number, ref_text = parsed
        resolved = _resolve_reference_text(ref_text, registry)
        if resolved is None:
            removed.append(
                RemovedCitation(
                    original_number=old_number,
                    ref_text=ref_text,
                    reason="not_in_source_registry",
                )
            )
            continue

        source, repaired_ref, repaired = resolved
        source_key = source.stable_key
        if source_key in seen_source_to_old_number:
            duplicate_to_kept[old_number] = seen_source_to_old_number[source_key]
            removed.append(
                RemovedCitation(
                    original_number=old_number,
                    ref_text=ref_text,
                    reason=f"duplicate_of_{seen_source_to_old_number[source_key]}",
                )
            )
            continue

        seen_source_to_old_number[source_key] = old_number
        kept.append((old_number, source_key, source, repaired_ref, repaired))
        if repaired:
            repaired_count += 1

    old_to_new: dict[int, int] = {}
    source_key_to_new: dict[str, int] = {}
    valid_citations: list[ValidCitation] = []
    for new_number, (old_number, source_key, source, ref_text, repaired) in enumerate(
        kept, start=1
    ):
        old_to_new[old_number] = new_number
        source_key_to_new[source_key] = new_number
        valid_citations.append(
            ValidCitation(
                original_number=old_number,
                new_number=new_number,
                source_id=source.source_id,
                ref_text=ref_text,
                repaired=repaired,
            )
        )

    for duplicate_old, kept_old in duplicate_to_kept.items():
        if kept_old in old_to_new:
            old_to_new[duplicate_old] = old_to_new[kept_old]

    cleaned_body = _rewrite_inline_citations(body, old_to_new)
    cleaned_body = _sanitize_body_urls(cleaned_body, registry, source_key_to_new)

    if not kept:
        return CitationSanitizeResult(
            sanitized_text=cleaned_body.rstrip() + "\n",
            valid_citations=[],
            removed_citations=removed,
            repaired_count=repaired_count,
        )

    rendered_refs = [header.strip()]
    for new_number, (_, _, _, ref_text, _) in enumerate(kept, start=1):
        rendered_refs.append(f"[{new_number}] {ref_text}")

    sanitized = (
        cleaned_body.rstrip() + "\n\n" + "\n".join(rendered_refs).rstrip() + "\n"
    )
    return CitationSanitizeResult(
        sanitized_text=sanitized,
        valid_citations=valid_citations,
        removed_citations=removed,
        repaired_count=repaired_count,
    )


def _split_references(text: str) -> tuple[str, str, list[str]] | None:
    lines = text.splitlines()
    char_offset = 0
    for index, line in enumerate(lines):
        if _REFERENCE_HEADER_RE.match(line):
            body = text[:char_offset].rstrip()
            header = line.strip() if line.strip().startswith("#") else "## References"
            return body, header, lines[index + 1 :]
        char_offset += len(line) + 1
    return None


def _parse_reference_line(line: str) -> tuple[int, str] | None:
    match = _REFERENCE_LINE_RE.match(line)
    if not match:
        return None
    return int(match.group(1)), match.group(2).strip()


def _resolve_reference_text(
    ref_text: str, registry: SourceRegistry
) -> tuple[CitationSource, str, bool] | None:
    url_match = _URL_RE.search(ref_text)
    if url_match:
        raw_url = _strip_url(url_match.group(0))
        source = registry.resolve_url(raw_url)
        if source is None:
            return None
        canonical = registry.canonical_url(source)
        if canonical and _normalize_url(raw_url) != canonical:
            return source, ref_text.replace(url_match.group(0), canonical), True
        return source, ref_text, False

    source = registry.resolve_doi(ref_text)
    if source is not None:
        return source, ref_text, False

    source = registry.resolve_arxiv(ref_text)
    if source is not None:
        return source, ref_text, False

    source = registry.resolve_title(ref_text)
    if source is not None:
        return source, ref_text, False
    return None


def _rewrite_inline_citations(body: str, old_to_new: dict[int, int]) -> str:
    def replace(match: re.Match[str]) -> str:
        numbers = [int(part.strip()) for part in match.group(1).split(",")]
        rewritten: list[int] = []
        for number in numbers:
            new = old_to_new.get(number)
            if new is not None and new not in rewritten:
                rewritten.append(new)
        if not rewritten:
            return ""
        return "[" + ", ".join(str(number) for number in rewritten) + "]"

    cleaned = _INLINE_CITATION_RE.sub(replace, body)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned


def _sanitize_body_urls(
    body: str, registry: SourceRegistry, source_key_to_new: dict[str, int]
) -> str:
    def replace_markdown(match: re.Match[str]) -> str:
        label = match.group(1)
        source = registry.resolve_url(match.group(2))
        if source is None:
            return label
        cite = source_key_to_new.get(source.stable_key)
        return f"{label} [{cite}]" if cite else label

    def replace_url(match: re.Match[str]) -> str:
        source = registry.resolve_url(match.group(0))
        if source is None:
            return ""
        cite = source_key_to_new.get(source.stable_key)
        return f"[{cite}]" if cite else ""

    cleaned = _MARKDOWN_LINK_RE.sub(replace_markdown, body)
    cleaned = _URL_RE.sub(replace_url, cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned


def _candidate_urls(source: CitationSource) -> list[str]:
    urls = []
    if source.url:
        urls.append(source.url)
    doi = _normalize_doi(source.doi)
    if doi:
        urls.append(f"https://doi.org/{quote(doi, safe='/')}")
    arxiv_id = _normalize_arxiv(source.arxiv_id)
    if arxiv_id:
        urls.append(f"https://arxiv.org/abs/{arxiv_id}")
        urls.append(f"https://arxiv.org/pdf/{arxiv_id}")
    return urls


def _normalize_url(raw_url: str) -> str:
    url = _strip_url(raw_url)
    if not url:
        return ""
    parsed = urlparse(unescape(url))
    if not parsed.scheme or not parsed.netloc:
        return ""
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    path = unquote(parsed.path).rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def _strip_url(raw_url: str) -> str:
    return unescape(str(raw_url or "").strip()).rstrip(_TRAILING_URL_CHARS)


def _is_citable_url(raw_url: str) -> bool:
    parsed = urlparse(_strip_url(raw_url))
    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host in _SHORTENER_HOSTS:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    if "..." in raw_url or "…" in raw_url:
        return False
    return not _is_domain_only(parsed)


def _is_domain_only(parsed) -> bool:
    return parsed.path in {"", "/"} and not parsed.query


def _normalize_doi(raw: str) -> str:
    match = _DOI_RE.search(str(raw or ""))
    if not match:
        return ""
    return match.group(1).rstrip(_TRAILING_URL_CHARS).lower()


def _extract_doi(text: str) -> str:
    return _normalize_doi(text)


def _normalize_arxiv(raw: str) -> str:
    match = _ARXIV_RE.search(str(raw or ""))
    if not match:
        return ""
    return match.group(1).lower()


def _extract_arxiv(text: str) -> str:
    return _normalize_arxiv(text)


def _normalize_title(title: str) -> str:
    value = re.sub(r"https?://\S+", "", title or "")
    value = _DOI_RE.sub("", value)
    value = _ARXIV_RE.sub("", value)
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)
