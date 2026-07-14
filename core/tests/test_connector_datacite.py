"""DataCite connector tests.

Every test in this file runs offline. The connector fixture replays the snapshots in
``core/tests/snapshots/datacite/``, which were recorded from the real api.datacite.org, so
the assertions below are made against real DataCite payloads rather than hand-written
fakes. In replay mode any request without a snapshot raises SnapshotMissingError instead of
quietly reaching the network, so there is no way for this file to go online by accident.

The one test that does call the live API is marked ``live`` and is deselected by default
(``addopts = -m 'not live'`` in core/pyproject.toml).

Coroutines are driven with ``asyncio.run`` rather than an async pytest plugin, so the suite
needs no test-time dependency beyond pytest itself.

The load-bearing case is the D9 clean-negative / source-error split, exercised with a mock
transport: a 404 from ``/dois/<doi>`` is a clean negative (``None``), while 429, 5xx,
timeouts, and garbage bodies are all SourceError. Getting that backwards would let a downed
DataCite accuse a researcher of fabricating a real dataset citation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import httpx
import pytest

from researcher_core.connectors import create_connector, get_connector_class
from researcher_core.connectors.base import SourceError, SourceErrorKind
from researcher_core.connectors.datacite import DataCiteConnector
from researcher_core.model import CSLRecord
from researcher_core.snapshots import (
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

T = TypeVar("T")

# The in-repo eval store, not the tmp_path store the autouse conftest fixture points env at.
SNAPSHOT_ROOT = Path(__file__).resolve().parent / "snapshots"

# The DOIs recorded in the fixture set.
DATASET_DOI = "10.5061/dryad.q447c"  # Dryad: the Sci-Hub download data
SOFTWARE_DOI = "10.5281/zenodo.1212303"  # Zenodo: explosion/spaCy v3.7.2
PREPRINT_DOI = "10.48550/arxiv.1706.03762"  # arXiv: Attention Is All You Need
CROSSREF_ONLY_DOI = "10.1038/nature14539"  # Nature: a Crossref DOI, not a DataCite one


def run(coro: Any) -> Any:
    """Drive one coroutine to completion on a fresh event loop."""
    return asyncio.run(coro)


@pytest.fixture()
def datacite() -> Iterator[DataCiteConnector]:
    """A connector that replays the recorded DataCite snapshots. Never goes online."""
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.REPLAY)
    yield DataCiteConnector(snapshots=session, mailto="mareksokol98@gmail.com")


def with_mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> DataCiteConnector:
    """A LIVE-mode connector whose transport is a mock. Also never goes online."""
    session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE, cache=None)
    connector = DataCiteConnector(
        snapshots=session, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    connector.max_retries = 0  # do not spend the suite's time on backoff sleeps
    connector.rate_limit_interval = 0.0
    return connector


# ---------------------------------------------------------------------------
# Contract wiring
# ---------------------------------------------------------------------------


def test_registered_under_its_name() -> None:
    assert get_connector_class("datacite") is DataCiteConnector
    assert isinstance(create_connector("datacite"), DataCiteConnector)


def test_capabilities_are_honest() -> None:
    """Three operations implemented and declared; the other three declared unsupported."""
    assert DataCiteConnector.supports("search")
    assert DataCiteConnector.supports("get_by_id")
    assert DataCiteConnector.supports("resolve_doi")
    assert not DataCiteConnector.supports("get_citations")
    assert not DataCiteConnector.supports("get_references")
    assert not DataCiteConnector.supports("get_oa_pdf")


def test_mailto_only_touches_the_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keyless by default: the contact address is optional and adds nothing but a header."""
    monkeypatch.setenv("DATACITE_MAILTO", "someone@example.org")
    assert "mailto:someone@example.org" in DataCiteConnector().default_headers()["User-Agent"]

    monkeypatch.delenv("DATACITE_MAILTO")
    monkeypatch.delenv("RESEARCHER_CORE_MAILTO", raising=False)
    assert "mailto:" not in DataCiteConnector().default_headers()["User-Agent"]


# ---------------------------------------------------------------------------
# D22: the DOIs Crossref does not index
# ---------------------------------------------------------------------------


