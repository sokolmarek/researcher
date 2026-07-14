"""OpenAlex connector tests.

Every test here runs OFFLINE. The records asserted below are replayed from the real
responses recorded in ``core/tests/snapshots/openalex/`` on 2026-07-14, so the assertions
are real parsed values (a real citation count, a real retraction flag, a real abstract
reconstructed from a real inverted index), not hand-written fixtures.

The two error-semantics tests use an ``httpx.MockTransport``, not the network: they pin the
one distinction the whole D9 verdict rests on, namely that a 404 is a clean negative
(``None``) while a 429 or a 5xx is a :class:`SourceError`.

The only test that touches the network is marked ``@pytest.mark.live`` and is deselected by
default (``addopts = -m 'not live'``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, TypeVar

import httpx
import pytest

from researcher_core.connectors import create_connector, get_connector_class
from researcher_core.connectors.base import SourceError, SourceErrorKind
from researcher_core.connectors.openalex import (
    OpenAlexConnector,
    invert_abstract,
)
from researcher_core.model import CSLRecord, OALocation
from researcher_core.snapshots import (
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

T = TypeVar("T")

#: The in-repo eval store. Absolute, so the autouse tmp_path env redirect in conftest.py
#: (which points the DEFAULT store at an empty temp dir) cannot accidentally hide it.
EVAL_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"

# Identifiers that were actually recorded. Keep in step with the recording script.
OA_DOI = "10.7717/peerj.4375"  # Piwowar et al., "The state of OA" (PeerJ, 2018)
OA_ID = "W2741809807"
RETRACTED_DOI = "10.1038/nature00870"  # Nature, retracted
ARXIV_ID = "2103.00020"  # CLIP
MISSING_DOI = "10.9999/definitely-not-a-real-doi-xyz"  # OpenAlex answers 404


def run(coro: Awaitable[T]) -> T:
    """Drive one coroutine to completion (the suite has no pytest-asyncio dependency)."""
    return asyncio.run(coro)  # type: ignore[arg-type]


@pytest.fixture()
def openalex() -> OpenAlexConnector:
    """A connector in REPLAY mode over the committed eval snapshots. Never goes live."""
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.REPLAY)
    return OpenAlexConnector(snapshots=session)


def mock_connector(handler: Any, **kwargs: Any) -> OpenAlexConnector:
    """A LIVE-mode connector whose transport is a stub. Exercises the HTTP error mapping."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE, cache=None)
    return OpenAlexConnector(client=client, snapshots=session, **kwargs)


# ---------------------------------------------------------------------------
# Registration and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("openalex") is OpenAlexConnector
    assert isinstance(create_connector("openalex"), OpenAlexConnector)


def test_declares_every_operation_it_implements() -> None:
    for operation in OpenAlexConnector.ALL_OPERATIONS:
        assert OpenAlexConnector.supports(operation), operation


# ---------------------------------------------------------------------------
# Abstract inversion
# ---------------------------------------------------------------------------


def test_invert_abstract_rebuilds_word_order() -> None:
    inverted = {"Despite": [0], "growing": [1], "interest": [2], "in": [3, 5], "OA": [4, 6]}
    assert invert_abstract(inverted) == "Despite growing interest in OA in OA"


def test_invert_abstract_is_empty_for_missing_or_broken_index() -> None:
    assert invert_abstract(None) == ""
    assert invert_abstract({}) == ""
    assert invert_abstract({"word": "not-a-list"}) == ""


# ---------------------------------------------------------------------------
# Search (replayed)
# ---------------------------------------------------------------------------


def test_search_returns_real_parsed_records(openalex: OpenAlexConnector) -> None:
    records = run(openalex.search("self-supervised ECG", limit=5))

    assert len(records) == 5
    assert all(isinstance(r, CSLRecord) for r in records)
    assert all(r.source == "openalex" for r in records)
    assert all(r.openalex_id.startswith("W") for r in records)

    top = records[0]
    assert top.title == (
        "Self-Supervised ECG Representation Learning for Emotion Recognition"
    )
    assert top.DOI == "10.1109/taffc.2020.3014842"
    assert top.openalex_id == "W3005055041"
    assert top.year == 2020
    assert top.type == "article-journal"
    assert top.first_author_surname == "Sarkar"
    assert top.citation_count is not None and top.citation_count > 100
    assert top.is_retracted is False


def test_search_since_filters_to_recent_work(openalex: OpenAlexConnector) -> None:
    records = run(openalex.search("self-supervised ECG", limit=5, since=2023))

    assert len(records) == 5
    assert all(r.year is not None and r.year >= 2023 for r in records)


def test_search_with_an_empty_query_is_a_clean_negative(openalex: OpenAlexConnector) -> None:
    # No request is made at all, so this must not raise SnapshotMissingError either.
    assert run(openalex.search("   ")) == []


# ---------------------------------------------------------------------------
# Lookup (replayed)
# ---------------------------------------------------------------------------


