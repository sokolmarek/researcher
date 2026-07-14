"""Citation-graph traversal: forward (who cites this) and backward (what this cites).

Three independently built graphs answer these questions, and they disagree: OpenAlex,
Semantic Scholar, and OpenCitations each miss edges the others hold. So a traversal queries
all three, unions the edges, and deduplicates the nodes, rather than trusting any one index.
The same per-source error isolation as ``search.py`` applies: a rate-limited Semantic
Scholar costs the traversal its S2 edges and a warning, never the whole result.

Depth is limited to :data:`MAX_DEPTH` (2). This is a hard cap, not a suggestion. Depth 2 on
a well-cited paper already fans out to thousands of works, and the value of the third hop
is close to nil next to its cost to the indexes we are guests of.

**A cycle must not loop forever.** Citation graphs are supposed to be acyclic (a paper
cannot cite one published after it), and in practice they are not: preprint versions,
simultaneous publication, and plain metadata errors all produce A cites B and B cites A.
Every discovered node key is therefore recorded in a visited set BEFORE it can enter the
next frontier, and the seed keys are in that set from the start. A node is expanded at most
once, so a cycle terminates by construction rather than by luck. ``test_graph.py`` pins
this with an explicit mutual-citation fixture.

Nodes are deduplicated against the seed set as well as against each other: a seed that
turns up as its own neighbor's neighbor is not a discovery, and reporting it as one would
inflate every downstream count.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .connectors import (
    BaseConnector,
    SourceError,
    UnsupportedOperation,
    create_connector,
)
from .dedupe import DedupDecision, dedupe, identifier_key, identity_key
from .model import CSLRecord
from .search import (
    OUTCOME_ERROR,
    OUTCOME_OK,
    OUTCOME_UNSUPPORTED,
    SourceOutcome,
    SourceWarning,
)
from .snapshots import SnapshotMissingError, SnapshotSession

__all__ = [
    "DEFAULT_DEPTH",
    "DEFAULT_GRAPH_SOURCES",
    "DIRECTION_BACKWARD",
    "DIRECTION_FORWARD",
    "MAX_DEPTH",
    "GraphEdge",
    "GraphResult",
    "traverse",
    "traverse_sync",
]

#: Forward: works that cite the seed. Backward: works the seed cites.
DIRECTION_FORWARD = "forward"
DIRECTION_BACKWARD = "backward"

#: One hop by default.
DEFAULT_DEPTH = 1
#: Two hops is the ceiling. See the module docstring.
MAX_DEPTH = 2

#: The three citation indexes, queried in this fixed order (which is also the order their
#: records enter dedupe, so the traversal is deterministic under D15).
DEFAULT_GRAPH_SOURCES: tuple[str, ...] = ("openalex", "semantic_scholar", "opencitations")

_OPERATION = {
    DIRECTION_FORWARD: "get_citations",
    DIRECTION_BACKWARD: "get_references",
}


@dataclass(frozen=True)
class GraphEdge:
    """One citation edge, with every index that reported it.

    Always stored citing-to-cited regardless of traversal direction, so a forward and a
    backward traversal over the same pair produce the same edge rather than two mirror
    images of one fact.
    """

    citing: str
    cited: str
    sources: tuple[str, ...] = ()
    depth: int = 1

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "citing": self.citing,
            "cited": self.cited,
            "sources": list(self.sources),
            "depth": self.depth,
        }


@dataclass
class GraphResult:
    """The neighborhood of the seeds: nodes, edges, and the per-source story."""

    seeds: list[str] = field(default_factory=list)
    direction: str = DIRECTION_FORWARD
    depth: int = DEFAULT_DEPTH
    nodes: list[CSLRecord] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    warnings: list[SourceWarning] = field(default_factory=list)
    outcomes: list[SourceOutcome] = field(default_factory=list)
    decisions: list[DedupDecision] = field(default_factory=list)
    #: Node records retrieved before dedupe, across every source and every level.
    retrieved_count: int = 0

    @property
    def node_keys(self) -> list[str]:
        return [identity_key(record) for record in self.nodes]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "seeds": self.seeds,
            "direction": self.direction,
            "depth": self.depth,
            "nodes": [record.to_csl_json() for record in self.nodes],
            "edges": [edge.to_json_dict() for edge in self.edges],
            "warnings": [w.to_json_dict() for w in self.warnings],
            "sources": [o.to_json_dict() for o in self.outcomes],
            "dedup_decisions": [d.to_json_dict() for d in self.decisions],
            "counts": {
                "retrieved": self.retrieved_count,
                "nodes": len(self.nodes),
                "edges": len(self.edges),
            },
        }


# ---------------------------------------------------------------------------
# One source, one seed
# ---------------------------------------------------------------------------


async def _neighbors_one(
    connector: BaseConnector,
    identifier: str,
    *,
    direction: str,
    limit: int,
) -> tuple[list[CSLRecord], SourceOutcome]:
    """Ask one source for one node's neighbors. Isolates every failure but a missing snapshot."""
    name = connector.name
    operation = _OPERATION[direction]
    if not connector.supports(operation):
        return [], SourceOutcome(source=name, status=OUTCOME_UNSUPPORTED)

    method = getattr(connector, operation)
    try:
        records = await method(identifier, limit=limit)
    except SnapshotMissingError:
        raise
    except UnsupportedOperation:
        return [], SourceOutcome(source=name, status=OUTCOME_UNSUPPORTED)
    except SourceError as exc:
        warning = SourceWarning.from_source_error(exc, operation=operation)
        return [], SourceOutcome(source=name, status=OUTCOME_ERROR, warning=warning)
    except Exception as exc:  # noqa: BLE001 - one bad index must not sink the traversal
        warning = SourceWarning.from_exception(name, exc, operation=operation)
        return [], SourceOutcome(source=name, status=OUTCOME_ERROR, warning=warning)

    return list(records), SourceOutcome(
        source=name, status=OUTCOME_OK, record_count=len(records)
    )


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


