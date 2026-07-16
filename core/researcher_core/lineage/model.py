"""The claim-evidence-result graph types (M3.1).

Three node kinds and one edge kind make up the lineage graph:

* A **claim node** is a span of manuscript text with a stable, replayable identifier. The
  identifier is `hash(normalized text + file path + parser version)`, so re-wrapping a
  sentence (a whitespace change) keeps the same node and does not orphan its evidence,
  while a substantive rewrite produces a new node and the old edge is reported dangling.
* An **evidence edge** ties a claim to its support: either an external source passage
  (an M2 passage id, with population/intervention/outcome qualifiers and the axis verdicts
  current at edge creation) or an internal experiment run (a manifest hash). A results
  number points at a run, not at the literature.
* An **experiment manifest** records what produced a number: the code commit, whether the
  worktree was dirty, the data hashes, the environment lock, the seed, the metric
  definitions, and the generated artifacts.

This module computes identifiers and serializes the types. It writes nothing. The compile
gate (M3.2) carries these in D19 ledger events and derives gate state from the stream;
nothing here is stored as a mutable aggregate. Every identifier is deterministic per D15:
the same bytes, configuration, and parser version yield byte-identical output, so a compile
replays exactly. No function here reads the clock; timestamps are caller-supplied per D19.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..model import canonical_json, content_hash, normalize_title, sha256_hex

# ---------------------------------------------------------------------------
# Vocabularies (D16). Kept here as the single source of truth for the graph, and
# mirrored by the JSON schemas so a typo'd verdict fails validation.
# ---------------------------------------------------------------------------

#: axis (a) reference identity
AXIS_IDENTITY_VERDICTS = ("verified", "mismatch", "unresolvable", "inconclusive")
#: axis (b) publication status
AXIS_STATUS_VERDICTS = ("current", "corrected", "retracted", "expression-of-concern")
#: axis (c) claim faithfulness
AXIS_FAITHFULNESS_VERDICTS = ("supported", "partial", "contradicted", "insufficient-passage")
#: axis (d) accessibility
AXIS_ACCESSIBILITY_VERDICTS = ("full-text", "abstract-only", "unavailable")

#: The only verdicts a consumer may act on as "this citation is wrong" (D9). A false
#: accusation is the worst failure this system has, so `inconclusive` and
#: `insufficient-passage` are deliberately absent: they are open items, never refusals.
REFUSAL_GRADE_VERDICTS = frozenset(
    {"unresolvable", "mismatch", "retracted", "contradicted"}
)


class ClaimKind(str, Enum):
    """What a claim asserts. Numbers point at experiment runs; the others at sources."""

    ASSERTION = "assertion"
    NUMBER = "number"
    COMPARISON = "comparison"


class EvidenceQuality(str, Enum):
    """A small ordinal quality vocabulary. M4 upgrades this to GRADE; it is a string enum
    from day one so that upgrade does not change the field's type."""

    SYSTEMATIC_REVIEW = "systematic-review"
    RCT = "RCT"
    OBSERVATIONAL = "observational"
    PREPRINT = "preprint"
    ABSTRACT_ONLY = "abstract-only"


EVIDENCE_QUALITY = tuple(q.value for q in EvidenceQuality)

#: The current parser version. Bumping it intentionally changes every claim id, which is
#: what makes a compile replayable: an id is only stable within one parser version.
CLAIM_PARSER_VERSION = "1"

MANIFEST_VERSION = "1"


def normalize_claim_text(text: str) -> str:
    """The comparison form of a claim: NFC normalized, whitespace collapsed, stripped.

    Reuses the kernel's title normalizer so the graph and the retrieval layer agree on what
    "the same text" means. Case and punctuation are preserved, so a reworded claim is a new
    claim, but line rewrapping and spacing changes are not.
    """
    return normalize_title(text)


def claim_id_for(
    normalized_text: str, file: str, parser_version: str = CLAIM_PARSER_VERSION
) -> str:
    """The stable claim identifier: `hash(normalized text + file + parser version)`.

    Deterministic and independent of dict ordering, because it hashes a canonical JSON
    list of exactly these three fields.
    """
    return sha256_hex(canonical_json([normalized_text, file, parser_version]))


