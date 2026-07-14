"""Crossref connector tests.

Every test here runs OFFLINE. The records asserted on were recorded from the live
api.crossref.org into ``core/tests/snapshots/crossref/`` and are replayed byte-for-byte, so
the values below (585 citations, 37 references, the Lancet update graph) are real Crossref
values, not invented ones. The one test that touches the network carries ``@pytest.mark.live``
and is deselected by default (``addopts = -m 'not live'``).

The distinction under test that matters most is the D9 one: a 404 from ``/works/<doi>`` is a
clean negative (``None``), while a 429, a 5xx, or a timeout is a
:class:`SourceError`. Those are asserted separately and must never converge.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from researcher_core.connectors import create_connector, get_connector_class
from researcher_core.connectors.base import (
    SourceError,
    SourceErrorKind,
    UnsupportedOperation,
)
from researcher_core.connectors.crossref import (
    UPDATE_TO_KEY,
    UPDATED_BY_KEY,
    CrossrefConnector,
)
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

# The in-repo eval store. Addressed explicitly rather than through the env var, because
# conftest redirects RESEARCHER_CORE_SNAPSHOT_DIR at tmp_path for isolation.
SNAPSHOT_ROOT = Path(__file__).resolve().parent / "snapshots"

CLEAN_DOI = "10.1371/journal.pone.0000308"  # Piwowar 2007, PLoS ONE
CONFERENCE_DOI = "10.1109/CVPR.2016.90"  # He et al. 2016, ResNet
RETRACTED_DOI = "10.1016/s0140-6736(20)31180-6"  # Mehra et al. 2020, retracted
MISSING_DOI = "10.1234/this-doi-does-not-exist-xyz"  # 404: a clean negative
QUERY = "self-supervised ECG"


def replay_connector(**kwargs: Any) -> CrossrefConnector:
    """A Crossref connector wired to the recorded eval snapshots. Never reaches the network."""
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.REPLAY)
    return CrossrefConnector(snapshots=session, **kwargs)


def live_shaped_connector(store_root: Path, **kwargs: Any) -> CrossrefConnector:
    """A connector in LIVE mode with no cache, for respx-mocked transport tests."""
    session = SnapshotSession(SnapshotStore(store_root), SnapshotMode.LIVE)
    connector = CrossrefConnector(snapshots=session, **kwargs)
    connector.max_retries = 0  # do not sleep through backoff in a unit test
    connector.rate_limit_interval = 0.0
    return connector


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Registration and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("crossref") is CrossrefConnector
    assert isinstance(create_connector("crossref"), CrossrefConnector)


def test_capabilities_declare_only_what_crossref_can_do() -> None:
    for operation in ("search", "get_by_id", "resolve_doi", "get_references"):
        assert CrossrefConnector.supports(operation), operation
    # Crossref has no forward-citation endpoint and no OA resolver.
    assert not CrossrefConnector.supports("get_citations")
    assert not CrossrefConnector.supports("get_oa_pdf")


def test_unsupported_operations_raise_rather_than_faking_an_answer() -> None:
    connector = replay_connector()
    with pytest.raises(UnsupportedOperation) as excinfo:
        run(connector.get_citations(CLEAN_DOI))
    assert excinfo.value.operation == "get_citations"
    # An empty list here would be a clean negative, which would be a lie: it would say
    # "nothing cites this paper" when the truth is "Crossref was never asked".
    with pytest.raises(UnsupportedOperation):
        run(connector.get_oa_pdf(CLEAN_DOI))


# ---------------------------------------------------------------------------
# resolve_doi: real recorded values
# ---------------------------------------------------------------------------


def test_resolve_doi_parses_the_recorded_work() -> None:
    record = run(replay_connector().resolve_doi(CLEAN_DOI))
    assert record is not None
    assert record.DOI == CLEAN_DOI
    assert record.id == CLEAN_DOI
    assert record.title == (
        "Sharing Detailed Research Data Is Associated with Increased Citation Rate"
    )
    assert record.type == "article-journal"
    assert record.extra["crossref_type"] == "journal-article"
    assert [a.surname for a in record.author] == ["Piwowar", "Day", "Fridsma"]
    assert record.author[0].given == "Heather A."
    assert record.first_author_surname == "Piwowar"
    assert record.year == 2007
    assert record.container_title == "PLoS ONE"
    assert record.publisher == "Public Library of Science (PLoS)"
    assert record.ISSN == ["1932-6203"]
    assert (record.volume, record.issue, record.page) == ("2", "3", "e308")
    assert record.URL == "https://doi.org/10.1371/journal.pone.0000308"
    assert record.citation_count == 585
    assert record.reference_count == 37
    assert record.source == "crossref"
    assert record.source_id == CLEAN_DOI


def test_resolve_doi_accepts_any_doi_spelling() -> None:
    """A resolver-prefixed, upper-cased DOI hits the same snapshot: the key is normalized."""
    record = run(replay_connector().resolve_doi("https://doi.org/10.1371/JOURNAL.PONE.0000308"))
    assert record is not None
    assert record.DOI == CLEAN_DOI


def test_get_by_id_is_doi_lookup() -> None:
    record = run(replay_connector().get_by_id(CLEAN_DOI))
    assert record is not None and record.DOI == CLEAN_DOI


def test_conference_paper_type_maps_to_paper_conference() -> None:
    record = run(replay_connector().resolve_doi(CONFERENCE_DOI))
    assert record is not None
    assert record.title == "Deep Residual Learning for Image Recognition"
    assert record.type == "paper-conference"
    assert record.extra["crossref_type"] == "proceedings-article"
    assert [a.surname for a in record.author] == ["He", "Zhang", "Ren", "Sun"]
    assert record.year == 2016
    assert "Computer Vision and Pattern Recognition" in record.container_title


# ---------------------------------------------------------------------------
# The clean-negative / source-error split (D9)
# ---------------------------------------------------------------------------


def test_unknown_doi_is_a_clean_negative_not_an_error() -> None:
    """A recorded 404 replays as None: Crossref answered, and the answer was 'no such DOI'."""
    store = SnapshotStore(SNAPSHOT_ROOT)
    assert store.replay("crossref", f"works/{MISSING_DOI}") is None  # the recorded body IS null
    assert run(replay_connector().resolve_doi(MISSING_DOI)) is None


def test_blank_doi_is_a_clean_negative() -> None:
    assert run(replay_connector().resolve_doi("")) is None
    assert run(replay_connector().get_references("   ")) == []


def test_empty_query_is_a_clean_negative() -> None:
    assert run(replay_connector().search("  ")) == []


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, SourceErrorKind.RATE_LIMIT),
        (500, SourceErrorKind.SERVER_ERROR),
        (503, SourceErrorKind.SERVER_ERROR),
    ],
)
def test_rate_limit_and_5xx_are_source_errors(
    tmp_path: Path, status: int, kind: SourceErrorKind
) -> None:
    """Crossref does rate-limit. A 429 must never be reported as 'this DOI does not exist'."""
    connector = live_shaped_connector(tmp_path)
    with respx.mock:
        respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(status)
        )
        with pytest.raises(SourceError) as excinfo:
            run(connector.resolve_doi(CLEAN_DOI))
    assert excinfo.value.kind is kind
    assert excinfo.value.status_code == status
    assert excinfo.value.source == "crossref"


def test_timeout_is_a_source_error(tmp_path: Path) -> None:
    connector = live_shaped_connector(tmp_path)
    with respx.mock:
        respx.get(url__startswith="https://api.crossref.org/works").mock(
            side_effect=httpx.ConnectTimeout("timed out")
        )
        with pytest.raises(SourceError) as excinfo:
            run(connector.resolve_doi(CLEAN_DOI))
    assert excinfo.value.kind is SourceErrorKind.TIMEOUT


def test_404_over_live_transport_is_still_a_clean_negative(tmp_path: Path) -> None:
    connector = live_shaped_connector(tmp_path)
    with respx.mock:
        respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(404, text="Resource not found.")
        )
        assert run(connector.resolve_doi(MISSING_DOI)) is None


def test_garbled_envelope_is_a_source_error(tmp_path: Path) -> None:
    """A 200 with no `message` object is a broken source, not an absent DOI."""
    connector = live_shaped_connector(tmp_path)
    with respx.mock:
        respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        with pytest.raises(SourceError) as excinfo:
            run(connector.resolve_doi(CLEAN_DOI))
    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE


# ---------------------------------------------------------------------------
# Axis (b): the update graph
# ---------------------------------------------------------------------------


def test_retracted_work_surfaces_update_to_with_types_intact() -> None:
    """status.py builds axis (b) on these arrays, so every entry's `type` must survive."""
    record = run(replay_connector().resolve_doi(RETRACTED_DOI))
    assert record is not None
    assert record.title.startswith("RETRACTED:")

    update_to = record.extra[UPDATE_TO_KEY]
    assert {entry["type"] for entry in update_to} == {"retraction"}
    assert "10.1016/s0140-6736(20)31324-6" in {entry["DOI"] for entry in update_to}

    updated_by = record.extra[UPDATED_BY_KEY]
    types = {entry["type"] for entry in updated_by}
    # The real Lancet update graph carries all three kinds. None may be flattened away.
    assert {"retraction", "correction", "expression_of_concern"} <= types

    retraction = next(e for e in updated_by if e["type"] == "retraction")
    assert retraction["label"] == "Retraction"
    assert retraction["source"] in {"publisher", "retraction-watch"}
    assert retraction["updated"].startswith("2020-")
    assert retraction["date_parts"][0] == 2020
    assert retraction["DOI"].startswith("10.1016/")

    # Deliberately NOT flattened into a boolean here: a retraction notice also carries
    # `update-to: [{type: retraction}]` while being a current document itself. Axis (b)
    # (status.py) owns that interpretation.
    assert record.is_retracted is None


