"""Full-text extraction and the axis (d) accessibility verdict (M2.8).

Everything here runs OFFLINE. Document bodies (PDF and HTML) are recorded into a tmp snapshot
store and replayed, exactly as an API response is, so no test reaches the network. The one
live test is marked ``@pytest.mark.live`` and is deselected by default.

The tests that matter most are the ones that assert what the module REFUSES to do:

* a paywalled work yields ``abstract-only`` with an empty segment list, never invented text;
* an unknown work yields ``unavailable``, likewise empty;
* a downed source is recorded as an error and never turns a real paper into ``unavailable``;
* and an :class:`ExtractedDocument` cannot even be constructed with segments unless its
  axis (d) verdict is ``full-text``.

Fabricated full text is the single worst failure this kernel could produce, so it is fenced
in four places and asserted here.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

from researcher_core.connectors.base import SourceError, SourceErrorKind, UnsupportedOperation
from researcher_core.connectors.unpaywall import Accessibility
from researcher_core.fulltext import (
    ABSTRACT_ONLY,
    FULL_TEXT,
    FULLTEXT_SOURCE,
    MAX_CHARS,
    UNAVAILABLE,
    ExtractedDocument,
    FullTextError,
    MissingExtraError,
    PageRect,
    TextBlock,
    build_document,
    extract,
    fetch_document,
    html_to_blocks,
    is_heading,
    pdf_to_blocks,
    pmc_url,
    pymupdf_available,
    resolve_oa,
)
from researcher_core.model import CSLRecord, OALocation
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

# ---------------------------------------------------------------------------
# Fixtures: a real PDF and a real HTML page, built here so no binary lands in the repo
# ---------------------------------------------------------------------------

PAGE_ONE = [
    (72, 720, "Abstract"),
    (72, 690, "We evaluate a self-supervised model on twelve-lead ECG data from 4200 patients."),
    (72, 640, "1. Introduction"),
    (72, 610, "Automated ECG interpretation has been studied for decades, with mixed results."),
]
PAGE_TWO = [
    (72, 720, "2. Methods"),
    (72, 690, "We pretrained the encoder on unlabeled recordings and fine-tuned on 500 labels."),
    (72, 640, "3. Results"),
    (72, 610, "The model reached an accuracy of 0.91, which exceeded the supervised baseline."),
]

HTML_DOC = """
<html>
  <head><title>Ignored</title><style>body { color: red; }</style></head>
  <body>
    <nav>Skip this navigation text entirely</nav>
    <h1>Self-supervised ECG representation learning</h1>
    <h2>Abstract</h2>
    <p>We evaluate a self-supervised model on twelve-lead ECG data from 4200 patients.</p>
    <h2>Methods</h2>
    <p>We pretrained the encoder on unlabeled recordings and fine-tuned on 500 labels.</p>
    <h3>Participants</h3>
    <p>Participants were recruited from two hospitals between 2019 and 2021.</p>
    <h2>Results</h2>
    <p>The model reached an accuracy of 0.91, which exceeded the supervised baseline.</p>
    <script>console.log("skip me");</script>
    <footer>Copyright notice that is not part of the article body</footer>
  </body>