# ---------------------------------------------------------------------------
# Claim nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimNode:
    """A hash-anchored span of manuscript text.

    `claim_id` is stable to re-wrapping; `text_hash` is over the RAW span bytes, so any
    edit at all (even one the id survives) is still visible by comparing text hashes.
    """

    claim_id: str
    file: str
    span_start: int
    span_end: int
    text_hash: str
    normalized_text: str
    kind: ClaimKind
    parser_version: str = CLAIM_PARSER_VERSION

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "file": self.file,
            "span": {"start": self.span_start, "end": self.span_end},
            "text_hash": self.text_hash,
            "normalized_text": self.normalized_text,
            "kind": self.kind.value,
            "parser_version": self.parser_version,
        }

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> ClaimNode:
        span = data.get("span") or {}
        return cls(
            claim_id=data["claim_id"],
            file=data["file"],
            span_start=int(span.get("start", data.get("span_start", 0))),
            span_end=int(span.get("end", data.get("span_end", 0))),
            text_hash=data["text_hash"],
            normalized_text=data["normalized_text"],
            kind=ClaimKind(data["kind"]),
            parser_version=data.get("parser_version", CLAIM_PARSER_VERSION),
        )


def make_claim_node(
    file: str,
    raw_text: str,
    span_start: int,
    span_end: int,
    kind: ClaimKind | str,
    parser_version: str = CLAIM_PARSER_VERSION,
) -> ClaimNode:
    """Build one claim node from a raw span. Core computes ids and hashes; Claude proposes
    the span boundaries and the kind."""
    if not isinstance(kind, ClaimKind):
        kind = ClaimKind(kind)
    normalized = normalize_claim_text(raw_text)
    return ClaimNode(
        claim_id=claim_id_for(normalized, file, parser_version),
        file=file,
        span_start=span_start,
        span_end=span_end,
        text_hash=sha256_hex(raw_text),
        normalized_text=normalized,
        kind=kind,
        parser_version=parser_version,
    )


def make_claim_nodes(
    file: str,
    text: str,
    spans: Sequence[Mapping[str, Any]],
    parser_version: str = CLAIM_PARSER_VERSION,
) -> list[ClaimNode]:
    """Build claim nodes for a file's proposed spans, in file order.

    Each span is `{"start": int, "end": int, "kind": ClaimKind|str}`. The raw text for a
    node is `text[start:end]`. Output order is by span start then end, so the node list is
    byte-identical across runs regardless of the order the spans were proposed in (D15).
    """
    ordered = sorted(spans, key=lambda s: (int(s["start"]), int(s["end"])))
    nodes: list[ClaimNode] = []
    for s in ordered:
        start, end = int(s["start"]), int(s["end"])
        nodes.append(
            make_claim_node(
                file=file,
                raw_text=text[start:end],
                span_start=start,
                span_end=end,
                kind=s.get("kind", ClaimKind.ASSERTION),
                parser_version=parser_version,
            )
        )
    return nodes


# ---------------------------------------------------------------------------
# Evidence edges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceVersion:
    """Which snapshot a source edge was drawn from, and when it was retrieved. Both feed
    the compile gate's stale-evidence check (C003)."""

    snapshot_hash: str = ""
    retrieved_at: str = ""

    def to_json_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.snapshot_hash:
            out["snapshot_hash"] = self.snapshot_hash
        if self.retrieved_at:
            out["retrieved_at"] = self.retrieved_at
        return out

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any] | None) -> SourceVersion:
        data = data or {}
        return cls(
            snapshot_hash=data.get("snapshot_hash", ""),
            retrieved_at=data.get("retrieved_at", ""),
        )