def test_resolves_a_real_dataset_doi(datacite: DataCiteConnector) -> None:
    """A Dryad dataset DOI: what Crossref cannot answer, mapped onto CSL `dataset`."""
    record = run(datacite.resolve_doi(DATASET_DOI))

    assert isinstance(record, CSLRecord)
    assert record.type == "dataset"
    assert record.DOI == DATASET_DOI
    assert record.title == "Data from: Who's downloading pirated papers? Everyone"
    assert record.publisher == "Dryad"
    assert record.year == 2021
    assert record.first_author_surname == "Elbakyan"
    assert [a.display() for a in record.author] == ["Alexandra Elbakyan", "John Bohannon"]
    assert record.source == "datacite"
    assert record.source_id == DATASET_DOI
    assert record.id == DATASET_DOI
    assert record.extra["datacite_resource_type"] == "Dataset"
    assert "Sci-Hub" in record.abstract


def test_resolves_a_real_software_doi(datacite: DataCiteConnector) -> None:
    """A Zenodo software release, mapped onto CSL `software` with its version preserved."""
    record = run(datacite.resolve_doi(SOFTWARE_DOI))

    assert isinstance(record, CSLRecord)
    assert record.type == "software"
    assert record.DOI == SOFTWARE_DOI
    assert record.title.startswith("explosion/spaCy: v3.7.2")
    assert record.publisher == "Zenodo"
    assert record.year == 2023
    assert record.version == "v3.7.2"
    assert record.first_author_surname == "Montani"
    assert record.source == "datacite"
    assert record.extra["datacite_resource_type"] == "Software"


def test_resolves_a_preprint_doi_as_article_journal(datacite: DataCiteConnector) -> None:
    """arXiv mints 10.48550/* via DataCite: resourceTypeGeneral Preprint -> article-journal."""
    record = run(datacite.resolve_doi(PREPRINT_DOI))

    assert isinstance(record, CSLRecord)
    assert record.type == "article-journal"
    assert record.title == "Attention Is All You Need"
    assert record.year == 2017
    assert record.publisher == "arXiv"
    assert record.first_author_surname == "Vaswani"
    assert record.extra["datacite_resource_type"] == "Preprint"


def test_doi_is_normalized_before_lookup(datacite: DataCiteConnector) -> None:
    """A resolver-prefixed mixed-case DOI hits the same snapshot as the bare lowercase form."""
    record = run(datacite.resolve_doi("https://doi.org/10.48550/arXiv.1706.03762"))
    assert record is not None
    assert record.DOI == PREPRINT_DOI


def test_get_by_id_is_doi_lookup(datacite: DataCiteConnector) -> None:
    """DataCite's native identifier IS the DOI, so the two entry points agree exactly."""
    by_id = run(datacite.get_by_id(SOFTWARE_DOI))
    by_doi = run(datacite.resolve_doi(SOFTWARE_DOI))
    assert by_id is not None and by_doi is not None
    assert by_id.content_hash() == by_doi.content_hash()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_returns_records(datacite: DataCiteConnector) -> None:
    records = run(datacite.search("self-supervised ECG", limit=5))

    assert len(records) == 5
    assert all(isinstance(r, CSLRecord) for r in records)
    assert all(r.source == "datacite" for r in records)
    assert all(r.DOI for r in records)
    assert records[0].DOI == "10.48550/arxiv.2607.09749"
    assert records[0].title.startswith("MorphologyFM")
    # The thesis in this result set proves the type mapping runs over search hits too,
    # not only over single-DOI lookups.
    assert {r.type for r in records} == {"article-journal", "thesis"}


def test_search_can_narrow_to_datasets(datacite: DataCiteConnector) -> None:
    """resource-type-id is how a caller asks DataCite for exactly what Crossref misses."""
    records = run(datacite.search("ECG", limit=5, resource_type="dataset"))

    assert len(records) == 5
    assert {r.type for r in records} == {"dataset"}
    assert all(r.extra["datacite_resource_type"] == "Dataset" for r in records)


def test_search_since_filters_by_year(datacite: DataCiteConnector) -> None:
    records = run(datacite.search("self-supervised ECG", limit=5, since=2023))

    assert records
    assert all((r.year or 0) >= 2023 for r in records)


def test_blank_search_is_a_clean_negative_without_a_call(datacite: DataCiteConnector) -> None:
    """No query, no request: an empty list, and not a SnapshotMissingError."""
    assert run(datacite.search("   ")) == []