</html>
"""


def make_pdf(pages: list[list[tuple[int, int, str]]]) -> bytes:
    """Build a small, valid, uncompressed PDF. Real bytes, so PyMuPDF really parses it."""
    count = len(pages)
    page_ids = [3 + i for i in range(count)]
    content_ids = [3 + count + i for i in range(count)]
    font_id = 3 + 2 * count

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            "<< /Type /Pages /Kids ["
            + " ".join(f"{i} 0 R" for i in page_ids)
            + f"] /Count {count} >>"
        ).encode("ascii"),
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for index, lines in enumerate(pages):
        body = ["BT /F1 11 Tf"]
        for x, y, text in lines:
            escaped = text.replace("(", r"\(").replace(")", r"\)")
            body.append(f"1 0 0 1 {x} {y} Tm ({escaped}) Tj")
        body.append("ET")
        stream = "\n".join(body).encode("ascii")
        objects[content_ids[index]] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )
        objects[page_ids[index]] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_ids[index]} 0 R >>"
        ).encode("ascii")

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode("ascii") + objects[number] + b"\nendobj\n"

    xref_at = len(out)
    highest = max(objects)
    out += f"xref\n0 {highest + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for number in range(1, highest + 1):
        out += f"{offsets.get(number, 0):010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {highest + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def run(coro: Any) -> Any:
    """Drive one coroutine to completion. The suite needs no pytest-asyncio."""
    return asyncio.run(coro)


def recorded_session(
    store: SnapshotStore, url: str, data: bytes, content_type: str
) -> SnapshotSession:
    """Record a document body into the store, then hand back a replay-only session over it."""
    import base64

    store.record(
        FULLTEXT_SOURCE,
        "document",
        {"url": url},
        {
            "url": url,
            "content_type": content_type,
            "encoding": "base64",
            "content_base64": base64.b64encode(data).decode("ascii"),
        },
    )
    return SnapshotSession(store, SnapshotMode.REPLAY)


# ---------------------------------------------------------------------------
# Stub connectors for the cascade. Each one answers exactly as the real contract says.
# ---------------------------------------------------------------------------


class StubUnpaywall:
    """Unpaywall's three honest answers, plus the outage that is none of them."""

    def __init__(
        self,
        accessibility: Accessibility | None = None,
        error: SourceError | None = None,
    ):
        self._accessibility = accessibility
        self._error = error

    async def get_accessibility(self, doi: str) -> Accessibility:
        if self._error is not None:
            raise self._error
        assert self._accessibility is not None
        return self._accessibility

    async def aclose(self) -> None:
        return None


class StubArxiv:
    """arXiv, which raises UnsupportedOperation for any non-arXiv DOI, as the real one does."""

    def __init__(self, location: OALocation | None = None, supported: bool = False):
        self._location = location
        self._supported = supported

    async def get_oa_pdf(self, identifier: str) -> OALocation | None:
        if not self._supported:
            raise UnsupportedOperation("arxiv", "get_oa_pdf(non-arXiv DOI)")
        return self._location

    async def aclose(self) -> None:
        return None


class StubPubMed:
    def __init__(self, record: CSLRecord | None = None):
        self._record = record

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        return self._record

    async def aclose(self) -> None:
        return None


CLOSED_DOI = "10.1109/5.726791"
OA_DOI = "10.7717/peerj.4375"
UNKNOWN_DOI = "10.9999/nonexistent.12345"


# ---------------------------------------------------------------------------
# Heading heuristics
# ---------------------------------------------------------------------------


def test_is_heading_recognizes_numbered_sections() -> None:
    assert is_heading("1. Introduction") == 1
    assert is_heading("3.2 Participants") == 2
    assert is_heading("4.1.2 Ablation study") == 3


def test_is_heading_recognizes_canonical_section_names() -> None:
    assert is_heading("Methods") == 1
    assert is_heading("Data availability") == 1
    assert is_heading("RESULTS") == 1


def test_is_heading_rejects_body_text() -> None:
    assert is_heading("We pretrained the encoder on unlabeled recordings and fine-tuned it.") == 0
    assert is_heading("") == 0
    assert is_heading("The model reached an accuracy of 0.91.") == 0


# ---------------------------------------------------------------------------
# HTML extraction: no extra required, ever
# ---------------------------------------------------------------------------


def test_html_extraction_produces_sections_and_offsets() -> None:
    blocks = html_to_blocks(HTML_DOC)
    document = build_document(blocks, doc_id=OA_DOI, doi=OA_DOI, content_type="html")

    assert document.accessibility == FULL_TEXT
    assert document.segments
    assert "Skip this navigation" not in document.text
    assert "console.log" not in document.text
    assert "color: red" not in document.text

    sections = document.sections()
    assert any(s.endswith("Methods") for s in sections)
    assert any(s.endswith("Methods/Participants") for s in sections)
    assert any(s.endswith("Results") for s in sections)

    previous_end = -1
    for segment in document.segments:
        assert segment.char_start >= previous_end
        assert segment.char_end > segment.char_start
        # The offsets are into the canonical text, and they are exact.
        assert document.text[segment.char_start : segment.char_end] == segment.text
        previous_end = segment.char_end

    # HTML has no pagination, so no coordinates are invented for it.
    assert all(segment.page_coords == [] for segment in document.segments)


