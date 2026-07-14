"""PubMed connector tests.

Everything in the default run is OFFLINE: every request replays a snapshot recorded from the
real NCBI E-utilities API into ``core/tests/snapshots/pubmed/``. Unplug the network and this
file still passes. The only live test is marked ``@pytest.mark.live`` and is deselected by
default (see ``addopts`` in ``core/pyproject.toml``).

The assertions are on the REAL parsed values from those recordings (PMID 34265844 is the
AlphaFold paper; PMID 32450107 is the retracted Lancet hydroxychloroquine registry study), not
on hand-written fixtures, so a parser regression that quietly mangles a field fails here.

The clean-negative versus source-error split (D9) is exercised in both directions, because
getting it backwards is the failure mode that would let a throttled index accuse a researcher
of fabricating a real citation:

* fabricated DOI, nonexistent PMID, no-hit query -> ``None`` / ``[]``
* 429, 500, timeout, efetch <ERROR>, esearch ERROR, unparseable XML -> ``SourceError``
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import httpx
import pytest

from researcher_core.connectors import create_connector, get_connector_class
from researcher_core.connectors.base import (
    SnapshotMissingError,
    SourceError,
    SourceErrorKind,
    UnsupportedOperation,
)
from researcher_core.connectors.pubmed import PubMedConnector
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

T = TypeVar("T")

EVAL_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"

ALPHAFOLD_DOI = "10.1038/s41586-021-03819-2"
ALPHAFOLD_PMID = "34265844"
ALPHAFOLD_PMCID = "PMC8371605"
RETRACTED_DOI = "10.1016/S0140-6736(20)31180-6"
RETRACTED_PMID = "32450107"
FABRICATED_DOI = "10.9999/this-doi-does-not-exist-12345"
MISSING_PMID = "999999999"
NO_HIT_QUERY = "zzzqqxxvv nonexistent phrase 12345 qqq"
QUERY = "self-supervised ECG"


def run(coro: Awaitable[T]) -> T:
    """Drive one coroutine to completion. The suite has no pytest-asyncio dependency."""
    return asyncio.run(coro)  # type: ignore[arg-type]


@pytest.fixture()
def pubmed() -> PubMedConnector:
    """A connector replaying the committed eval snapshots. Never touches the network."""
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.REPLAY)
    return PubMedConnector(snapshots=session)


def mock_connector(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    store: SnapshotStore | None = None,
    **kwargs: Any,
) -> PubMedConnector:
    """A LIVE-mode connector whose transport is a stub. Still no network, but no snapshot
    either: this is how the transport-level error mapping gets exercised."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    session = SnapshotSession(store or SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE)
    connector = PubMedConnector(client=client, snapshots=session, **kwargs)
    connector.max_retries = 0  # keep the backoff out of the test runtime
    connector.rate_limit_interval = 0.0
    return connector


# ---------------------------------------------------------------------------
# Registry and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("pubmed") is PubMedConnector
    assert isinstance(create_connector("pubmed"), PubMedConnector)


def test_declares_exactly_the_operations_it_implements() -> None:
    for operation in ("search", "get_by_id", "resolve_doi"):
        assert PubMedConnector.supports(operation)
    for operation in ("get_citations", "get_references", "get_oa_pdf"):
        assert not PubMedConnector.supports(operation)


def test_unsupported_operations_raise_rather_than_faking_a_negative(
    pubmed: PubMedConnector,
) -> None:
    # UnsupportedOperation is not a clean negative and not a source error: nothing was asked
    # of the API, so callers skip the source instead of recording an outcome.
    with pytest.raises(UnsupportedOperation):
        run(pubmed.get_citations(ALPHAFOLD_PMID))
    with pytest.raises(UnsupportedOperation):
        run(pubmed.get_references(ALPHAFOLD_PMID))
    with pytest.raises(UnsupportedOperation):
        run(pubmed.get_oa_pdf(ALPHAFOLD_DOI))


