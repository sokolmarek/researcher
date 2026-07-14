"""Unpaywall connector tests.

Everything here runs OFFLINE. The four snapshots in ``core/tests/snapshots/unpaywall/`` were
recorded from the real API, and every assertion below is against values that really came back
from it. Replay mode never falls through to a live call, so a test that tried to would fail
with :class:`SnapshotMissingError` rather than quietly reaching the network.

The one live-calling test is marked ``@pytest.mark.live`` and is deselected by default
(``addopts = -m 'not live'``).

The load-bearing distinction under test is the clean negative versus the source error:

* HTTP 404 (DOI unknown to Unpaywall) -> ``None`` / ``unavailable``. A clean negative.
* HTTP 429, 500, or a timeout          -> :class:`SourceError`. NEVER a negative.

Getting that backwards would let a downed Unpaywall accuse a researcher of fabricating a real
citation, so both directions are asserted explicitly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from researcher_core.connectors import get_connector_class
from researcher_core.connectors.base import SourceError, SourceErrorKind, UnsupportedOperation
from researcher_core.connectors.unpaywall import (
    ABSTRACT_ONLY,
    FULL_TEXT,
    UNAVAILABLE,
    UnpaywallConnector,
)
from researcher_core.model import OALocation
from researcher_core.snapshots import (
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

# The in-repo eval store, addressed explicitly: conftest redirects the env override at
# tmp_path, and these tests want the real recorded snapshots.
SNAPSHOT_ROOT = Path(__file__).resolve().parent / "snapshots"

OA_PDF_DOI = "10.1371/journal.pone.0000308"  # gold OA, publisher, direct PDF link
OA_LANDING_DOI = "10.7717/peerj.4375"  # gold OA, publisher, landing page only
CLOSED_DOI = "10.1109/5.726791"  # known to Unpaywall, no OA copy
UNKNOWN_DOI = "10.9999/nonexistent.12345"  # HTTP 404
MALFORMED_DOI = "not-a-doi-at-all"


def run(coro: Any) -> Any:
    """Drive one coroutine to completion. The suite has no pytest-asyncio, and needs none."""
    return asyncio.run(coro)


def replay_connector(**kwargs: Any) -> UnpaywallConnector:
    """A connector wired to the recorded snapshots, in replay mode. Cannot reach the network."""
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.REPLAY)
    return UnpaywallConnector(snapshots=session, **kwargs)


def mock_connector(handler: Any) -> UnpaywallConnector:
    """A connector over a stubbed transport, for the error paths no snapshot can express."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    connector = UnpaywallConnector(
        client=client,
        snapshots=SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE),
    )
    connector.max_retries = 0  # do not spend the backoff budget in a unit test
    return connector


@pytest.fixture()
def connector() -> UnpaywallConnector:
    return replay_connector()


# ---------------------------------------------------------------------------
# Registration and capabilities
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("unpaywall") is UnpaywallConnector


def test_declares_only_what_it_implements() -> None:
    assert UnpaywallConnector.capabilities == frozenset(
        {"get_by_id", "resolve_doi", "get_oa_pdf"}
    )
    for supported in ("get_by_id", "resolve_doi", "get_oa_pdf"):
        assert UnpaywallConnector.supports(supported)
    # Unpaywall is not a search index and holds no citation graph. Say so, do not fake it.
    for unsupported in ("search", "get_citations", "get_references"):
        assert not UnpaywallConnector.supports(unsupported)


@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("search", lambda c: c.search("self-supervised ECG")),
        ("get_citations", lambda c: c.get_citations("10.7717/peerj.4375")),
        ("get_references", lambda c: c.get_references("10.7717/peerj.4375")),
    ],
)
def test_unsupported_operations_raise(
    connector: UnpaywallConnector, operation: str, call: Any
) -> None:
    with pytest.raises(UnsupportedOperation) as excinfo:
        run(call(connector))
    assert excinfo.value.operation == operation
    assert excinfo.value.source == "unpaywall"


# ---------------------------------------------------------------------------
# resolve_doi: real parsed values from the recorded payloads
# ---------------------------------------------------------------------------


def test_resolve_doi_parses_the_recorded_record(connector: UnpaywallConnector) -> None:
    record = run(connector.resolve_doi(OA_PDF_DOI))
    assert record is not None
    assert record.DOI == OA_PDF_DOI
    assert record.title == (
        "Sharing Detailed Research Data Is Associated with Increased Citation Rate"
    )
    assert record.year == 2007
    # Unpaywall ships a single display string ("Heather A. Piwowar"); parse_name splits it.
    assert record.first_author_surname == "Piwowar"
    assert record.author[0].given == "Heather A."
    assert [a.surname for a in record.author] == ["Piwowar", "Day", "Fridsma"]
    assert record.container_title == "PLoS ONE"
    assert record.publisher == "Public Library of Science (PLoS)"
    assert record.ISSN == ["1932-6203"]
    assert record.type == "article-journal"
    assert record.source == "unpaywall"
    assert record.is_oa is True
    assert record.extra["oa_status"] == "gold"
    assert record.URL == "https://doi.org/10.1371/journal.pone.0000308"


