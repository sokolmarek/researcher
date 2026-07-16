"""Tests for the thin stable-core MCP server (M5.9).

Everything here runs OFFLINE and, by design, WITHOUT ``fastmcp`` installed. The server's
value is that it re-exports the kernel with no new logic, so the tests assert two things:

1. The module imports and its five tool callables return the expected JSON shapes when
   called directly with injected or replayed data. Injection (stub connectors, a recorded
   document snapshot, a monkeypatched verify entry point) keeps every case on real kernel
   code paths with no network.
2. The optional ``[mcp]`` extra is truly optional: the module imports without ``fastmcp``,
   ``build_server`` raises the actionable install error, and ``main`` prints the install hint
   and exits 1 rather than throwing a traceback.

If ``fastmcp`` happens to be installed in the dev environment, one extra test drives the
real server object to confirm it registers the five stable tools; it skips otherwise, so the
default suite never requires the extra.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

from researcher_core import mcp_server
from researcher_core.fulltext import FULL_TEXT, FULLTEXT_SOURCE
from researcher_core.mcp_server import (
    STABLE_TOOLS,
    build_server,
    download_oa,
    export_bibliography,
    fastmcp_available,
    get_paper,
    main,
    search_papers,
    verify_citations,
)
from researcher_core.model import CSLRecord
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore
from researcher_core.verify import ReferenceClaim

# ---------------------------------------------------------------------------
# Stub sources: duck-typed connectors that answer from canned records, no network.
# ---------------------------------------------------------------------------


class StubSource:
    """A connector-shaped stub. Answers ``search`` / ``resolve_doi`` / ``get_by_id`` locally."""

    def __init__(
        self,
        name: str,
        *,
        records: list[CSLRecord] | None = None,
        resolve: CSLRecord | None = None,
        caps: tuple[str, ...] = ("search",),
    ) -> None:
        self.name = name
        self._records = records or []
        self._resolve = resolve
        self._caps = set(caps)

    def supports(self, operation: str) -> bool:
        return operation in self._caps

    async def search(
        self, query: str, *, limit: int = 25, since: int | None = None
    ) -> list[CSLRecord]:
        return list(self._records)

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        return self._resolve

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        return self._resolve

    async def aclose(self) -> None:
        return None


def make_record(**fields: Any) -> CSLRecord:
    data: dict[str, Any] = {"type": "article-journal"}
    data.update(fields)
    return CSLRecord.from_csl_json(data)


HTML_DOC = b"""
<html><head><title>ignored</title></head><body>
<h1>Self-supervised ECG representation learning</h1>
<h2>Methods</h2>
<p>We pretrained an encoder on unlabeled recordings and fine-tuned on a labeled subset.</p>
<h2>Results</h2>
<p>The linear probe reached an accuracy of 0.91 on the held-out evaluation split.</p>
</body></html>
"""


def recorded_url_session(
    store: SnapshotStore, url: str, body: bytes, content_type: str
) -> SnapshotSession:
    """Record one document body and hand back a replay-only session over it."""
    store.record(
        FULLTEXT_SOURCE,
        "document",
        {"url": url},
        {
            "url": url,
            "content_type": content_type,
            "encoding": "base64",
            "content_base64": base64.b64encode(body).decode("ascii"),
        },
    )
    return SnapshotSession(store, SnapshotMode.REPLAY)


# ---------------------------------------------------------------------------
# The optional extra is optional: import, build_server, main without fastmcp
# ---------------------------------------------------------------------------


def test_module_exposes_exactly_the_five_stable_tools() -> None:
    assert STABLE_TOOLS == (
        "search_papers",
        "get_paper",
        "verify_citations",
        "export_bibliography",
        "download_oa",
    )
    for name in STABLE_TOOLS:
        assert callable(getattr(mcp_server, name))


def test_build_server_without_fastmcp_raises_an_actionable_error() -> None:
    if fastmcp_available():
        pytest.skip("fastmcp is installed; the missing-extra path cannot be exercised")
    from researcher_core.fulltext import MissingExtraError

    with pytest.raises(MissingExtraError) as excinfo:
        build_server()
    message = str(excinfo.value)
    assert "core[mcp]" in message
    assert "uv sync --project core --extra mcp" in message


def test_main_without_fastmcp_prints_install_hint_and_exits_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    if fastmcp_available():
        pytest.skip("fastmcp is installed; the missing-extra path cannot be exercised")
    code = main([])
    captured = capsys.readouterr()
    assert code == 1
    assert "core[mcp]" in captured.err
    # A clean one-line hint, never a traceback.
    assert "Traceback" not in captured.err


# ---------------------------------------------------------------------------
# Tool 1: search_papers
# ---------------------------------------------------------------------------


def test_search_papers_returns_the_search_result_shape() -> None:
    stub = StubSource(
        "openalex",
        records=[
            make_record(id="W1", title="Self-supervised ECG learning", DOI="10.1000/ecg1"),
            make_record(id="W2", title="Contrastive ECG pretraining", DOI="10.1000/ecg2"),
        ],
    )
    payload = search_papers("ecg", connectors=[stub], limit=5)

    assert payload["query"] == "ecg"
    assert {r["title"] for r in payload["records"]} == {
        "Self-supervised ECG learning",
        "Contrastive ECG pretraining",
    }
    assert payload["counts"]["deduplicated"] == 2
    assert [o["source"] for o in payload["sources"]] == ["openalex"]


def test_search_papers_rejects_a_nonpositive_limit() -> None:
    with pytest.raises(ValueError):
        search_papers("ecg", connectors=[StubSource("openalex")], limit=0)


# ---------------------------------------------------------------------------
# Tool 2: get_paper
# ---------------------------------------------------------------------------


def test_get_paper_found_returns_the_record_and_per_source_outcomes() -> None:
    record = make_record(id="W1", title="A resolved paper", DOI="10.1000/found")
    stub = StubSource("crossref", resolve=record, caps=("resolve_doi", "get_by_id"))
    payload = get_paper("10.1000/found", connectors=[stub])

    assert payload["found"] is True
    assert payload["record"]["title"] == "A resolved paper"
    assert payload["identifier"] == "10.1000/found"
    assert payload["sources"][0]["source"] == "crossref"
    assert payload["sources"][0]["status"] == "ok"


def test_get_paper_clean_negative_is_a_real_answer_not_an_error() -> None:
    stub = StubSource("crossref", resolve=None, caps=("resolve_doi", "get_by_id"))
    payload = get_paper("10.1000/missing", connectors=[stub])

    assert payload["found"] is False
    assert payload["record"] is None
    assert payload["sources"][0]["status"] == "ok"
    assert payload["sources"][0]["record_count"] == 0


# ---------------------------------------------------------------------------
# Tool 3: verify_citations
# ---------------------------------------------------------------------------


def test_verify_citations_builds_claims_from_bibtex_and_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_verify_claims(claims: Any, **kwargs: Any) -> dict[str, Any]:
        claims = list(claims)
        seen["claims"] = claims
        seen["kwargs"] = kwargs
        return {"entries": [], "summary": {"total": len(claims)}}

    monkeypatch.setattr(mcp_server, "verify_claims", fake_verify_claims)

    bibtex = "@article{smith2020, title={A real title}, doi={10.1000/xyz}, year={2020}}"
    report = verify_citations(
        bibtex=bibtex,
        references=["10.1000/abc", "An untyped title reference"],
        check_status=False,
    )

    claims: list[ReferenceClaim] = seen["claims"]
    assert len(claims) == 3
    assert any(c.doi == "10.1000/xyz" for c in claims)
    assert any(c.doi == "10.1000/abc" for c in claims)
    assert any(c.title and not c.doi for c in claims)
    assert seen["kwargs"]["check_status"] is False
    assert report["summary"]["total"] == 3


def test_verify_citations_needs_some_input() -> None:
    with pytest.raises(ValueError):
        verify_citations()


def test_verify_citations_rejects_an_unusable_reference_type() -> None:
    # A reference must be a DOI/title string or a field mapping; anything else is a caller
    # error caught before any source is touched.
    with pytest.raises(ValueError):
        verify_citations(references=[12345])


# ---------------------------------------------------------------------------
# Tool 4: export_bibliography
# ---------------------------------------------------------------------------


def test_export_bibliography_emits_bibtex_from_csl_json() -> None:
    record = {
        "id": "smith2020",
        "type": "article-journal",
        "title": "A real title",
        "DOI": "10.1000/xyz",
    }
    payload = export_bibliography(records=[record], format="bibtex")

    assert payload["format"] == "bibtex"
    assert payload["record_count"] == 1
    assert "A real title" in payload["content"]
    assert "10.1000/xyz" in payload["content"]


def test_export_bibliography_emits_csl_json() -> None:
    import json

    record = {"id": "smith2020", "type": "article-journal", "title": "A real title"}
    payload = export_bibliography(records=[record], format="csl-json")

    assert payload["format"] == "csl-json"
    parsed = json.loads(payload["content"])
    assert parsed[0]["title"] == "A real title"


def test_export_bibliography_reports_unavailable_ris_without_the_export_module() -> None:
    # RIS lives in the optional export module; when it is absent the tool returns a
    # structured error, never a traceback.
    try:
        from researcher_core import export  # noqa: F401

        has_ris = mcp_server._export_emitter("ris") is not None
    except ImportError:
        has_ris = False
    if has_ris:
        pytest.skip("the export module provides RIS; the unavailable path cannot be tested")

    payload = export_bibliography(
        records=[{"id": "x", "type": "article-journal", "title": "T"}], format="ris"
    )
    assert payload["error"] == "format-unavailable"
    assert "ris" in payload["message"]


def test_export_bibliography_round_trips_through_bibtex_input() -> None:
    bibtex = "@article{smith2020, title={A real title}, doi={10.1000/xyz}}"
    payload = export_bibliography(bibtex=bibtex, format="bibtex")
    assert payload["record_count"] == 1
    assert "A real title" in payload["content"]


# ---------------------------------------------------------------------------
# Tool 5: download_oa
# ---------------------------------------------------------------------------


def test_download_oa_extracts_a_replayed_html_document(store: SnapshotStore) -> None:
    url = "https://example.org/oa/ecg.html"
    session = recorded_url_session(store, url, HTML_DOC, "text/html")

    payload = download_oa(url, session=session)

    assert payload["accessibility"] == FULL_TEXT
    assert payload["segment_count"] >= 1
    assert any("Methods" in segment["section"] for segment in payload["sections"])
    # The extractor never invents text: everything present came from the recorded bytes.
    assert any("0.91" in segment["text"] for segment in payload["sections"])


def test_download_oa_missing_document_snapshot_is_reported_loudly(store: SnapshotStore) -> None:
    # A missing snapshot in replay must surface, never a silent empty answer.
    from researcher_core.snapshots import SnapshotMissingError

    session = SnapshotSession(store, SnapshotMode.REPLAY)
    with pytest.raises(SnapshotMissingError):
        download_oa("https://example.org/never/recorded.html", session=session)


# ---------------------------------------------------------------------------
# Sanitization degrades gracefully when the sibling module is absent
# ---------------------------------------------------------------------------


def test_sanitize_is_identity_when_the_module_is_absent() -> None:
    payload = {"text": "plain", "nested": [1, 2, 3]}
    # Whether or not sanitize.py exists, the call must return a well-formed structure with the
    # same data present. Identity is the documented fallback.
    result = mcp_server._sanitize(payload)
    assert result["text"] == "plain"
    assert result["nested"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Optional: exercise the real server when fastmcp is installed
# ---------------------------------------------------------------------------


def test_build_server_registers_five_tools_when_fastmcp_is_present() -> None:
    if not fastmcp_available():
        pytest.skip("fastmcp is not installed; the default suite does not require it")
    import asyncio

    server = build_server()

    async def list_tool_names() -> set[str]:
        tools = await server.list_tools()
        names: set[str] = set()
        for tool in tools:
            name = getattr(tool, "name", None)
            if name is None and isinstance(tool, tuple):
                name = tool[0]
            names.add(str(name))
        return names

    names = asyncio.run(list_tool_names())
    # Five tools registered; the exact registered names carry a _tool suffix in the wrappers.
    assert len([n for n in names if n.endswith("_tool")]) == 5
