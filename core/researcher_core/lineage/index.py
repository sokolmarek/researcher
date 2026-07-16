"""Source-dependency lineage: which snapshot produced this derived artifact.

This module answers exactly one question, and answers it from the ledger rather than from
any separate bookkeeping: given a derived artifact (a deduplicated :class:`CSLRecord`, and
in M3 a table, a figure, or a claim), which raw API responses does it ultimately rest on?

That question is the one the M3 compile gate needs, in two directions:

* **Forward (stale evidence):** the artifact's snapshots are named by content hash. If a
  snapshot with that hash is no longer the current recorded response for its request, the
  world moved under the artifact and the artifact is stale. :meth:`LineageIndex.stale`
  reports that against a live :class:`~researcher_core.snapshots.SnapshotStore`.
* **Backward (drift blast radius):** when a re-record changes a response, which artifacts
  were built on the old bytes? :meth:`LineageIndex.dependents` answers, transitively.

The input is the ``record_lineage`` event (see :mod:`researcher_core.provenance`). Its
payload convention::

    {
      "artifact_id":   "10.7717/peerj.4375",     # id of the derived artifact
      "artifact_hash": "<content hash of the derived artifact>",
      "artifact_type": "record",
      "inputs": [                                  # what it was derived FROM
        {"id": "openalex:W2741809807", "hash": "<record content hash>", "source": "openalex"},
        {"id": "crossref:10.7717/peerj.4375", "hash": "...", "source": "crossref"}
      ]
    }

and the event's ``source_response_hashes`` carry the snapshots consumed in producing it.

Lineage is transitive: an input ``id`` that is itself an artifact with its own
``record_lineage`` event contributes that artifact's snapshots too. Cycles (which a
malformed emitter could write) are traversed once and never loop.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..provenance import ProvenanceEvent, ProvenanceLedger
from ..snapshots import Snapshot, SnapshotStore

__all__ = [
    "LineageEdge",
    "LineageIndex",
    "LineageNode",
    "LineageResult",
    "StaleReport",
    "strip_hash_prefix",
]


def strip_hash_prefix(value: str) -> str:
    """Drop an optional ``sha256:`` prefix, so hashes compare however they were written."""
    text = str(value).strip()
    return text[7:] if text.startswith("sha256:") else text


# ---------------------------------------------------------------------------
# Nodes and edges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineageEdge:
    """One upstream input of a derived artifact."""

    id: str
    hash: str = ""
    source: str = ""
    role: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id}
        if self.hash:
            out["hash"] = self.hash
        if self.source:
            out["source"] = self.source
        if self.role:
            out["role"] = self.role
        return out

    @classmethod
    def from_payload(cls, data: Mapping[str, Any] | str) -> LineageEdge:
        if isinstance(data, str):
            return cls(id=data)
        identifier = data.get("id") or data.get("record_id") or data.get("artifact_id") or ""
        return cls(
            id=str(identifier),
            hash=str(data.get("hash") or data.get("record_hash") or ""),
            source=str(data.get("source") or ""),
            role=str(data.get("role") or ""),
        )


@dataclass(frozen=True)
class LineageNode:
    """One ``record_lineage`` event, read as a node in the dependency graph."""

    artifact_id: str
    artifact_hash: str
    artifact_type: str
    inputs: tuple[LineageEdge, ...]
    snapshot_hashes: tuple[str, ...]
    event_id: str
    run_id: str
    ts: str

    @classmethod
    def from_event(cls, event: ProvenanceEvent) -> LineageNode:
        if event.type != "record_lineage":
            raise ValueError(
                f"LineageNode is built from record_lineage events, not {event.type!r}."
            )
        payload = event.payload
        raw_inputs = payload.get("inputs") or ()
        if isinstance(raw_inputs, (str, bytes)) or not isinstance(raw_inputs, Sequence):
            raw_inputs = ()
        return cls(
            artifact_id=str(payload.get("artifact_id") or ""),
            artifact_hash=str(payload.get("artifact_hash") or ""),
            artifact_type=str(payload.get("artifact_type") or "record"),
            inputs=tuple(LineageEdge.from_payload(item) for item in raw_inputs),
            snapshot_hashes=tuple(
                strip_hash_prefix(h) for h in event.source_response_hashes
            ),
            event_id=event.event_id,
            run_id=event.run_id,
            ts=event.ts,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "artifact_type": self.artifact_type,
            "inputs": [edge.to_json_dict() for edge in self.inputs],
            "snapshot_hashes": list(self.snapshot_hashes),
            "event_id": self.event_id,
            "run_id": self.run_id,
            "ts": self.ts,
        }


@dataclass(frozen=True)
class LineageResult:
    """The full resolution of one artifact back to the raw responses under it."""

    artifact_id: str
    artifact_hash: str = ""
    artifact_type: str = ""
    snapshot_hashes: tuple[str, ...] = ()
    upstream_ids: tuple[str, ...] = ()
    nodes: tuple[LineageNode, ...] = ()
    known: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "artifact_type": self.artifact_type,
            "known": self.known,
            "snapshot_hashes": list(self.snapshot_hashes),
            "upstream_ids": list(self.upstream_ids),
            "nodes": [node.to_json_dict() for node in self.nodes],
        }


@dataclass(frozen=True)
class StaleReport:
    """Whether an artifact still rests on snapshots the store currently holds."""

    artifact_id: str
    is_stale: bool
    present_hashes: tuple[str, ...] = ()
    missing_hashes: tuple[str, ...] = ()
    known: bool = True

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "known": self.known,
            "is_stale": self.is_stale,
            "present_hashes": list(self.present_hashes),
            "missing_hashes": list(self.missing_hashes),
        }


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------


@dataclass
class LineageIndex:
    """An in-memory dependency graph built from ``record_lineage`` events.

    Built from a ledger (:meth:`from_ledger`) or from a list of events
    (:meth:`from_events`), which is what makes it work equally over a live ledger and over
    a JSONL export replayed offline.
    """

    nodes_by_artifact: dict[str, list[LineageNode]] = field(default_factory=dict)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_events(cls, events: Iterable[ProvenanceEvent]) -> LineageIndex:
        index = cls()
        for event in events:
            if event.type != "record_lineage":
                continue
            node = LineageNode.from_event(event)
            if not node.artifact_id:
                continue
            index.nodes_by_artifact.setdefault(node.artifact_id, []).append(node)
        return index

    @classmethod
    def from_ledger(cls, ledger: ProvenanceLedger, *, run_id: str | None = None) -> LineageIndex:
        return cls.from_events(ledger.iter_events(run_id=run_id, type="record_lineage"))

    # -- queries -----------------------------------------------------------

    def artifacts(self) -> list[str]:
        """Every artifact id the index knows about, sorted."""
        return sorted(self.nodes_by_artifact)

    def nodes_for(self, artifact_id: str) -> list[LineageNode]:
        """Every ``record_lineage`` node recorded for this artifact, in append order."""
        return list(self.nodes_by_artifact.get(artifact_id, ()))

    def resolve(self, artifact_id: str) -> LineageResult:
        """Resolve an artifact transitively back to the snapshot hashes under it.

        An unknown artifact resolves to ``known=False`` with no hashes, rather than an
        exception: "no lineage recorded" is a legitimate, reportable answer (and, for the
        M3 gate, a finding in its own right).
        """
        nodes = self.nodes_for(artifact_id)
        if not nodes:
            return LineageResult(artifact_id=artifact_id, known=False)

        hashes: list[str] = []
        upstream: list[str] = []
        visited_nodes: list[LineageNode] = []
        seen_artifacts: set[str] = set()
        seen_hashes: set[str] = set()
        seen_upstream: set[str] = set()

        stack: list[str] = [artifact_id]
        while stack:
            current = stack.pop(0)
            if current in seen_artifacts:
                continue
            seen_artifacts.add(current)
            for node in self.nodes_for(current):
                visited_nodes.append(node)
                for digest in node.snapshot_hashes:
                    if digest not in seen_hashes:
                        seen_hashes.add(digest)
                        hashes.append(digest)
                for edge in node.inputs:
                    if not edge.id:
                        continue
                    if edge.id not in seen_upstream:
                        seen_upstream.add(edge.id)
                        upstream.append(edge.id)
                    # Transitive: an input that is itself a derived artifact contributes
                    # its own snapshots. Guarded by seen_artifacts, so a cycle terminates.
                    if edge.id in self.nodes_by_artifact:
                        stack.append(edge.id)

        head = nodes[-1]
        return LineageResult(
            artifact_id=artifact_id,
            artifact_hash=head.artifact_hash,
            artifact_type=head.artifact_type,
            snapshot_hashes=tuple(sorted(hashes)),
            upstream_ids=tuple(sorted(upstream)),
            nodes=tuple(visited_nodes),
            known=True,
        )

    def dependents(self, response_hash: str) -> list[str]:
        """Every artifact that (transitively) rests on the snapshot with this hash."""
        target = strip_hash_prefix(response_hash)
        return sorted(
            artifact_id
            for artifact_id in self.nodes_by_artifact
            if target in self.resolve(artifact_id).snapshot_hashes
        )

    # -- store-joined queries ----------------------------------------------

    def resolve_snapshots(self, artifact_id: str, store: SnapshotStore) -> list[Snapshot]:
        """The actual snapshot records under an artifact, loaded from a snapshot store.

        This is the concrete form of "which snapshot produced this record": not a hash, the
        recorded response body itself, ready to be re-read or diffed.
        """
        wanted = set(self.resolve(artifact_id).snapshot_hashes)
        if not wanted:
            return []
        found = [
            snapshot
            for snapshot in store.iter_snapshots()
            if strip_hash_prefix(snapshot.response_hash) in wanted
        ]
        return sorted(found, key=lambda s: (s.source, s.endpoint, s.response_hash))

    def stale(self, artifact_id: str, store: SnapshotStore) -> StaleReport:
        """Stale-evidence check: are the snapshots this artifact was built on still current?

        A hash the store no longer holds means the recorded response for that request has
        changed (a re-record wrote different bytes) or the snapshot is gone. Either way the
        artifact rests on evidence that is no longer what the store says the source
        returned, which is precisely the condition the M3 compile gate refuses to compile
        over.
        """
        result = self.resolve(artifact_id)
        if not result.known:
            return StaleReport(artifact_id=artifact_id, is_stale=False, known=False)
        current = {strip_hash_prefix(s.response_hash) for s in store.iter_snapshots()}
        present = tuple(h for h in result.snapshot_hashes if h in current)
        missing = tuple(h for h in result.snapshot_hashes if h not in current)
        return StaleReport(
            artifact_id=artifact_id,
            is_stale=bool(missing),
            present_hashes=present,
            missing_hashes=missing,
        )