async def traverse(
    seeds: Iterable[str],
    *,
    direction: str = DIRECTION_FORWARD,
    depth: int = DEFAULT_DEPTH,
    limit: int = 100,
    sources: Iterable[str] | None = None,
    connectors: Sequence[BaseConnector] | None = None,
    session: SnapshotSession | None = None,
) -> GraphResult:
    """Breadth-first citation traversal from ``seeds``, at most ``depth`` hops.

    Raises ``ValueError`` for an unknown direction or a depth outside 1..:data:`MAX_DEPTH`.
    Every other failure is isolated into :attr:`GraphResult.warnings`.
    """
    if direction not in _OPERATION:
        raise ValueError(
            f"Unknown traversal direction {direction!r}. "
            f"Use {DIRECTION_FORWARD!r} or {DIRECTION_BACKWARD!r}."
        )
    if depth < 1 or depth > MAX_DEPTH:
        raise ValueError(
            f"Traversal depth must be between 1 and {MAX_DEPTH}; got {depth}. "
            "Deeper traversals fan out to thousands of works for no added evidence."
        )

    seed_ids = [str(s).strip() for s in seeds if str(s).strip()]
    if connectors is None:
        names = list(sources) if sources is not None else list(DEFAULT_GRAPH_SOURCES)
        built = [_build(name, session) for name in names]
        try:
            return await traverse(
                seed_ids,
                direction=direction,
                depth=depth,
                limit=limit,
                connectors=built,
            )
        finally:
            for connector in built:
                await connector.aclose()

    result = GraphResult(seeds=seed_ids, direction=direction, depth=depth)
    if not seed_ids or not connectors:
        return result

    seed_keys = {identifier_key(s) for s in seed_ids}
    # Visited BEFORE expansion, and seeded with the seeds. This is what terminates a cycle.
    visited: set[str] = set(seed_keys)
    known: list[CSLRecord] = []
    edges: dict[tuple[str, str], list[str]] = {}
    edge_depth: dict[tuple[str, str], int] = {}
    outcomes: dict[str, SourceOutcome] = {}
    frontier: list[str] = list(seed_ids)

    for level in range(1, depth + 1):
        if not frontier:
            break

        level_records: list[CSLRecord] = []
        raw_edges: list[tuple[str, str, str]] = []

        for parent in frontier:
            parent_key = identifier_key(parent)
            tasks = [
                _neighbors_one(connector, parent, direction=direction, limit=limit)
                for connector in connectors
            ]
            for records, outcome in await asyncio.gather(*tasks):
                _merge_outcome(outcomes, outcome)
                for record in records:
                    level_records.append(record)
                    raw_edges.append((parent_key, identity_key(record), outcome.source))

        result.retrieved_count += len(level_records)

        # Dedupe the new records against everything already known, so a work reported by
        # OpenAlex at level 1 and by Semantic Scholar at level 2 stays one node.
        # dedupe() is idempotent over its own output (a collapsed set has nothing left to
        # collapse), so re-running it over `known` yields decisions for the NEW records
        # only, never a duplicate decision for a merge already recorded at an earlier level.
        merged = dedupe(known + level_records)
        result.decisions.extend(merged.decisions)
        known = merged.records
        key_map = merged.key_map

        for parent_key, neighbor_key, source in raw_edges:
            canonical_parent = key_map.get(parent_key, parent_key)
            canonical_neighbor = key_map.get(neighbor_key, neighbor_key)
            if canonical_parent == canonical_neighbor:
                continue  # a self-citation edge is a metadata defect, not a neighbor
            edge = (
                (canonical_neighbor, canonical_parent)
                if direction == DIRECTION_FORWARD
                else (canonical_parent, canonical_neighbor)
            )
            reported = edges.setdefault(edge, [])
            if source not in reported:
                reported.append(source)
            edge_depth.setdefault(edge, level)

        next_frontier: list[str] = []
        for record in known:
            key = identity_key(record)
            if key in visited:
                continue
            visited.add(key)
            record.extra.setdefault("graph_depth", level)
            expandable = _expansion_id(record)
            if expandable:
                next_frontier.append(expandable)
        frontier = next_frontier

    # Seeds are not discoveries. Drop them from the node list even when a neighbor cites
    # them back (the edge is kept, so the cycle stays visible in the output).
    result.nodes = [r for r in known if identity_key(r) not in seed_keys]
    result.edges = [
        GraphEdge(
            citing=citing,
            cited=cited,
            sources=tuple(sorted(reported)),
            depth=edge_depth[(citing, cited)],
        )
        for (citing, cited), reported in edges.items()
    ]
    result.outcomes = [outcomes[name] for name in sorted(outcomes)]
    result.warnings = [o.warning for o in result.outcomes if o.warning is not None]
    return result


