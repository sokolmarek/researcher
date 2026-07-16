"""Tests for the M3.2 compile gate: each defect class, the D9 source-error rule, and D15 replay."""

from __future__ import annotations

from researcher_core.lineage.compile import (
    C001_ORPHAN_CLAIM,
    C002_ALTERED_NUMBER,
    C003_STALE_EVIDENCE,
    C004_QUALIFIER_MISMATCH,
    C005_RETRACTION,
    C006_ARTIFACT_CODE_DRIFT,
    StatusCheck,
    compile_events,
    compile_graph,
    status_checker_from_map,
)
from researcher_core.lineage.graph import (
    LineageGraph,
    claim_node_event,
    evidence_edge_event,
)
from researcher_core.lineage.model import (
    ArtifactHash,
    AxisVerdicts,
    EvidenceEdge,
    EvidenceQuality,
    ExperimentManifest,
    SourceVersion,
    make_claim_node,
)

TS = "2026-07-14T00:00:00Z"
RUN = "run-1"


def graph_with(nodes=(), edges=(), manifests=()):
    g = LineageGraph()
    for n in nodes:
        g.claims[n.claim_id] = n
    from researcher_core.lineage.graph import EdgeRecord

    for e in edges:
        g.edges.append(e if isinstance(e, EdgeRecord) else EdgeRecord(edge=e))
    for m in manifests:
        g.manifests[m.manifest_hash()] = m
    return g


def clean_external_edge(claim_id, **kw):
    return EvidenceEdge(
        claim_id=claim_id,
        target_kind="external",
        passage_id="p1",
        axis_verdicts=AxisVerdicts(
            identity="verified",
            status="current",
            faithfulness="supported",
            accessibility="full-text",
        ),
        **kw,
    )


# --- the happy path -------------------------------------------------------


def test_clean_manuscript_passes():
    claim = make_claim_node("intro.tex", "A supported claim.", 0, 18, "assertion")
    graph = graph_with(nodes=[claim], edges=[clean_external_edge(claim.claim_id)])
    report = compile_graph(graph)
    assert report.passed
    assert report.diagnostics == []
    assert report.to_json_dict()["verdict"] == "pass"


# --- one test per defect class --------------------------------------------


def test_c001_orphan_claim():
    claim = make_claim_node("intro.tex", "An unsupported claim.", 0, 21, "assertion")
    report = compile_graph(graph_with(nodes=[claim]))
    codes = [d.code for d in report.diagnostics]
    assert C001_ORPHAN_CLAIM in codes
    assert not report.passed


def test_c002_altered_number():
    claim = make_claim_node("results.tex", "Accuracy was 0.92.", 0, 18, "number")
    manifest = ExperimentManifest(
        run_id="r",
        code_commit="abc",
        ts=TS,
        artifact_hashes=(ArtifactHash("results/table.tex", "recorded-hash"),),
    )
    edge = EvidenceEdge(
        claim_id=claim.claim_id, target_kind="internal", manifest_hash=manifest.manifest_hash()
    )
    graph = graph_with(nodes=[claim], edges=[edge], manifests=[manifest])
    # the file on disk now hashes to something else: it was hand-edited
    report = compile_graph(graph, artifact_hasher=lambda p: "different-hash")
    assert C002_ALTERED_NUMBER in [d.code for d in report.diagnostics]
    assert not report.passed
    # and when the hash matches, no C002
    ok = compile_graph(graph, artifact_hasher=lambda p: "recorded-hash")
    assert C002_ALTERED_NUMBER not in [d.code for d in ok.diagnostics]


def test_c003_stale_evidence_status_flip():
    claim = make_claim_node("intro.tex", "A claim citing a paper.", 0, 23, "assertion")
    edge = clean_external_edge(claim.claim_id)
    from researcher_core.lineage.graph import EdgeRecord

    record = EdgeRecord(edge=edge, source_doi="10.1/x")
    graph = graph_with(nodes=[claim], edges=[record])
    checker = status_checker_from_map({"10.1/x": StatusCheck(verdict="corrected")})
    report = compile_graph(graph, status_checker=checker)
    assert C003_STALE_EVIDENCE in [d.code for d in report.diagnostics]