def test_clean_work_carries_no_update_entries() -> None:
    record = run(replay_connector().resolve_doi(CLEAN_DOI))
    assert record is not None
    assert UPDATE_TO_KEY not in record.extra
    assert UPDATED_BY_KEY not in record.extra


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_parses_the_recorded_result_page() -> None:
    records = run(replay_connector().search(QUERY, limit=3))
    assert len(records) == 3
    assert [r.DOI for r in records] == [
        "10.32920/22734386",
        "10.32920/22734386.v1",
        "10.1016/j.jelectrocard.2025.153947",
    ]
    assert all(r.source == "crossref" for r in records)
    first = records[0]
    assert first.title.startswith("Contrastive Self-Supervised Learning for Stress Detection")
    assert [a.surname for a in first.author] == ["Rabbani", "Khan"]
    assert first.year == 2023
    # A Crossref `posted-content` preprint maps to the CSL `article` type.
    assert first.type == "article"
    assert first.extra["crossref_type"] == "posted-content"
    last = records[-1]
    assert last.type == "article-journal"
    assert last.container_title == "Journal of Electrocardiology"
    assert last.year == 2025


def test_search_sends_the_bibliographic_query_and_row_count(tmp_path: Path) -> None:
    connector = live_shaped_connector(tmp_path)
    with respx.mock:
        route = respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(200, json={"message": {"items": []}})
        )
        assert run(connector.search("ecg", limit=5, since=2020)) == []
    params = route.calls.last.request.url.params
    assert params["query.bibliographic"] == "ecg"
    assert params["rows"] == "5"
    assert params["filter"] == "from-pub-date:2020-01-01"


