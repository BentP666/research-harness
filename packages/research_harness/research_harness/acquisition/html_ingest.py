"""Minimal HTML → markdown fetcher for URL-only paper_ingest.

Designed for the 'doctrine' / blog-post case where the source is a
plain-text article (e.g. an Anthropic engineering blog, a research lab
writeup) rather than a PDF. Stdlib-only: uses html.parser so there is
no runtime dependency on bs4 / html2text / readability.

Not a general-purpose scraper:
- No JS execution.
- Strips <script>, <style>, <nav>, <header>, <footer> blocks.
- Preserves structure at heading / paragraph / list / code / link level.
- Returns (title, markdown_body). Either may be empty on failure.

If the URL returns a non-text MIME type (e.g. application/pdf) we
return empty strings and let the caller decide to dispatch to the
PDF-acquisition pipeline instead.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


_SKIP_TAGS = frozenset(
    {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg"}
)
_BLOCK_TAGS = frozenset({"p", "div", "section", "article", "br", "hr"})
_HEADING_TAGS = {f"h{i}": i for i in range(1, 7)}
_LIST_ITEM_TAGS = frozenset({"li"})


@dataclass
class FetchedPage:
    url: str
    title: str = ""
    markdown: str = ""
    content_type: str = ""
    http_status: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.markdown.strip())


class _MarkdownExtractor(HTMLParser):
    """Convert a limited subset of HTML to markdown.

    Tracks a tag stack so we can detect <script> / <style> and drop
    their text entirely. Keeps link text + href. Emits paragraph breaks
    at block-level tags.
    """

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self._parts: list[str] = []
        self._title_parts: list[str] = []
        self._in_title = False
        self._pending_href: str = ""
        self._in_link = False
        self._link_text: list[str] = []

    # ---- helpers ----

    def _in_skip(self) -> bool:
        return any(t in _SKIP_TAGS for t in self._stack)

    def _emit(self, s: str) -> None:
        if s:
            self._parts.append(s)

    # ---- events ----

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack.append(tag)
        if tag == "title":
            self._in_title = True
            return
        if self._in_skip():
            return
        if tag in _HEADING_TAGS:
            self._emit("\n\n" + "#" * _HEADING_TAGS[tag] + " ")
        elif tag == "li":
            self._emit("\n- ")
        elif tag == "br":
            self._emit("  \n")
        elif tag in _BLOCK_TAGS:
            self._emit("\n\n")
        elif tag == "code":
            self._emit("`")
        elif tag == "pre":
            self._emit("\n\n```\n")
        elif tag in {"strong", "b"}:
            self._emit("**")
        elif tag in {"em", "i"}:
            self._emit("*")
        elif tag == "a":
            self._in_link = True
            self._link_text = []
            href = ""
            for k, v in attrs:
                if k == "href" and v:
                    href = v
                    break
            self._pending_href = href

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag == "title":
            self._in_title = False
            return
        if self._in_skip():
            return
        if tag == "code":
            self._emit("`")
        elif tag == "pre":
            self._emit("\n```\n")
        elif tag in {"strong", "b"}:
            self._emit("**")
        elif tag in {"em", "i"}:
            self._emit("*")
        elif tag == "a" and self._in_link:
            text = "".join(self._link_text).strip()
            href = self._pending_href
            if text and href:
                self._emit(f"[{text}]({href})")
            elif text:
                self._emit(text)
            self._in_link = False
            self._link_text = []
            self._pending_href = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
            return
        if self._in_skip():
            return
        if self._in_link:
            self._link_text.append(data)
            return
        self._parts.append(data)

    # ---- result ----

    def title(self) -> str:
        return " ".join("".join(self._title_parts).split())

    def markdown(self) -> str:
        text = "".join(self._parts)
        # Collapse > 2 newlines in a row, trim trailing whitespace per line
        lines = [line.rstrip() for line in text.splitlines()]
        collapsed: list[str] = []
        blank_run = 0
        for line in lines:
            if not line.strip():
                blank_run += 1
                if blank_run > 1:
                    continue
            else:
                blank_run = 0
            collapsed.append(line)
        return "\n".join(collapsed).strip()


def fetch_html_as_markdown(
    url: str, *, timeout: float = 15.0, user_agent: str | None = None
) -> FetchedPage:
    """Fetch a URL and extract (title, markdown_body).

    Non-text-HTML responses (e.g. application/pdf) return an empty body
    so the caller can fall through to PDF acquisition.
    """
    ua = user_agent or "research-harness/paper_ingest (HTML extractor)"
    req = urllib.request.Request(
        url, headers={"User-Agent": ua, "Accept": "text/html,*/*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" not in ct and "application/xhtml" not in ct:
                return FetchedPage(
                    url=url,
                    content_type=ct,
                    http_status=getattr(resp, "status", 200),
                    error=f"non-HTML content-type: {ct or 'unknown'}",
                )
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                body = raw.decode(charset, errors="replace")
            except LookupError:
                body = raw.decode("utf-8", errors="replace")
            http_status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        return FetchedPage(
            url=url, http_status=exc.code, error=f"HTTP {exc.code}: {exc.reason}"
        )
    except Exception as exc:  # noqa: BLE001 — network errors all logged the same
        logger.warning("fetch_html_as_markdown network error for %s: %s", url, exc)
        return FetchedPage(url=url, error=f"{type(exc).__name__}: {exc}")

    extractor = _MarkdownExtractor()
    try:
        extractor.feed(body)
        extractor.close()
    except Exception as exc:  # noqa: BLE001 — malformed HTML should not crash ingest
        logger.warning("fetch_html_as_markdown parse error for %s: %s", url, exc)
        return FetchedPage(url=url, http_status=http_status, error=f"parse: {exc}")

    return FetchedPage(
        url=url,
        title=extractor.title(),
        markdown=extractor.markdown(),
        content_type=ct,
        http_status=http_status,
    )


__all__ = ["FetchedPage", "fetch_html_as_markdown"]
