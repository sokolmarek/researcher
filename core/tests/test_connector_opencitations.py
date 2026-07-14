"""OpenCitations connector tests.

Every test in this file is OFFLINE. The bodies replayed here are real OpenCitations
responses recorded from the live index into ``core/tests/snapshots/opencitations/`` (see
``retrieved_at`` in each file), so the assertions below are assertions about real data, not
about a hand-written fixture. The one test that touches the network carries
``@pytest.mark.live`` and is deselected by default (``addopts = -m 'not live'``).

The load-bearing distinction under test is D9: an empty edge array is a clean negative
(empty list), while an outage is a SourceError. They are checked separately and must never
collapse into each other.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from researcher_core.connectors import create_connector, get_connector_class
from researcher_core.connectors.base import (
    SnapshotMissingError,
    SourceError,
    SourceErrorKind,
    UnsupportedOperation,
)
from researcher_core.connectors.opencitations import OpenCitationsConnector, _split_dois
from researcher_core.snapshots import SnapshotMode, SnapshotSession, SnapshotStore

#: The in-repo eval store, addressed explicitly: conftest redirects the env var at tmp_path,
#: so a test that wants the recorded snapshots must point at them itself.
SNAPSHOT_ROOT = Path(__file__).resolve().parent / "snapshots"

SEED_DOI = "10.1007/s11192-021-04026-6"
UNCITED_DOI = "10.5334/dsj-2021-020"  # a real DOI with zero citations in OpenCitations
PEERJ_DOI = "10.7717/peerj.4375"  # its reference list has empty and multi-DOI edges


def replay_connector(**kwargs: Any) -> OpenCitationsConnector:
    """A connector wired to the recorded snapshots. It cannot reach the network."""
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.REPLAY)
    return OpenCitationsConnector(snapshots=session, **kwargs)


def mock_connector(handler: Any) -> OpenCitationsConnector:
    """A connector over a stubbed transport, for the failure modes no snapshot can encode."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE)
    conn = OpenCitationsConnector(client=client, snapshots=session)
    conn.max_retries = 0  # do not spend the backoff budget in a unit test
    conn.rate_limit_interval = 0.0
    return conn


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Registration and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("opencitations") is OpenCitationsConnector
    assert isinstance(create_connector("opencitations"), OpenCitationsConnector)


def test_capabilities_are_exactly_the_two_graph_operations() -> None:
    assert OpenCitationsConnector.capabilities == {"get_citations", "get_references"}
    assert OpenCitationsConnector.supports("get_citations")
    assert OpenCitationsConnector.supports("get_references")
    for operation in ("search", "get_by_id", "resolve_doi", "get_oa_pdf"):
        assert not OpenCitationsConnector.supports(operation)


@pytest.mark.parametrize(
    ("operation", "args"),
    [
        ("search", ("self-supervised ECG",)),
        ("get_by_id", (SEED_DOI,)),
        ("resolve_doi", (SEED_DOI,)),
        ("get_oa_pdf", (SEED_DOI,)),
    ],
)
def test_metadata_operations_are_declared_unsupported(operation: str, args: tuple) -> None:
    """COCI is a citation index, not a metadata index. It says so instead of faking it."""
    conn = replay_connector()
    with pytest.raises(UnsupportedOperation) as exc:
        run(getattr(conn, operation)(*args))
    assert exc.value.operation == operation
    assert exc.value.source == "opencitations"


# ---------------------------------------------------------------------------
# get_citations / get_references, replayed from real recorded responses
# ---------------------------------------------------------------------------


def test_get_citations_returns_doi_only_records() -> None:
    records = run(replay_connector().get_citations(SEED_DOI))

    assert len(records) == 10  # the recorded response holds exactly 10 incoming edges
    first = records[0]
    assert first.DOI == "10.1002/int.22846"
    assert first.source == "opencitations"
    assert first.source_id == "061601089786-061202127523"  # the real OCI of that edge
    assert first.id == "10.1002/int.22846"  # default_id falls back to the DOI
    assert first.URL == "https://doi.org/10.1002/int.22846"
    assert first.extra["edge_role"] == "cites"
    assert first.extra["creation"] == "2022-02-09"
    # Nothing is invented: COCI hands back no metadata, so none is claimed.
    assert first.title == ""
    assert first.author == []
    assert first.issued is None

    dois = [r.DOI for r in records]
    assert "10.1016/j.joi.2025.101725" in dois
    assert len(set(dois)) == len(dois)  # deduplicated
    assert all(r.source == "opencitations" for r in records)


def test_get_references_returns_the_cited_side_of_each_edge() -> None:
    records = run(replay_connector().get_references(SEED_DOI))

    assert len(records) == 46
    assert records[0].DOI == "10.1016/j.energy.2009.12.015"
    assert records[0].extra["edge_role"] == "cited_by"
    assert "10.1007/s11192-012-0679-8" in [r.DOI for r in records]
    # The seed itself is the citing side and must never appear in its own reference list.
    assert SEED_DOI not in [r.DOI for r in records]


def test_empty_array_is_a_clean_negative_not_an_error() -> None:
    """A real DOI with no known citing works. This must be [] and must NOT raise."""
    records = run(replay_connector().get_citations(UNCITED_DOI))
    assert records == []


def test_limit_caps_the_returned_records() -> None:
    records = run(replay_connector().get_references(SEED_DOI, limit=5))
    assert len(records) == 5
    assert records[0].DOI == "10.1016/j.energy.2009.12.015"


