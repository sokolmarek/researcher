"""The research passport (M3.3): RO-Crate and W3C PROV serializations of the lineage graph.

A passport is not a new store. It is the same claim-evidence graph, re-expressed in two standard
formats so a reviewer or a repository can read it without this tool:

* **RO-Crate 1.1** describes the manuscript as a dataset: its files, the claims in them, the sources
  they cite (as context entities with DOIs), the experiment runs (as CreateActions), and the
  generated artifacts. It validates against the RO-Crate 1.1 profile: a metadata file descriptor
  that conformsTo the profile and points at a root data entity.
* **W3C PROV** (as PROV-JSON-LD) expresses the same graph as provenance: claims and sources are
  Entities, experiment runs and the compile gate are Activities, and the edges are wasDerivedFrom
  and wasGeneratedBy relations.

Both are pure functions of the graph (and, for PROV, the compile verdict). No timestamp is invented;
the manifests' caller-supplied ts values are used as-is.
"""

from __future__ import annotations

from typing import Any

from .compile import CompileReport
from .graph import LineageGraph

RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
RO_CRATE_PROFILE = "https://w3id.org/ro/crate/1.1"
PROV_CONTEXT = "http://www.w3.org/ns/prov#"


def _claim_ref(claim_id: str) -> str:
    return f"#claim-{claim_id[:16]}"


def _source_ref(doi: str) -> str:
    return f"https://doi.org/{doi}"


def _run_ref(run_id: str, manifest_hash: str) -> str:
    return f"#run-{run_id}-{manifest_hash[:12]}"


def to_ro_crate(graph: LineageGraph, *, name: str = "Manuscript") -> dict[str, Any]:
    """Serialize the graph as an RO-Crate 1.1 metadata document."""
    graph_entities: list[dict[str, Any]] = []

    # The metadata file descriptor and the root data entity, both required by the profile.
    root_parts: list[dict[str, str]] = []
    graph_entities.append(
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": {"@id": RO_CRATE_PROFILE},
            "about": {"@id": "./"},
        }
    )

    # Manuscript files mentioned by claim nodes.
    files = sorted({claim.file for claim in graph.claims.values() if claim.file})
    for f in files:
        graph_entities.append({"@id": f, "@type": "File", "name": f})
        root_parts.append({"@id": f})

    # Claim nodes.
    for claim in graph.claims.values():
        ref = _claim_ref(claim.claim_id)
        graph_entities.append(
            {
                "@id": ref,
                "@type": "CreativeWork",
                "name": f"claim {claim.claim_id[:12]}",
                "text": claim.normalized_text,
                "isPartOf": {"@id": claim.file} if claim.file else None,
                "additionalType": claim.kind.value,
            }
        )
        root_parts.append({"@id": ref})

    # Sources (external edges) and experiment runs (internal edges).
    seen_sources: set[str] = set()
    seen_runs: set[str] = set()
    for record in graph.edges:
        edge = record.edge
        if edge.target_kind == "external" and record.source_doi:
            src = _source_ref(record.source_doi)
            if src not in seen_sources:
                seen_sources.add(src)
                graph_entities.append(
                    {
                        "@id": src,
                        "@type": "ScholarlyArticle",
                        "identifier": record.source_doi,
                    }
                )
            _link(graph_entities, _claim_ref(edge.claim_id), "citation", src)
        elif edge.target_kind == "internal":
            manifest = graph.manifests.get(edge.manifest_hash)
            if manifest is None:
                continue
            run = _run_ref(manifest.run_id, edge.manifest_hash)
            if run not in seen_runs:
                seen_runs.add(run)
                graph_entities.append(
                    {
                        "@id": run,
                        "@type": "CreateAction",
                        "name": f"run {manifest.run_id}",
                        "endTime": manifest.ts,
                        "instrument": manifest.command_line or None,
                        "result": [
                            {"@id": a.path} for a in manifest.artifact_hashes
                        ]
                        or None,
                    }
                )
                for artifact in manifest.artifact_hashes:
                    graph_entities.append(
                        {"@id": artifact.path, "@type": "File", "name": artifact.path}
                    )
                    root_parts.append({"@id": artifact.path})
            _link(graph_entities, _claim_ref(edge.claim_id), "wasGeneratedBy", run)

    graph_entities.insert(
        1,
        {
            "@id": "./",
            "@type": "Dataset",
            "name": name,
            "hasPart": root_parts,
        },
    )

    return {
        "@context": RO_CRATE_CONTEXT,
        "@graph": [_drop_none(entity) for entity in graph_entities],
    }


def to_prov_jsonld(graph: LineageGraph, report: CompileReport | None = None) -> dict[str, Any]:
    """Serialize the graph as PROV-JSON-LD: claims and sources as Entities, runs and the compile
    gate as Activities, edges as wasDerivedFrom / wasGeneratedBy."""
    entities: list[dict[str, Any]] = []
    activities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    for claim in graph.claims.values():
        entities.append(
            {
                "@id": _claim_ref(claim.claim_id),
                "@type": "prov:Entity",
                "prov:value": claim.normalized_text,
            }
        )

    seen_sources: set[str] = set()
    seen_runs: set[str] = set()
    for record in graph.edges:
        edge = record.edge
        claim_ref = _claim_ref(edge.claim_id)
        if edge.target_kind == "external" and record.source_doi:
            src = _source_ref(record.source_doi)
            if src not in seen_sources:
                seen_sources.add(src)
                entities.append({"@id": src, "@type": "prov:Entity"})
            relations.append(
                {
                    "@type": "prov:Derivation",
                    "prov:generatedEntity": {"@id": claim_ref},
                    "prov:usedEntity": {"@id": src},
                }
            )
        elif edge.target_kind == "internal":
            manifest = graph.manifests.get(edge.manifest_hash)
            if manifest is None:
                continue
            run = _run_ref(manifest.run_id, edge.manifest_hash)
            if run not in seen_runs:
                seen_runs.add(run)
                activities.append(
                    {"@id": run, "@type": "prov:Activity", "prov:endTime": manifest.ts}
                )
            relations.append(
                {
                    "@type": "prov:Generation",
                    "prov:entity": {"@id": claim_ref},
                    "prov:activity": {"@id": run},
                }
            )

    if report is not None:
        gate_activity = "#compile-gate"
        report_entity = "#compile-report"
        activities.append({"@id": gate_activity, "@type": "prov:Activity"})
        entities.append(
            {
                "@id": report_entity,
                "@type": "prov:Entity",
                "verdict": "pass" if report.passed else "fail",
            }
        )
        relations.append(
            {
                "@type": "prov:Generation",
                "prov:entity": {"@id": report_entity},
                "prov:activity": {"@id": gate_activity},
            }
        )

    return {
        "@context": {"prov": PROV_CONTEXT},
        "@graph": entities + activities + relations,
    }


def _link(entities: list[dict[str, Any]], subject_id: str, prop: str, object_id: str) -> None:
    for entity in entities:
        if entity.get("@id") == subject_id:
            existing = entity.get(prop)
            ref = {"@id": object_id}
            if existing is None:
                entity[prop] = ref
            elif isinstance(existing, list):
                existing.append(ref)
            else:
                entity[prop] = [existing, ref]
            return


def _drop_none(entity: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entity.items() if v is not None}