def test_throttles_at_the_ncbi_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    keyless = PubMedConnector()
    assert keyless.rate_limit_interval == pytest.approx(0.34)  # 3 requests/second
    assert keyless.rate_limit_interval * 3 >= 1.0

    keyed = PubMedConnector(api_key="fake-key")
    assert keyed.rate_limit_interval == pytest.approx(0.11)  # 10 requests/second
    assert keyed.rate_limit_interval < keyless.rate_limit_interval


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_replays_real_records(pubmed: PubMedConnector) -> None:
    hits = run(pubmed.search(QUERY, limit=10))

    assert len(hits) == 10
    assert [h.pmid for h in hits[:3]] == ["34973584", "36004899", "40102504"]

    first = hits[0]
    assert first.title == "Self-supervised representation learning from 12-lead ECG data"
    assert first.DOI == "10.1016/j.compbiomed.2021.105114"
    assert first.container_title == "Computers in biology and medicine"
    assert first.year == 2022
    assert first.volume == "141"
    assert first.page == "105114"
    assert first.ISSN == ["1879-0534"]
    assert first.language == "eng"
    assert [a.surname for a in first.author] == ["Mehari", "Strodthoff"]
    assert first.author[0].given == "Temesgen"
    assert first.abstract.startswith("Clinical 12-lead electrocardiography")
    assert first.URL == "https://pubmed.ncbi.nlm.nih.gov/34973584/"

    assert all(h.source == "pubmed" for h in hits)
    assert all(h.source_id == h.pmid for h in hits)
    assert all(h.type == "article-journal" for h in hits)


def test_search_preserves_the_esearch_relevance_order(pubmed: PubMedConnector) -> None:
    # efetch does not promise to echo the id order, so the connector re-imposes it.
    hits = run(pubmed.search(QUERY, limit=10))
    assert [h.pmid for h in hits] == [
        "34973584",
        "36004899",
        "40102504",
        "41056617",
        "39250357",
        "37948139",
        "40749448",
        "39631267",
        "41446031",
        "41337234",
    ]


def test_search_populates_pmcid_when_pubmed_has_free_full_text(
    pubmed: PubMedConnector,
) -> None:
    # pmcid is the free-full-text route the axis (d) OA cascade consumes, so it has to
    # survive the parse. Absence is normal (paywalled), presence must be exact.
    hits = run(pubmed.search(QUERY, limit=10))
    by_pmid = {h.pmid: h for h in hits}
    assert by_pmid["36004899"].pmcid == "PMC9404921"
    assert by_pmid["40102504"].pmcid == "PMC11920277"
    assert by_pmid["34973584"].pmcid == ""


def test_search_since_filters_by_publication_year(pubmed: PubMedConnector) -> None:
    hits = run(pubmed.search(QUERY, limit=5, since=2024))
    assert len(hits) == 5
    assert all(h.year is not None and h.year >= 2024 for h in hits)


def test_search_with_no_hits_is_a_clean_negative(pubmed: PubMedConnector) -> None:
    # An empty list, NOT an exception: the query succeeded and nothing matched.
    assert run(pubmed.search(NO_HIT_QUERY)) == []


def test_empty_query_short_circuits_without_a_request(pubmed: PubMedConnector) -> None:
    # No snapshot exists for an empty term, so if this hit the API it would raise
    # SnapshotMissingError instead of returning [].
    assert run(pubmed.search("   ")) == []


# ---------------------------------------------------------------------------
# resolve_doi and get_by_id
# ---------------------------------------------------------------------------


def test_resolve_doi_returns_the_real_record(pubmed: PubMedConnector) -> None:
    record = run(pubmed.resolve_doi(ALPHAFOLD_DOI))

    assert record is not None
    assert record.pmid == ALPHAFOLD_PMID
    assert record.pmcid == ALPHAFOLD_PMCID
    assert record.DOI == ALPHAFOLD_DOI.lower()
    assert record.title == "Highly accurate protein structure prediction with AlphaFold"
    assert record.container_title == "Nature"
    assert record.year == 2021
    assert record.issued is not None and record.issued.month == 8
    assert record.volume == "596"
    assert record.issue == "7873"
    assert record.page == "583-589"
    assert record.first_author_surname == "Jumper"
    assert len(record.author) == 34
    assert record.author[8].family == "Žídek"  # Zidek: unicode survives the parse
    assert record.extra["journal_abbreviation"] == "Nature"
    assert record.is_retracted is None  # not flagged, and absence is not asserted as False


def test_resolve_doi_is_case_insensitive_and_accepts_a_resolver_url(
    pubmed: PubMedConnector,
) -> None:
    # normalize_doi lowercases before the [AID] query, so all three spellings hit the one
    # recorded snapshot. The DOI on the record is the bare, lowercased canonical form.
    for spelling in (
        ALPHAFOLD_DOI,
        ALPHAFOLD_DOI.upper(),
        f"https://doi.org/{ALPHAFOLD_DOI}",
    ):
        record = run(pubmed.resolve_doi(spelling))
        assert record is not None and record.DOI == ALPHAFOLD_DOI.lower()


def test_get_by_id_accepts_a_pmid_with_or_without_its_prefix(
    pubmed: PubMedConnector,
) -> None:
    direct = run(pubmed.get_by_id(ALPHAFOLD_PMID))
    prefixed = run(pubmed.get_by_id(f"PMID: {ALPHAFOLD_PMID}"))

    assert direct is not None and prefixed is not None
    assert direct.content_hash() == prefixed.content_hash()
    assert direct.DOI == ALPHAFOLD_DOI.lower()
    assert direct.first_author_surname == "Jumper"


