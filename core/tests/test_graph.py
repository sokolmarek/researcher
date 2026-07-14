"""Citation-graph traversal tests.

The fixture is a small hand-built citation graph served by stub connectors, because the
properties under test are properties of the TRAVERSAL, not of any one index's payload
shape (which the connector tests already pin against real recorded responses).

The test this file exists for is :func:`test_a_citation_cycle_terminates`. Citation graphs
are supposed to be acyclic and are not: preprints, simultaneous publication, and plain
metadata errors all produce A cites B and B cites A. A traversal that expands a node twice
loops forever, so the fixture plants exactly that cycle and asserts termination.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from typing import Any, TypeVar

import pytest

from researcher_core.connectors.base import BaseConnector, SourceError, SourceErrorKind
from researcher_core.graph import (
    DEFAULT_GRAPH_SOURCES,
    DIRECTION_BACKWARD,
    DIRECTION_FORWARD,
    MAX_DEPTH,
    traverse,
    traverse_sync,
)
from researcher_core.model import CSLDate, CSLRecord, canonical_json, normalize_doi

T = TypeVar("T")

# A small citation graph. Keys are DOIs; values are the DOIs that CITE the key.
#
#   B --cites--> A
#   C --cites--> A
#   D --cites--> B
#
# So a forward traversal from A reaches {B, C} at depth 1 and {B, C, D} at depth 2.
SEED = "10.1000/a"
CITED_BY = {
    "10.1000/a": ["10.1000/b", "10.1000/c"],
    "10.1000/b": ["10.1000/d"],
    "10.1000/c": [],
    "10.1000/d": [],
}
# What each work CITES (the backward direction). A cites X and Y.
REFERENCES = {
    "10.1000/a": ["10.1000/x", "10.1000/y"],
    "10.1000/x": [],
    "10.1000/y": [],
}

TITLES = {
    "10.1000/a": "The seed paper on cardiac representation learning",
    "10.1000/b": "A paper that cites the seed paper",
    "10.1000/c": "Another paper that cites the seed paper",
    "10.1000/d": "A second-hop paper that cites B",
    "10.1000/x": "A reference of the seed paper",
    "10.1000/y": "Another reference of the seed paper",
}


def run(coro: Awaitable[T]) -> T:
    return asyncio.run(coro)  # type: ignore[arg-type]


def make_record(doi: str, *, source: str, year: int = 2020) -> CSLRecord:
    return CSLRecord(
        title=TITLES.get(doi, f"Untitled {doi}"),
        DOI=doi,
        source=source,
        source_id=doi,
        issued=CSLDate.from_year(year),
        citation_count=1,
    )


class _StubGraphConnector(BaseConnector):
    """Serves a hand-built adjacency map, or raises, exactly as configured."""

    capabilities = frozenset({"get_citations", "get_references"})

    def __init__(
        self,
        *,
        cited_by: Mapping[str, list[str]] | None = None,
        references: Mapping[str, list[str]] | None = None,
        error: BaseException | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._cited_by = dict(cited_by or {})
        self._references = dict(references or {})
        self._error = error
        self.calls: list[str] = []

    async def search(
        self, query: str, *, limit: int = 25, since: int | None = None
    ) -> list[CSLRecord]:
        return []

    async def get_by_id(self, identifier: str) -> CSLRecord | None:
        return None

    async def resolve_doi(self, doi: str) -> CSLRecord | None:
        return None

    async def get_citations(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        return self._neighbors(self._cited_by, identifier)

    async def get_references(self, identifier: str, *, limit: int = 100) -> list[CSLRecord]:
        return self._neighbors(self._references, identifier)

    def _neighbors(self, table: Mapping[str, list[str]], identifier: str) -> list[CSLRecord]:
        if self._error is not None:
            raise self._error
        doi = normalize_doi(identifier)
        self.calls.append(doi)
        return [make_record(neighbor, source=self.name) for neighbor in table.get(doi, [])]


def stub(
    name: str,
    *,
    cited_by: Mapping[str, list[str]] | None = None,
    references: Mapping[str, list[str]] | None = None,
    error: BaseException | None = None,
) -> Any:
    cls = type(f"Stub_{name}", (_StubGraphConnector,), {"name": name})
    return cls(cited_by=cited_by, references=references, error=error)


# ---------------------------------------------------------------------------
# Forward and backward traversal
# ---------------------------------------------------------------------------


def test_forward_traversal_returns_the_expected_neighbors() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    result = run(traverse([SEED], direction=DIRECTION_FORWARD, connectors=[connector]))

    assert sorted(r.DOI for r in result.nodes) == ["10.1000/b", "10.1000/c"]
    assert sorted((e.citing, e.cited) for e in result.edges) == [
        ("doi:10.1000/b", "doi:10.1000/a"),
        ("doi:10.1000/c", "doi:10.1000/a"),
    ]
    assert result.depth == 1
    assert result.warnings == []


def test_backward_traversal_returns_the_references() -> None:
    connector = stub("openalex", references=REFERENCES)

    result = run(traverse([SEED], direction=DIRECTION_BACKWARD, connectors=[connector]))

    assert sorted(r.DOI for r in result.nodes) == ["10.1000/x", "10.1000/y"]
    # Edges are always stored citing-to-cited, whichever way the traversal ran.
    assert sorted((e.citing, e.cited) for e in result.edges) == [
        ("doi:10.1000/a", "doi:10.1000/x"),
        ("doi:10.1000/a", "doi:10.1000/y"),
    ]


def test_depth_two_reaches_the_second_hop() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    result = run(traverse([SEED], depth=2, connectors=[connector]))

    assert sorted(r.DOI for r in result.nodes) == ["10.1000/b", "10.1000/c", "10.1000/d"]
    assert ("doi:10.1000/d", "doi:10.1000/b") in {(e.citing, e.cited) for e in result.edges}
    depths = {r.DOI: r.extra["graph_depth"] for r in result.nodes}
    assert depths == {"10.1000/b": 1, "10.1000/c": 1, "10.1000/d": 2}


def test_depth_is_capped_at_two() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    with pytest.raises(ValueError, match="between 1 and 2"):
        run(traverse([SEED], depth=MAX_DEPTH + 1, connectors=[connector]))
    with pytest.raises(ValueError, match="between 1 and 2"):
        run(traverse([SEED], depth=0, connectors=[connector]))


def test_an_unknown_direction_is_rejected() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    with pytest.raises(ValueError, match="direction"):
        run(traverse([SEED], direction="sideways", connectors=[connector]))


# ---------------------------------------------------------------------------
# The cycle
# ---------------------------------------------------------------------------


def test_a_citation_cycle_terminates() -> None:
    """A cites B and B cites A. The traversal must terminate, and it must not loop."""
    cycle = {"10.1000/a": ["10.1000/b"], "10.1000/b": ["10.1000/a"]}
    connector = stub("openalex", cited_by=cycle)

    result = run(traverse([SEED], depth=2, connectors=[connector]))

    # B is the only discovery. A is the seed, so finding it again is not a discovery,
    # even though the mutual edge is real and is reported.
    assert [r.DOI for r in result.nodes] == ["10.1000/b"]
    assert sorted((e.citing, e.cited) for e in result.edges) == [
        ("doi:10.1000/a", "doi:10.1000/b"),
        ("doi:10.1000/b", "doi:10.1000/a"),
    ]
    # Each node was expanded exactly once. Without the visited set this would recur until
    # the depth cap, and without the depth cap it would never return at all.
    assert connector.calls == ["10.1000/a", "10.1000/b"]


def test_a_self_citation_edge_is_dropped() -> None:
    connector = stub("openalex", cited_by={"10.1000/a": ["10.1000/a", "10.1000/b"]})

    result = run(traverse([SEED], connectors=[connector]))

    assert [r.DOI for r in result.nodes] == ["10.1000/b"]
    assert [(e.citing, e.cited) for e in result.edges] == [("doi:10.1000/b", "doi:10.1000/a")]


# ---------------------------------------------------------------------------
# Multiple sources: union the edges, dedupe the nodes, isolate the failures
# ---------------------------------------------------------------------------


def test_edges_are_unioned_across_indexes_and_nodes_deduplicated() -> None:
    """OpenAlex misses an edge OpenCitations holds. The traversal keeps both."""
    openalex = stub("openalex", cited_by={"10.1000/a": ["10.1000/b"]})
    opencitations = stub("opencitations", cited_by={"10.1000/a": ["10.1000/b", "10.1000/c"]})

    result = run(traverse([SEED], connectors=[openalex, opencitations]))

    assert sorted(r.DOI for r in result.nodes) == ["10.1000/b", "10.1000/c"]
    edges = {(e.citing, e.cited): e.sources for e in result.edges}
    assert edges[("doi:10.1000/b", "doi:10.1000/a")] == ("openalex", "opencitations")
    assert edges[("doi:10.1000/c", "doi:10.1000/a")] == ("opencitations",)
    # B was reported twice and is ONE node, carrying both attributions.
    node_b = next(r for r in result.nodes if r.DOI == "10.1000/b")
    assert node_b.extra["sources"] == ["openalex", "opencitations"]
    assert result.retrieved_count == 3


def test_a_failing_index_costs_its_edges_and_nothing_else() -> None:
    healthy = stub("openalex", cited_by=CITED_BY)
    rate_limited = stub(
        "semantic_scholar",
        error=SourceError(
            "semantic_scholar",
            "api.semanticscholar.org returned HTTP 429.",
            kind=SourceErrorKind.RATE_LIMIT,
            status_code=429,
        ),
    )

    result = run(traverse([SEED], connectors=[healthy, rate_limited]))

    assert sorted(r.DOI for r in result.nodes) == ["10.1000/b", "10.1000/c"]
    assert len(result.warnings) == 1
    assert result.warnings[0].source == "semantic_scholar"
    assert result.warnings[0].kind == "rate_limit"
    assert result.warnings[0].operation == "get_citations"


def test_a_source_that_errors_on_one_node_stays_reported_as_errored() -> None:
    """An index that failed anywhere in the traversal never reads as a clean success."""

    class _Flaky(_StubGraphConnector):
        name = "opencitations"

        async def get_citations(
            self, identifier: str, *, limit: int = 100
        ) -> list[CSLRecord]:
            if normalize_doi(identifier) == "10.1000/b":
                raise SourceError("opencitations", "boom", kind=SourceErrorKind.SERVER_ERROR)
            return await super().get_citations(identifier, limit=limit)

    flaky = _Flaky(cited_by=CITED_BY)

    result = run(traverse([SEED], depth=2, connectors=[flaky]))

    outcomes = {o.source: o.status for o in result.outcomes}
    assert outcomes == {"opencitations": "error"}
    assert [w.source for w in result.warnings] == ["opencitations"]
    # And the nodes it DID return before failing are still there.
    assert sorted(r.DOI for r in result.nodes) == ["10.1000/b", "10.1000/c"]


# ---------------------------------------------------------------------------
# Surface and determinism
# ---------------------------------------------------------------------------


def test_the_default_sources_are_the_three_citation_indexes() -> None:
    assert DEFAULT_GRAPH_SOURCES == ("openalex", "semantic_scholar", "opencitations")


def test_no_seeds_is_an_empty_result() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    result = run(traverse([], connectors=[connector]))

    assert result.nodes == []
    assert result.edges == []
    assert connector.calls == []


def test_a_seed_with_no_neighbors_is_a_clean_empty_traversal() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    result = run(traverse(["10.1000/d"], connectors=[connector]))

    assert result.nodes == []
    assert result.warnings == []


def test_traverse_sync_drives_the_coroutine() -> None:
    connector = stub("openalex", cited_by=CITED_BY)

    result = traverse_sync([SEED], connectors=[connector])

    assert sorted(r.DOI for r in result.nodes) == ["10.1000/b", "10.1000/c"]


def test_two_traversals_produce_byte_identical_json() -> None:
    """D15 again: the fan-out is concurrent, the output order is not."""
    first = run(traverse([SEED], depth=2, connectors=[stub("openalex", cited_by=CITED_BY)]))
    second = run(traverse([SEED], depth=2, connectors=[stub("openalex", cited_by=CITED_BY)]))

    assert canonical_json(first.to_json_dict()) == canonical_json(second.to_json_dict())