def traverse_sync(seeds: Iterable[str], **kwargs: Any) -> GraphResult:
    """Blocking :func:`traverse`, for the CLI and for callers with no event loop."""
    return asyncio.run(traverse(seeds, **kwargs))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _expansion_id(record: CSLRecord) -> str:
    """The identifier to expand a node by. DOI first: all three indexes accept one."""
    return record.DOI or record.openalex_id or record.arxiv_id or record.s2_id


def _merge_outcome(outcomes: dict[str, SourceOutcome], outcome: SourceOutcome) -> None:
    """Fold one call's outcome into the per-source summary.

    A source that errored on ANY node in the traversal keeps its error outcome and its
    warning: the traversal is incomplete from that source's point of view, and saying
    otherwise because a later node happened to succeed would overstate the evidence.
    """
    previous = outcomes.get(outcome.source)
    if previous is None:
        outcomes[outcome.source] = outcome
        return
    if previous.status == OUTCOME_ERROR:
        outcomes[outcome.source] = SourceOutcome(
            source=previous.source,
            status=OUTCOME_ERROR,
            record_count=previous.record_count + outcome.record_count,
            warning=previous.warning,
        )
        return
    if outcome.status == OUTCOME_ERROR:
        outcomes[outcome.source] = SourceOutcome(
            source=outcome.source,
            status=OUTCOME_ERROR,
            record_count=previous.record_count + outcome.record_count,
            warning=outcome.warning,
        )
        return
    seen_statuses = (previous.status, outcome.status)
    status = OUTCOME_OK if OUTCOME_OK in seen_statuses else OUTCOME_UNSUPPORTED
    outcomes[outcome.source] = SourceOutcome(
        source=outcome.source,
        status=status,
        record_count=previous.record_count + outcome.record_count,
    )


def _build(name: str, session: SnapshotSession | None) -> BaseConnector:
    if session is None:
        return create_connector(name)
    return create_connector(name, snapshots=session)