@dataclass(frozen=True)
class AxisVerdicts:
    """The four D16 axis verdicts current at edge creation. Each is optional (an internal
    edge carries none), but when present it must be from that axis's vocabulary."""

    identity: str | None = None
    status: str | None = None
    faithfulness: str | None = None
    accessibility: str | None = None

    def __post_init__(self) -> None:
        for name, value, vocab in (
            ("identity", self.identity, AXIS_IDENTITY_VERDICTS),
            ("status", self.status, AXIS_STATUS_VERDICTS),
            ("faithfulness", self.faithfulness, AXIS_FAITHFULNESS_VERDICTS),
            ("accessibility", self.accessibility, AXIS_ACCESSIBILITY_VERDICTS),
        ):
            if value is not None and value not in vocab:
                raise ValueError(
                    f"axis {name} verdict {value!r} is not one of {vocab}"
                )

    def refusal_grade(self) -> list[str]:
        """The refusal-grade verdicts present, if any (D9). Only these may be acted on as
        'this citation is wrong'."""
        return [
            v
            for v in (self.identity, self.status, self.faithfulness)
            if v in REFUSAL_GRADE_VERDICTS
        ]

    def to_json_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in ("identity", "status", "faithfulness", "accessibility"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        return out

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any] | None) -> AxisVerdicts:
        data = data or {}
        return cls(
            identity=data.get("identity"),
            status=data.get("status"),
            faithfulness=data.get("faithfulness"),
            accessibility=data.get("accessibility"),
        )


@dataclass(frozen=True)
class EvidenceEdge:
    """A claim's support. External edges point at an M2 passage id; internal edges at an
    experiment manifest hash. Exactly one target is set."""

    claim_id: str
    #: "external" (a source passage) or "internal" (an experiment run)
    target_kind: str
    passage_id: str = ""
    manifest_hash: str = ""
    # external-edge qualifiers
    population: str = ""
    intervention_or_exposure: str = ""
    outcome: str = ""
    source_version: SourceVersion = field(default_factory=SourceVersion)
    evidence_quality: EvidenceQuality | None = None
    axis_verdicts: AxisVerdicts = field(default_factory=AxisVerdicts)

    def __post_init__(self) -> None:
        if self.target_kind not in ("external", "internal"):
            raise ValueError(f"target_kind must be external or internal, got {self.target_kind!r}")
        if self.target_kind == "external" and not self.passage_id:
            raise ValueError("an external edge must carry a passage_id")
        if self.target_kind == "internal" and not self.manifest_hash:
            raise ValueError("an internal edge must carry a manifest_hash")
        if self.target_kind == "internal" and self.passage_id:
            raise ValueError("an internal edge must not carry a passage_id")

    def is_refusal_grade(self) -> bool:
        """True if any axis verdict on this edge is refusal-grade (D9)."""
        return bool(self.axis_verdicts.refusal_grade())

    def satisfies_gate(self) -> bool:
        """Whether this edge, on its own, can satisfy the compile gate for its claim.

        An edge with a refusal-grade verdict never satisfies. An external edge whose
        faithfulness is `insufficient-passage` is a valid edge but an OPEN ITEM: it cannot
        satisfy the gate alone (D11), because a claim degraded to abstract level was never
        actually checked against the source text. An internal edge (a claim backed by an
        experiment run) satisfies once it is not refusal-grade.
        """
        if self.is_refusal_grade():
            return False
        if self.target_kind == "external":
            if self.axis_verdicts.faithfulness in (None, "insufficient-passage"):
                return False
        return True

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "claim_id": self.claim_id,
            "target_kind": self.target_kind,
        }
        if self.target_kind == "external":
            out["passage_id"] = self.passage_id
            qualifiers: dict[str, Any] = {}
            if self.population:
                qualifiers["population"] = self.population
            if self.intervention_or_exposure:
                qualifiers["intervention_or_exposure"] = self.intervention_or_exposure
            if self.outcome:
                qualifiers["outcome"] = self.outcome
            sv = self.source_version.to_json_dict()
            if sv:
                qualifiers["source_version"] = sv
            if self.evidence_quality is not None:
                qualifiers["evidence_quality"] = self.evidence_quality.value
            if qualifiers:
                out["qualifiers"] = qualifiers
            verdicts = self.axis_verdicts.to_json_dict()
            if verdicts:
                out["axis_verdicts"] = verdicts
        else:
            out["manifest_hash"] = self.manifest_hash
        return out

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> EvidenceEdge:
        target_kind = data["target_kind"]
        if target_kind == "internal":
            return cls(
                claim_id=data["claim_id"],
                target_kind="internal",
                manifest_hash=data["manifest_hash"],
            )
        q = data.get("qualifiers") or {}
        eq = q.get("evidence_quality")
        return cls(
            claim_id=data["claim_id"],
            target_kind="external",
            passage_id=data["passage_id"],
            population=q.get("population", ""),
            intervention_or_exposure=q.get("intervention_or_exposure", ""),
            outcome=q.get("outcome", ""),
            source_version=SourceVersion.from_json_dict(q.get("source_version")),
            evidence_quality=EvidenceQuality(eq) if eq else None,
            axis_verdicts=AxisVerdicts.from_json_dict(data.get("axis_verdicts")),
        )


