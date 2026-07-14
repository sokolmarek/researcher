"""Fan-out search tests.

Everything here runs OFFLINE. Two kinds of fixture appear:

* **Real recorded responses.** The committed eval snapshots in ``core/tests/snapshots/`` are
  replayed through the real connectors, so the fan-out is exercised end to end against
  bodies the live APIs actually returned.
* **Planted duplicates.** A snapshot store built in ``tmp_path`` holds OpenAlex-shaped and
  Crossref-shaped bodies carrying the two duplicate cases the M2.4 acceptance names: the
  same DOI from two sources, and the same title with no DOI. These still travel through the
  real connectors and the real snapshot layer; only the recorded bodies are authored.

The error-isolation tests use connectors that raise. That is the property this module
exists for: Semantic Scholar rate-limits the keyless tier most of the time, and a search
that dies because of it is a search nobody can use.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, TypeVar

import pytest

from researcher_core.connectors import create_connector
from researcher_core.connectors.base import (
    BaseConnector,
    SourceError,
    SourceErrorKind,
    UnsupportedOperation,
)
from researcher_core.connectors.openalex import WORK_FIELDS
from researcher_core.dedupe import REASON_DOI_EXACT, REASON_TITLE_SIMILARITY
from researcher_core.model import CSLRecord, canonical_json
from researcher_core.search import (
    DEFAULT_SEARCH_SOURCES,
    OUTCOME_ERROR,
    OUTCOME_OK,
    OUTCOME_UNSUPPORTED,
    UNEXPECTED_KIND,
    fan_out,
    search,
    search_sync,
)
from researcher_core.snapshots import (
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
)

T = TypeVar("T")

#: The committed eval store. Absolute, so the conftest tmp_path redirect cannot hide it.
EVAL_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"

RECORDED_QUERY = "self-supervised ECG"  # recorded for openalex and arxiv at limit 5
PLANTED_QUERY = "planted duplicate fixture"


def run(coro: Awaitable[T]) -> T:
    return asyncio.run(coro)  # type: ignore[arg-type]


def replay_connector(name: str) -> BaseConnector:
    """A real connector in REPLAY mode over the committed eval snapshots."""
    session = SnapshotSession(SnapshotStore(EVAL_SNAPSHOTS), SnapshotMode.REPLAY)
    return create_connector(name, snapshots=session)


# ---------------------------------------------------------------------------
# Stub connectors for the isolation tests
# ---------------------------------------------------------------------------


class _StubConnector(BaseConnector):
    """A connector whose search result is decided in the test, not by an API."""

    capabilities = frozenset({"search", "get_by_id", "resolve_doi"})

    def __init__(
        self,
        *,
        records: list[CSLRecord] | None = None,
        error: BaseException | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._records = records or []
        self._error = error

    async def search(
        self, query: str, *, limit: int = 25, since: int | None = None
    ) -> list[CSLRecord]:
        if self._error is not None:
            raise self._error
        return [
            CSLRecord.from_csl_json(record.to_csl_json()) for record in self._records[:limit]
        ]

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        return None

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        return None


def stub(
    name: str,
    *,
    records: list[CSLRecord] | None = None,
    error: BaseException | None = None,
    supports_search: bool = True,
) -> BaseConnector:
    capabilities = frozenset({"search"} if supports_search else set())
    cls = type(
        f"Stub_{name}",
        (_StubConnector,),
        {"name": name, "capabilities": capabilities},
    )
    return cls(records=records, error=error)  # type: ignore[call-arg]


def make_record(title: str, *, doi: str = "", source: str = "stub") -> CSLRecord:
    return CSLRecord(title=title, DOI=doi, source=source)


# ---------------------------------------------------------------------------
# Planted duplicates, replayed through the real connectors
# ---------------------------------------------------------------------------


@pytest.fixture()
def planted(tmp_path: Path) -> SnapshotSession:
    """A snapshot store holding one OpenAlex page and one Crossref page with duplicates.

    The planted duplicates, exactly as the M2.4 acceptance describes them:

    * ``10.1109/taffc.2020.3014842`` appears in BOTH pages (Crossref writes it uppercase and
      as a resolver URL, which normalization has to collapse).
    * "A Study of Wearable ECG Signal Quality" appears in both, with NO DOI on the OpenAlex
      side (OpenAlex indexes plenty of DOI-less works) and a DOI on the Crossref side.
    """
    store = SnapshotStore(tmp_path / "planted")
    select = ",".join(WORK_FIELDS)

    store.record(
        "openalex",
        "works",
        {"search": PLANTED_QUERY, "per-page": 5, "select": select},
        {
            "meta": {"count": 2},
            "results": [
                {
                    "id": "https://openalex.org/W3005055041",
                    "doi": "https://doi.org/10.1109/taffc.2020.3014842",
                    "title": "Self-Supervised ECG Representation Learning",
                    "publication_year": 2020,
                    "type": "article",
                    "cited_by_count": 150,
                    "is_retracted": False,
                    "authorships": [{"author": {"display_name": "Pritam Sarkar"}}],
                },
                {
                    "id": "https://openalex.org/W3000000001",
                    "doi": None,
                    "title": "A Study of Wearable ECG Signal Quality",
                    "publication_year": 2022,
                    "type": "article",
                    "cited_by_count": 5,
                    "is_retracted": False,
                    "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                },
            ],
        },
    )
    store.record(
        "crossref",
        "works",
        {"query.bibliographic": PLANTED_QUERY, "rows": 5},
        {
            "status": "ok",
            "message": {
                "items": [
                    {
                        "DOI": "https://doi.org/10.1109/TAFFC.2020.3014842",
                        "title": ["Self-supervised ECG representation learning"],
                        "type": "journal-article",
                        "container-title": ["IEEE Transactions on Affective Computing"],
                        "issued": {"date-parts": [[2020]]},
                        "author": [{"given": "Pritam", "family": "Sarkar"}],
                        "is-referenced-by-count": 161,
                    },
                    {
                        "DOI": "10.1000/quality",
                        "title": ["A study of wearable ECG signal quality!"],
                        "type": "journal-article",
                        "issued": {"date-parts": [[2022]]},
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                    },
                ]
            },
        },
    )
    return SnapshotSession(store, SnapshotMode.REPLAY)


def test_planted_duplicates_collapse(planted: SnapshotSession) -> None:
    result = run(
        search(
            PLANTED_QUERY,
            sources=["openalex", "crossref"],
            limit=5,
            session=planted,
        )
    )

    assert result.retrieved_count == 4
    assert len(result.records) == 2
    assert result.duplicates_removed == 2
    assert sorted(d.reason for d in result.decisions) == [
        REASON_DOI_EXACT,
        REASON_TITLE_SIMILARITY,
    ]

    by_doi = {r.DOI: r for r in result.records}
    shared = by_doi["10.1109/taffc.2020.3014842"]
    assert shared.extra["sources"] == ["openalex", "crossref"]
    # The Crossref copy is the fresher count, and the merge keeps the larger one.
    assert shared.citation_count == 161

    # The DOI-less OpenAlex record and the Crossref record with a DOI are one work, and the
    # survivor carries BOTH the OpenAlex id and the DOI it only learned from Crossref.
    quality = by_doi["10.1000/quality"]
    assert quality.openalex_id == "W3000000001"
    assert quality.extra["sources"] == ["openalex", "crossref"]


def test_planted_search_output_is_byte_identical_across_runs(planted: SnapshotSession) -> None:
    """D15: same snapshots, same configuration, same parser -> same bytes."""
    first = run(search(PLANTED_QUERY, sources=["openalex", "crossref"], limit=5, session=planted))
    second = run(search(PLANTED_QUERY, sources=["openalex", "crossref"], limit=5, session=planted))

    assert canonical_json(first.to_json_dict()) == canonical_json(second.to_json_dict())


# ---------------------------------------------------------------------------
# Real recorded responses
# ---------------------------------------------------------------------------


def test_fan_out_over_real_snapshots_returns_every_source() -> None:
    connectors = [replay_connector("openalex"), replay_connector("arxiv")]

    records, outcomes = run(fan_out(RECORDED_QUERY, connectors, limit=5))

    assert [o.source for o in outcomes] == ["openalex", "arxiv"]
    assert all(o.status == OUTCOME_OK for o in outcomes)
    assert all(o.record_count == 5 for o in outcomes)
    assert len(records) == 10
    # Records land in connector order, not in completion order: that is what makes the
    # concurrent fan-out deterministic.
    assert [r.source for r in records[:5]] == ["openalex"] * 5
    assert [r.source for r in records[5:]] == ["arxiv"] * 5


def test_search_over_real_snapshots_dedupes_and_ranks() -> None:
    connectors = [replay_connector("openalex"), replay_connector("arxiv")]

    result = run(search(RECORDED_QUERY, connectors=connectors, limit=5))

    assert result.warnings == []
    assert result.retrieved_count == 10
    assert 0 < len(result.records) <= 10
    scores = [r.extra["score"] for r in result.records]
    assert scores == sorted(scores, reverse=True)
    assert all("sources" in r.extra for r in result.records)


def test_per_source_ranks_are_recorded_for_the_relevance_term() -> None:
    connectors = [replay_connector("openalex")]

    records, _ = run(fan_out(RECORDED_QUERY, connectors, limit=5))

    assert [r.extra["source_ranks"]["openalex"] for r in records] == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Per-source error isolation: the point of the module
# ---------------------------------------------------------------------------


def test_a_rate_limited_source_yields_a_warning_and_the_others_still_answer() -> None:
    healthy = stub("openalex", records=[make_record("A real paper", doi="10.1000/a")])
    rate_limited = stub(
        "semantic_scholar",
        error=SourceError(
            "semantic_scholar",
            "api.semanticscholar.org returned HTTP 429.",
            kind=SourceErrorKind.RATE_LIMIT,
            status_code=429,
        ),
    )

    result = run(search("anything", connectors=[healthy, rate_limited]))

    assert [r.title for r in result.records] == ["A real paper"]
    assert result.sources_ok == ["openalex"]
    assert result.sources_failed == ["semantic_scholar"]
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.source == "semantic_scholar"
    assert warning.kind == "rate_limit"
    assert warning.status_code == 429
    assert warning.operation == "search"


def test_an_unexpected_exception_is_isolated_too() -> None:
    healthy = stub("openalex", records=[make_record("A real paper", doi="10.1000/a")])
    broken = stub("crossref", error=RuntimeError("a parser bug, not an outage"))

    result = run(search("anything", connectors=[healthy, broken]))

    assert len(result.records) == 1
    assert result.warnings[0].kind == UNEXPECTED_KIND
    assert "RuntimeError" in result.warnings[0].message


def test_every_source_failing_yields_no_records_and_every_warning() -> None:
    """No records, but never an exception: the caller decides what to do with nothing."""
    down = [
        stub("openalex", error=SourceError("openalex", "boom", kind=SourceErrorKind.SERVER_ERROR)),
        stub("crossref", error=SourceError("crossref", "timeout", kind=SourceErrorKind.TIMEOUT)),
    ]

    result = run(search("anything", connectors=down))

    assert result.records == []
    assert result.sources_ok == []
    assert len(result.warnings) == 2
    assert {w.kind for w in result.warnings} == {"server_error", "timeout"}


def test_a_source_that_cannot_search_is_skipped_without_a_warning() -> None:
    """Nothing was asked of OpenCitations, so there is nothing to warn about."""
    healthy = stub("openalex", records=[make_record("A real paper", doi="10.1000/a")])
    graph_only = stub("opencitations", supports_search=False)

    result = run(search("anything", connectors=[healthy, graph_only]))

    outcomes = {o.source: o.status for o in result.outcomes}
    assert outcomes == {"openalex": OUTCOME_OK, "opencitations": OUTCOME_UNSUPPORTED}
    assert result.warnings == []


def test_an_unsupported_operation_raised_at_call_time_is_also_skipped() -> None:
    healthy = stub("openalex", records=[make_record("A real paper", doi="10.1000/a")])
    liar = stub("unpaywall", error=UnsupportedOperation("unpaywall", "search"))

    result = run(search("anything", connectors=[healthy, liar]))

    outcomes = {o.source: o.status for o in result.outcomes}
    assert outcomes["unpaywall"] == OUTCOME_UNSUPPORTED
    assert result.warnings == []


def test_a_missing_snapshot_is_never_isolated_into_a_warning() -> None:
    """A gap in the snapshot store is a fixture defect, not a source outage (D15)."""
    connectors = [replay_connector("openalex"), replay_connector("arxiv")]

    with pytest.raises(SnapshotMissingError):
        run(search("a query that was never recorded", connectors=connectors))


def test_isolated_failures_still_produce_a_full_source_report() -> None:
    healthy = stub("openalex", records=[make_record("A real paper", doi="10.1000/a")])
    down = stub("crossref", error=SourceError("crossref", "boom", kind=SourceErrorKind.NETWORK))

    result = run(search("anything", connectors=[healthy, down]))
    payload = result.to_json_dict()

    assert [s["source"] for s in payload["sources"]] == ["openalex", "crossref"]
    assert payload["sources"][1]["status"] == OUTCOME_ERROR
    assert payload["sources"][1]["warning"]["kind"] == "network"
    assert payload["counts"] == {
        "retrieved": 1,
        "deduplicated": 1,
        "duplicates_removed": 0,
    }


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


def test_the_default_fan_out_is_the_three_keyless_indexes() -> None:
    assert DEFAULT_SEARCH_SOURCES == ("openalex", "crossref", "arxiv")


def test_search_with_no_connectors_is_an_empty_result() -> None:
    result = run(search("anything", connectors=[]))

    assert result.records == []
    assert result.outcomes == []
    assert result.warnings == []


def test_search_sync_drives_the_coroutine_for_callers_with_no_event_loop() -> None:
    healthy = stub("openalex", records=[make_record("A real paper", doi="10.1000/a")])

    result = search_sync("anything", connectors=[healthy])

    assert [r.title for r in result.records] == ["A real paper"]


def test_search_builds_and_closes_its_own_connectors_when_none_are_injected(
    planted: SnapshotSession,
) -> None:
    result = run(
        search(PLANTED_QUERY, sources=["openalex", "crossref"], limit=5, session=planted)
    )

    assert result.sources_queried == ["openalex", "crossref"]
    assert len(result.records) == 2