def test_blank_doi_is_a_clean_negative_without_a_call(datacite: DataCiteConnector) -> None:
    assert run(datacite.resolve_doi("")) is None


def test_replay_never_falls_through_to_the_network(datacite: DataCiteConnector) -> None:
    """An unrecorded request fails loudly: that is a snapshot defect, not a source outage."""
    with pytest.raises(SnapshotMissingError):
        run(datacite.resolve_doi("10.5281/zenodo.99999999999"))


# ---------------------------------------------------------------------------
# D9: clean negative versus source error, the split the whole verdict rests on
# ---------------------------------------------------------------------------


def test_crossref_only_doi_is_a_clean_negative(datacite: DataCiteConnector) -> None:
    """A real recorded 404 for a Crossref-registered DOI. None, and never a SourceError."""
    assert run(datacite.resolve_doi(CROSSREF_ONLY_DOI)) is None


def test_404_is_a_clean_negative_not_a_source_error() -> None:
    connector = with_mock_transport(lambda request: httpx.Response(404, json={"errors": []}))
    try:
        assert run(connector.resolve_doi("10.5281/zenodo.404")) is None
    finally:
        run(connector.aclose())


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, SourceErrorKind.RATE_LIMIT),
        (500, SourceErrorKind.SERVER_ERROR),
        (503, SourceErrorKind.SERVER_ERROR),
    ],
)
def test_rate_limit_and_5xx_are_source_errors(status: int, kind: SourceErrorKind) -> None:
    """A downed index must never look like "this DOI does not exist"."""
    connector = with_mock_transport(lambda request: httpx.Response(status, text="down"))
    try:
        with pytest.raises(SourceError) as caught:
            run(connector.resolve_doi(DATASET_DOI))
    finally:
        run(connector.aclose())

    assert caught.value.kind is kind
    assert caught.value.status_code == status
    assert caught.value.source == "datacite"


def test_timeout_is_a_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    connector = with_mock_transport(handler)
    try:
        with pytest.raises(SourceError) as caught:
            run(connector.search("self-supervised ECG"))
    finally:
        run(connector.aclose())

    assert caught.value.kind is SourceErrorKind.TIMEOUT


def test_unparseable_body_is_a_source_error() -> None:
    connector = with_mock_transport(
        lambda request: httpx.Response(200, text="<html>nope</html>")
    )
    try:
        with pytest.raises(SourceError) as caught:
            run(connector.search("self-supervised ECG"))
    finally:
        run(connector.aclose())

    assert caught.value.kind is SourceErrorKind.BAD_RESPONSE


def test_wrong_shaped_payload_is_a_source_error() -> None:
    """Valid JSON that is not JSON:API means we learned nothing: a source error, not a miss."""
    connector = with_mock_transport(
        lambda request: httpx.Response(200, json={"data": "nonsense"})
    )
    try:
        with pytest.raises(SourceError) as caught:
            run(connector.search("self-supervised ECG"))
    finally:
        run(connector.aclose())

    assert caught.value.kind is SourceErrorKind.BAD_RESPONSE


def test_empty_data_array_is_a_clean_negative() -> None:
    """A search that matched nothing is an empty list, and emphatically not an error."""
    connector = with_mock_transport(
        lambda request: httpx.Response(200, json={"data": [], "meta": {"total": 0}})
    )
    try:
        assert run(connector.search("zzzz no such thing zzzz")) == []
    finally:
        run(connector.aclose())


# ---------------------------------------------------------------------------
# Normalization details worth pinning
# ---------------------------------------------------------------------------


def test_organizational_creator_becomes_a_literal_name() -> None:
    """Zenodo deposits "The pandas development team" as a creator; it is not a person."""
    record = DataCiteConnector().to_record(
        {
            "id": "10.5281/zenodo.3509134",
            "attributes": {
                "doi": "10.5281/ZENODO.3509134",
                "titles": [{"title": "pandas-dev/pandas: Pandas"}],
                "creators": [
                    {"name": "The pandas development team", "nameType": "Organizational"}
                ],
                "publisher": {"name": "Zenodo"},  # schema 4.5 object form
                "publicationYear": 2020,
                "types": {"resourceTypeGeneral": "Software"},
                "version": "v1.0.0",
            },
        }
    )
    assert record.type == "software"
    assert record.DOI == "10.5281/zenodo.3509134"  # normalized by CSLRecord, not by hand
    assert record.author[0].literal == "The pandas development team"
    assert record.author[0].surname == "The pandas development team"
    assert record.publisher == "Zenodo"


