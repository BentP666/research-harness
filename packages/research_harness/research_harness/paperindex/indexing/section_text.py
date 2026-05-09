from __future__ import annotations

import re

from ..types import SectionNode
from ..utils import flatten_nodes, summarize_text


def normalize_section_title(title: str) -> str:
    text = re.sub(r"\*+", "", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^\s*(?:appendix|chapter|section)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*[A-Za-z]?(?:\d+(?:\.\d+)*)[:.\-\s]+", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def titles_match(left: str, right: str) -> bool:
    left_norm = normalize_section_title(left)
    right_norm = normalize_section_title(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    shorter, longer = sorted((left_norm, right_norm), key=len)
    return len(shorter) >= 6 and shorter in longer


def attach_section_text(
    tree: list[SectionNode], pages_text: list[str]
) -> list[SectionNode]:
    for node in flatten_nodes(tree):
        start = max(1, node.start_page)
        end = max(start, node.end_page)
        chunk = "\n".join(
            pages_text[index - 1]
            for index in range(start, min(end, len(pages_text)) + 1)
            if 0 < index <= len(pages_text)
        )
        node.section_text = _trim_page_span_text(chunk, node.title)
        node.summary = _build_node_summary(node.title, node.section_text)
    return tree


def attach_markdown_section_text(
    tree: list[SectionNode], markdown: str
) -> list[SectionNode]:
    """Attach bounded section chunks from a Markdown heading outline."""

    lines = markdown.splitlines()
    spans = _markdown_heading_line_indices(lines)
    for node, (start_idx, _, _) in zip(flatten_nodes(tree), spans):
        next_start = len(lines)
        for candidate_idx, _, _ in spans:
            if candidate_idx > start_idx:
                next_start = candidate_idx
                break
        chunk = "\n".join(lines[start_idx:next_start]).strip()
        node.section_text = chunk
        node.summary = _build_node_summary(node.title, chunk)
    return tree


def _trim_page_span_text(text: str, title: str) -> str:
    normalized_title = normalize_section_title(title)
    if not normalized_title:
        return text.strip()
    lines = [line for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        normalized_line = normalize_section_title(line)
        if titles_match(title, line) or (
            normalized_title and normalized_title in normalized_line
        ):
            return "\n".join(lines[idx:]).strip()
    return text.strip()


def _build_node_summary(title: str, text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    filtered: list[str] = []
    for line in lines:
        if titles_match(title, line):
            continue
        filtered.append(line)
    return summarize_text(" ".join(filtered) or text)


def _markdown_heading_line_indices(lines: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if not match:
            continue
        title = re.sub(r"\s+", " ", match.group(2)).strip()
        title = re.sub(r"<!--.*?-->", "", title).strip()
        if title:
            spans.append((idx, len(match.group(1)), title))
    return spans
