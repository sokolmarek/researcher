"""The claim-evidence-result graph (M3, the evidence-lineage compiler).

This package holds the data model (M3.1), the compile gate (M3.2), and the research
passport exporters (M3.3). `model` is the foundation: it defines the node, edge, and
manifest types and their canonical serialization, and computes stable identifiers. It
writes nothing on its own. The compile gate records graph events into the D19 ledger and
derives gate state from them; nothing about the graph is stored as a mutable aggregate.
"""

from __future__ import annotations

from .index import (
    LineageEdge,
    LineageIndex,
    LineageNode,
    LineageResult,
    StaleReport,
    strip_hash_prefix,
)
from .model import (
    AXIS_ACCESSIBILITY_VERDICTS,
    AXIS_FAITHFULNESS_VERDICTS,
    AXIS_IDENTITY_VERDICTS,
    AXIS_STATUS_VERDICTS,
    EVIDENCE_QUALITY,
    REFUSAL_GRADE_VERDICTS,
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

__all__ = [
    "AXIS_ACCESSIBILITY_VERDICTS",
    "AXIS_FAITHFULNESS_VERDICTS",
    "AXIS_IDENTITY_VERDICTS",
    "AXIS_STATUS_VERDICTS",
    "EVIDENCE_QUALITY",
    "REFUSAL_GRADE_VERDICTS",
    "ArtifactHash",
    "AxisVerdicts",
    "ClaimKind",
    "ClaimNode",
    "EvidenceEdge",
    "EvidenceQuality",
    "ExperimentManifest",
    "MetricDefinition",
    "SourceVersion",
    "claim_id_for",
    "make_claim_nodes",
    "manifest_hash_for",
    # M2 source-dependency lineage (moved from lineage.py into this package)
    "LineageEdge",
    "LineageIndex",
    "LineageNode",
    "LineageResult",
    "StaleReport",
    "strip_hash_prefix",
]