def test_resolve_doi_normalizes_a_resolver_prefixed_doi(connector: UnpaywallConnector) -> None:
    # The snapshot key is the normalized DOI, so a URL-form DOI hits the same snapshot.
    record = run(connector.resolve_doi("https://doi.org/10.7717/peerj.4375"))
    assert record is not None
    assert record.DOI == OA_LANDING_DOI
    assert record.title.startswith("The state of OA")
    assert record.first_author_surname == "Piwowar"


def test_get_by_id_is_resolve_doi(connector: UnpaywallConnector) -> None:
    by_id = run(connector.get_by_id(CLOSED_DOI))
    by_doi = run(connector.resolve_doi(CLOSED_DOI))
    assert by_id is not None and by_doi is not None
    assert by_id.content_hash() == by_doi.content_hash()


# ---------------------------------------------------------------------------
# Axis (d): full-text / abstract-only / unavailable
# ---------------------------------------------------------------------------


def test_full_text_with_a_direct_pdf(connector: UnpaywallConnector) -> None:
    access = run(connector.get_accessibility(OA_PDF_DOI))
    assert access.verdict == FULL_TEXT
    assert access.known is True
    assert access.is_oa is True
    assert access.oa_status == "gold"

    location = access.location
    assert isinstance(location, OALocation)
    assert location.url == (
        "https://journals.plos.org/plosone/article/file"
        "?id=10.1371/journal.pone.0000308&type=printable"
    )
    assert location.content_type == "pdf"
    assert location.host_type == "publisher"
    assert location.license == "cc-by"
    assert location.version == "publishedVersion"
    assert location.source == "unpaywall"
    assert location.is_oa is True


def test_full_text_when_only_a_landing_page_is_known(connector: UnpaywallConnector) -> None:
    # best_oa_location.url_for_pdf is null for this record, but the OA copy is real: it is
    # still full-text, served as HTML, so the html extractor runs rather than the PDF one.
    access = run(connector.get_accessibility(OA_LANDING_DOI))
    assert access.verdict == FULL_TEXT
    assert access.location is not None
    assert access.location.url == "https://doi.org/10.7717/peerj.4375"
    assert access.location.content_type == "html"
    assert access.location.host_type == "publisher"
    assert access.location.version == "publishedVersion"
    assert access.location.license == "cc-by"


def test_abstract_only_when_the_doi_is_known_but_closed(connector: UnpaywallConnector) -> None:
    access = run(connector.get_accessibility(CLOSED_DOI))
    assert access.verdict == ABSTRACT_ONLY
    assert access.known is True  # Unpaywall answered, and it knows this work
    assert access.is_oa is False
    assert access.oa_status == "closed"
    assert access.location is None

    # Known-but-closed still yields a record: the work exists, only the full text does not.
    assert access.record is not None
    assert access.record.title == "Gradient-based learning applied to document recognition"
    assert access.record.year == 1998
    # Unpaywall really does store "Y. Lecun" for this record, lowercase c and all. The
    # assertion is against what the API returned, not against what it ought to have returned.
    assert access.record.first_author_surname == "Lecun"
    assert access.record.author[0].given == "Y."
    assert access.record.ISSN == ["0018-9219", "1558-2256"]
    assert access.record.container_title == "Proceedings of the IEEE"
    assert run(connector.get_oa_pdf(CLOSED_DOI)) is None


def test_unavailable_when_the_doi_is_unknown(connector: UnpaywallConnector) -> None:
    # HTTP 404 from the lookup endpoint. This is a CLEAN NEGATIVE, not a source error.
    access = run(connector.get_accessibility(UNKNOWN_DOI))
    assert access.verdict == UNAVAILABLE
    assert access.known is False
    assert access.is_oa is False
    assert access.location is None
    assert access.record is None

    assert run(connector.resolve_doi(UNKNOWN_DOI)) is None
    assert run(connector.get_oa_pdf(UNKNOWN_DOI)) is None


def test_the_three_verdicts_are_distinguishable_from_get_oa_pdf_alone_only_via_accessibility(
    connector: UnpaywallConnector,
) -> None:
    # get_oa_pdf returns None for both closed and unknown, which is why axis (d) reads the
    # verdict off get_accessibility instead.
    assert run(connector.get_oa_pdf(CLOSED_DOI)) is None
    assert run(connector.get_oa_pdf(UNKNOWN_DOI)) is None
    assert run(connector.get_accessibility(CLOSED_DOI)).verdict == ABSTRACT_ONLY
    assert run(connector.get_accessibility(UNKNOWN_DOI)).verdict == UNAVAILABLE


def test_accessibility_serializes(connector: UnpaywallConnector) -> None:
    payload = run(connector.get_accessibility(OA_PDF_DOI)).to_json_dict()
    assert payload["verdict"] == FULL_TEXT
    assert payload["known"] is True
    assert payload["location"]["content_type"] == "pdf"
    assert payload["location"]["source"] == "unpaywall"


# ---------------------------------------------------------------------------
# A malformed DOI is a clean negative, and costs no request
# ---------------------------------------------------------------------------