def test_resolve_doi_parses_the_full_record(openalex: OpenAlexConnector) -> None:
    record = run(openalex.resolve_doi(OA_DOI))

    assert record is not None
    assert record.DOI == OA_DOI
    assert record.openalex_id == OA_ID
    assert record.title.startswith("The state of OA: a large-scale analysis")
    assert record.container_title == "PeerJ"
    assert record.year == 2018
    # OpenAlex itself types this journal article as "book-chapter" (its own metadata
    # defect). The connector maps the type it is given rather than second-guessing it, so
    # the record says "chapter". Recorded here deliberately: it is the kind of cross-source
    # disagreement axis (a) exists to surface, not something to paper over in the parser.
    assert record.type == "chapter"
    assert record.first_author_surname == "Piwowar"
    assert [a.surname for a in record.author][:3] == ["Piwowar", "Priem", "Larivière"]
    assert record.volume == "6"
    assert record.page == "e4375"
    assert record.ISSN and "2167-8359" in record.ISSN
    assert record.citation_count is not None and record.citation_count > 1000
    assert record.reference_count is not None and record.reference_count > 0
    assert record.is_oa is True
    assert record.is_retracted is False
    assert record.source == "openalex"
    # The default citation key falls out of the DOI.
    assert record.id == OA_DOI


def test_abstract_is_reconstructed_from_the_inverted_index(
    openalex: OpenAlexConnector,
) -> None:
    record = run(openalex.resolve_doi(OA_DOI))

    assert record is not None
    assert record.abstract.startswith("Despite growing interest in Open Access (OA)")
    assert len(record.abstract) > 500


def test_resolve_doi_accepts_a_resolver_url(openalex: OpenAlexConnector) -> None:
    # normalize_doi strips the prefix, so this hits the same recorded request.
    record = run(openalex.resolve_doi("https://doi.org/10.7717/PeerJ.4375"))

    assert record is not None
    assert record.openalex_id == OA_ID


def test_unknown_doi_is_a_clean_negative_not_an_error(openalex: OpenAlexConnector) -> None:
    """OpenAlex 404s on a DOI it does not hold. Under D9 that is evidence, not an outage."""
    record = run(openalex.resolve_doi(MISSING_DOI))

    assert record is None


def test_get_by_id_accepts_an_openalex_id(openalex: OpenAlexConnector) -> None:
    record = run(openalex.get_by_id(OA_ID))

    assert record is not None
    assert record.DOI == OA_DOI
    assert record.openalex_id == OA_ID


def test_get_by_id_accepts_a_doi(openalex: OpenAlexConnector) -> None:
    record = run(openalex.get_by_id(OA_DOI))

    assert record is not None
    assert record.openalex_id == OA_ID


def test_get_by_id_accepts_an_arxiv_id(openalex: OpenAlexConnector) -> None:
    record = run(openalex.get_by_id(ARXIV_ID))

    assert record is not None
    assert record.title == "Learning Transferable Visual Models From Natural Language Supervision"
    assert record.arxiv_id == ARXIV_ID
    assert record.DOI == "10.48550/arxiv.2103.00020"
    assert record.id == "10.48550/arxiv.2103.00020"
    assert record.type == "article"  # OpenAlex "preprint"
    assert record.is_oa is True


def test_get_by_id_rejects_garbage_as_a_clean_negative(openalex: OpenAlexConnector) -> None:
    assert run(openalex.get_by_id("")) is None
    assert run(openalex.get_by_id("not an identifier")) is None


# ---------------------------------------------------------------------------
# Axis (b): is_retracted must survive the trip
# ---------------------------------------------------------------------------


def test_retraction_flag_is_populated_not_dropped(openalex: OpenAlexConnector) -> None:
    """status.py reads this field. A dropped flag would silently clear a real retraction."""
    record = run(openalex.resolve_doi(RETRACTED_DOI))

    assert record is not None
    assert record.is_retracted is True
    assert record.title.startswith("RETRACTED ARTICLE")
    # And it survives serialization into the CSL-JSON custom slot.
    assert record.to_csl_json()["custom"]["is_retracted"] is True


def test_a_clean_work_reports_is_retracted_false(openalex: OpenAlexConnector) -> None:
    record = run(openalex.resolve_doi(OA_DOI))

    assert record is not None
    assert record.is_retracted is False  # False, not None: the field was really present.


# ---------------------------------------------------------------------------
# Citation graph (replayed)
# ---------------------------------------------------------------------------


def test_get_citations_returns_citing_works(openalex: OpenAlexConnector) -> None:
    citing = run(openalex.get_citations(OA_DOI, limit=5))

    assert len(citing) == 5
    assert all(r.source == "openalex" for r in citing)
    assert all(r.openalex_id.startswith("W") for r in citing)
    assert OA_ID not in {r.openalex_id for r in citing}  # never cites itself