def test_search_row_count_is_capped(tmp_path: Path) -> None:
    connector = live_shaped_connector(tmp_path)
    with respx.mock:
        route = respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(200, json={"message": {"items": []}})
        )
        run(connector.search("ecg", limit=10_000))
    assert route.calls.last.request.url.params["rows"] == str(CrossrefConnector.max_rows)


# ---------------------------------------------------------------------------
# get_references
# ---------------------------------------------------------------------------


def test_get_references_parses_the_deposited_reference_list() -> None:
    references = run(replay_connector().get_references(CLEAN_DOI, limit=100))
    assert len(references) == 37  # the real deposited count for this work

    with_dois = [r for r in references if r.DOI]
    assert "10.1177/1075547095016004003" in {r.DOI for r in with_dois}

    mccain = next(r for r in references if r.DOI == "10.1177/1075547095016004003")
    # Kept exactly as deposited, trailing period and all. Nothing is cleaned up here.
    assert mccain.title == "Mandating Sharing: Journal Policies in the Natural Sciences."
    assert mccain.first_author_surname == "McCain"
    assert mccain.year == 1995
    assert mccain.container_title == "Science Communication"
    assert mccain.volume == "16"
    assert mccain.page == "403"
    assert mccain.source == "crossref"
    assert mccain.extra["crossref_reference_key"]

    # A reference with no DOI is kept, not dropped: it is real evidence of a citation edge.
    fienberg = references[0]
    assert fienberg.DOI == ""
    assert fienberg.first_author_surname == "Fienberg"
    assert fienberg.year == 1985
    assert fienberg.id  # a record with no DOI still gets a stable id