def test_get_by_id_resolves_a_pmcid_through_the_article_id_index(
    pubmed: PubMedConnector,
) -> None:
    record = run(pubmed.get_by_id(ALPHAFOLD_PMCID))
    assert record is not None
    assert record.pmid == ALPHAFOLD_PMID
    assert record.pmcid == ALPHAFOLD_PMCID


def test_get_by_id_with_a_doi_delegates_to_resolve_doi(pubmed: PubMedConnector) -> None:
    by_doi = run(pubmed.get_by_id(ALPHAFOLD_DOI))
    by_pmid = run(pubmed.get_by_id(ALPHAFOLD_PMID))
    assert by_doi is not None and by_pmid is not None
    assert by_doi.content_hash() == by_pmid.content_hash()


def test_retracted_publication_type_sets_the_retraction_flag(
    pubmed: PubMedConnector,
) -> None:
    record = run(pubmed.resolve_doi(RETRACTED_DOI))
    assert record is not None
    assert record.pmid == RETRACTED_PMID
    assert record.is_retracted is True
    assert "Retracted Publication" in record.extra["publication_types"]
    assert record.year == 2020
    assert record.abstract.startswith("BACKGROUND: ")  # labeled AbstractText sections


# ---------------------------------------------------------------------------
# Clean negatives (D9: these are the ONLY things that may count toward "unresolvable")
# ---------------------------------------------------------------------------


def test_fabricated_doi_is_a_clean_negative(pubmed: PubMedConnector) -> None:
    assert run(pubmed.resolve_doi(FABRICATED_DOI)) is None


def test_nonexistent_pmid_is_a_clean_negative(pubmed: PubMedConnector) -> None:
    # NCBI answers a valid-but-unknown PMID with HTTP 200 and an empty PubmedArticleSet.
    assert run(pubmed.get_by_id(MISSING_PMID)) is None


def test_empty_identifiers_are_clean_negatives(pubmed: PubMedConnector) -> None:
    assert run(pubmed.get_by_id("")) is None
    assert run(pubmed.resolve_doi("")) is None


def test_aid_match_on_a_different_doi_is_not_a_confirmation() -> None:
    # PubMed tokenizes identifiers, so [AID] can match a neighboring record. Answering with
    # it would be a false confirmation, so the connector reports a clean negative instead.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(
                200, json={"esearchresult": {"count": "1", "idlist": ["34265844"]}}
            )
        return httpx.Response(
            200,
            text=(
                "<PubmedArticleSet><PubmedArticle><MedlineCitation>"
                "<PMID>34265844</PMID><Article><ArticleTitle>Something else.</ArticleTitle>"
                "</Article></MedlineCitation><PubmedData><ArticleIdList>"
                '<ArticleId IdType="doi">10.1038/s41586-021-03819-2</ArticleId>'
                "</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"
            ),
        )

    connector = mock_connector(handler)
    assert run(connector.resolve_doi("10.1234/some.other.doi")) is None


# ---------------------------------------------------------------------------
# Source errors (D9: these force `inconclusive` and are NEVER refusal-grade)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, SourceErrorKind.RATE_LIMIT),  # NCBI throttles at 3 req/s without a key
        (500, SourceErrorKind.SERVER_ERROR),
        (503, SourceErrorKind.SERVER_ERROR),
    ],
)
def test_throttling_and_outages_raise_rather_than_returning_a_negative(
    status: int, kind: SourceErrorKind
) -> None:
    connector = mock_connector(lambda request: httpx.Response(status))

    with pytest.raises(SourceError) as excinfo:
        run(connector.search(QUERY))
    assert excinfo.value.kind is kind
    assert excinfo.value.status_code == status
    assert excinfo.value.source == "pubmed"


def test_timeout_raises_a_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    connector = mock_connector(handler)
    with pytest.raises(SourceError) as excinfo:
        run(connector.resolve_doi(ALPHAFOLD_DOI))
    assert excinfo.value.kind is SourceErrorKind.TIMEOUT


def test_network_failure_raises_a_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure", request=request)

    connector = mock_connector(handler)
    with pytest.raises(SourceError) as excinfo:
        run(connector.search(QUERY))
    assert excinfo.value.kind is SourceErrorKind.NETWORK


def test_esearch_error_element_raises_rather_than_returning_a_negative() -> None:
    connector = mock_connector(
        lambda request: httpx.Response(
            200, json={"esearchresult": {"ERROR": "Invalid db name: pubmedd"}}
        )
    )
    with pytest.raises(SourceError) as excinfo:
        run(connector.search(QUERY))
    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE


def test_efetch_error_element_raises_rather_than_returning_a_negative() -> None:
    # An <ERROR> from efetch means the exchange was malformed, not that the article is
    # absent. An empty <PubmedArticleSet/> means absent. They must not be conflated.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(
                200, json={"esearchresult": {"count": "1", "idlist": ["34265844"]}}
            )
        return httpx.Response(
            200,
            text="<eFetchResult><ERROR>ID list is empty!</ERROR></eFetchResult>",
        )

    connector = mock_connector(handler)
    with pytest.raises(SourceError) as excinfo:
        run(connector.get_by_id(ALPHAFOLD_PMID))
    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE
    assert "ID list is empty" in str(excinfo.value)


def test_unparseable_xml_raises_a_source_error() -> None:
    connector = mock_connector(
        lambda request: httpx.Response(200, text="<PubmedArticleSet><oops")
    )
    with pytest.raises(SourceError) as excinfo:
        run(connector.get_by_id(ALPHAFOLD_PMID))
    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE


def test_unparseable_json_raises_a_source_error() -> None:
    connector = mock_connector(lambda request: httpx.Response(200, text="not json at all"))
    with pytest.raises(SourceError) as excinfo:
        run(connector.search(QUERY))
    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE


def test_empty_article_set_is_a_negative_not_an_error() -> None:
    # The other half of the same coin: HTTP 200 plus an empty set is a clean negative.
    connector = mock_connector(
        lambda request: httpx.Response(200, text="<PubmedArticleSet></PubmedArticleSet>")
    )
    assert run(connector.get_by_id(MISSING_PMID)) is None


# ---------------------------------------------------------------------------
# Snapshot discipline
# ---------------------------------------------------------------------------


def test_replay_never_falls_through_to_the_network(pubmed: PubMedConnector) -> None:
    # A missing snapshot is a defect in the snapshot set, not a source outage, so it raises
    # SnapshotMissingError and must NOT be caught as a SourceError.
    with pytest.raises(SnapshotMissingError):
        run(pubmed.search("a query that was never recorded"))

    with pytest.raises(SnapshotMissingError):
        run(pubmed.get_by_id("11111111"))


def test_credentials_stay_out_of_the_snapshot_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # A key or an email must never change the request key, or snapshots would only replay on
    # the machine that recorded them, and a secret would land in a committed file.
    monkeypatch.setenv("NCBI_API_KEY", "secret-key-do-not-record")
    monkeypatch.setenv("NCBI_EMAIL", "someone.else@example.org")

    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.REPLAY)
    connector = PubMedConnector(snapshots=session)
    assert connector.api_key == "secret-key-do-not-record"

    record = run(connector.resolve_doi(ALPHAFOLD_DOI))
    assert record is not None and record.pmid == ALPHAFOLD_PMID


def test_credentials_are_sent_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"esearchresult": {"count": "0", "idlist": []}})

    connector = mock_connector(handler, api_key="k123", email="who@example.org")
    assert run(connector.search(QUERY)) == []

    params = dict(seen[0].params)
    assert params["api_key"] == "k123"
    assert params["email"] == "who@example.org"
    assert params["tool"] == "researcher-core"
    assert params["term"] == QUERY


def test_committed_snapshots_are_intact() -> None:
    store = SnapshotStore(EVAL_SNAPSHOTS)
    snapshots = list(store.iter_snapshots("pubmed"))
    assert len(snapshots) >= 10
    for snapshot in snapshots:
        snapshot.verify()  # stored response_hash still matches the stored body
        assert snapshot.source == "pubmed"
        assert snapshot.endpoint in {"esearch.fcgi", "efetch.fcgi"}
        # No credential ever entered the request key, so none is in the recorded params.
        assert not {"api_key", "email", "tool"} & set(snapshot.request_params)


# ---------------------------------------------------------------------------
# Live smoke (opt-in: pytest -m live)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_smoke() -> None:
    async def smoke() -> None:
        # One event loop for the whole exchange: the httpx client is bound to the loop it
        # was created on, so opening and closing it must happen inside the same asyncio.run.
        session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.LIVE)
        async with PubMedConnector(snapshots=session) as connector:
            assert isinstance(connector, PubMedConnector)

            hits = await connector.search(QUERY, limit=5)
            assert len(hits) == 5
            assert all(h.pmid and h.title for h in hits)

            record = await connector.resolve_doi(ALPHAFOLD_DOI)
            assert record is not None and record.pmid == ALPHAFOLD_PMID

            # A DOI that does not exist is a clean negative from a live index too.
            assert await connector.resolve_doi(FABRICATED_DOI) is None

    run(smoke())