def test_html_section_hierarchy_nests_under_the_h1() -> None:
    document = build_document(html_to_blocks(HTML_DOC), doc_id="d", content_type="html")
    paths = document.sections()
    assert paths[0].startswith("Self-supervised ECG representation learning/")
    assert "Self-supervised ECG representation learning/Methods/Participants" in paths


# ---------------------------------------------------------------------------
# PDF extraction: gated behind the [fulltext] extra
# ---------------------------------------------------------------------------


def test_pdf_extraction_without_the_extra_gives_an_install_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No traceback out of an ImportError: a clear, actionable line the CLI can print."""
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    monkeypatch.setitem(sys.modules, "fitz", None)

    assert pymupdf_available() is False
    with pytest.raises(MissingExtraError) as excinfo:
        pdf_to_blocks(b"%PDF-1.4\n")

    message = str(excinfo.value)
    assert "core[fulltext]" in message
    assert "uv sync --project core --extra fulltext" in message
    # It is a FullTextError, so the CLI catches one family, not a bare ImportError.
    assert isinstance(excinfo.value, FullTextError)


def test_pdf_extraction_yields_pages_offsets_and_coordinates() -> None:
    pytest.importorskip("pymupdf", reason="PDF extraction needs the [fulltext] extra")

    blocks = pdf_to_blocks(make_pdf([PAGE_ONE, PAGE_TWO]))
    assert blocks
    assert {b.page for b in blocks} == {1, 2}
    assert all(b.rect is not None for b in blocks)

    document = build_document(blocks, doc_id=OA_DOI, doi=OA_DOI, content_type="pdf")
    assert document.accessibility == FULL_TEXT
    assert document.segments

    sections = document.sections()
    assert any("Abstract" in s for s in sections)
    assert any("Methods" in s for s in sections)
    assert any("Results" in s for s in sections)

    previous_end = -1
    for segment in document.segments:
        assert segment.char_start >= previous_end
        assert segment.char_end > segment.char_start
        assert document.text[segment.char_start : segment.char_end] == segment.text
        previous_end = segment.char_end

    coords = [rect for segment in document.segments for rect in segment.page_coords]
    assert coords, "PDF segments must carry page coordinates"
    assert {rect.page for rect in coords} == {1, 2}
    for rect in coords:
        assert rect.x1 > rect.x0
        assert rect.y1 > rect.y0

    results = [s for s in document.segments if s.section_path.endswith("Results")]
    assert results
    assert "0.91" in results[0].text
    assert results[0].page_coords[0].page == 2


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def test_long_block_is_split_at_sentence_boundaries_with_exact_offsets() -> None:
    sentence = "The encoder was pretrained on unlabeled recordings from many hospitals. "
    blocks = [
        TextBlock(text="Methods", heading_level=1),
        TextBlock(text=(sentence * 40).strip(), heading_level=0),
    ]
    document = build_document(blocks, doc_id="d", content_type="html")

    assert len(document.segments) > 1
    for segment in document.segments:
        assert len(segment.text) <= MAX_CHARS
        assert document.text[segment.char_start : segment.char_end] == segment.text
    assert all(s.section_path == "Methods" for s in document.segments)


# ---------------------------------------------------------------------------
# The fabrication fence
# ---------------------------------------------------------------------------


def test_a_non_full_text_document_cannot_carry_segments() -> None:
    from researcher_core.fulltext import TextSegment

    with pytest.raises(FullTextError):
        ExtractedDocument(
            doc_id=CLOSED_DOI,
            accessibility=ABSTRACT_ONLY,
            segments=[
                TextSegment(section_path="Results", text="invented", char_start=0, char_end=8)
            ],
        )


def test_paywalled_work_yields_abstract_only_and_never_fabricates_text() -> None:
    """The load-bearing test. A closed paper must come back empty, not imagined."""
    known_but_closed = Accessibility(doi=CLOSED_DOI, verdict=ABSTRACT_ONLY, known=True, is_oa=False)
    record = CSLRecord(
        title="Gradient-based learning applied to document recognition",
        DOI=CLOSED_DOI,
        abstract="Multilayer neural networks trained with the back-propagation algorithm.",
    )
    connectors = {
        "unpaywall": StubUnpaywall(known_but_closed),
        "arxiv": StubArxiv(),
        "pubmed": StubPubMed(record),
    }

    document = run(extract(CLOSED_DOI, connectors=connectors))

    assert document.accessibility == ABSTRACT_ONLY
    assert document.segments == []
    assert document.text == ""
    assert document.abstract.startswith("Multilayer neural networks")
    assert "no open-access copy" in document.reason


def test_unknown_doi_yields_unavailable() -> None:
    connectors = {
        "unpaywall": StubUnpaywall(
            Accessibility(doi=UNKNOWN_DOI, verdict=UNAVAILABLE, known=False)
        ),
        "arxiv": StubArxiv(),
        "pubmed": StubPubMed(None),
    }
    document = run(extract(UNKNOWN_DOI, connectors=connectors))

    assert document.accessibility == UNAVAILABLE
    assert document.segments == []
    assert document.text == ""


def test_a_downed_source_is_an_error_not_a_negative() -> None:
    """A source outage must never demote a known work to `unavailable`."""
    outage = SourceError("unpaywall", "boom", kind=SourceErrorKind.SERVER_ERROR, status_code=503)
    record = CSLRecord(title="A real paper", DOI=CLOSED_DOI, abstract="A real abstract.")
    connectors = {
        "unpaywall": StubUnpaywall(error=outage),
        "arxiv": StubArxiv(),
        "pubmed": StubPubMed(record),
    }

    resolution = run(resolve_oa(CLOSED_DOI, connectors=connectors))
    assert resolution.errors and resolution.errors[0]["kind"] == "server_error"
    assert resolution.known is True
    assert resolution.verdict == ABSTRACT_ONLY

    document = run(extract(CLOSED_DOI, connectors=connectors))
    assert document.accessibility == ABSTRACT_ONLY
    assert document.errors[0]["source"] == "unpaywall"


# ---------------------------------------------------------------------------
# The full-text path, end to end, from a replayed document snapshot
# ---------------------------------------------------------------------------


def test_full_text_cascade_extracts_from_a_replayed_html_snapshot(store: SnapshotStore) -> None:
    url = "https://example.org/oa/peerj.4375.html"
    session = recorded_session(store, url, HTML_DOC.encode("utf-8"), "text/html; charset=utf-8")
    connectors = {
        "unpaywall": StubUnpaywall(
            Accessibility(
                doi=OA_DOI,
                verdict=FULL_TEXT,
                known=True,
                is_oa=True,
                location=OALocation(url=url, content_type="html", source="unpaywall"),
            )
        ),
        "arxiv": StubArxiv(),
        "pubmed": StubPubMed(None),
    }

    document = run(extract(OA_DOI, snapshots=session, connectors=connectors))

    assert document.accessibility == FULL_TEXT
    assert document.doi == OA_DOI
    assert document.source == "unpaywall"
    assert document.source_response_hashes and len(document.source_response_hashes[0]) == 64
    assert any("Results" in s for s in document.sections())
    assert "0.91" in document.text


def test_full_text_cascade_extracts_from_a_replayed_pdf_snapshot(store: SnapshotStore) -> None:
    pytest.importorskip("pymupdf", reason="PDF extraction needs the [fulltext] extra")

    url = "https://example.org/oa/paper.pdf"
    session = recorded_session(store, url, make_pdf([PAGE_ONE, PAGE_TWO]), "application/pdf")
    connectors = {
        "unpaywall": StubUnpaywall(
            Accessibility(
                doi=OA_DOI,
                verdict=FULL_TEXT,
                known=True,
                is_oa=True,
                location=OALocation(url=url, content_type="pdf", source="unpaywall"),
            )
        ),
        "arxiv": StubArxiv(),
        "pubmed": StubPubMed(None),
    }

    document = run(extract(OA_DOI, snapshots=session, connectors=connectors))

    assert document.accessibility == FULL_TEXT
    assert document.content_type == "pdf"
    coords = [r for s in document.segments for r in s.page_coords]
    assert {r.page for r in coords} == {1, 2}


def test_an_oa_link_that_yields_no_text_degrades_to_abstract_only(store: SnapshotStore) -> None:
    """An OA landing page with no article body is not full text, and must not claim to be."""
    url = "https://example.org/oa/empty.html"
    session = recorded_session(store, url, b"<html><body></body></html>", "text/html")
    connectors = {
        "unpaywall": StubUnpaywall(
            Accessibility(
                doi=OA_DOI,
                verdict=FULL_TEXT,
                known=True,
                is_oa=True,
                location=OALocation(url=url, content_type="html", source="unpaywall"),
            )
        ),
        "arxiv": StubArxiv(),
        "pubmed": StubPubMed(None),
    }

    document = run(extract(OA_DOI, snapshots=session, connectors=connectors))
    assert document.accessibility == ABSTRACT_ONLY
    assert document.segments == []


def test_fetch_document_replays_bytes_and_never_goes_live(store: SnapshotStore) -> None:
    url = "https://example.org/oa/paper.html"
    session = recorded_session(store, url, HTML_DOC.encode("utf-8"), "text/html")

    fetched = run(fetch_document(url, snapshots=session))
    assert fetched.data == HTML_DOC.encode("utf-8")
    assert fetched.kind == "html"
    assert len(fetched.response_hash) == 64

    # Byte-identical on replay: the same snapshot, the same configuration, the same bytes.
    again = run(fetch_document(url, snapshots=session))
    assert again.data == fetched.data
    assert again.response_hash == fetched.response_hash


def test_a_missing_document_snapshot_fails_loudly_in_replay(store: SnapshotStore) -> None:
    from researcher_core.snapshots import SnapshotMissingError

    session = SnapshotSession(store, SnapshotMode.REPLAY)
    with pytest.raises(SnapshotMissingError):
        run(fetch_document("https://example.org/never-recorded.pdf", snapshots=session))


def test_a_direct_url_is_extracted_without_the_cascade(store: SnapshotStore) -> None:
    url = "https://example.org/oa/direct.html"
    session = recorded_session(store, url, HTML_DOC.encode("utf-8"), "text/html")

    document = run(extract(url, snapshots=session))
    assert document.accessibility == FULL_TEXT
    assert document.source == "url"
    assert document.doc_id == url


def test_pmc_url_normalizes_the_identifier() -> None:
    assert pmc_url("PMC8371605").endswith("/PMC8371605/")
    assert pmc_url("8371605").endswith("/PMC8371605/")


def test_page_rect_round_trips() -> None:
    rect = PageRect(page=2, x0=72.0, y0=100.5, x1=540.25, y1=120.0)
    assert PageRect.from_json_dict(rect.to_json_dict()) == rect


@pytest.mark.live
def test_live_arxiv_pdf_extracts_full_text(tmp_path: Path) -> None:
    """Opt-in only. Deselected by default; run with `-m live`."""
    pytest.importorskip("pymupdf", reason="PDF extraction needs the [fulltext] extra")
    session = SnapshotSession(SnapshotStore(tmp_path / "live"), SnapshotMode.LIVE)
    document = run(extract("2101.00190", snapshots=session))
    assert document.accessibility == FULL_TEXT
    assert document.segments
