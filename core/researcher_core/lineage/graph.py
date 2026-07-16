"""Loading the lineage graph from the provenance ledger (M3.2 support).

The graph is never stored as an aggregate. It is a fold of append-only `record_lineage`
events (D19): one per claim node, one per evidence edge, one per experiment manifest. This
module builds the events (so the graph can be recorded) and folds a stream of them back into
the current node, edge, and manifest sets, latest-writer-wins by identity. Reading the graph
is therefore always a derivation, never a lookup of mutable state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..provenance import ProvenanceEvent
from .model import ClaimNode, EvidenceEdge, ExperimentManifest

CLAIM_NODE_KIND = "claim_node"
EVIDENCE_EDGE_KIND = "evidence_edge"
MANIFEST_KIND = "experiment_manifest"


def claim_node_event(
    node: ClaimNode, ts: str, run_id: str, *, protocol_version: str | None = None
) -> ProvenanceEvent:
    """A `record_lineage` event carrying one claim node."""
    return _lineage_event(
        run_id=run_id,
        ts=ts,
        protocol_version=protocol_version,
        payload={"lineage_kind": CLAIM_NODE_KIND, "node": node.to_json_dict()},
    )


def evidence_edge_event(
    edge: EvidenceEdge,
    ts: str,
    run_id: str,
    *,
    source_doi: str = "",
    claim_qualifiers: Mapping[str, Any] | None = None,
    source_response_hashes: Iterable[str] = (),
    protocol_version: str | None = None,
) -> ProvenanceEvent:
    """A `record_lineage` event carrying one evidence edge.

    `source_doi` and `claim_qualifiers` are compile-time inputs, not part of the edge schema:
    the DOI lets the compiler re-check publication status (C003/C005), and the claim
    qualifiers are what C004 compares against the edge's source qualifiers.
    """
    payload: dict[str, Any] = {
        "lineage_kind": EVIDENCE_EDGE_KIND,
        "edge": edge.to_json_dict(),
    }
    if source_doi:
        payload["source_doi"] = source_doi
    if claim_qualifiers:
        payload["claim_qualifiers"] = dict(claim_qualifiers)
    return _lineage_event(
        run_id=run_id,
        ts=ts,
        protocol_version=protocol_version,
        payload=payload,
        source_response_hashes=source_response_hashes,
    )


def manifest_event(
    manifest: ExperimentManifest, ts: str, run_id: str, *, protocol_version: str | None = None
) -> ProvenanceEvent:
    """A `record_lineage` event carrying one experiment manifest."""
    return _lineage_event(
        run_id=run_id,
        ts=ts,
        protocol_version=protocol_version,
        payload={
            "lineage_kind": MANIFEST_KIND,
            "manifest": manifest.to_json_dict(),
            "manifest_hash": manifest.manifest_hash(),
        },
    )


def _lineage_event(
    *,
    run_id: str,
    ts: str,
    payload: dict[str, Any],
    protocol_version: str | None,
    source_response_hashes: Iterable[str] = (),
) -> ProvenanceEvent:
    kwargs: dict[str, Any] = {
        "run_id": run_id,
        "type": "record_lineage",
        "ts": ts,
        "payload": payload,
        "source_response_hashes": tuple(source_response_hashes),
    }
    if protocol_version is not None:
        kwargs["protocol_version"] = protocol_version
    return ProvenanceEvent(**kwargs)


@dataclass
class EdgeRecord:
    """An edge plus the compile-time inputs recorded alongside it."""

    edge: EvidenceEdge
    source_doi: str = ""
    claim_qualifiers: dict[str, Any] = field(default_factory=dict)
    source_response_hashes: tuple[str, ...] = ()


@dataclass
class LineageGraph:
    """The current graph, folded from a lineage event stream."""

    claims: dict[str, ClaimNode] = field(default_factory=dict)
    edges: list[EdgeRecord] = field(default_factory=list)
    manifests: dict[str, ExperimentManifest] = field(default_factory=dict)

    def edges_for(self, claim_id: str) -> list[EdgeRecord]:
        return [e for e in self.edges if e.edge.claim_id == claim_id]

    @classmethod
    def from_events(cls, events: Iterable[ProvenanceEvent]) -> LineageGraph:
        """Fold record_lineage events into the current graph.

        Claim nodes and manifests are keyed by identity (latest event wins), so a re-recorded
        node replaces its predecessor. Edges accumulate; a compile reasons over the full set.
        """
        graph = cls()
        # keyed edges so a re-recorded edge (same claim + target) replaces its predecessor,
        # while preserving first-seen order for a deterministic report.
        edge_index: dict[tuple[str, str], int] = {}
        for event in events:
            if event.type != "record_lineage":
                continue
            payload = event.payload or {}
            kind = payload.get("lineage_kind")
            if kind == CLAIM_NODE_KIND and "node" in payload:
                node = ClaimNode.from_json_dict(payload["node"])
                graph.claims[node.claim_id] = node
            elif kind == EVIDENCE_EDGE_KIND and "edge" in payload:
                edge = EvidenceEdge.from_json_dict(payload["edge"])
                target = edge.passage_id or edge.manifest_hash
                key = (edge.claim_id, target)
                record = EdgeRecord(
                    edge=edge,
                    source_doi=payload.get("source_doi", ""),
                    claim_qualifiers=dict(payload.get("claim_qualifiers", {})),
                    source_response_hashes=tuple(event.source_response_hashes),
                )
                if key in edge_index:
                    graph.edges[edge_index[key]] = record
                else:
                    edge_index[key] = len(graph.edges)
                    graph.edges.append(record)
            elif kind == MANIFEST_KIND and "manifest" in payload:
                manifest = ExperimentManifest.from_json_dict(payload["manifest"])
                graph.manifests[manifest.manifest_hash()] = manifest
        return graph


def load_graph_events(events: Sequence[ProvenanceEvent]) -> LineageGraph:
    """Convenience wrapper mirroring `LineageGraph.from_events` for a materialized list."""
    return LineageGraph.from_events(events)
