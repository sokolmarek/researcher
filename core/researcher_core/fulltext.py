"""Minimal open-access full-text extraction and the axis (d) accessibility verdict (M2.8, D11).

What this module does, and nothing more: resolve an open-access copy of a work through the
OA cascade (Unpaywall, then arXiv, then PMC), fetch it, extract its text, split it into
sections by heading heuristics, keep page coordinates for PDF text, and report how deep the
available evidence went. It is deliberately NOT the semantic RAG stack: no embeddings, no
vector store, no GROBID. Those stay deferred post-1.0.

Axis (d) verdicts, derived from the cascade outcome:

* ``full-text``     - an OA copy was resolved, fetched, and extracted into non-empty text.
* ``abstract-only`` - the work is known to at least one source but no OA copy is reachable,
  so only metadata (and, when a source carries one, an abstract) is available.
* ``unavailable``   - no source knows the identifier at all, or nothing could be extracted.

The verdict is what contextualizes axis (c): an ``insufficient-passage`` faithfulness result
on an ``abstract-only`` document is expected degradation, not a defect.

**This module never invents text.** A paywalled work yields ``abstract-only`` (or
``unavailable``) with an empty segment list. There is no code path that produces a segment
from anything other than bytes that were actually fetched. Fabricated full text would be the
exact failure the whole plugin exists to prevent.

Dependencies and determinism
----------------------------

* **PDF** extraction needs PyMuPDF, which lives behind the ``[fulltext]`` extra. When it is
  absent, :func:`pdf_to_blocks` raises :class:`MissingExtraError`, whose message tells the
  user how to install it. The CLI turns that into a one-line error and exit code 1, never a
  traceback. Nothing else in the kernel imports PyMuPDF, so the base install stays minimal.
* **HTML** extraction uses the stdlib :mod:`html.parser`, always, even when ``selectolax``
  is installed. That is a deliberate determinism choice, not an oversight: passage IDs (D21)
  hash the extracted text, so if extraction depended on which optional parser happened to be
  present, the same document would produce different passage IDs on two machines. One parser,
  one output, IDs stable across machines. A parser change is a
  :data:`researcher_core.PARSER_VERSION` bump, which changes IDs on purpose (D15).

Document fetches route through the snapshot layer exactly like API calls do, under the
source name ``fulltext``, so a recorded PDF or HTML body replays offline byte-for-byte.
"""

from __future__ import annotations

import base64
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

import httpx

from . import PARSER_VERSION as _RAW_PARSER_VERSION
from .connectors import create_connector
from .connectors.base import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    BaseConnector,
    SourceError,
    UnsupportedOperation,
)
from .connectors.unpaywall import ABSTRACT_ONLY, FULL_TEXT, UNAVAILABLE
from .model import CSLRecord, OALocation, is_valid_doi, normalize_doi, sha256_hex
from .snapshots import SnapshotSession, response_hash

__all__ = [
    "ABSTRACT_ONLY",
    "ACCESSIBILITY_VERDICTS",
    "FULL_TEXT",
    "FULLTEXT_SOURCE",
    "MISSING_EXTRA_MESSAGE",
    "PARSER_VERSION",
    "UNAVAILABLE",
    "ExtractedDocument",
    "FetchedDocument",
    "FullTextError",
    "MissingExtraError",
    "OAResolution",
    "PageRect",
    "TextBlock",
    "TextSegment",
    "build_document",
    "dotted_version",
    "extract",
    "extract_blocks",
    "fetch_document",
    "html_to_blocks",
    "is_heading",
    "pdf_to_blocks",
    "resolve_oa",
]


def dotted_version(value: str) -> str:
    """Coerce a version string into the ``major.minor`` form the JSON schemas require.

    ``researcher_core.PARSER_VERSION`` is the bare ``"1"``, while every schema's
    ``versionString`` pattern demands at least two components. Rather than fork the version
    into two constants that could drift apart, the single source of truth is normalized here.
    """
    text = str(value).strip()
    return f"{text}.0" if "." not in text else text


#: Parser version in schema-valid form. It is an input to every passage ID (D21): the same
#: bytes under a different parser version yield different IDs, by design.
PARSER_VERSION = dotted_version(_RAW_PARSER_VERSION)

