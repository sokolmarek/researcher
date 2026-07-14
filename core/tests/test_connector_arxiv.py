"""arXiv connector tests.

Every test here is OFFLINE. The parsing tests replay the real snapshots recorded from the
live API into ``core/tests/snapshots/arxiv/`` and assert the actual values arXiv returned
(real titles, real authors, real ids), so a parser regression fails on real data rather
than on a hand-written fixture that agrees with the bug.

The transport tests (429, 5xx, timeout, error feeds) drive an ``httpx.MockTransport``, so
they too never touch the network. The single live test is marked ``@pytest.mark.live`` and
is deselected by default (see ``addopts = "-q -m 'not live'"`` in pyproject.toml).

The load-bearing distinction under test throughout: a clean negative (``[]`` / ``None``) is
NOT a source error, and a source error is NOT a clean negative. Under D9 the first is
evidence toward the refusal-grade ``unresolvable`` verdict and the second must force
``inconclusive``. Confusing them makes a rate-limited arXiv accuse a researcher of
fabricating a real preprint.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from researcher_core.connectors import create_connector, get_connector_class
from researcher_core.connectors.arxiv import (
    ArxivConnector,
    parse_arxiv_id,
    split_arxiv_version,
)
from researcher_core.connectors.base import (
    SnapshotMissingError,
    SourceError,
    SourceErrorKind,
    UnsupportedOperation,
)
from researcher_core.model import OALocation
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

SNAPSHOT_ROOT = Path(__file__).resolve().parent / "snapshots"


def replay_connector() -> ArxivConnector:
    """An arXiv connector bound to the in-repo eval snapshots, in replay mode.

    Replay never creates an HTTP client and never awaits a fetcher, so this is offline by
    construction: a request with no snapshot raises SnapshotMissingError.
    """
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.REPLAY)
    return ArxivConnector(snapshots=session)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Identifier handling (old style, new style, versions, arXiv DOIs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2005.13249", "2005.13249"),
        ("2005.13249v3", "2005.13249v3"),
        ("arXiv:2005.13249", "2005.13249"),
        ("math/0309136", "math/0309136"),
        ("hep-th/9901001v2", "hep-th/9901001v2"),
        ("cond-mat.stat-mech/0703470", "cond-mat.stat-mech/0703470"),
        ("https://arxiv.org/abs/2005.13249v3", "2005.13249v3"),
        ("http://arxiv.org/pdf/math/0309136v1", "math/0309136v1"),
        ("10.48550/arXiv.2005.13249", "2005.13249"),
        ("https://doi.org/10.48550/arXiv.math/0309136", "math/0309136"),
        # Not arXiv's: a publisher DOI, an empty string, junk.
        ("10.1038/s41586-020-2649-2", ""),
        ("", ""),
        ("not-an-id", ""),
    ],
)
def test_parse_arxiv_id(raw: str, expected: str) -> None:
    assert parse_arxiv_id(raw) == expected


def test_split_arxiv_version() -> None:
    assert split_arxiv_version("2005.13249v3") == ("2005.13249", "v3")
    assert split_arxiv_version("math/0309136v11") == ("math/0309136", "v11")
    assert split_arxiv_version("2005.13249") == ("2005.13249", "")


# ---------------------------------------------------------------------------
# Registry and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("arxiv") is ArxivConnector
    assert isinstance(create_connector("arxiv"), ArxivConnector)


def test_capabilities_are_honest() -> None:
    """arXiv has no citation graph, so it declares those operations unsupported."""
    assert ArxivConnector.supports("search")
    assert ArxivConnector.supports("get_by_id")
    assert ArxivConnector.supports("resolve_doi")
    assert ArxivConnector.supports("get_oa_pdf")
    assert not ArxivConnector.supports("get_citations")
    assert not ArxivConnector.supports("get_references")

    api = replay_connector()
    with pytest.raises(UnsupportedOperation):
        run(api.get_citations("2005.13249"))
    with pytest.raises(UnsupportedOperation):
        run(api.get_references("2005.13249"))


def test_rate_limit_interval_respects_arxiv_policy() -> None:
    assert ArxivConnector.rate_limit_interval >= 3.0


# ---------------------------------------------------------------------------
# search: real snapshot, real values
# ---------------------------------------------------------------------------


def test_search_replays_real_results() -> None:
    records = run(replay_connector().search("self-supervised ECG", limit=5))

    assert len(records) == 5
    assert [r.arxiv_id for r in records] == [
        "2304.06427",
        "2002.03898",
        "2411.11896",
        "2202.12458",
        "2512.15250",
    ]

    top = records[0]
    assert top.title == (
        "In-Distribution and Out-of-Distribution Self-supervised ECG "
        "Representation Learning for Arrhythmia Detection"
    )
    assert top.first_author_surname == "Soltanieh"
    assert top.year == 2023
    assert top.source == "arxiv"
    assert top.version == "v2"
    assert top.oa_url == "https://arxiv.org/pdf/2304.06427v2"
    assert top.is_oa is True
    assert "cs.LG" in top.keyword
    assert top.abstract.startswith("This paper presents a systematic investigation")
    # No version suffix leaks into arxiv_id; the versioned form is kept alongside.
    assert top.extra["arxiv_id_versioned"] == "2304.06427v2"
    # This preprint was published (arXiv reports a DOI, and no journal-ref), so it is an
    # article-journal keyed on its DOI, lowercased by the CSLRecord normalizer.
    assert top.DOI == "10.1109/jbhi.2023.3331626"
    assert top.type == "article-journal"
    assert top.id == "10.1109/jbhi.2023.3331626"

    # A preprint arXiv reports no DOI for stays an "article" and keys on its arXiv id.
    unpublished = records[3]
    assert unpublished.arxiv_id == "2202.12458"
    assert unpublished.DOI == ""
    assert unpublished.type == "article"
    assert unpublished.id == "arxiv:2202.12458"


def test_search_since_filters_by_year() -> None:
    records = run(replay_connector().search("self-supervised ECG", limit=5, since=2023))

    assert len(records) == 4
    assert all(r.year is not None and r.year >= 2023 for r in records)
    assert "2002.03898" not in {r.arxiv_id for r in records}


def test_search_with_no_matches_is_a_clean_negative() -> None:
    """arXiv answered with totalResults 0. That is [], NOT a SourceError."""
    records = run(replay_connector().search("zzqqxx nonexistent phrase glorp", limit=5))
    assert records == []


def test_empty_query_short_circuits_without_a_request() -> None:
    assert run(replay_connector().search("   ", limit=5)) == []


# ---------------------------------------------------------------------------
# get_by_id: new style, old style, versions
# ---------------------------------------------------------------------------


def test_get_by_id_new_style() -> None:
    record = run(replay_connector().get_by_id("2005.13249"))

    assert record is not None
    assert record.arxiv_id == "2005.13249"
    assert record.version == "v3"
    assert record.title == (
        "CLOCS: Contrastive Learning of Cardiac Signals Across Space, Time, and Patients"
    )
    assert [a.display() for a in record.author] == [
        "Dani Kiyasseh",
        "Tingting Zhu",
        "David A. Clifton",
    ]
    assert record.author[0].family == "Kiyasseh"
    assert record.year == 2020
    assert record.URL == "https://arxiv.org/abs/2005.13249v3"
    assert record.oa_url == "https://arxiv.org/pdf/2005.13249v3"
    assert record.source == "arxiv"
    assert record.source_id == "2005.13249v3"
    # A preprint with no journal-ref is an "article", not an "article-journal".
    assert record.type == "article"
    assert record.DOI == ""


def test_get_by_id_old_style() -> None:
    record = run(replay_connector().get_by_id("math/0309136"))

    assert record is not None
    assert record.arxiv_id == "math/0309136"
    assert record.version == "v1"
    assert record.title == "Regular points in affine Springer fibers"
    assert record.year == 2003
    assert [a.surname for a in record.author] == ["Goresky", "Kottwitz", "MacPherson"]
    assert record.keyword == ["math.RT"]
    assert record.oa_url == "https://arxiv.org/pdf/math/0309136v1"
    assert record.id == "arxiv:math/0309136"


def test_get_by_id_pinned_version_returns_that_version() -> None:
    """v1 of CLOCS carries the ORIGINAL title; v3 renamed it. The version suffix matters."""
    record = run(replay_connector().get_by_id("2005.13249v1"))

    assert record is not None
    assert record.arxiv_id == "2005.13249"
    assert record.version == "v1"
    assert record.title == "CLOCS: Contrastive Learning of Cardiac Signals"
    assert record.oa_url == "https://arxiv.org/pdf/2005.13249v1"


def test_get_by_id_published_preprint_carries_its_doi_and_journal_ref() -> None:
    """1207.7214 is the ATLAS Higgs paper: published, so arXiv reports a DOI."""
    record = run(replay_connector().get_by_id("1207.7214"))

    assert record is not None
    assert record.arxiv_id == "1207.7214"
    assert record.DOI == "10.1016/j.physletb.2012.08.020"
    assert record.container_title == "Phys.Lett. B716 (2012) 1-29"
    assert record.type == "article-journal"
    assert record.year == 2012
    # DOI wins the citation key once the preprint is published.
    assert record.id == "10.1016/j.physletb.2012.08.020"


def test_get_by_id_unknown_id_is_a_clean_negative() -> None:
    """HTTP 200, totalResults 0. The lookup succeeded and nothing matched."""
    assert run(replay_connector().get_by_id("2999.99999")) is None


def test_get_by_id_malformed_id_is_a_clean_negative() -> None:
    """arXiv answers a malformed id with HTTP 400 plus an Atom "incorrect id format" entry.

    The API answered cleanly: that string names no arXiv paper. It is a clean negative,
    not an outage, so it must be None rather than a SourceError.
    """
    assert run(replay_connector().get_by_id("not-an-id")) is None


def test_get_by_id_rejects_a_non_arxiv_doi_rather_than_faking_a_negative() -> None:
    """arXiv has no DOI index. Returning None here would be evidence toward "fabricated"."""
    with pytest.raises(UnsupportedOperation):
        run(replay_connector().get_by_id("10.1038/s41586-020-2649-2"))


# ---------------------------------------------------------------------------
# resolve_doi
# ---------------------------------------------------------------------------


def test_resolve_doi_resolves_an_arxiv_issued_doi() -> None:
    record = run(replay_connector().resolve_doi("10.48550/arXiv.2005.13249"))

    assert record is not None
    assert record.arxiv_id == "2005.13249"
    assert record.title.startswith("CLOCS: Contrastive Learning of Cardiac Signals")


def test_resolve_doi_accepts_a_resolver_prefixed_arxiv_doi() -> None:
    record = run(replay_connector().resolve_doi("https://doi.org/10.48550/arXiv.math/0309136"))

    assert record is not None
    assert record.arxiv_id == "math/0309136"


def test_resolve_doi_on_a_publisher_doi_is_unsupported_not_negative() -> None:
    with pytest.raises(UnsupportedOperation) as excinfo:
        run(replay_connector().resolve_doi("10.1016/j.physletb.2012.08.020"))
    assert excinfo.value.source == "arxiv"


def test_resolve_doi_of_an_unknown_arxiv_doi_is_a_clean_negative() -> None:
    assert run(replay_connector().resolve_doi("10.48550/arXiv.2999.99999")) is None


# ---------------------------------------------------------------------------
# get_oa_pdf (axis (d)): arXiv always has a free PDF
# ---------------------------------------------------------------------------


def test_get_oa_pdf_from_an_arxiv_doi() -> None:
    location = run(replay_connector().get_oa_pdf("10.48550/arXiv.math/0309136"))

    assert isinstance(location, OALocation)
    assert location.url == "https://arxiv.org/pdf/math/0309136v1"
    assert location.content_type == "pdf"
    assert location.source == "arxiv"
    assert location.host_type == "repository"
    assert location.is_oa is True


def test_get_oa_pdf_from_a_bare_arxiv_id() -> None:
    location = run(replay_connector().get_oa_pdf("2005.13249"))

    assert location is not None
    assert location.url == "https://arxiv.org/pdf/2005.13249v3"


def test_get_oa_pdf_of_an_unknown_id_is_a_clean_negative() -> None:
    assert run(replay_connector().get_oa_pdf("2999.99999")) is None


def test_get_oa_pdf_of_a_publisher_doi_is_unsupported() -> None:
    with pytest.raises(UnsupportedOperation):
        run(replay_connector().get_oa_pdf("10.1038/s41586-020-2649-2"))


# ---------------------------------------------------------------------------
# Replay is airtight: a missing snapshot never falls through to the network
# ---------------------------------------------------------------------------


def test_missing_snapshot_raises_loudly_and_is_not_a_source_error() -> None:
    with pytest.raises(SnapshotMissingError):
        run(replay_connector().get_by_id("1706.03762"))

    # SnapshotMissingError is a defect in the snapshot set, never a source outage: it must
    # not be catchable as a SourceError, or replay gaps would masquerade as inconclusive.
    assert not issubclass(SnapshotMissingError, SourceError)


# ---------------------------------------------------------------------------
# Transport failures: rate limit, 5xx, timeout, junk payload. All SourceError.
# ---------------------------------------------------------------------------


class _NoRetryArxiv(ArxivConnector):
    """Same connector, no retries and no throttle, so failure tests stay fast."""

    max_retries = 0
    rate_limit_interval = 0.0


def mock_connector(handler: Any) -> _NoRetryArxiv:
    """A live-mode connector whose transport is a mock. Still never touches the network."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE)
    return _NoRetryArxiv(client=client, snapshots=session)