def test_zenodo_names_with_no_real_split_are_parsed() -> None:
    """The Zenodo pathology, straight out of the recorded spaCy record.

    ``nameType: Personal`` with the whole display name copied into ``familyName`` and no
    ``givenName``. Trusting that verbatim would make the first-author surname "Ines
    Montani", which matches no bibliography entry anywhere.
    """
    record = DataCiteConnector().to_record(
        {
            "id": "10.5281/zenodo.1212303",
            "attributes": {
                "titles": [{"title": "explosion/spaCy"}],
                "creators": [
                    {
                        "name": "Ines Montani",
                        "familyName": "Ines Montani",
                        "nameType": "Personal",
                    }
                ],
                "types": {"resourceTypeGeneral": "Software"},
            },
        }
    )
    assert record.first_author_surname == "Montani"
    assert record.author[0].given == "Ines"


def test_text_resource_type_defers_to_the_depositors_own_type() -> None:
    """Text is DataCite's catch-all, so a depositor's own "Preprint" beats it."""
    record = DataCiteConnector().to_record(
        {
            "id": "10.1101/2020.01.01.000000",
            "attributes": {
                "titles": [{"title": "A repository preprint"}],
                "types": {"resourceTypeGeneral": "Text", "resourceType": "Preprint"},
            },
        }
    )
    assert record.type == "article-journal"


def test_container_subjects_and_editors_are_mapped() -> None:
    record = DataCiteConnector().to_record(
        {
            "id": "10.1234/example",
            "attributes": {
                "titles": [{"title": "Sub", "titleType": "Subtitle"}, {"title": "Main title"}],
                "container": {
                    "title": "Journal of Examples",
                    "volume": "12",
                    "issue": "3",
                    "firstPage": "100",
                    "lastPage": "115",
                },
                "subjects": [{"subject": "ECG"}, {"subject": "ECG"}, {"subject": "wearables"}],
                "contributors": [
                    {"name": "Itor, Ed", "contributorType": "Editor"},
                    {"name": "Manager, Data", "contributorType": "DataManager"},
                ],
                "types": {"resourceTypeGeneral": "JournalArticle"},
                "citationCount": 4,
                "referenceCount": 31,
            },
        }
    )
    assert record.title == "Main title"  # the untyped title, not the subtitle
    assert record.container_title == "Journal of Examples"
    assert record.volume == "12"
    assert record.issue == "3"
    assert record.page == "100-115"
    assert record.keyword == ["ECG", "wearables"]
    assert [e.display() for e in record.editor] == ["Ed Itor"]  # only the Editor contributor
    assert record.citation_count == 4
    assert record.reference_count == 31


def test_unknown_resource_type_falls_back_to_citeproc() -> None:
    record = DataCiteConnector().to_record(
        {
            "id": "10.1234/unknown",
            "attributes": {
                "titles": [{"title": "Something new"}],
                "types": {"resourceTypeGeneral": "Hologram", "citeproc": "dataset"},
            },
        }
    )
    assert record.type == "dataset"


# ---------------------------------------------------------------------------
# Live smoke, opt-in only: pytest core/tests/test_connector_datacite.py -m live
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_smoke() -> None:  # pragma: no cover - network
    async def exercise() -> None:
        session = SnapshotSession(SnapshotStore(SNAPSHOT_ROOT), SnapshotMode.LIVE, cache=None)
        async with DataCiteConnector(
            snapshots=session, mailto="mareksokol98@gmail.com"
        ) as connector:
            hits = await connector.search("self-supervised ECG", limit=5)
            assert hits
            assert all(h.DOI for h in hits)

            dataset = await connector.resolve_doi(DATASET_DOI)
            assert dataset is not None and dataset.type == "dataset"

            software = await connector.resolve_doi(SOFTWARE_DOI)
            assert software is not None and software.type == "software"

            # DataCite genuinely does not hold this Crossref DOI: a clean negative.
            assert await connector.resolve_doi(CROSSREF_ONLY_DOI) is None

    run(exercise())