def test_get_references_respects_the_limit() -> None:
    references = run(replay_connector().get_references(CLEAN_DOI, limit=4))
    assert len(references) == 4


def test_get_references_on_an_unknown_doi_is_a_clean_negative() -> None:
    assert run(replay_connector().get_references(MISSING_DOI)) == []


# ---------------------------------------------------------------------------
# Politeness, without poisoning the snapshot key
# ---------------------------------------------------------------------------


def test_mailto_never_enters_the_snapshot_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A snapshot recorded with a polite-pool address must replay for anyone, with any address."""
    monkeypatch.setenv("CROSSREF_MAILTO", "someone.else@example.org")
    record = run(replay_connector().resolve_doi(CLEAN_DOI))
    assert record is not None and record.DOI == CLEAN_DOI

    store = SnapshotStore(SNAPSHOT_ROOT)
    snapshot = store.load("crossref", f"works/{CLEAN_DOI}", {})
    assert "mailto" not in snapshot.request_params


def test_mailto_is_sent_to_the_api_when_configured(tmp_path: Path) -> None:
    connector = live_shaped_connector(tmp_path, mailto="mareksokol98@gmail.com")
    with respx.mock:
        route = respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(200, json={"message": {"items": []}})
        )
        run(connector.search("ecg"))
    request = route.calls.last.request
    assert request.url.params["mailto"] == "mareksokol98@gmail.com"
    assert "mailto:mareksokol98@gmail.com" in request.headers["User-Agent"]


def test_no_mailto_configured_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The polite pool is an optimization. Crossref is keyless, so absence must still work."""
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    connector = live_shaped_connector(tmp_path)
    assert connector.mailto == ""
    with respx.mock:
        route = respx.get(url__startswith="https://api.crossref.org/works").mock(
            return_value=httpx.Response(200, json={"message": {"items": []}})
        )
        run(connector.search("ecg"))
    assert "mailto" not in route.calls.last.request.url.params


# ---------------------------------------------------------------------------
# Snapshot hygiene
# ---------------------------------------------------------------------------


def test_recorded_snapshots_are_intact() -> None:
    store = SnapshotStore(SNAPSHOT_ROOT)
    snapshots = list(store.iter_snapshots("crossref"))
    assert len(snapshots) >= 5
    for snapshot in snapshots:
        snapshot.verify()  # stored response_hash still matches the stored body
        assert snapshot.source == "crossref"
        assert "mailto" not in snapshot.request_params


# ---------------------------------------------------------------------------
# Live smoke, opt-in only: pytest -m live
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_search_returns_plausible_results() -> None:
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE)

    async def go() -> None:
        async with CrossrefConnector(snapshots=session) as connector:
            records = await connector.search(QUERY, limit=5)
            assert records
            assert all(r.DOI for r in records)
            assert all(r.source == "crossref" for r in records)
            resolved = await connector.resolve_doi(CLEAN_DOI)
            assert resolved is not None
            assert resolved.first_author_surname == "Piwowar"

    run(go())
