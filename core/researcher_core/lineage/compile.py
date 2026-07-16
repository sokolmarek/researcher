"""`researcher compile`: the evidence-lineage gate (M3.2).

Walks the lineage graph and reports one diagnostic per defect class:

    C001 orphan claim        a claim with no evidence edge
    C002 altered number      a generated artifact whose content hash no longer matches its manifest
    C003 stale evidence      a source snapshot superseded, or status flipped to corrected
    C004 qualifier mismatch  the claim's population/intervention/outcome does not match the source's
    C005 retraction          an edge whose source is now retracted or under an expression of concern
    C006 artifact-code drift  a run's commit is not an ancestor of HEAD, or its worktree was dirty

The verdict semantics follow D9 exactly. A `source_error` during a compile-time status re-check is
NEVER a C003 or C005: it yields an `inconclusive` line item, because a downed index is not evidence
that a paper was retracted or that a snapshot went stale. Only C001 through C006, on clean evidence,
are refusal-grade. A claim backed only by an `insufficient-passage` edge is an open item, not a
refusal: it does not pass the gate, but it does not fail it as a defect either (D11).

The gate PASSES only when there are no refusal-grade diagnostics and every claim has at least one
edge that satisfies it. The status and git checks are injected so the logic is testable offline and
so the CLI can wire the snapshot-backed status module and real git plumbing; the checks themselves
never reach the network, which keeps a compile replayable per D15.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..model import sha256_hex
from .graph import EdgeRecord, LineageGraph
from .model import ClaimNode

# Defect codes, stable so a report can be diffed and a remediation looked up.
C001_ORPHAN_CLAIM = "C001"
C002_ALTERED_NUMBER = "C002"
C003_STALE_EVIDENCE = "C003"
C004_QUALIFIER_MISMATCH = "C004"
C005_RETRACTION = "C005"
C006_ARTIFACT_CODE_DRIFT = "C006"

REFUSAL_GRADE_CODES = frozenset(
    {
        C001_ORPHAN_CLAIM,
        C002_ALTERED_NUMBER,
        C003_STALE_EVIDENCE,
        C004_QUALIFIER_MISMATCH,
        C005_RETRACTION,
        C006_ARTIFACT_CODE_DRIFT,
    }
)

_REMEDIATION = {
    C001_ORPHAN_CLAIM: (
        "Attach an evidence edge (a source passage or an experiment run) to this claim."
    ),
    C002_ALTERED_NUMBER: (
        "A generated number was hand-edited. Re-generate it, or add an evidence edge if it "
        "is now hand-authored."
    ),
    C003_STALE_EVIDENCE: (
        "The cited source moved. Re-retrieve it and re-anchor the edge to the current snapshot."
    ),
    C004_QUALIFIER_MISMATCH: (
        "The source studied a different population, intervention, or outcome than the claim "
        "asserts. Cite a matching source or soften the claim."
    ),
    C005_RETRACTION: (
        "The cited source has been retracted or flagged. Remove or replace the citation."
    ),
    C006_ARTIFACT_CODE_DRIFT: (
        "The run's code commit is not in the current history, or its worktree was dirty. "
        "Re-run from a committed, clean tree."
    ),
}


@dataclass(frozen=True)
class Diagnostic:
    """One compile finding. `inconclusive` marks a source re-check that could not be completed
    (a source error), which is never refusal-grade."""

    code: str
    claim_id: str
    message: str
    file: str = ""
    span_start: int = 0
    span_end: int = 0
    inconclusive: bool = False

    def is_refusal_grade(self) -> bool:
        return (not self.inconclusive) and self.code in REFUSAL_GRADE_CODES

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "claim_id": self.claim_id,
            "message": self.message,
            "refusal_grade": self.is_refusal_grade(),
        }
        if self.file:
            out["file"] = self.file
            out["span"] = {"start": self.span_start, "end": self.span_end}
        if self.inconclusive:
            out["inconclusive"] = True
        if self.code in _REMEDIATION:
            out["remediation"] = _REMEDIATION[self.code]
        return out


@dataclass(frozen=True)
class StatusCheck:
    """The result of a compile-time publication-status re-check for one source.

    `verdict` is one of the axis (b) verdicts, or None. `source_error` True means no clean
    answer was obtained (a downed index), which must degrade to inconclusive, never a defect.
    `snapshot_hash` is the snapshot the re-check read, so C003 can tell a superseded snapshot.
    """

    verdict: str | None = None
    source_error: bool = False
    snapshot_hash: str = ""


#: A status checker maps a DOI to a StatusCheck. Injected so the logic is offline-testable.
StatusChecker = Callable[[str], StatusCheck]
#: An artifact hasher maps a worktree-relative path to its current content hash, or None if
#: the file is absent. Injected so tests need no real files.
ArtifactHasher = Callable[[str], str | None]
#: An ancestry check: is `commit` an ancestor of (or equal to) the current HEAD? Injected so
#: tests need no real git.
AncestryCheck = Callable[[str], bool]


def default_artifact_hasher(root: Any) -> ArtifactHasher:
    """Hash a worktree file's raw bytes, or None if it does not exist."""
    from pathlib import Path

    base = Path(root)

    def hasher(rel_path: str) -> str | None:
        p = base / rel_path
        if not p.is_file():
            return None
        return sha256_hex(p.read_bytes())

    return hasher