def test_malformed_doi_is_a_clean_negative_without_a_request(
    connector: UnpaywallConnector,
) -> None:
    # No snapshot exists for this input. Replay mode raises SnapshotMissingError on any
    # request, so returning None proves the connector short-circuited instead of calling out.
    assert run(connector.resolve_doi(MALFORMED_DOI)) is None
    assert run(connector.get_accessibility(MALFORMED_DOI)).verdict == UNAVAILABLE
    assert run(connector.resolve_doi("")) is None


def test_a_missing_snapshot_is_loud_and_is_not_a_source_error(
    connector: UnpaywallConnector,
) -> None:
    # A DOI-shaped input with no recorded snapshot must fail loudly rather than go live or
    # degrade into a clean negative. This is the guard that keeps the offline suite honest.
    with pytest.raises(SnapshotMissingError):
        run(connector.resolve_doi("10.1234/not-recorded"))


# ---------------------------------------------------------------------------
# Snapshot keying: the politeness email must not be part of the key
# ---------------------------------------------------------------------------


def test_snapshots_replay_under_any_email() -> None:
    # The recorded snapshots must be replayable by a contributor whose UNPAYWALL_EMAIL differs
    # from the one used to record them, so the email stays out of the request key.
    other = replay_connector(email="someone.else@example.org")
    record = run(other.resolve_doi(OA_PDF_DOI))
    assert record is not None
    assert record.DOI == OA_PDF_DOI


def test_email_defaults_and_is_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNPAYWALL_EMAIL", "env.person@example.org")
    assert replay_connector().email == "env.person@example.org"
    assert replay_connector(email="explicit@example.org").email == "explicit@example.org"

    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    assert replay_connector().email  # a documented default, so the connector stays keyless

    url = replay_connector(email="a@b.org")._request_url("10.1371/journal.pone.0000308")
    assert url == (
        "https://api.unpaywall.org/v2/10.1371/journal.pone.0000308?email=a%40b.org"
    )


# ---------------------------------------------------------------------------
# Source error versus clean negative, over a stubbed transport
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, SourceErrorKind.RATE_LIMIT),
        (500, SourceErrorKind.SERVER_ERROR),
        (503, SourceErrorKind.SERVER_ERROR),
    ],
)
def test_rate_limit_and_5xx_raise_source_error(status: int, kind: SourceErrorKind) -> None:
    connector = mock_connector(lambda request: httpx.Response(status, text="down"))
    with pytest.raises(SourceError) as excinfo:
        run(connector.get_accessibility(OA_PDF_DOI))
    assert excinfo.value.kind is kind
    assert excinfo.value.status_code == status
    assert excinfo.value.source == "unpaywall"


def test_timeout_raises_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    connector = mock_connector(handler)
    with pytest.raises(SourceError) as excinfo:
        run(connector.get_oa_pdf(OA_PDF_DOI))
    assert excinfo.value.kind is SourceErrorKind.TIMEOUT


def test_unparseable_body_raises_source_error() -> None:
    connector = mock_connector(lambda request: httpx.Response(200, text="<html>nope</html>"))
    with pytest.raises(SourceError) as excinfo:
        run(connector.resolve_doi(OA_PDF_DOI))
    assert excinfo.value.kind is SourceErrorKind.BAD_RESPONSE


def test_404_over_the_wire_is_a_clean_negative_not_an_error() -> None:
    connector = mock_connector(lambda request: httpx.Response(404, text="Not Found"))
    assert run(connector.resolve_doi(UNKNOWN_DOI)) is None
    assert run(connector.get_accessibility(UNKNOWN_DOI)).verdict == UNAVAILABLE


def test_json_error_envelope_is_a_clean_negative() -> None:
    body = {"error": True, "message": "'x' is an invalid doi", "HTTP_status_code": 404}
    connector = mock_connector(lambda request: httpx.Response(200, json=body))
    assert run(connector.resolve_doi(UNKNOWN_DOI)) is None
    assert run(connector.get_accessibility(UNKNOWN_DOI)).known is False


def test_the_request_carries_the_polite_email() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    connector = UnpaywallConnector(
        client=client,
        snapshots=SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE),
        email="polite@example.org",
    )
    run(connector.resolve_doi(UNKNOWN_DOI))
    assert len(seen) == 1
    assert seen[0].path == "/v2/10.9999/nonexistent.12345"
    assert seen[0].params["email"] == "polite@example.org"


# ---------------------------------------------------------------------------
# Live smoke, opt-in only
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_smoke() -> None:
    async def go() -> None:
        session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE)
        async with UnpaywallConnector(snapshots=session) as connector:
            access = await connector.get_accessibility(OA_PDF_DOI)
            assert access.verdict == FULL_TEXT
            assert access.location is not None
            assert access.location.url.startswith("http")
            assert (await connector.get_accessibility(CLOSED_DOI)).verdict == ABSTRACT_ONLY
            assert (await connector.get_accessibility(UNKNOWN_DOI)).verdict == UNAVAILABLE

    run(go())