def test_get_references_hydrates_referenced_works(openalex: OpenAlexConnector) -> None:
    references = run(openalex.get_references(OA_ID, limit=5))

    assert len(references) == 5
    titles = [r.title for r in references]
    assert "Anatomy of green open access" in titles
    assert all(r.openalex_id.startswith("W") for r in references)


def test_get_citations_of_an_unknown_doi_is_a_clean_negative(
    openalex: OpenAlexConnector,
) -> None:
    assert run(openalex.get_citations(MISSING_DOI)) == []


def test_get_references_of_an_unknown_doi_is_a_clean_negative(
    openalex: OpenAlexConnector,
) -> None:
    assert run(openalex.get_references(MISSING_DOI)) == []


# ---------------------------------------------------------------------------
# Axis (d): OA locations (replayed)
# ---------------------------------------------------------------------------


def test_get_oa_pdf_returns_the_best_oa_location(openalex: OpenAlexConnector) -> None:
    location = run(openalex.get_oa_pdf(OA_DOI))

    assert isinstance(location, OALocation)
    assert location.is_oa is True
    assert location.source == "openalex"
    assert location.version == "publishedVersion"
    assert location.license == "cc-by"
    assert location.url.startswith("https://")


def test_get_oa_pdf_prefers_a_real_pdf_url(openalex: OpenAlexConnector) -> None:
    location = run(openalex.get_oa_pdf("10.48550/arxiv.2103.00020"))

    assert location is not None
    assert location.content_type == "pdf"
    assert location.url == "https://arxiv.org/pdf/2103.00020"
    assert location.version == "submittedVersion"
    assert location.host_type == "repository"


def test_get_oa_pdf_of_an_unknown_doi_is_a_clean_negative(
    openalex: OpenAlexConnector,
) -> None:
    assert run(openalex.get_oa_pdf(MISSING_DOI)) is None


# ---------------------------------------------------------------------------
# Source errors versus clean negatives (stub transport, still offline)
# ---------------------------------------------------------------------------


def test_server_error_raises_source_error(openalex: OpenAlexConnector) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    connector = mock_connector(handler, timeout=1.0)
    connector.max_retries = 0
    with pytest.raises(SourceError) as excinfo:
        run(connector.resolve_doi(OA_DOI))

    assert excinfo.value.kind is SourceErrorKind.SERVER_ERROR
    assert excinfo.value.status_code == 500
    assert excinfo.value.source == "openalex"


def test_rate_limit_raises_source_error(openalex: OpenAlexConnector) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")

    connector = mock_connector(handler, timeout=1.0)
    connector.max_retries = 0
    with pytest.raises(SourceError) as excinfo:
        run(connector.search("self-supervised ECG"))

    assert excinfo.value.kind is SourceErrorKind.RATE_LIMIT


def test_not_found_is_a_clean_negative_over_the_transport(openalex: OpenAlexConnector) -> None:
    """The same 404 that the live API returns, asserted at the transport boundary."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="<!doctype html><title>404 Not Found</title>")

    connector = mock_connector(handler)
    assert run(connector.resolve_doi(MISSING_DOI)) is None


def test_polite_pool_mailto_is_sent_but_stays_out_of_the_snapshot_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The request carries &mailto=; the snapshot key does not depend on it."""
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(404)

    monkeypatch.setenv("OPENALEX_MAILTO", "mareksokol98@gmail.com")
    connector = mock_connector(handler)
    assert run(connector.resolve_doi(MISSING_DOI)) is None
    assert seen[0].params["mailto"] == "mareksokol98@gmail.com"

    # And a replay with the env var set still finds the snapshot recorded without it.
    replayer = OpenAlexConnector(
        snapshots=SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.REPLAY)
    )
    record = run(replayer.resolve_doi(OA_DOI))
    assert record is not None and record.openalex_id == OA_ID


def test_missing_snapshot_is_loud_and_is_not_a_source_error(
    openalex: OpenAlexConnector,
) -> None:
    """Replay never falls through to the network, and a gap in the store is never an outage."""
    with pytest.raises(SnapshotMissingError):
        run(openalex.search("a query that was never recorded"))

    try:
        run(openalex.search("a query that was never recorded"))
    except SnapshotMissingError as exc:
        assert not isinstance(exc, SourceError)


# ---------------------------------------------------------------------------
# Live smoke (opt-in: pytest -m live)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_search_smoke() -> None:
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE, cache=None)
    connector = OpenAlexConnector(snapshots=session)
    try:
        records = run(connector.search("self-supervised ECG", limit=5))
    finally:
        run(connector.aclose())

    assert records
    assert all(r.title for r in records)
    assert all(r.source == "openalex" for r in records)


@pytest.mark.live
def test_live_unknown_doi_is_a_clean_negative() -> None:
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE, cache=None)
    connector = OpenAlexConnector(snapshots=session)
    try:
        assert run(connector.resolve_doi(MISSING_DOI)) is None
    finally:
        run(connector.aclose())