@dataclass
class CompileReport:
    """The full result of a compile: the diagnostics, the open items, and the derived verdict."""

    diagnostics: list[Diagnostic] = field(default_factory=list)
    open_items: list[Diagnostic] = field(default_factory=list)
    claim_count: int = 0
    ts: str = ""

    @property
    def refusal_grade(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.is_refusal_grade()]

    @property
    def inconclusive(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.inconclusive]

    @property
    def passed(self) -> bool:
        """A pass needs zero refusal-grade diagnostics and zero open items (every claim has a
        satisfying edge). Inconclusive line items do not fail the gate."""
        return not self.refusal_grade and not self.open_items

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "verdict": "pass" if self.passed else "fail",
            "claim_count": self.claim_count,
            "counts": {
                "refusal_grade": len(self.refusal_grade),
                "inconclusive": len(self.inconclusive),
                "open_items": len(self.open_items),
            },
            "diagnostics": [d.to_json_dict() for d in self.diagnostics],
            "open_items": [d.to_json_dict() for d in self.open_items],
        }

    def to_human(self) -> str:
        lines = [
            f"researcher compile: {'PASS' if self.passed else 'FAIL'} "
            f"({self.claim_count} claim(s))",
        ]
        if not self.diagnostics and not self.open_items:
            lines.append("  every claim compiles from clean evidence.")
        for d in self.diagnostics:
            tag = "inconclusive" if d.inconclusive else d.code
            loc = f" {d.file}:{d.span_start}" if d.file else ""
            lines.append(f"  [{tag}]{loc} {d.message}")
        for d in self.open_items:
            loc = f" {d.file}:{d.span_start}" if d.file else ""
            lines.append(f"  [open]{loc} {d.message}")
        return "\n".join(lines)


def _short(claim_id: str) -> str:
    return claim_id[:12]


def compile_graph(
    graph: LineageGraph,
    *,
    status_checker: StatusChecker | None = None,
    artifact_hasher: ArtifactHasher | None = None,
    ancestry_check: AncestryCheck | None = None,
    ts: str = "",
) -> CompileReport:
    """Run every defect check over the graph and return the report.

    Checks whose external inputs are not provided are skipped (their absence is not a defect):
    without a `status_checker` no C003/C005 fires, without an `artifact_hasher` no C002, without
    an `ancestry_check` no C006. The CLI wires all three; a unit test wires only what it exercises.
    """
    report = CompileReport(claim_count=len(graph.claims), ts=ts)

    for claim in graph.claims.values():
        edges = graph.edges_for(claim.claim_id)

        # C001: a claim with no evidence edge at all.
        if not edges:
            report.diagnostics.append(
                _diag(C001_ORPHAN_CLAIM, claim, "orphan claim: no evidence edge.")
            )
            continue

        _check_edges(claim, edges, graph, report, status_checker)

        # A claim with edges but none that satisfies (all open or all refused). If it already
        # drew a refusal-grade diagnostic above, that is the failure; otherwise it is an open item.
        satisfied = any(e.edge.satisfies_gate() for e in edges)
        drew_refusal = any(
            d.is_refusal_grade() for d in report.diagnostics if d.claim_id == claim.claim_id
        )
        if not satisfied and not drew_refusal:
            report.open_items.append(
                _diag(
                    "open",
                    claim,
                    "no full-text supporting evidence yet (insufficient-passage); open item.",
                )
            )

    _check_manifests(graph, report, artifact_hasher, ancestry_check)
    return report


