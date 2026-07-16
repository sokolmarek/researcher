"""Tests for the M3.1 lineage data model, including schema conformance and D15 replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researcher_core.lineage import (
    ArtifactHash,
    AxisVerdicts,
    ClaimKind,
    ClaimNode,
    EvidenceEdge,
    EvidenceQuality,
    ExperimentManifest,
    MetricDefinition,
    SourceVersion,
    claim_id_for,
    make_claim_nodes,
    manifest_hash_for,
)
from researcher_core.lineage.model import make_claim_node, normalize_claim_text

jsonschema = pytest.importorskip("jsonschema")

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


# --- claim nodes ----------------------------------------------------------


def test_claim_id_is_stable_to_rewrapping():
    # Same text, differently wrapped (extra whitespace/newlines) -> same normalized text
    # -> same claim id. A re-wrap must not orphan the evidence edge.
    a = make_claim_node("intro.tex", "The model reached 0.92 accuracy.", 0, 32, ClaimKind.NUMBER)
    b = make_claim_node(
        "intro.tex", "The model reached\n  0.92   accuracy.", 0, 36, ClaimKind.NUMBER
    )
    assert a.claim_id == b.claim_id
    # but the raw text hash differs, so the edit is still visible
    assert a.text_hash != b.text_hash


def test_substantive_rewrite_yields_a_new_claim_id():
    a = make_claim_node("intro.tex", "The model reached 0.92 accuracy.", 0, 32, ClaimKind.NUMBER)
    b = make_claim_node("intro.tex", "The model reached 0.95 accuracy.", 0, 32, ClaimKind.NUMBER)
    assert a.claim_id != b.claim_id


def test_claim_id_depends_on_file_and_parser_version():
    base = claim_id_for("a claim", "a.tex", "1")
    assert base != claim_id_for("a claim", "b.tex", "1")
    assert base != claim_id_for("a claim", "a.tex", "2")


def test_make_claim_nodes_is_order_independent():
    text = "First claim here. Second claim here. Third claim here."
    spans = [
        {"start": 0, "end": 17, "kind": "assertion"},
        {"start": 18, "end": 36, "kind": "assertion"},
        {"start": 37, "end": 54, "kind": "comparison"},
    ]
    forward = make_claim_nodes("s.tex", text, spans)
    backward = make_claim_nodes("s.tex", text, list(reversed(spans)))
    # byte-identical node lists regardless of the order spans were proposed in (D15)
    assert [n.to_json_dict() for n in forward] == [n.to_json_dict() for n in backward]
    assert [n.span_start for n in forward] == [0, 18, 37]


def test_claim_node_round_trips_and_validates():
    schema = load_schema("claim-node.schema.json")
    node = make_claim_node("m.tex", "A supported claim.", 5, 23, "assertion")
    d = node.to_json_dict()
    jsonschema.validate(d, schema)
    assert ClaimNode.from_json_dict(d) == node


def test_normalize_claim_text_collapses_whitespace():
    assert normalize_claim_text("  a   b\n c ") == "a b c"


# --- evidence edges -------------------------------------------------------


def test_external_edge_requires_a_passage_id():
    with pytest.raises(ValueError):
        EvidenceEdge(claim_id="a" * 64, target_kind="external")


def test_internal_edge_requires_a_manifest_hash():
    with pytest.raises(ValueError):
        EvidenceEdge(claim_id="a" * 64, target_kind="internal")


def test_bad_target_kind_rejected():
    with pytest.raises(ValueError):
        EvidenceEdge(claim_id="a" * 64, target_kind="sideways", passage_id="p")


def test_axis_verdicts_reject_out_of_vocabulary():
    with pytest.raises(ValueError):
        AxisVerdicts(identity="totally-fabricated")


def test_supported_full_text_edge_satisfies_the_gate():
    edge = EvidenceEdge(
        claim_id="a" * 64,
        target_kind="external",
        passage_id="p1",
        evidence_quality=EvidenceQuality.RCT,
        axis_verdicts=AxisVerdicts(
            identity="verified",
            status="current",
            faithfulness="supported",
            accessibility="full-text",
        ),
    )
    assert edge.satisfies_gate() is True
    assert edge.is_refusal_grade() is False


def test_insufficient_passage_edge_is_valid_but_open():
    # A claim degraded to abstract level is a valid edge but never satisfies the gate alone (D11).
    edge = EvidenceEdge(
        claim_id="a" * 64,
        target_kind="external",
        passage_id="p1",
        axis_verdicts=AxisVerdicts(
            identity="verified", faithfulness="insufficient-passage", accessibility="abstract-only"
        ),
    )
    assert edge.satisfies_gate() is False
    assert edge.is_refusal_grade() is False  # open item, not a refusal


@pytest.mark.parametrize(
    "verdicts",
    [
        AxisVerdicts(identity="unresolvable"),
        AxisVerdicts(identity="mismatch"),
        AxisVerdicts(status="retracted"),
        AxisVerdicts(faithfulness="contradicted"),
    ],
)
def test_refusal_grade_verdicts_never_satisfy(verdicts):
    edge = EvidenceEdge(
        claim_id="a" * 64, target_kind="external", passage_id="p1", axis_verdicts=verdicts
    )
    assert edge.is_refusal_grade() is True
    assert edge.satisfies_gate() is False


def test_inconclusive_is_not_refusal_grade():
    # inconclusive is the safe verdict: it is never an accusation (D9).
    v = AxisVerdicts(identity="inconclusive")
    assert v.refusal_grade() == []


def test_internal_edge_satisfies_when_not_refusal_grade():
    edge = EvidenceEdge(claim_id="a" * 64, target_kind="internal", manifest_hash="b" * 64)
    assert edge.satisfies_gate() is True


def test_external_edge_round_trips_and_validates():
    schema = load_schema("evidence-edge.schema.json")
    edge = EvidenceEdge(
        claim_id="a" * 64,
        target_kind="external",
        passage_id="p1",
        population="adults with hypertension",
        intervention_or_exposure="ACE inhibitor",
        outcome="systolic blood pressure",
        source_version=SourceVersion(snapshot_hash="c" * 64, retrieved_at="2026-07-14T00:00:00Z"),
        evidence_quality=EvidenceQuality.RCT,
        axis_verdicts=AxisVerdicts(
            identity="verified", faithfulness="supported", accessibility="full-text"
        ),
    )
    d = edge.to_json_dict()
    jsonschema.validate(d, schema)
    assert EvidenceEdge.from_json_dict(d) == edge


def test_internal_edge_round_trips_and_validates():
    schema = load_schema("evidence-edge.schema.json")
    edge = EvidenceEdge(claim_id="a" * 64, target_kind="internal", manifest_hash="b" * 64)
    d = edge.to_json_dict()
    jsonschema.validate(d, schema)
    assert EvidenceEdge.from_json_dict(d) == edge


# --- experiment manifests -------------------------------------------------


def make_manifest(ts="2026-07-14T00:00:00Z") -> ExperimentManifest:
    return ExperimentManifest(
        run_id="run-1",
        code_commit="deadbeef",
        ts=ts,
        dirty_worktree=False,
        data_hashes=("d1", "d2"),
        environment_lockfile_hash="lock1",
        seed=42,
        metric_definitions=(MetricDefinition("accuracy", "correct/total"),),
        artifact_hashes=(ArtifactHash("results/table.tex", "h1", "2026-07-14T00:00:00Z"),),
        command_line="python train.py --seed 42",
    )


def test_manifest_hash_is_deterministic():
    assert make_manifest().manifest_hash() == make_manifest().manifest_hash()


def test_manifest_hash_changes_with_ts():
    # ts is part of the manifest: two runs that differ only in when they ran are distinct.
    a = make_manifest("2026-07-14T00:00:00Z").manifest_hash()
    b = make_manifest("2026-07-15T00:00:00Z").manifest_hash()
    assert a != b


def test_manifest_round_trips_and_validates():
    schema = load_schema("experiment-manifest.schema.json")
    m = make_manifest()
    d = m.to_json_dict()
    jsonschema.validate(d, schema)
    assert ExperimentManifest.from_json_dict(d) == m
    assert manifest_hash_for(d) == m.manifest_hash()


def test_manifest_no_clock_call():
    # A manifest never reads the clock; the source has no time.time / datetime.now.
    model_py = Path(__file__).resolve().parents[1] / "researcher_core" / "lineage" / "model.py"
    src = model_py.read_text(encoding="utf-8")
    assert "time.time" not in src
    assert "datetime.now" not in src
    assert "datetime.utcnow" not in src
