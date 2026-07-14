"""Semantic Scholar connector tests.

Every test in the default run REPLAYS a snapshot recorded from the live Graph API into
``core/tests/snapshots/semantic_scholar/``. Nothing here touches the network: replay mode
never falls through to a live call, and a missing snapshot raises SnapshotMissingError.
The one live test is marked ``live`` and is deselected by default.

Coroutines are driven with :func:`asyncio.run` rather than pytest-asyncio, so the suite
needs no extra plugin.

The load-bearing assertions are the ones that pin the clean-negative / source-error split:

* 404 from a lookup  -> ``None`` or ``[]``  (a clean negative; S2 answered)
* ``total: 0`` search -> ``[]``             (a clean negative)
* 429 / 500 / timeout -> ``SourceError``    (no clean answer; NEVER a negative)

If a 429 ever became a clean negative, a rate-limited S2 would push D9 axis (a) toward the
refusal-grade ``unresolvable`` verdict and accuse a researcher of fabricating a real
citation. These tests exist to make that regression impossible to land quietly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import httpx
import pytest

from researcher_core.connectors import available_connectors, get_connector_class
from researcher_core.connectors.base import SourceError, SourceErrorKind
from researcher_core.connectors.semantic_scholar import SemanticScholarConnector
from researcher_core.model import CSLRecord, OALocation
from researcher_core.snapshots import (
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

T = TypeVar("T")

PEERJ_DOI = "10.7717/peerj.4375"
MISSING_DOI = "10.1234/thisdoesnotexist9999"
NONSENSE = "zzqqxx blorptron quuxfrobnicator vlimtropy"

#: The in-repo eval store, addressed explicitly: conftest redirects the env override at a
#: tmp_path, and these tests want the real recorded snapshots.
EVAL_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"


def run(coro: Awaitable[T]) -> T:
    """Drive one coroutine to completion."""
    return asyncio.run(coro)  # type: ignore[arg-type]


@pytest.fixture()
def s2() -> SemanticScholarConnector:
    """A connector bound to the recorded eval snapshots, in replay mode. Offline by force."""
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.REPLAY)
    return SemanticScholarConnector(snapshots=session, api_key="")


def with_mock(
    handler: Callable[[httpx.Request], httpx.Response],
    call: Callable[[SemanticScholarConnector], Awaitable[Any]],
) -> Any:
    """Run ``call`` against a connector wired to a stub transport, in LIVE mode.

    Retries and throttling are disabled on the instance so an error path resolves at once
    instead of sleeping through the real backoff schedule.
    """

    async def inner() -> Any:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        connector = SemanticScholarConnector(
            client=client,
            snapshots=SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE),
            api_key="",
        )
        connector.max_retries = 0
        connector.rate_limit_interval = 0.0
        try:
            return await call(connector)
        finally:
            await connector.aclose()

    return asyncio.run(inner())


# ---------------------------------------------------------------------------
# Registration and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert "semantic_scholar" in available_connectors()
    assert get_connector_class("semantic_scholar") is SemanticScholarConnector


def test_declares_all_six_operations() -> None:
    for operation in SemanticScholarConnector.ALL_OPERATIONS:
        assert SemanticScholarConnector.supports(operation), operation


def test_api_key_is_optional_and_never_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S2_API_KEY", raising=False)
    keyless = SemanticScholarConnector()
    assert keyless.api_key == ""
    assert "x-api-key" not in keyless.default_headers()

    monkeypatch.setenv("S2_API_KEY", "secret-quota-key")
    keyed = SemanticScholarConnector()
    assert keyed.default_headers()["x-api-key"] == "secret-quota-key"


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_replays_real_results(s2: SemanticScholarConnector) -> None:
    records = run(s2.search("self-supervised ECG", limit=5))
    assert len(records) == 5
    first = records[0]
    assert first.title == "Self-Supervised ECG Representation Learning for Emotion Recognition"
    assert first.year == 2020
    assert first.source == "semantic_scholar"
    assert first.s2_id == "a484fc24b62758b5bc61e6b967e7935c1a08dcab"
    assert first.citation_count is not None and first.citation_count > 0
    assert all(r.source == "semantic_scholar" for r in records)
    assert all(r.s2_id for r in records)
    assert all(isinstance(r, CSLRecord) for r in records)


def test_search_with_no_hits_is_a_clean_negative(s2: SemanticScholarConnector) -> None:
    # The recorded body is {"offset": 0, "total": 0}: no "data" key at all. That is the API
    # succeeding and saying "nothing matched", so it must be an empty list, not an error.
    assert run(s2.search(NONSENSE, limit=5)) == []


def test_blank_query_short_circuits(s2: SemanticScholarConnector) -> None:
    assert run(s2.search("   ")) == []


# ---------------------------------------------------------------------------
# get_by_id and resolve_doi
# ---------------------------------------------------------------------------


def test_get_by_id_populates_the_full_record(s2: SemanticScholarConnector) -> None:
    record = run(s2.get_by_id(PEERJ_DOI))
    assert record is not None
    assert record.title == (
        "The state of OA: a large-scale analysis of the prevalence and impact of "
        "Open Access articles"
    )
    assert record.DOI == PEERJ_DOI
    assert record.year == 2018
    assert record.issued is not None
    assert (record.issued.month, record.issued.day) == (2, 13)
    assert record.container_title == "PeerJ"
    assert record.volume == "6"
    assert record.ISSN == ["2167-8359"]
    assert record.type == "article-journal"
    assert record.first_author_surname == "Piwowar"
    assert record.author[0].given == "Heather A."
    assert record.s2_id == "c2fccee04fd91439096a80972659dd764e9c0e2d"
    assert record.source_id == record.s2_id
    assert record.citation_count == 1106
    assert record.reference_count == 64
    assert record.pmid == "29456894"
    assert record.pmcid == "PMC5815332"
    assert record.is_oa is True
    assert record.oa_url.startswith("https://")
    assert record.extra["corpus_id"] == "79563844"
    assert record.extra["oa_status"] == "GOLD"
    assert record.abstract.startswith("Despite growing interest in Open Access")


def test_resolve_doi_strips_the_resolver_prefix(s2: SemanticScholarConnector) -> None:
    # The https://doi.org/ form must hash to the SAME request as the bare form, or it would
    # miss the snapshot. That is the normalizer doing its job before the request is built.
    record = run(s2.resolve_doi("https://doi.org/10.7717/PeerJ.4375"))
    assert record is not None
    assert record.DOI == PEERJ_DOI
    assert record.s2_id == "c2fccee04fd91439096a80972659dd764e9c0e2d"


def test_unknown_doi_is_a_clean_negative_not_an_error(s2: SemanticScholarConnector) -> None:
    # S2 answers HTTP 404 with {"error": "Paper with id ... not found"}. The query SUCCEEDED.
    # This is the one case that legitimately feeds D9's "unresolvable", so it must be None
    # and must not raise.
    assert run(s2.get_by_id(f"DOI:{MISSING_DOI}")) is None


def test_resolve_doi_rejects_a_non_doi_without_calling_out(s2: SemanticScholarConnector) -> None:
    assert run(s2.resolve_doi("")) is None
    assert run(s2.resolve_doi("not-a-doi")) is None


def test_get_by_id_accepts_an_arxiv_id(s2: SemanticScholarConnector) -> None:
    record = run(s2.get_by_id("ARXIV:1706.03762"))
    assert record is not None
    assert record.title == "Attention is All you Need"
    assert record.arxiv_id == "1706.03762"
    assert record.DOI == ""  # S2 carries no DOI for this record
    assert record.s2_id == "204e3073870fae3d05bcbc2f6a8e263d9b72e776"
    assert record.citation_count is not None and record.citation_count > 100_000
    # With no DOI, the default citation key falls back to the arXiv id.
    assert record.id == "arxiv:1706.03762"


def test_native_id_normalizes_every_accepted_shape() -> None:
    native = SemanticScholarConnector.native_id
    assert native("10.7717/PeerJ.4375") == "DOI:10.7717/peerj.4375"
    assert native("https://doi.org/10.7717/peerj.4375") == "DOI:10.7717/peerj.4375"
    assert native("doi:10.7717/PeerJ.4375") == "DOI:10.7717/peerj.4375"
    assert native("DOI:10.7717/peerj.4375") == "DOI:10.7717/peerj.4375"
    assert native("1706.03762") == "ARXIV:1706.03762"
    assert native("ARXIV:1706.03762") == "ARXIV:1706.03762"
    assert native("CorpusId:79563844") == "CorpusId:79563844"
    assert native("PMID:29456894") == "PMID:29456894"
    assert (
        native("C2FCCEE04FD91439096A80972659DD764E9C0E2D")
        == "c2fccee04fd91439096a80972659dd764e9c0e2d"
    )
    assert native("") == ""


# ---------------------------------------------------------------------------
# citation graph
# ---------------------------------------------------------------------------


def test_get_citations_unwraps_citing_papers(s2: SemanticScholarConnector) -> None:
    records = run(s2.get_citations(PEERJ_DOI, limit=5))
    assert len(records) == 5
    assert records[0].title == (
        "Mapping global innovations in GenAI for smart cities and implications for Africa"
    )
    assert records[0].DOI == "10.1108/uss-03-2026-0017"
    assert all(r.s2_id for r in records)
    assert all(r.source == "semantic_scholar" for r in records)


def test_get_references_unwraps_cited_papers(s2: SemanticScholarConnector) -> None:
    records = run(s2.get_references(PEERJ_DOI, limit=5))
    assert len(records) == 5
    assert records[0].title == "Sci-Hub provides access to nearly all scholarly literature"
    assert records[0].DOI == "10.7554/elife.32822"
    assert records[0].pmcid == "PMC5832410"
    assert all(r.source == "semantic_scholar" for r in records)


# ---------------------------------------------------------------------------
# open access
# ---------------------------------------------------------------------------


def test_get_oa_pdf_returns_the_recorded_location(s2: SemanticScholarConnector) -> None:
    location = run(s2.get_oa_pdf(PEERJ_DOI))
    assert isinstance(location, OALocation)
    assert location.url == "https://www.neiconjournal.com/jour/article/download/71/53"
    assert location.content_type == "pdf"
    assert location.source == "semantic_scholar"
    assert location.license == "CCBY"
    assert location.is_oa is True


def test_get_oa_pdf_without_an_oa_copy_is_a_clean_negative(s2: SemanticScholarConnector) -> None:
    # A paper S2 knows about but has no open PDF for. Not an error: it answered.
    assert run(s2.get_oa_pdf("10.1126/science.aaq1560")) is None
    assert run(s2.get_oa_pdf("")) is None


# ---------------------------------------------------------------------------
# THE contract: outages are never clean negatives
# ---------------------------------------------------------------------------


def test_429_raises_a_rate_limit_source_error_and_never_an_empty_list() -> None:
    body = {
        "message": "Too Many Requests. Please wait and try again or apply for a key.",
        "code": "429",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json=body)

    async def call(connector: SemanticScholarConnector) -> None:
        with pytest.raises(SourceError) as excinfo:
            await connector.search("self-supervised ECG", limit=5)
        assert excinfo.value.kind is SourceErrorKind.RATE_LIMIT
        assert excinfo.value.status_code == 429
        assert excinfo.value.source == "semantic_scholar"

        # And the same on every other operation: a throttled S2 must never look like a
        # source that cleanly failed to find the paper.
        for operation in (
            connector.resolve_doi(PEERJ_DOI),
            connector.get_by_id(PEERJ_DOI),
            connector.get_citations(PEERJ_DOI),
            connector.get_references(PEERJ_DOI),
            connector.get_oa_pdf(PEERJ_DOI),
        ):
            with pytest.raises(SourceError):
                await operation

    with_mock(handler, call)


def test_5xx_raises_a_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    async def call(connector: SemanticScholarConnector) -> None:
        with pytest.raises(SourceError) as excinfo:
            await connector.resolve_doi(PEERJ_DOI)
        assert excinfo.value.kind is SourceErrorKind.SERVER_ERROR
        assert excinfo.value.status_code == 503

    with_mock(handler, call)


def test_timeout_raises_a_timeout_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    async def call(connector: SemanticScholarConnector) -> None:
        with pytest.raises(SourceError) as excinfo:
            await connector.resolve_doi(PEERJ_DOI)
        assert excinfo.value.kind is SourceErrorKind.TIMEOUT

    with_mock(handler, call)


def test_non_json_payload_raises_bad_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    async def call(connector: SemanticScholarConnector) -> None:
        with pytest.raises(SourceError) as excinfo:
            await connector.search("self-supervised ECG")
        assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE

    with_mock(handler, call)


def test_a_missing_snapshot_is_loud_and_is_not_a_source_error(
    s2: SemanticScholarConnector,
) -> None:
    # SnapshotMissingError is a defect in the snapshot set, not a source outage, so it must
    # not be catchable as SourceError (which would silently degrade it to source_error).
    with pytest.raises(SnapshotMissingError):
        run(s2.search("a query that was never recorded", limit=5))
    assert not issubclass(SnapshotMissingError, SourceError)


# ---------------------------------------------------------------------------
# live smoke (opt-in: pytest -m live)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_search_returns_plausible_results() -> None:
    async def call() -> list[CSLRecord]:
        session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE)
        async with SemanticScholarConnector(snapshots=session) as connector:
            return await connector.search("self-supervised ECG", limit=5)

    records = asyncio.run(call())
    assert records
    assert all(r.title for r in records)
    assert all(r.s2_id for r in records)