def _check_edges(
    claim: ClaimNode,
    edges: list[EdgeRecord],
    graph: LineageGraph,
    report: CompileReport,
    status_checker: StatusChecker | None,
) -> None:
    for record in edges:
        edge = record.edge

        # C005 / C003: publication-status re-check against the live-recorded snapshot.
        if status_checker is not None and record.source_doi:
            check = status_checker(record.source_doi)
            if check.source_error:
                report.diagnostics.append(
                    _diag(
                        C003_STALE_EVIDENCE,
                        claim,
                        f"status re-check for {record.source_doi} could not be completed "
                        f"(source error); no defect asserted.",
                        inconclusive=True,
                    )
                )
            elif check.verdict in ("retracted", "expression-of-concern"):
                report.diagnostics.append(
                    _diag(
                        C005_RETRACTION,
                        claim,
                        f"cited source {record.source_doi} is now {check.verdict}.",
                    )
                )
            elif (
                check.verdict == "corrected"
                and edge.axis_verdicts.status not in (None, "corrected")
            ):
                report.diagnostics.append(
                    _diag(
                        C003_STALE_EVIDENCE,
                        claim,
                        f"cited source {record.source_doi} status changed from "
                        f"{edge.axis_verdicts.status} to corrected since the edge was made.",
                    )
                )
            elif (
                check.snapshot_hash
                and edge.source_version.snapshot_hash
                and check.snapshot_hash != edge.source_version.snapshot_hash
            ):
                report.diagnostics.append(
                    _diag(
                        C003_STALE_EVIDENCE,
                        claim,
                        f"the snapshot behind {record.source_doi} was superseded since the edge "
                        f"was made.",
                    )
                )

        # A refusal-grade axis verdict recorded on the edge itself. A retracted status is
        # left to the live status re-check above (C005). An identity unresolvable or mismatch,
        # or a contradicted faithfulness, is a defect the compile reports directly.
        for verdict in edge.axis_verdicts.refusal_grade():
            if verdict == "retracted":
                if status_checker is None or not record.source_doi:
                    # No live re-check will fire, so report the recorded retraction now.
                    report.diagnostics.append(
                        _diag(C005_RETRACTION, claim, "edge source was recorded as retracted.")
                    )
                continue
            if verdict in ("unresolvable", "mismatch"):
                report.diagnostics.append(
                    _diag(
                        C003_STALE_EVIDENCE,
                        claim,
                        f"edge source no longer holds up (identity: {verdict}).",
                    )
                )
            elif verdict == "contradicted":
                report.diagnostics.append(
                    _diag(
                        C004_QUALIFIER_MISMATCH,
                        claim,
                        "the cited passage contradicts the claim (faithfulness: contradicted).",
                    )
                )

        # C004: the claim's qualifiers vs the source's qualifiers.
        for name, source_value in (
            ("population", edge.population),
            ("intervention_or_exposure", edge.intervention_or_exposure),
            ("outcome", edge.outcome),
        ):
            claim_value = str(record.claim_qualifiers.get(name, "")).strip()
            if not claim_value:
                continue
            if not _qualifiers_compatible(claim_value, source_value):
                report.diagnostics.append(
                    _diag(
                        C004_QUALIFIER_MISMATCH,
                        claim,
                        f"claim {name} '{claim_value}' does not match the source's "
                        f"'{source_value or 'unspecified'}'.",
                    )
                )