def test_c004_qualifier_mismatch():
    claim = make_claim_node("intro.tex", "Drug X lowers mortality.", 0, 24, "assertion")
    edge = clean_external_edge(
        claim.claim_id, outcome="systolic blood pressure", evidence_quality=EvidenceQuality.RCT
    )
    from researcher_core.lineage.graph import EdgeRecord

    record = EdgeRecord(edge=edge, claim_qualifiers={"outcome": "mortality"})
    report = compile_graph(graph_with(nodes=[claim], edges=[record]))
    assert C004_QUALIFIER_MISMATCH in [d.code for d in report.diagnostics]


def test_c005_retraction():
    claim = make_claim_node("intro.tex", "A claim citing a retracted paper.", 0, 33, "assertion")
    edge = clean_external_edge(claim.claim_id)
    from researcher_core.lineage.graph import EdgeRecord

    record = EdgeRecord(edge=edge, source_doi="10.1/retracted")
    checker = status_checker_from_map({"10.1/retracted": StatusCheck(verdict="retracted")})
    report = compile_graph(graph_with(nodes=[claim], edges=[record]), status_checker=checker)
    assert C005_RETRACTION in [d.code for d in report.diagnostics]


def test_c006_artifact_code_drift():
    claim = make_claim_node("results.tex", "Accuracy was 0.92.", 0, 18, "number")
    manifest = ExperimentManifest(
        run_id="r", code_commit="orphan-commit", ts=TS, dirty_worktree=False
    )
    edge = EvidenceEdge(
        claim_id=claim.claim_id, target_kind="internal", manifest_hash=manifest.manifest_hash()
    )
    graph = graph_with(nodes=[claim], edges=[edge], manifests=[manifest])
    # the commit is not an ancestor of HEAD
    report = compile_graph(graph, ancestry_check=lambda commit: False)
    assert C006_ARTIFACT_CODE_DRIFT in [d.code for d in report.diagnostics]
    # a clean, committed run does not drift
    ok = compile_graph(graph, ancestry_check=lambda commit: True)
    assert C006_ARTIFACT_CODE_DRIFT not in [d.code for d in ok.diagnostics]


def test_c006_dirty_worktree_drifts():
    claim = make_claim_node("results.tex", "Accuracy was 0.92.", 0, 18, "number")
    manifest = ExperimentManifest(run_id="r", code_commit="abc", ts=TS, dirty_worktree=True)
    edge = EvidenceEdge(
        claim_id=claim.claim_id, target_kind="internal", manifest_hash=manifest.manifest_hash()
    )
    graph = graph_with(nodes=[claim], edges=[edge], manifests=[manifest])
    report = compile_graph(graph, ancestry_check=lambda commit: True)
    assert C006_ARTIFACT_CODE_DRIFT in [d.code for d in report.diagnostics]


# --- the D9 rule: a source error is never a defect -------------------------


def test_source_error_is_inconclusive_never_refusal_grade():
    claim = make_claim_node("intro.tex", "A claim citing a paper.", 0, 23, "assertion")
    edge = clean_external_edge(claim.claim_id)
    from researcher_core.lineage.graph import EdgeRecord

    record = EdgeRecord(edge=edge, source_doi="10.1/down")
    checker = status_checker_from_map({"10.1/down": StatusCheck(source_error=True)})
    report = compile_graph(graph_with(nodes=[claim], edges=[record]), status_checker=checker)
    # it produced an inconclusive line item, NOT a C003 or C005 refusal
    assert report.inconclusive
    assert not report.refusal_grade
    # an inconclusive line does not fail the gate
    assert report.passed


# --- open items (insufficient-passage) ------------------------------------


def test_insufficient_passage_is_an_open_item_not_a_defect():
    claim = make_claim_node("intro.tex", "A claim with only an abstract.", 0, 30, "assertion")
    edge = EvidenceEdge(
        claim_id=claim.claim_id,
        target_kind="external",
        passage_id="p1",
        axis_verdicts=AxisVerdicts(
            identity="verified", faithfulness="insufficient-passage", accessibility="abstract-only"
        ),
    )
    report = compile_graph(graph_with(nodes=[claim], edges=[edge]))
    assert report.open_items
    assert not report.refusal_grade
    assert not report.passed  # an open item still prevents a pass