ERROR_FEED_400 = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>1</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>1</opensearch:itemsPerPage>
  <entry>
    <id>https://arxiv.org/api/errors#incorrect_id_format_for_not-an-id</id>
    <title>Error</title>
    <summary>incorrect id format for not-an-id</summary>
  </entry>
</feed>
"""


def test_rate_limit_is_a_source_error_never_a_clean_negative() -> None:
    """A 429 must NEVER look like "no such paper": that would accuse a real citation."""
    api = mock_connector(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(SourceError) as excinfo:
        run(api.get_by_id("2005.13249"))

    assert excinfo.value.kind is SourceErrorKind.RATE_LIMIT
    assert excinfo.value.status_code == 429
    assert excinfo.value.source == "arxiv"
    run(api.aclose())


def test_server_error_is_a_source_error() -> None:
    api = mock_connector(lambda request: httpx.Response(503, text="down"))
    with pytest.raises(SourceError) as excinfo:
        run(api.search("self-supervised ECG", limit=5))

    assert excinfo.value.kind is SourceErrorKind.SERVER_ERROR
    assert excinfo.value.status_code == 503
    run(api.aclose())


def test_timeout_is_a_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    api = mock_connector(handler)
    with pytest.raises(SourceError) as excinfo:
        run(api.get_by_id("2005.13249"))

    assert excinfo.value.kind is SourceErrorKind.TIMEOUT
    run(api.aclose())


def test_network_failure_is_a_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    api = mock_connector(handler)
    with pytest.raises(SourceError) as excinfo:
        run(api.get_by_id("2005.13249"))

    assert excinfo.value.kind is SourceErrorKind.NETWORK
    run(api.aclose())


def test_unparseable_xml_is_a_source_error() -> None:
    api = mock_connector(lambda request: httpx.Response(200, text="<feed><broken>"))
    with pytest.raises(SourceError) as excinfo:
        run(api.get_by_id("2005.13249"))

    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE
    run(api.aclose())


def test_error_feed_on_a_lookup_is_a_clean_negative() -> None:
    """The same 400 error feed the live API returns for a malformed id: None, not an error."""
    api = mock_connector(lambda request: httpx.Response(400, text=ERROR_FEED_400))
    assert run(api.get_by_id("garbage id")) is None
    run(api.aclose())


def test_error_feed_on_a_search_is_a_source_error() -> None:
    """A rejected search_query is OUR bad request, so we learned nothing about the corpus.

    Reporting it as [] would be a fabricated clean negative.
    """
    api = mock_connector(lambda request: httpx.Response(400, text=ERROR_FEED_400))
    with pytest.raises(SourceError) as excinfo:
        run(api.search("self-supervised ECG", limit=5))

    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE
    run(api.aclose())


def test_unexplained_4xx_is_a_source_error() -> None:
    api = mock_connector(lambda request: httpx.Response(403, text="<feed/>"))
    with pytest.raises(SourceError) as excinfo:
        run(api.get_by_id("2005.13249"))

    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE
    assert excinfo.value.status_code == 403
    run(api.aclose())


# ---------------------------------------------------------------------------
# Keyless and polite
# ---------------------------------------------------------------------------


def test_works_with_no_api_key_and_no_email() -> None:
    """Keyless by default: no env var is required for any operation above."""
    api = replay_connector()
    headers = api.default_headers()
    assert headers["Accept"] == "application/atom+xml"
    assert "Authorization" not in headers
    assert run(api.get_by_id("2005.13249")) is not None


def test_optional_contact_email_rides_in_the_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARXIV_MAILTO", "mareksokol98@gmail.com")
    headers = replay_connector().default_headers()
    assert "mailto:mareksokol98@gmail.com" in headers["User-Agent"]


# ---------------------------------------------------------------------------
# Live smoke (opt-in): pytest -m live
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_search_and_lookup() -> None:
    async def go() -> None:
        session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE)
        async with ArxivConnector(snapshots=session) as api:
            records = await api.search("self-supervised ECG", limit=5)
            assert records, "live arXiv search returned nothing for a query with known hits"
            assert all(r.arxiv_id and r.title for r in records)

            record = await api.get_by_id("2005.13249")
            assert record is not None
            assert record.title.startswith("CLOCS")

            assert await api.get_by_id("2999.99999") is None

    run(go())