# ---------------------------------------------------------------------------
# Experiment manifests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula_or_ref: str = ""

    def to_json_dict(self) -> dict[str, str]:
        return {"name": self.name, "formula_or_ref": self.formula_or_ref}

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> MetricDefinition:
        return cls(name=data["name"], formula_or_ref=data.get("formula_or_ref", ""))


@dataclass(frozen=True)
class ArtifactHash:
    path: str
    hash: str
    produced_at: str = ""

    def to_json_dict(self) -> dict[str, str]:
        out = {"path": self.path, "hash": self.hash}
        if self.produced_at:
            out["produced_at"] = self.produced_at
        return out

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> ArtifactHash:
        return cls(
            path=data["path"], hash=data["hash"], produced_at=data.get("produced_at", "")
        )


@dataclass(frozen=True)
class ExperimentManifest:
    """What produced a results number. `ts` is caller-supplied (D19), never read from the
    clock, so a manifest hashes identically on replay."""

    run_id: str
    code_commit: str
    ts: str
    dirty_worktree: bool = False
    data_hashes: tuple[str, ...] = ()
    environment_lockfile_hash: str = ""
    seed: int | None = None
    metric_definitions: tuple[MetricDefinition, ...] = ()
    artifact_hashes: tuple[ArtifactHash, ...] = ()
    command_line: str = ""
    manifest_version: str = MANIFEST_VERSION

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "manifest_version": self.manifest_version,
            "run_id": self.run_id,
            "code_commit": self.code_commit,
            "dirty_worktree": self.dirty_worktree,
            "data_hashes": list(self.data_hashes),
            "environment_lockfile_hash": self.environment_lockfile_hash,
            "metric_definitions": [m.to_json_dict() for m in self.metric_definitions],
            "artifact_hashes": [a.to_json_dict() for a in self.artifact_hashes],
            "command_line": self.command_line,
            "ts": self.ts,
        }
        if self.seed is not None:
            out["seed"] = self.seed
        return out

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> ExperimentManifest:
        return cls(
            manifest_version=data.get("manifest_version", MANIFEST_VERSION),
            run_id=data["run_id"],
            code_commit=data["code_commit"],
            ts=data["ts"],
            dirty_worktree=bool(data.get("dirty_worktree", False)),
            data_hashes=tuple(data.get("data_hashes", ())),
            environment_lockfile_hash=data.get("environment_lockfile_hash", ""),
            seed=data.get("seed"),
            metric_definitions=tuple(
                MetricDefinition.from_json_dict(m)
                for m in data.get("metric_definitions", ())
            ),
            artifact_hashes=tuple(
                ArtifactHash.from_json_dict(a) for a in data.get("artifact_hashes", ())
            ),
            command_line=data.get("command_line", ""),
        )

    def manifest_hash(self) -> str:
        """The content hash that internal edges point at. Covers every field, `ts`
        included, so two runs that differ only in when they ran are distinct manifests."""
        return content_hash(self.to_json_dict())


def manifest_hash_for(manifest: ExperimentManifest | Mapping[str, Any]) -> str:
    """The manifest hash for a manifest object or its JSON dict."""
    if isinstance(manifest, ExperimentManifest):
        return manifest.manifest_hash()
    return content_hash(ExperimentManifest.from_json_dict(manifest).to_json_dict())