# --- events round-trip + replay -------------------------------------------


def test_compile_from_events_matches_direct_graph():
    claim = make_claim_node("intro.tex", "A supported claim.", 0, 18, "assertion")
    edge = clean_external_edge(claim.claim_id)
    events = [
        claim_node_event(claim, TS, RUN),
        evidence_edge_event(edge, TS, RUN),
    ]
    report = compile_events(events)
    assert report.passed
    assert report.claim_count == 1


def test_compile_is_replayable():
    claim = make_claim_node("intro.tex", "A claim citing a paper.", 0, 23, "assertion")
    from researcher_core.lineage.graph import EdgeRecord

    edge = clean_external_edge(claim.claim_id, source_version=SourceVersion(snapshot_hash="s1"))
    record = EdgeRecord(edge=edge, source_doi="10.1/x")
    graph = graph_with(nodes=[claim], edges=[record])
    checker = status_checker_from_map(
        {"10.1/x": StatusCheck(verdict="current", snapshot_hash="s1")}
    )
    import json

    a = json.dumps(compile_graph(graph, status_checker=checker).to_json_dict(), sort_keys=True)
    b = json.dumps(compile_graph(graph, status_checker=checker).to_json_dict(), sort_keys=True)
    assert a == b


def test_full_defect_set_reports_all_six_codes():
    # A graph carrying one instance of each defect at once produces all six codes.
    orphan = make_claim_node("a.tex", "Orphan claim.", 0, 13, "assertion")
    stale = make_claim_node("a.tex", "Stale citation claim.", 20, 41, "assertion")
    qual = make_claim_node("a.tex", "Mortality claim.", 50, 66, "assertion")
    retr = make_claim_node("a.tex", "Retracted citation.", 70, 89, "assertion")
    altered = make_claim_node("a.tex", "Altered number 0.9.", 100, 119, "number")
    drift = make_claim_node("a.tex", "Drift number 0.8.", 130, 147, "number")

    from researcher_core.lineage.graph import EdgeRecord

    manifest_c002 = ExperimentManifest(
        run_id="m2", code_commit="c", ts=TS, artifact_hashes=(ArtifactHash("t.tex", "orig"),)
    )
    manifest_c006 = ExperimentManifest(run_id="m6", code_commit="orphan", ts=TS)

    edges = [
        EdgeRecord(edge=clean_external_edge(stale.claim_id), source_doi="10.1/corrected"),
        EdgeRecord(
            edge=clean_external_edge(qual.claim_id, outcome="blood pressure"),
            claim_qualifiers={"outcome": "mortality"},
        ),
        EdgeRecord(edge=clean_external_edge(retr.claim_id), source_doi="10.1/retracted"),
        EdgeRecord(
            edge=EvidenceEdge(
                claim_id=altered.claim_id,
                target_kind="internal",
                manifest_hash=manifest_c002.manifest_hash(),
            )
        ),
        EdgeRecord(
            edge=EvidenceEdge(
                claim_id=drift.claim_id,
                target_kind="internal",
                manifest_hash=manifest_c006.manifest_hash(),
            )
        ),
    ]
    graph = graph_with(
        nodes=[orphan, stale, qual, retr, altered, drift],
        edges=edges,
        manifests=[manifest_c002, manifest_c006],
    )
    checker = status_checker_from_map(
        {
            "10.1/corrected": StatusCheck(verdict="corrected"),
            "10.1/retracted": StatusCheck(verdict="retracted"),
        }
    )
    report = compile_graph(
        graph,
        status_checker=checker,
        artifact_hasher=lambda p: "edited",
        ancestry_check=lambda commit: commit != "orphan",
    )
    codes = {d.code for d in report.diagnostics}
    assert codes == {
        C001_ORPHAN_CLAIM,
        C002_ALTERED_NUMBER,
        C003_STALE_EVIDENCE,
        C004_QUALIFIER_MISMATCH,
        C005_RETRACTION,
        C006_ARTIFACT_CODE_DRIFT,
    }
    assert not report.passed
