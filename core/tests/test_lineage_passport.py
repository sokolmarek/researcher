"""Tests for the M3.3 research passport: RO-Crate 1.1 structure and PROV-JSON-LD validity."""

from __future__ import annotations

import json

from researcher_core.lineage.compile import compile_graph
from researcher_core.lineage.graph import EdgeRecord, LineageGraph
from researcher_core.lineage.model import (
    ArtifactHash,
    AxisVerdicts,
    EvidenceEdge,
    ExperimentManifest,
    make_claim_node,
)
from researcher_core.lineage.passport import (
    RO_CRATE_PROFILE,
    to_prov_jsonld,
    to_ro_crate,
)


def sample_graph() -> LineageGraph:
    g = LineageGraph()
    claim_a = make_claim_node("intro.tex", "A claim citing a paper.", 0, 23, "assertion")
    claim_b = make_claim_node("results.tex", "Accuracy was 0.92.", 0, 18, "number")
    g.claims[claim_a.claim_id] = claim_a
    g.claims[claim_b.claim_id] = claim_b
    manifest = ExperimentManifest(
        run_id="train-1",
        code_commit="abc",
        ts="2026-07-14T00:00:00Z",
        artifact_hashes=(ArtifactHash("results/table.tex", "h1"),),
    )
    g.manifests[manifest.manifest_hash()] = manifest
    g.edges.append(
        EdgeRecord(
            edge=EvidenceEdge(
                claim_id=claim_a.claim_id,
                target_kind="external",
                passage_id="p1",
                axis_verdicts=AxisVerdicts(identity="verified", faithfulness="supported"),
            ),
            source_doi="10.1000/real",
        )
    )
    g.edges.append(
        EdgeRecord(
            edge=EvidenceEdge(
                claim_id=claim_b.claim_id,
                target_kind="internal",
                manifest_hash=manifest.manifest_hash(),
            )
        )
    )
    return g


# --- RO-Crate 1.1 ---------------------------------------------------------


def test_ro_crate_has_the_required_descriptor_and_root():
    crate = to_ro_crate(sample_graph(), name="Test manuscript")
    assert crate["@context"] == "https://w3id.org/ro/crate/1.1/context"
    by_id = {e["@id"]: e for e in crate["@graph"]}

    # The metadata file descriptor: conformsTo the profile, about the root.
    descriptor = by_id["ro-crate-metadata.json"]
    assert descriptor["conformsTo"] == {"@id": RO_CRATE_PROFILE}
    assert descriptor["about"] == {"@id": "./"}

    # The root data entity is a Dataset with parts.
    root = by_id["./"]
    assert root["@type"] == "Dataset"
    assert root["hasPart"]


def test_ro_crate_serializes_json():
    crate = to_ro_crate(sample_graph())
    # round-trips as JSON with no non-serializable values (no None leaked through)
    text = json.dumps(crate)
    assert '"@graph"' in text
    for entity in crate["@graph"]:
        assert None not in entity.values()


def test_ro_crate_includes_source_and_run():
    crate = to_ro_crate(sample_graph())
    ids = {e["@id"] for e in crate["@graph"]}
    assert "https://doi.org/10.1000/real" in ids  # the cited source
    assert any(i.startswith("#run-train-1") for i in ids)  # the experiment run
    assert "results/table.tex" in ids  # the generated artifact


# --- PROV-JSON-LD ---------------------------------------------------------


def test_prov_jsonld_has_prov_context_and_types():
    report = compile_graph(sample_graph())
    prov = to_prov_jsonld(sample_graph(), report)
    assert "prov" in prov["@context"]
    types = {node.get("@type") for node in prov["@graph"]}
    assert "prov:Entity" in types
    assert "prov:Activity" in types
    # derivation (claim from source) and generation (claim from run) both present
    assert any(n.get("@type") == "prov:Derivation" for n in prov["@graph"])
    assert any(n.get("@type") == "prov:Generation" for n in prov["@graph"])


def test_prov_jsonld_records_the_compile_verdict():
    report = compile_graph(sample_graph())
    prov = to_prov_jsonld(sample_graph(), report)
    report_entities = [n for n in prov["@graph"] if n.get("@id") == "#compile-report"]
    assert report_entities
    assert report_entities[0]["verdict"] in ("pass", "fail")


def test_prov_jsonld_serializes_json():
    prov = to_prov_jsonld(sample_graph())
    assert json.loads(json.dumps(prov)) == prov