def test_edges_without_a_doi_are_dropped_and_multi_doi_edges_keep_their_aliases() -> None:
    """The recorded PeerJ reference list has 40 edges: 2 with an empty ``cited`` string."""
    stored = SnapshotStore(SNAPSHOT_ROOT).replay(
        "opencitations", f"references/{PEERJ_DOI}", {}
    )
    assert len(stored) == 40
    assert sum(1 for edge in stored if not edge["cited"].strip()) == 2

    records = run(replay_connector().get_references(PEERJ_DOI))
    assert len(records) == 38  # the two DOI-less edges are dropped, not faked
    assert all(r.DOI for r in records)

    # One recorded edge cites an entity carrying two DOIs (a preprint and its eLife version
    # of record): the first is the record's DOI, the other is kept rather than dropped.
    aliased = [r for r in records if "doi_aliases" in r.extra]
    assert len(aliased) == 1
    assert aliased[0].DOI == "10.7287/peerj.preprints.3100v3"
    assert aliased[0].extra["doi_aliases"] == ["10.7554/elife.32822"]


def test_records_serialize_as_valid_csl_json() -> None:
    record = run(replay_connector().get_citations(SEED_DOI, limit=1))[0]
    payload = record.to_csl_json()
    assert payload["DOI"] == "10.1002/int.22846"
    assert payload["custom"]["source"] == "opencitations"
    assert payload["custom"]["edge_role"] == "cites"
    assert "title" not in payload
    assert "author" not in payload


# ---------------------------------------------------------------------------
# D9: outages are SourceErrors, never clean negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, SourceErrorKind.RATE_LIMIT),
        (500, SourceErrorKind.SERVER_ERROR),
        (503, SourceErrorKind.SERVER_ERROR),
    ],
)
def test_rate_limit_and_server_errors_raise_source_error(
    status: int, kind: SourceErrorKind
) -> None:
    conn = mock_connector(lambda request: httpx.Response(status, text="down"))
    with pytest.raises(SourceError) as exc:
        run(conn.get_citations(SEED_DOI))
    assert exc.value.kind is kind
    assert exc.value.status_code == status
    assert exc.value.source == "opencitations"


def test_timeout_raises_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    conn = mock_connector(handler)
    with pytest.raises(SourceError) as exc:
        run(conn.get_references(SEED_DOI))
    assert exc.value.kind is SourceErrorKind.TIMEOUT


def test_network_failure_raises_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    conn = mock_connector(handler)
    with pytest.raises(SourceError) as exc:
        run(conn.get_citations(SEED_DOI))
    assert exc.value.kind is SourceErrorKind.NETWORK


def test_non_array_payload_raises_bad_response() -> None:
    conn = mock_connector(lambda request: httpx.Response(200, json={"error": "nope"}))
    with pytest.raises(SourceError) as exc:
        run(conn.get_citations(SEED_DOI))
    assert exc.value.kind is SourceErrorKind.BAD_RESPONSE


def test_404_from_the_lookup_route_is_a_clean_negative() -> None:
    """A 404 on /citations/<doi> means the index holds nothing there: [] , not an error."""
    conn = mock_connector(lambda request: httpx.Response(404, text="not found"))
    assert run(conn.get_citations(SEED_DOI)) == []


def test_non_doi_identifier_is_a_source_error_never_a_clean_negative() -> None:
    """The index is DOI-addressed. It was never asked, so it cannot have answered "no"."""
    conn = replay_connector()
    for identifier in ("W2741809807", "arXiv:1706.03762", ""):
        with pytest.raises(SourceError) as exc:
            run(conn.get_citations(identifier))
        assert exc.value.kind is SourceErrorKind.CONFIG


def test_missing_snapshot_raises_loudly_and_is_not_a_source_error() -> None:
    """Replay never falls through to the network, and a gap in the set is not an outage."""
    conn = replay_connector()
    with pytest.raises(SnapshotMissingError) as exc:
        run(conn.get_citations("10.1234/never.recorded"))
    assert not isinstance(exc.value, SourceError)


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


def test_doi_is_normalized_before_it_reaches_the_url() -> None:
    """An upper-case, resolver-prefixed DOI hits the same snapshot as the bare one."""
    records = run(replay_connector().get_citations("https://doi.org/10.1007/S11192-021-04026-6"))
    assert len(records) == 10


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.7717/peerj.4375", ["10.7717/peerj.4375"]),
        ("", []),
        ("   ", []),
        (None, []),
        (12, []),
        ("10.1000/a 10.2000/b", ["10.1000/a", "10.2000/b"]),
        ("10.1000/a 10.1000/a", ["10.1000/a"]),
        ("not-a-doi", []),
        ("10.1/a", []),  # too short a prefix to be a DOI
        ("https://doi.org/10.7717/PeerJ.4375", ["10.7717/peerj.4375"]),
    ],
)
def test_split_dois(raw: Any, expected: list[str]) -> None:
    assert _split_dois(raw) == expected


def test_token_and_mailto_are_optional_and_only_add_headers() -> None:
    keyless = OpenCitationsConnector(snapshots=SnapshotSession(mode=SnapshotMode.REPLAY))
    assert "authorization" not in keyless.default_headers()

    polite = OpenCitationsConnector(
        snapshots=SnapshotSession(mode=SnapshotMode.REPLAY),
        token="secret",
        mailto="mareksokol98@gmail.com",
    )
    headers = polite.default_headers()
    assert headers["authorization"] == "secret"
    assert "mailto:mareksokol98@gmail.com" in headers["User-Agent"]


# ---------------------------------------------------------------------------
# Live smoke, opt-in only: pytest -m live
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_citations_smoke() -> None:
    async def go() -> list:
        conn = OpenCitationsConnector(
            snapshots=SnapshotSession(mode=SnapshotMode.LIVE),
            mailto="mareksokol98@gmail.com",
        )
        async with conn:
            return await conn.get_citations(PEERJ_DOI, limit=5)

    records = run(go())
    assert records
    assert all(r.DOI and r.source == "opencitations" for r in records)