#: Snapshot source name for fetched document bodies (PDF or HTML), as opposed to API calls.
FULLTEXT_SOURCE = "fulltext"

#: The axis (d) vocabulary, in decreasing evidence depth.
ACCESSIBILITY_VERDICTS = (FULL_TEXT, ABSTRACT_ONLY, UNAVAILABLE)

MISSING_EXTRA_MESSAGE = (
    "PDF extraction needs PyMuPDF, which ships in the optional [fulltext] extra.\n"
    "Install it with one of:\n"
    "  uv sync --project core --extra fulltext\n"
    '  pip install -e "core[fulltext]"\n'
    "HTML full text and every other kernel command work without it."
)

# Chunking targets, in characters of extracted text. A passage is a paragraph-sized unit:
# small enough that a BM25 hit points at something a human can check at a glance, large
# enough that a claim's supporting sentence is not split away from its context.
TARGET_CHARS = 600
MAX_CHARS = 1500

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# Canonical IMRaD-ish section names. A line that IS one of these (after stripping numbering
# and punctuation) is a heading, whatever its typography.
_SECTION_WORDS = frozenset(
    {
        "abstract",
        "acknowledgement",
        "acknowledgements",
        "acknowledgment",
        "acknowledgments",
        "appendix",
        "author contributions",
        "availability",
        "background",
        "code availability",
        "competing interests",
        "conclusion",
        "conclusions",
        "data availability",
        "declarations",
        "discussion",
        "ethics statement",
        "evaluation",
        "experiments",
        "experimental setup",
        "funding",
        "introduction",
        "limitations",
        "materials",
        "materials and methods",
        "method",
        "methodology",
        "methods",
        "participants",
        "procedure",
        "references",
        "related work",
        "results",
        "results and discussion",
        "statistical analysis",
        "summary",
        "supplementary material",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FullTextError(RuntimeError):
    """Full-text resolution or extraction failed in a way the caller must see."""


class MissingExtraError(FullTextError):
    """An optional extraction dependency is not installed.

    Carries the install instructions in its message so the CLI can print ``str(exc)`` and
    exit, which is the whole contract: a clear "install core[fulltext]" line, never a
    traceback out of an ImportError.
    """

    def __init__(self, message: str = MISSING_EXTRA_MESSAGE) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Geometry and text units
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageRect:
    """A rectangle on one page of a PDF, in PDF points, origin at the top left."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "page": int(self.page),
            "x0": round(float(self.x0), 2),
            "y0": round(float(self.y0), 2),
            "x1": round(float(self.x1), 2),
            "y1": round(float(self.y1), 2),
        }

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> PageRect:
        return cls(
            page=int(data["page"]),
            x0=float(data["x0"]),
            y0=float(data["y0"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
        )


@dataclass(frozen=True)
class TextBlock:
    """One extracted block of text, with its rectangle when the source had one.

    ``heading_level`` is ``None`` when the source does not say (a PDF has no markup, so the
    heading heuristics decide), ``0`` when the source says "body" (an HTML ``<p>``), and
    ``1``-``6`` when the source says "heading" (an HTML ``<h2>``).
    """

    text: str
    page: int | None = None
    rect: PageRect | None = None
    heading_level: int | None = None


@dataclass(frozen=True)
class TextSegment:
    """A contiguous chunk of one section: the unit the passage index hashes into an ID.

    ``char_start`` and ``char_end`` index into :attr:`ExtractedDocument.text`, the canonical
    extracted text, and are the offsets that go into the passage ID (D21).
    """

    section_path: str
    text: str
    char_start: int
    char_end: int
    page_coords: list[PageRect] = field(default_factory=list)
    ordinal: int = 0

    @property
    def char_offsets(self) -> tuple[int, int]:
        return (self.char_start, self.char_end)

    def to_json_dict(self) -> dict[str, Any]:
        """The ``{section, text, char_offsets, page_coords}`` shape the CLI emits."""
        return {
            "section": self.section_path,
            "text": self.text,
            "char_offsets": [self.char_start, self.char_end],
            "page_coords": [r.to_json_dict() for r in self.page_coords] or None,
            "ordinal": self.ordinal,
        }


# ---------------------------------------------------------------------------
# The extracted document
# ---------------------------------------------------------------------------


@dataclass
class ExtractedDocument:
    """The result of the cascade plus extraction: text, sections, and the axis (d) verdict.

    ``accessibility`` is the axis (d) verdict. When it is not ``full-text``, ``segments`` is
    empty: no OA bytes were extracted, so there is nothing honest to put there.
    """

    doc_id: str
    accessibility: str
    doi: str = ""
    url: str = ""
    content_type: str = ""
    text: str = ""
    segments: list[TextSegment] = field(default_factory=list)
    abstract: str = ""
    parser_version: str = PARSER_VERSION
    source: str = ""
    source_response_hashes: list[str] = field(default_factory=list)
    sources_tried: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    def __post_init__(self) -> None:
        if self.accessibility not in ACCESSIBILITY_VERDICTS:
            raise FullTextError(
                f"Unknown accessibility verdict {self.accessibility!r}. "
                f"Valid: {', '.join(ACCESSIBILITY_VERDICTS)}."
            )
        if self.accessibility != FULL_TEXT and self.segments:
            # Belt and braces around the fabrication vector: no segment may exist unless the
            # document really was fetched and extracted.
            raise FullTextError(
                "Segments are only permitted on a full-text document; "
                f"accessibility is {self.accessibility!r}."
            )

    @property
    def doc_hash(self) -> str:
        """SHA-256 of the canonical extracted text. Part of every passage ID (D21)."""
        return sha256_hex(self.text)

    @property
    def is_full_text(self) -> bool:
        return self.accessibility == FULL_TEXT

    def sections(self) -> list[str]:
        """Every distinct section path, in reading order."""
        seen: list[str] = []
        for segment in self.segments:
            if segment.section_path not in seen:
                seen.append(segment.section_path)
        return seen

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doi": self.doi or None,
            "url": self.url,
            "content_type": self.content_type,
            "accessibility": self.accessibility,
            "parser_version": self.parser_version,
            "doc_hash": self.doc_hash,
            "source": self.source,
            "source_response_hashes": list(self.source_response_hashes),
            "sources_tried": list(self.sources_tried),
            "errors": list(self.errors),
            "reason": self.reason,
            "abstract": self.abstract,
            "char_count": len(self.text),
            "section_count": len(self.sections()),
            "segment_count": len(self.segments),
            "sections": [s.to_json_dict() for s in self.segments],
        }


# ---------------------------------------------------------------------------
# Heading heuristics
# ---------------------------------------------------------------------------


def is_heading(text: str) -> int:
    """Heuristic heading detector. Returns the heading depth, or ``0`` for body text.

    The rules, in order:

    1. ``3.2 Participants`` -> depth 2 (one level per numbering component).
    2. A canonical section name (``Methods``, ``Data availability``) -> depth 1.
    3. A short ALL-CAPS or Title Case line with no terminal period -> depth 1.

    Anything longer than a headline, or ending in a sentence-final period, is body text.
    """
    line = _collapse(text)
    if not line or len(line) > 120:
        return 0

    numbered = _NUMBERED_HEADING_RE.match(line)
    if numbered:
        rest = numbered.group(2).strip()
        if 0 < len(rest.split()) <= 12 and not rest.endswith("."):
            return len(numbered.group(1).split("."))

    bare = line.strip().strip(".:").casefold()
    if bare in _SECTION_WORDS:
        return 1

    words = line.split()
    if len(words) > 8 or line.endswith((".", ",", ";")):
        return 0
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return 0
    if all(c.isupper() for c in letters):
        return 1
    if all(w[0].isupper() or not w[0].isalpha() for w in words) and len(words) >= 2:
        return 1
    return 0


def _collapse(text: str) -> str:
    """NFC-normalize and collapse every whitespace run to one space."""
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", str(text))).strip()


# ---------------------------------------------------------------------------
# Extraction: PDF
# ---------------------------------------------------------------------------


def pdf_to_blocks(data: bytes) -> list[TextBlock]:
    """Extract text blocks with page rectangles from PDF bytes.

    Requires PyMuPDF (the ``[fulltext]`` extra). Raises :class:`MissingExtraError` with
    install instructions when it is absent, so no caller ever sees a bare ``ImportError``.
    """
    fitz = _import_pymupdf()
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # pragma: no cover - corrupt-PDF path
        raise FullTextError(f"Cannot open the fetched bytes as a PDF: {exc}") from exc

    blocks: list[TextBlock] = []
    try:
        for page_index, page in enumerate(document):
            for raw in page.get_text("blocks"):
                x0, y0, x1, y1, text = raw[0], raw[1], raw[2], raw[3], raw[4]
                block_type = raw[6] if len(raw) > 6 else 0
                if block_type != 0:  # 1 == image block; it carries no text
                    continue
                collapsed = _collapse(text)
                if not collapsed:
                    continue
                page_number = page_index + 1
                blocks.append(
                    TextBlock(
                        text=collapsed,
                        page=page_number,
                        rect=PageRect(page=page_number, x0=x0, y0=y0, x1=x1, y1=y1),
                    )
                )
    finally:
        document.close()
    return blocks


def _import_pymupdf() -> Any:
    """Import PyMuPDF, or raise the actionable :class:`MissingExtraError`."""
    try:
        import pymupdf  # type: ignore[import-not-found]

        return pymupdf
    except ImportError:
        pass
    try:
        import fitz  # type: ignore[import-not-found]

        return fitz
    except ImportError as exc:
        raise MissingExtraError() from exc


def pymupdf_available() -> bool:
    """True when PDF extraction is possible in this environment."""
    try:
        _import_pymupdf()
    except MissingExtraError:
        return False
    return True


# ---------------------------------------------------------------------------
# Extraction: HTML
# ---------------------------------------------------------------------------

_HTML_SKIP_TAGS = frozenset(
    {
        # Void elements (meta, link, br) are deliberately NOT here: they have no end tag, so
        # a skip depth opened on one would never close and would swallow the rest of the page.
        "head",
        "title",
        "script",
        "style",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "svg",
        "iframe",
        "template",
        "button",
        "select",
        "option",
    }
)

_HTML_BLOCK_TAGS = frozenset(
    {
        "p",
        "li",
        "dd",
        "dt",
        "blockquote",
        "pre",
        "figcaption",
        "caption",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "div",
        "section",
        "article",
        "br",
    }
)


class _HTMLBlockExtractor(HTMLParser):
    """Collect block-level text from HTML with the stdlib parser.

    Stdlib on purpose: see the module docstring. Extraction must not vary with which optional
    HTML parser happens to be installed, because passage IDs hash the extracted text.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[TextBlock] = []
        self._buffer: list[str] = []
        self._skip_depth = 0
        self._heading_stack: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth:
            if tag in _HTML_SKIP_TAGS:
                self._skip_depth += 1
            return
        if tag in _HTML_SKIP_TAGS:
            self._flush()
            self._skip_depth = 1
            return
        if tag in _HTML_BLOCK_TAGS:
            self._flush()
        if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            self._heading_stack.append(int(tag[1]))

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if tag in _HTML_SKIP_TAGS:
                self._skip_depth -= 1
            return
        if tag in _HTML_BLOCK_TAGS:
            self._flush()
        if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit() and self._heading_stack:
            self._heading_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = _collapse("".join(self._buffer))
        self._buffer.clear()
        if not text:
            return
        level = self._heading_stack[-1] if self._heading_stack else 0
        self.blocks.append(TextBlock(text=text, heading_level=level))


def html_to_blocks(data: bytes | str) -> list[TextBlock]:
    """Extract block-level text from an HTML document. No extra required, ever."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
    parser = _HTMLBlockExtractor()
    parser.feed(text)
    parser.close()
    return parser.blocks


def extract_blocks(data: bytes, content_type: str) -> list[TextBlock]:
    """Dispatch to the PDF or HTML extractor by content type."""
    kind = _content_kind(content_type, data)
    if kind == "pdf":
        return pdf_to_blocks(data)
    return html_to_blocks(data)


def _content_kind(content_type: str, data: bytes | None = None) -> str:
    """``"pdf"`` or ``"html"``, sniffing the bytes when the declared type is useless."""
    declared = (content_type or "").lower()
    if "pdf" in declared:
        return "pdf"
    if "html" in declared or "xml" in declared or "text" in declared:
        return "html"
    if data is not None and data[:5] == b"%PDF-":
        return "pdf"
    return "html"


# ---------------------------------------------------------------------------
# Sectioning and chunking
# ---------------------------------------------------------------------------


def build_document(
    blocks: Sequence[TextBlock],
    *,
    doc_id: str,
    accessibility: str = FULL_TEXT,
    doi: str = "",
    url: str = "",
    content_type: str = "",
    abstract: str = "",
    source: str = "",
    source_response_hashes: Sequence[str] = (),
    sources_tried: Sequence[str] = (),
    parser_version: str = PARSER_VERSION,
    reason: str = "",
) -> ExtractedDocument:
    """Turn extracted blocks into a sectioned document with offsets and page coordinates.

    The canonical text is every block joined by a blank line, headings included, so a
    character offset is meaningful against a text a human can read. Body blocks are then
    accumulated into segments of roughly :data:`TARGET_CHARS`, never crossing a section
    boundary, and an oversized block is split at sentence boundaries.
    """
    if accessibility != FULL_TEXT:
        return ExtractedDocument(
            doc_id=doc_id,
            accessibility=accessibility,
            doi=doi,
            url=url,
            content_type=content_type,
            abstract=abstract,
            parser_version=parser_version,
            source=source,
            source_response_hashes=list(source_response_hashes),
            sources_tried=list(sources_tried),
            reason=reason,
        )

    pieces: list[str] = []
    spans: list[tuple[TextBlock, int, int, int]] = []  # block, start, end, heading depth
    cursor = 0
    for block in blocks:
        text = _collapse(block.text)
        if not text:
            continue
        start = cursor
        end = start + len(text)
        depth = (
            block.heading_level
            if block.heading_level is not None
            else is_heading(text)
        )
        pieces.append(text)
        spans.append((block, start, end, depth))
        cursor = end + 2  # the "\n\n" separator between blocks

    document_text = "\n\n".join(pieces)

    segments: list[TextSegment] = []
    stack: list[tuple[int, str]] = []
    buffer: list[tuple[TextBlock, int, int]] = []
    section_path = ""

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        for chunk in _chunk_buffer(buffer, document_text, section_path, len(segments)):
            segments.append(chunk)
        buffer = []

    for block, start, end, depth in spans:
        if depth > 0:
            flush()
            title = _collapse(block.text)
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack.append((depth, title))
            section_path = "/".join(t for _, t in stack)
            continue
        buffer.append((block, start, end))
        if sum(e - s for _, s, e in buffer) >= TARGET_CHARS:
            flush()
    flush()

    return ExtractedDocument(
        doc_id=doc_id,
        accessibility=FULL_TEXT,
        doi=doi,
        url=url,
        content_type=content_type,
        text=document_text,
        segments=segments,
        abstract=abstract,
        parser_version=parser_version,
        source=source,
        source_response_hashes=list(source_response_hashes),
        sources_tried=list(sources_tried),
        reason=reason,
    )


def _chunk_buffer(
    buffer: Sequence[tuple[TextBlock, int, int]],
    document_text: str,
    section_path: str,
    ordinal_base: int,
) -> list[TextSegment]:
    """Split one section buffer into segments no longer than :data:`MAX_CHARS`.

    Every offset is computed against ``document_text`` itself rather than by adding up piece
    lengths, so the separators between blocks (and between sentences) can never make an
    offset drift. ``document_text[char_start:char_end] == segment.text`` always holds, and
    the passage-index tests assert it.
    """
    if not buffer:
        return []

    start = buffer[0][1]
    end = buffer[-1][2]
    span = document_text[start:end]
    if len(span) <= MAX_CHARS:
        bounds = [(0, len(span))]
    else:
        bounds = _pack_sentences(span, MAX_CHARS)

    return [
        _segment(
            buffer,
            document_text,
            section_path,
            ordinal_base + index,
            start + rel_start,
            start + rel_end,
        )
        for index, (rel_start, rel_end) in enumerate(bounds)
    ]


def _segment(
    buffer: Sequence[tuple[TextBlock, int, int]],
    document_text: str,
    section_path: str,
    ordinal: int,
    start: int,
    end: int,
) -> TextSegment:
    """One segment over ``[start, end)``, carrying the rectangles of the blocks it covers."""
    covering = [block for block, b_start, b_end in buffer if b_start < end and b_end > start]
    return TextSegment(
        section_path=section_path,
        text=document_text[start:end],
        char_start=start,
        char_end=end,
        page_coords=_merge_rects(covering),
        ordinal=ordinal,
    )


def _pack_sentences(text: str, limit: int) -> list[tuple[int, int]]:
    """Greedily pack sentences into ``(start, end)`` spans of at most ``limit`` characters.

    Spans are offsets into ``text``, never reconstructed strings: the whitespace a split
    consumes stays accounted for.
    """
    sentences: list[tuple[int, int]] = []
    cursor = 0
    for match in _SENTENCE_END_RE.finditer(text):
        if match.start() > cursor:
            sentences.append((cursor, match.start()))
        cursor = match.end()
    if cursor < len(text):
        sentences.append((cursor, len(text)))
    if not sentences:
        return [(0, len(text))]

    spans: list[tuple[int, int]] = []
    current_start, current_end = sentences[0]
    for sentence_start, sentence_end in sentences[1:]:
        if sentence_end - current_start > limit:
            spans.append((current_start, current_end))
            current_start, current_end = sentence_start, sentence_end
        else:
            current_end = sentence_end
    spans.append((current_start, current_end))
    return spans


def _merge_rects(blocks: Any) -> list[PageRect]:
    """One bounding rectangle per page the blocks touch. Empty for HTML, which has no pages."""
    by_page: dict[int, list[float]] = {}
    for block in blocks:
        rect = block.rect
        if rect is None:
            continue
        current = by_page.get(rect.page)
        if current is None:
            by_page[rect.page] = [rect.x0, rect.y0, rect.x1, rect.y1]
        else:
            current[0] = min(current[0], rect.x0)
            current[1] = min(current[1], rect.y0)
            current[2] = max(current[2], rect.x1)
            current[3] = max(current[3], rect.y1)
    return [
        PageRect(page=page, x0=box[0], y0=box[1], x1=box[2], y1=box[3])
        for page, box in sorted(by_page.items())
    ]


# ---------------------------------------------------------------------------
# The OA cascade
# ---------------------------------------------------------------------------


@dataclass
class OAResolution:
    """The outcome of the Unpaywall -> arXiv -> PMC cascade for one identifier."""

    doi: str
    location: OALocation | None = None
    known: bool = False
    record: CSLRecord | None = None
    sources_tried: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        """The axis (d) verdict this cascade outcome implies BEFORE extraction is attempted.

        Extraction can still demote ``full-text`` to ``abstract-only`` (an OA link that
        yields no text is not full text), but it can never promote.
        """
        if self.location is not None:
            return FULL_TEXT
        return ABSTRACT_ONLY if self.known else UNAVAILABLE

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "verdict": self.verdict,
            "known": self.known,
            "location": self.location.to_json_dict() if self.location else None,
            "sources_tried": list(self.sources_tried),
            "errors": list(self.errors),
        }


async def resolve_oa(
    identifier: str,
    *,
    snapshots: SnapshotSession | None = None,
    connectors: Mapping[str, BaseConnector] | None = None,
) -> OAResolution:
    """Resolve an OA location for a DOI through the cascade: Unpaywall, then arXiv, then PMC.

    A source outage is recorded in :attr:`OAResolution.errors` and the cascade moves on: one
    downed index must never turn a reachable paper into ``unavailable``. A clean negative
    (the source answered, it has no OA copy) simply advances to the next step.
    """
    doi = normalize_doi(identifier)
    resolution = OAResolution(doi=doi)
    owned: list[BaseConnector] = []

    def connector(name: str) -> BaseConnector:
        if connectors is not None and name in connectors:
            return connectors[name]
        instance = create_connector(name, snapshots=snapshots)
        owned.append(instance)
        return instance

    try:
        # 1. Unpaywall: the purpose-built OA index, and the only source that distinguishes
        #    "known but closed" (abstract-only) from "unknown" (unavailable).
        try:
            unpaywall = connector("unpaywall")
            accessibility = await unpaywall.get_accessibility(doi)  # type: ignore[attr-defined]
            resolution.sources_tried.append("unpaywall")
            resolution.known = resolution.known or accessibility.known
            if accessibility.record is not None:
                resolution.record = accessibility.record
            if accessibility.location is not None:
                resolution.location = accessibility.location
                return resolution
        except SourceError as exc:
            resolution.sources_tried.append("unpaywall")
            resolution.errors.append(exc.to_json_dict())

        # 2. arXiv: an arXiv-issued DOI or a bare arXiv identifier always has a free PDF.
        try:
            arxiv = connector("arxiv")
            location = await arxiv.get_oa_pdf(identifier)
            resolution.sources_tried.append("arxiv")
            if location is not None:
                resolution.known = True
                resolution.location = location
                return resolution
        except UnsupportedOperation:
            pass  # not an arXiv identifier; the step simply does not apply
        except SourceError as exc:
            resolution.sources_tried.append("arxiv")
            resolution.errors.append(exc.to_json_dict())

        # 3. PMC: PubMed knows the PMC identifier, and a PMC article is free full text.
        try:
            pubmed = connector("pubmed")
            record = await pubmed.resolve_doi(doi) if is_valid_doi(doi) else None
            resolution.sources_tried.append("pubmed")
            if record is not None:
                resolution.known = True
                if resolution.record is None or not resolution.record.abstract:
                    resolution.record = record
                if record.pmcid:
                    resolution.location = OALocation(
                        url=pmc_url(record.pmcid),
                        content_type="html",
                        source="pmc",
                        host_type="repository",
                        is_oa=True,
                    )
                    return resolution
        except SourceError as exc:
            resolution.sources_tried.append("pubmed")
            resolution.errors.append(exc.to_json_dict())
    finally:
        for instance in owned:
            await instance.aclose()

    return resolution


def pmc_url(pmcid: str) -> str:
    """The PMC article URL for a PMC identifier (``PMC8371605`` or ``8371605``)."""
    bare = str(pmcid).strip().upper()
    if not bare.startswith("PMC"):
        bare = f"PMC{bare}"
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{bare}/"


# ---------------------------------------------------------------------------
# Fetching a document body
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FetchedDocument:
    """Bytes of one fetched OA document, plus the snapshot hash of the recorded body."""

    url: str
    content_type: str
    data: bytes
    response_hash: str

    @property
    def kind(self) -> str:
        return _content_kind(self.content_type, self.data)


def _document_body(url: str, content_type: str, data: bytes) -> dict[str, Any]:
    """The snapshot body for a fetched document: base64, so it is JSON and content-addressed."""
    return {
        "url": url,
        "content_type": content_type,
        "encoding": "base64",
        "content_base64": base64.b64encode(data).decode("ascii"),
    }


async def fetch_document(
    url: str,
    *,
    snapshots: SnapshotSession | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> FetchedDocument:
    """Fetch one OA document, routed through the snapshot layer.

    In replay mode this reads the recorded body and never opens a socket, exactly like a
    connector call: the snapshot source is ``fulltext`` and the request params are
    ``{"url": <url>}``.
    """
    session = snapshots or SnapshotSession.from_env()
    params = {"url": url}
    owns_client = client is None

    async def fetcher() -> dict[str, Any]:
        nonlocal client
        if client is None:
            client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": user_agent},
            )
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            raise FullTextError(f"Cannot fetch {url}: {exc}") from exc
        if response.status_code >= 400:
            raise FullTextError(f"{url} returned HTTP {response.status_code}.")
        return _document_body(
            url,
            response.headers.get("Content-Type", ""),
            response.content,
        )

    try:
        body = await session.afetch(FULLTEXT_SOURCE, "document", params, fetcher)
    finally:
        if owns_client and client is not None:
            await client.aclose()

    if not isinstance(body, Mapping) or "content_base64" not in body:
        raise FullTextError(
            f"The recorded body for {url} is not a document snapshot "
            "(expected a 'content_base64' field)."
        )
    return FetchedDocument(
        url=str(body.get("url") or url),
        content_type=str(body.get("content_type") or ""),
        data=base64.b64decode(str(body["content_base64"])),
        response_hash=response_hash(body),
    )


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


async def extract(
    identifier: str,
    *,
    snapshots: SnapshotSession | None = None,
    connectors: Mapping[str, BaseConnector] | None = None,
    client: httpx.AsyncClient | None = None,
    doc_id: str = "",
) -> ExtractedDocument:
    """Resolve, fetch, and extract the full text of a DOI, arXiv ID, or direct OA URL.

    Returns an :class:`ExtractedDocument` carrying the axis (d) verdict. The three outcomes,
    and what each one guarantees:

    * ``full-text``     - bytes were fetched and text was extracted. ``segments`` is non-empty.
    * ``abstract-only`` - a source knows the work; no OA copy is reachable. ``segments`` is
      EMPTY, and so is ``text``. The abstract, when a source supplied one, is in ``abstract``.
    * ``unavailable``   - nothing resolved. ``segments`` and ``text`` are empty.

    Nothing in this function can put text into ``segments`` that did not come out of fetched
    bytes, which is the invariant that keeps a paywalled paper from acquiring an invented
    body (:class:`ExtractedDocument` re-checks it on construction).

    Raises :class:`MissingExtraError` when the resolved document is a PDF and PyMuPDF is not
    installed. The message names the extra to install; the CLI prints it and exits 1.
    """
    if _looks_like_url(identifier):
        fetched = await fetch_document(identifier, snapshots=snapshots, client=client)
        blocks = extract_blocks(fetched.data, fetched.content_type)
        return _finish(
            blocks,
            doc_id=doc_id or identifier,
            doi="",
            url=fetched.url,
            content_type=fetched.kind,
            source="url",
            response_hashes=[fetched.response_hash],
            sources_tried=["url"],
            abstract="",
            errors=[],
        )

    resolution = await resolve_oa(identifier, snapshots=snapshots, connectors=connectors)
    record = resolution.record
    abstract = record.abstract if record is not None else ""
    doi = resolution.doi or normalize_doi(identifier)
    identity = doc_id or doi or identifier

    if resolution.location is None:
        verdict = resolution.verdict
        reason = (
            "no open-access copy found; the work is known to "
            f"{', '.join(resolution.sources_tried) or 'no source'}"
            if verdict == ABSTRACT_ONLY
            else "no source resolved this identifier"
        )
        return ExtractedDocument(
            doc_id=identity,
            accessibility=verdict,
            doi=doi,
            content_type="",
            abstract=abstract,
            sources_tried=resolution.sources_tried,
            errors=resolution.errors,
            reason=reason,
        )

    fetched = await fetch_document(
        resolution.location.url, snapshots=snapshots, client=client
    )
    blocks = extract_blocks(fetched.data, fetched.content_type or resolution.location.content_type)
    return _finish(
        blocks,
        doc_id=identity,
        doi=doi,
        url=fetched.url,
        content_type=fetched.kind,
        source=resolution.location.source,
        response_hashes=[fetched.response_hash],
        sources_tried=resolution.sources_tried,
        abstract=abstract,
        errors=resolution.errors,
    )


def _finish(
    blocks: Sequence[TextBlock],
    *,
    doc_id: str,
    doi: str,
    url: str,
    content_type: str,
    source: str,
    response_hashes: Sequence[str],
    sources_tried: Sequence[str],
    abstract: str,
    errors: Sequence[dict[str, Any]],
) -> ExtractedDocument:
    """Build the document, demoting to ``abstract-only`` when the fetch yielded no text."""
    if not blocks:
        return ExtractedDocument(
            doc_id=doc_id,
            accessibility=ABSTRACT_ONLY,
            doi=doi,
            url=url,
            content_type=content_type,
            abstract=abstract,
            source=source,
            source_response_hashes=list(response_hashes),
            sources_tried=list(sources_tried),
            errors=list(errors),
            reason="the resolved open-access location yielded no extractable text",
        )
    return build_document(
        blocks,
        doc_id=doc_id,
        accessibility=FULL_TEXT,
        doi=doi,
        url=url,
        content_type=content_type,
        abstract=abstract,
        source=source,
        source_response_hashes=list(response_hashes),
        sources_tried=list(sources_tried),
    )


def _looks_like_url(value: str) -> bool:
    return str(value).strip().lower().startswith(("http://", "https://"))