def _check_manifests(
    graph: LineageGraph,
    report: CompileReport,
    artifact_hasher: ArtifactHasher | None,
    ancestry_check: AncestryCheck | None,
) -> None:
    # Map each manifest to the claims whose internal edge points at it, so a defect is
    # attributed to a claim rather than floating free.
    claims_by_manifest: dict[str, list[str]] = {}
    for record in graph.edges:
        if record.edge.target_kind == "internal":
            claims_by_manifest.setdefault(record.edge.manifest_hash, []).append(
                record.edge.claim_id
            )

    for manifest_hash, manifest in graph.manifests.items():
        claim_ids = claims_by_manifest.get(manifest_hash, [""])

        # C006: the run's commit must be in the current history and its worktree clean.
        if ancestry_check is not None:
            drift = manifest.dirty_worktree or not ancestry_check(manifest.code_commit)
            if drift:
                reason = (
                    "the worktree was dirty at run time"
                    if manifest.dirty_worktree
                    else f"commit {manifest.code_commit[:12]} is not an ancestor of HEAD"
                )
                for cid in claim_ids:
                    report.diagnostics.append(
                        _diag_id(
                            C006_ARTIFACT_CODE_DRIFT,
                            cid,
                            f"artifact-code drift in run {manifest.run_id}: {reason}.",
                        )
                    )

        # C002: each generated artifact's current content hash must match the recorded one.
        if artifact_hasher is not None:
            for artifact in manifest.artifact_hashes:
                current = artifact_hasher(artifact.path)
                if current is not None and current != artifact.hash:
                    for cid in claim_ids:
                        report.diagnostics.append(
                            _diag_id(
                                C002_ALTERED_NUMBER,
                                cid,
                                f"generated artifact {artifact.path} was altered after "
                                f"run {manifest.run_id} (content hash mismatch).",
                            )
                        )


def _qualifiers_compatible(claim_value: str, source_value: str) -> bool:
    """A mechanical compatibility check. Empty source qualifier is treated as a mismatch when
    the claim asserts one, because an unqualified source cannot back a qualified claim. Otherwise
    a case-insensitive containment either way counts as compatible."""
    source_value = (source_value or "").strip()
    if not source_value:
        return False
    a, b = claim_value.casefold(), source_value.casefold()
    return a in b or b in a


def _diag(
    code: str, claim: ClaimNode, message: str, *, inconclusive: bool = False
) -> Diagnostic:
    return Diagnostic(
        code=code,
        claim_id=claim.claim_id,
        message=f"{message} [{_short(claim.claim_id)}]",
        file=claim.file,
        span_start=claim.span_start,
        span_end=claim.span_end,
        inconclusive=inconclusive,
    )


def _diag_id(code: str, claim_id: str, message: str) -> Diagnostic:
    tag = f" [{_short(claim_id)}]" if claim_id else ""
    return Diagnostic(code=code, claim_id=claim_id, message=f"{message}{tag}")


def gate_event_payload(report: CompileReport) -> dict[str, Any]:
    """The payload for the `gate` ledger event a compile appends (D19). Carries the verdict and
    the diagnostic codes so the derived gate state can be recomputed from events alone."""
    return {
        "gate": "compile",
        "verdict": "pass" if report.passed else "fail",
        "claim_count": report.claim_count,
        "codes": sorted({d.code for d in report.refusal_grade}),
        "open_items": len(report.open_items),
    }


def compile_events(
    events: Iterable[Any],
    *,
    status_checker: StatusChecker | None = None,
    artifact_hasher: ArtifactHasher | None = None,
    ancestry_check: AncestryCheck | None = None,
    ts: str = "",
) -> CompileReport:
    """Fold a lineage event stream into a graph and compile it. Convenience for the CLI."""
    graph = LineageGraph.from_events(events)
    return compile_graph(
        graph,
        status_checker=status_checker,
        artifact_hasher=artifact_hasher,
        ancestry_check=ancestry_check,
        ts=ts,
    )


def status_checker_from_map(mapping: Mapping[str, StatusCheck]) -> StatusChecker:
    """A status checker backed by a dict, for fixtures and tests."""

    def checker(doi: str) -> StatusCheck:
        return mapping.get(doi, StatusCheck(verdict="current"))

    return checker
